"""Confirmed production issue, return, transfer and scrap documents."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from inventory_database import InventoryDatabase, inventory_now
from inventory_service import EPSILON, InventoryService
from requirement_service import RequirementService


class MaterialFlowService:
    def __init__(self, db: InventoryDatabase):
        self.db = db
        self.inventory = InventoryService(db)
        self.requirements = RequirementService(db)

    def list_pending_issues(self, q: str = "") -> List[Dict[str, Any]]:
        params: List[Any] = []
        where = ["q.status!='已冻结'", "r.status='有效'", "(r.quantity-r.issued_quantity)>?"]
        params.append(EPSILON)
        if q.strip():
            term = f"%{q.strip()}%"
            where.append("(q.production_no LIKE ? OR i.material_code LIKE ? OR i.material_name LIKE ?)")
            params.extend([term, term, term])
        return self.db.fetch_all(
            f"""SELECT r.id AS reservation_id, r.requirement_item_id, r.warehouse_id,
                       r.location_id, (r.quantity-r.issued_quantity) AS available_quantity,
                       q.id AS requirement_id, q.order_id, q.door_unit_id, q.production_no,
                       q.due_date, i.material_id, i.material_code, i.material_name,
                       i.specification, i.unit, w.name AS warehouse_name, l.name AS location_name
                FROM inventory_reservations r
                JOIN material_requirement_items i ON i.id=r.requirement_item_id
                JOIN material_requirements q ON q.id=i.requirement_id
                JOIN inventory_warehouses w ON w.id=r.warehouse_id
                JOIN inventory_locations l ON l.id=r.location_id
                WHERE {' AND '.join(where)}
                ORDER BY CASE WHEN q.due_date='' THEN 1 ELSE 0 END, q.due_date,
                         q.production_no, i.sequence_no, r.id""",
            params,
        )

    def issue(self, payload: Dict[str, Any], operator_uid: str) -> Dict[str, Any]:
        items = payload.get("items") or []
        if not items:
            raise ValueError("发料单至少需要一条明细")
        now = inventory_now()
        requirement_id = int(payload["requirement_id"])
        with self.db.transaction() as conn:
            requirement = conn.execute(
                "SELECT * FROM material_requirements WHERE id=?", (requirement_id,)
            ).fetchone()
            if not requirement:
                raise LookupError("物料需求单不存在")
            if requirement["status"] == "已冻结":
                raise RuntimeError("已冻结的需求不能发料")
            flow_id, document_no = self._create_header(
                conn, "生产发料", requirement, str(payload.get("remark") or ""), operator_uid, now
            )
            affected: set[int] = set()
            for sequence, item in enumerate(items, 1):
                reservation = conn.execute(
                    """SELECT r.*, i.material_id, i.unit, i.requirement_id
                       FROM inventory_reservations r
                       JOIN material_requirement_items i ON i.id=r.requirement_item_id
                       WHERE r.id=?""",
                    (int(item["reservation_id"]),),
                ).fetchone()
                if not reservation or int(reservation["requirement_item_id"]) != int(item["requirement_item_id"]):
                    raise ValueError("发料明细与库存预留不匹配")
                if int(reservation["requirement_id"]) != requirement_id or reservation["status"] != "有效":
                    raise ValueError("只能发放本需求单的有效预留")
                quantity = float(item["quantity"])
                available = float(reservation["quantity"] or 0) - float(reservation["issued_quantity"] or 0)
                if quantity - available > EPSILON:
                    raise ValueError(f"发料数量超过预留：最多可发 {available:g} {reservation['unit']}")
                self._insert_item(
                    conn, flow_id, sequence, int(reservation["material_id"]), quantity,
                    str(reservation["unit"]), str(item.get("remark") or ""),
                    requirement_item_id=int(reservation["requirement_item_id"]),
                    reservation_id=int(reservation["id"]),
                    source_warehouse_id=int(reservation["warehouse_id"]),
                    source_location_id=int(reservation["location_id"]),
                )
                self.inventory.post_transaction(
                    material_id=int(reservation["material_id"]),
                    warehouse_id=int(reservation["warehouse_id"]),
                    location_id=int(reservation["location_id"]),
                    transaction_type="生产发料", quantity=-quantity, unit=str(reservation["unit"]),
                    source_type="material_issue", source_id=document_no, source_line=str(sequence),
                    order_id=int(requirement["order_id"]), door_unit_id=int(requirement["door_unit_id"]),
                    production_no=str(requirement["production_no"]), operator_uid=operator_uid,
                    remark=str(item.get("remark") or payload.get("remark") or ""), conn=conn,
                )
                conn.execute(
                    "UPDATE inventory_balances SET reserved=MAX(0,reserved-?),updated_at=? WHERE material_id=? AND warehouse_id=? AND location_id=?",
                    (quantity, now, reservation["material_id"], reservation["warehouse_id"], reservation["location_id"]),
                )
                conn.execute(
                    "UPDATE inventory_reservations SET issued_quantity=issued_quantity+?,updated_at=? WHERE id=?",
                    (quantity, now, reservation["id"]),
                )
                conn.execute(
                    "UPDATE material_requirement_items SET issued_quantity=issued_quantity+?,updated_at=? WHERE id=?",
                    (quantity, now, reservation["requirement_item_id"]),
                )
                affected.add(int(reservation["material_id"]))
            for material_id in affected:
                self.requirements._reallocate_material(conn, material_id, now)
        return self.get_order(flow_id)

    def return_material(self, payload: Dict[str, Any], operator_uid: str) -> Dict[str, Any]:
        items = payload.get("items") or []
        if not items:
            raise ValueError("退料单至少需要一条明细")
        now = inventory_now()
        requirement_id = int(payload["requirement_id"])
        with self.db.transaction() as conn:
            requirement = conn.execute("SELECT * FROM material_requirements WHERE id=?", (requirement_id,)).fetchone()
            if not requirement:
                raise LookupError("物料需求单不存在")
            flow_id, document_no = self._create_header(
                conn, "生产退料", requirement, str(payload.get("remark") or ""), operator_uid, now
            )
            affected: set[int] = set()
            for sequence, item in enumerate(items, 1):
                requirement_item = conn.execute(
                    "SELECT * FROM material_requirement_items WHERE id=? AND requirement_id=?",
                    (int(item["requirement_item_id"]), requirement_id),
                ).fetchone()
                if not requirement_item or int(requirement_item["material_id"]) != int(item["material_id"]):
                    raise ValueError("退料明细与需求物料不匹配")
                net_issued = float(requirement_item["issued_quantity"] or 0) - float(requirement_item["returned_quantity"] or 0)
                quantity = float(item["quantity"])
                if quantity - net_issued > EPSILON:
                    raise ValueError(f"退料数量超过净领料：最多可退 {net_issued:g} {requirement_item['unit']}")
                self._insert_item(
                    conn, flow_id, sequence, int(item["material_id"]), quantity, str(item["unit"]),
                    str(item.get("remark") or ""), requirement_item_id=int(item["requirement_item_id"]),
                    target_warehouse_id=int(item["warehouse_id"]), target_location_id=int(item["location_id"]),
                )
                self.inventory.post_transaction(
                    material_id=int(item["material_id"]), warehouse_id=int(item["warehouse_id"]),
                    location_id=int(item["location_id"]), transaction_type="生产退料", quantity=quantity,
                    unit=str(item["unit"]), source_type="material_return", source_id=document_no,
                    source_line=str(sequence), order_id=int(requirement["order_id"]),
                    door_unit_id=int(requirement["door_unit_id"]), production_no=str(requirement["production_no"]),
                    operator_uid=operator_uid, remark=str(item.get("remark") or payload.get("remark") or ""), conn=conn,
                )
                conn.execute(
                    "UPDATE material_requirement_items SET returned_quantity=returned_quantity+?,updated_at=? WHERE id=?",
                    (quantity, now, item["requirement_item_id"]),
                )
                affected.add(int(item["material_id"]))
            for material_id in affected:
                self.requirements._reallocate_material(conn, material_id, now)
        return self.get_order(flow_id)

    def transfer(self, payload: Dict[str, Any], operator_uid: str) -> Dict[str, Any]:
        return self._stock_operation("库存调拨", payload, operator_uid)

    def scrap(self, payload: Dict[str, Any], operator_uid: str) -> Dict[str, Any]:
        return self._stock_operation("报废出库", payload, operator_uid)

    def send_subcontract(self, payload: Dict[str, Any], operator_uid: str) -> Dict[str, Any]:
        items = payload.get("items") or []
        if not str(payload.get("supplier") or "").strip() or not items:
            raise ValueError("外协供应商和发出明细不能为空")
        now = inventory_now()
        with self.db.transaction() as conn:
            transit = conn.execute("SELECT id FROM inventory_warehouses WHERE code='SUBCONTRACT'").fetchone()
            if not transit:
                raise LookupError("外协在途仓不存在")
            location = conn.execute(
                "SELECT id FROM inventory_locations WHERE warehouse_id=? AND is_active=1 ORDER BY id LIMIT 1",
                (transit["id"],),
            ).fetchone()
            if not location:
                cursor = conn.execute(
                    """INSERT INTO inventory_locations(warehouse_id,code,name,is_active,remark,created_at,updated_at)
                       VALUES(?,'TRANSIT','外协在途',1,'系统自动创建',?,?)""", (transit["id"], now, now)
                )
                transit_location_id = int(cursor.lastrowid)
            else:
                transit_location_id = int(location["id"])
            next_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 AS value FROM subcontract_orders").fetchone()["value"])
            subcontract_no = f"WX{now[:10].replace('-', '')}{next_id:04d}"
            cursor = conn.execute(
                """INSERT INTO subcontract_orders(subcontract_no,supplier,work_package,expected_return_date,status,
                   remark,created_by,created_at,updated_at) VALUES(?,?,?,?,'外协中',?,?,?,?)""",
                (subcontract_no, str(payload["supplier"]).strip(), str(payload.get("work_package") or ""),
                 str(payload.get("expected_return_date") or ""), str(payload.get("remark") or ""), operator_uid, now, now),
            )
            order_id = int(cursor.lastrowid)
            for sequence, item in enumerate(items, 1):
                quantity = float(item["quantity"]); material_id = int(item["material_id"]); unit = str(item["unit"])
                source_balance = conn.execute(
                    "SELECT on_hand,reserved FROM inventory_balances WHERE material_id=? AND warehouse_id=? AND location_id=?",
                    (material_id, item["source_warehouse_id"], item["source_location_id"]),
                ).fetchone()
                available = float(source_balance["on_hand"] if source_balance else 0) - float(source_balance["reserved"] if source_balance else 0)
                if quantity - available > EPSILON:
                    raise ValueError(f"外协发出数量超过可用库存：最多 {max(0, available):g} {unit}")
                self.inventory.post_transaction(
                    material_id=material_id, warehouse_id=int(item["source_warehouse_id"]),
                    location_id=int(item["source_location_id"]), transaction_type="外协发出", quantity=-quantity,
                    unit=unit, source_type="subcontract_send", source_id=subcontract_no, source_line=f"{sequence}-out",
                    production_no=str(item.get("production_no") or ""), operator_uid=operator_uid,
                    remark=str(item.get("remark") or payload.get("remark") or ""), conn=conn,
                )
                self.inventory.post_transaction(
                    material_id=material_id, warehouse_id=int(transit["id"]), location_id=transit_location_id,
                    transaction_type="外协在途入库", quantity=quantity, unit=unit, source_type="subcontract_send",
                    source_id=subcontract_no, source_line=f"{sequence}-in", production_no=str(item.get("production_no") or ""),
                    operator_uid=operator_uid, remark=str(item.get("remark") or payload.get("remark") or ""), conn=conn,
                )
                conn.execute(
                    """INSERT INTO subcontract_items(subcontract_order_id,material_id,source_warehouse_id,source_location_id,
                       transit_warehouse_id,transit_location_id,sent_quantity,unit,production_no,status,remark,sequence_no)
                       VALUES(?,?,?,?,?,?,?, ?,?,'外协中',?,?)""",
                    (order_id, material_id, item["source_warehouse_id"], item["source_location_id"], transit["id"],
                     transit_location_id, quantity, unit, str(item.get("production_no") or ""),
                     str(item.get("remark") or ""), sequence),
                )
        return self.get_subcontract_order(order_id)

    def receive_subcontract(self, order_id: int, payload: Dict[str, Any], operator_uid: str) -> Dict[str, Any]:
        items = payload.get("items") or []
        if not items:
            raise ValueError("外协返回至少需要一条明细")
        now = inventory_now()
        with self.db.transaction() as conn:
            order = conn.execute("SELECT * FROM subcontract_orders WHERE id=?", (order_id,)).fetchone()
            if not order or order["status"] in ("已完成", "已取消"):
                raise LookupError("外协单不存在或已关闭")
            next_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 AS value FROM subcontract_receipts").fetchone()["value"])
            receipt_no = f"WXSH{now[:10].replace('-', '')}{next_id:04d}"
            cursor = conn.execute(
                """INSERT INTO subcontract_receipts(receipt_no,subcontract_order_id,return_date,status,remark,
                   created_by,created_at,updated_at) VALUES(?,?,?,'待检',?,?,?,?)""",
                (receipt_no, order_id, str(payload.get("return_date") or now[:10]), str(payload.get("remark") or ""), operator_uid, now, now),
            )
            receipt_id = int(cursor.lastrowid)
            for item in items:
                source = conn.execute("SELECT * FROM subcontract_items WHERE id=? AND subcontract_order_id=?", (item["subcontract_item_id"], order_id)).fetchone()
                if not source:
                    raise ValueError("外协返回明细不存在")
                quantity = float(item["quantity"])
                remaining = float(source["sent_quantity"] or 0) - float(source["returned_quantity"] or 0)
                if quantity - remaining > EPSILON:
                    raise ValueError(f"外协返回数量超过待回数量：最多 {remaining:g} {source['unit']}")
                conn.execute(
                    """INSERT INTO subcontract_receipt_items(receipt_id,subcontract_item_id,material_id,returned_quantity,
                       unit,status,created_at,updated_at) VALUES(?,?,?,?,?,'待检',?,?)""",
                    (receipt_id, source["id"], source["material_id"], quantity, source["unit"], now, now),
                )
                conn.execute(
                    "UPDATE subcontract_items SET returned_quantity=returned_quantity+?,status='待检' WHERE id=?",
                    (quantity, source["id"]),
                )
        return self.get_subcontract_receipt(receipt_id)

    def inspect_subcontract(self, receipt_item_id: int, payload: Dict[str, Any], operator_uid: str) -> Dict[str, Any]:
        accepted = float(payload.get("accepted_quantity") or 0); rejected = float(payload.get("rejected_quantity") or 0)
        now = inventory_now()
        with self.db.transaction() as conn:
            row = conn.execute(
                """SELECT ri.*,r.receipt_no,r.id AS receipt_id,si.transit_warehouse_id,si.transit_location_id,
                          si.production_no,si.subcontract_order_id
                   FROM subcontract_receipt_items ri JOIN subcontract_receipts r ON r.id=ri.receipt_id
                   JOIN subcontract_items si ON si.id=ri.subcontract_item_id WHERE ri.id=?""", (receipt_item_id,)
            ).fetchone()
            if not row:
                raise LookupError("外协待检明细不存在")
            if row["status"] != "待检":
                raise RuntimeError("该外协返回明细已经检验")
            if abs(accepted + rejected - float(row["returned_quantity"])) > EPSILON:
                raise ValueError("接收数量与不合格数量之和必须等于本次返回数量")
            if accepted > EPSILON:
                self.inventory.post_transaction(
                    material_id=int(row["material_id"]), warehouse_id=int(row["transit_warehouse_id"]),
                    location_id=int(row["transit_location_id"]), transaction_type="外协返回出库", quantity=-accepted,
                    unit=str(row["unit"]), source_type="subcontract_receipt", source_id=str(row["receipt_no"]),
                    source_line=f"{receipt_item_id}-out", production_no=str(row["production_no"]), operator_uid=operator_uid, conn=conn,
                )
                self.inventory.post_transaction(
                    material_id=int(row["material_id"]), warehouse_id=int(payload["warehouse_id"]),
                    location_id=int(payload["location_id"]), transaction_type="外协合格入库", quantity=accepted,
                    unit=str(row["unit"]), source_type="subcontract_receipt", source_id=str(row["receipt_no"]),
                    source_line=f"{receipt_item_id}-in", production_no=str(row["production_no"]), operator_uid=operator_uid,
                    remark=str(payload.get("remark") or ""), conn=conn,
                )
            if rejected > EPSILON:
                self.inventory.post_transaction(
                    material_id=int(row["material_id"]), warehouse_id=int(row["transit_warehouse_id"]),
                    location_id=int(row["transit_location_id"]), transaction_type="外协不合格核销", quantity=-rejected,
                    unit=str(row["unit"]), source_type="subcontract_reject", source_id=str(row["receipt_no"]),
                    source_line=str(receipt_item_id), production_no=str(row["production_no"]), operator_uid=operator_uid,
                    remark=str(payload.get("remark") or ""), conn=conn,
                )
            conn.execute(
                """UPDATE subcontract_receipt_items SET accepted_quantity=?,rejected_quantity=?,target_warehouse_id=?,
                   target_location_id=?,status=?,remark=?,updated_at=? WHERE id=?""",
                (accepted, rejected, payload["warehouse_id"], payload["location_id"],
                 "合格" if rejected <= EPSILON else ("不合格" if accepted <= EPSILON else "部分合格"),
                 str(payload.get("remark") or ""), now, receipt_item_id),
            )
            conn.execute(
                """UPDATE subcontract_items SET accepted_quantity=accepted_quantity+?,rejected_quantity=rejected_quantity+?,
                   status=CASE WHEN returned_quantity>=sent_quantity THEN '已完成' ELSE '外协中' END WHERE id=?""",
                (accepted, rejected, row["subcontract_item_id"]),
            )
            pending = int(conn.execute("SELECT COUNT(*) AS total FROM subcontract_receipt_items WHERE receipt_id=? AND status='待检'", (row["receipt_id"],)).fetchone()["total"])
            if pending == 0:
                conn.execute("UPDATE subcontract_receipts SET status='已检验',updated_at=? WHERE id=?", (now, row["receipt_id"]))
            open_items = int(conn.execute("SELECT COUNT(*) AS total FROM subcontract_items WHERE subcontract_order_id=? AND status!='已完成'", (row["subcontract_order_id"],)).fetchone()["total"])
            conn.execute("UPDATE subcontract_orders SET status=?,updated_at=? WHERE id=?", ("已完成" if open_items == 0 else "部分返回", now, row["subcontract_order_id"]))
        return self.get_subcontract_receipt(int(row["receipt_id"]))

    def list_subcontract_orders(self, status: str = "") -> List[Dict[str, Any]]:
        where = "WHERE o.status=?" if status else ""; params = (status,) if status else ()
        return self.db.fetch_all(
            f"""SELECT o.*,COUNT(i.id) AS item_count,COALESCE(SUM(i.sent_quantity),0) AS sent_quantity,
                       COALESCE(SUM(i.returned_quantity),0) AS returned_quantity,
                       COALESCE(SUM(i.sent_quantity-i.returned_quantity),0) AS pending_quantity
                FROM subcontract_orders o LEFT JOIN subcontract_items i ON i.subcontract_order_id=o.id
                {where} GROUP BY o.id ORDER BY CASE WHEN o.expected_return_date='' THEN 1 ELSE 0 END,
                o.expected_return_date,o.id DESC""", params
        )

    def get_subcontract_order(self, order_id: int) -> Dict[str, Any]:
        order = self.db.fetch_one("SELECT * FROM subcontract_orders WHERE id=?", (order_id,))
        if not order:
            raise LookupError("外协单不存在")
        order["items"] = self.db.fetch_all(
            """SELECT i.*,m.code AS material_code,m.name AS material_name,m.specification
               FROM subcontract_items i JOIN inventory_materials m ON m.id=i.material_id
               WHERE i.subcontract_order_id=? ORDER BY i.sequence_no,i.id""", (order_id,)
        )
        return order

    def list_subcontract_receipts(self, status: str = "") -> List[Dict[str, Any]]:
        where = "WHERE r.status=?" if status else ""; params = (status,) if status else ()
        return self.db.fetch_all(
            f"""SELECT r.*,o.subcontract_no,o.supplier,COUNT(i.id) AS item_count
                FROM subcontract_receipts r JOIN subcontract_orders o ON o.id=r.subcontract_order_id
                LEFT JOIN subcontract_receipt_items i ON i.receipt_id=r.id {where}
                GROUP BY r.id ORDER BY r.id DESC""", params
        )

    def get_subcontract_receipt(self, receipt_id: int) -> Dict[str, Any]:
        receipt = self.db.fetch_one(
            """SELECT r.*,o.subcontract_no,o.supplier FROM subcontract_receipts r
               JOIN subcontract_orders o ON o.id=r.subcontract_order_id WHERE r.id=?""", (receipt_id,)
        )
        if not receipt:
            raise LookupError("外协返回单不存在")
        receipt["items"] = self.db.fetch_all(
            """SELECT i.*,m.code AS material_code,m.name AS material_name,m.specification,si.production_no
               FROM subcontract_receipt_items i JOIN inventory_materials m ON m.id=i.material_id
               JOIN subcontract_items si ON si.id=i.subcontract_item_id WHERE i.receipt_id=? ORDER BY i.id""", (receipt_id,)
        )
        return receipt

    def _stock_operation(self, document_type: str, payload: Dict[str, Any], operator_uid: str) -> Dict[str, Any]:
        items = payload.get("items") or []
        if not items:
            raise ValueError(f"{document_type}至少需要一条明细")
        now = inventory_now()
        with self.db.transaction() as conn:
            sequence_no = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 AS value FROM material_flow_orders").fetchone()["value"])
            prefix = "DB" if document_type == "库存调拨" else "BF"
            document_no = f"{prefix}{now[:10].replace('-', '')}{sequence_no:04d}"
            cursor = conn.execute(
                """INSERT INTO material_flow_orders(document_no,document_type,production_no,status,remark,created_by,created_at,confirmed_at)
                   VALUES(?,?,?,'已确认',?,?,?,?)""",
                (document_no, document_type, str(payload.get("production_no") or ""), str(payload.get("remark") or ""), operator_uid, now, now),
            )
            flow_id = int(cursor.lastrowid)
            for sequence, item in enumerate(items, 1):
                material_id = int(item["material_id"]); quantity = float(item["quantity"]); unit = str(item["unit"])
                source_warehouse = int(item.get("source_warehouse_id") or item.get("warehouse_id"))
                source_location = int(item.get("source_location_id") or item.get("location_id"))
                target_warehouse = item.get("target_warehouse_id"); target_location = item.get("target_location_id")
                source_balance = conn.execute(
                    "SELECT on_hand,reserved FROM inventory_balances WHERE material_id=? AND warehouse_id=? AND location_id=?",
                    (material_id, source_warehouse, source_location),
                ).fetchone()
                available = float(source_balance["on_hand"] if source_balance else 0) - float(source_balance["reserved"] if source_balance else 0)
                if quantity - available > EPSILON:
                    raise ValueError(f"可用库存不足：最多可操作 {max(0, available):g} {unit}")
                if document_type == "库存调拨" and source_warehouse == int(target_warehouse) and source_location == int(target_location):
                    raise ValueError("调出和调入库位不能相同")
                self._insert_item(conn, flow_id, sequence, material_id, quantity, unit, str(item.get("remark") or ""),
                                  source_warehouse_id=source_warehouse, source_location_id=source_location,
                                  target_warehouse_id=int(target_warehouse) if target_warehouse else None,
                                  target_location_id=int(target_location) if target_location else None)
                self.inventory.post_transaction(
                    material_id=material_id, warehouse_id=source_warehouse, location_id=source_location,
                    transaction_type="调拨出库" if document_type == "库存调拨" else "报废出库",
                    quantity=-quantity, unit=unit, source_type="stock_transfer" if document_type == "库存调拨" else "stock_scrap",
                    source_id=document_no, source_line=f"{sequence}-out", production_no=str(payload.get("production_no") or ""),
                    operator_uid=operator_uid, remark=str(item.get("remark") or payload.get("remark") or ""), conn=conn,
                )
                if document_type == "库存调拨":
                    self.inventory.post_transaction(
                        material_id=material_id, warehouse_id=int(target_warehouse), location_id=int(target_location),
                        transaction_type="调拨入库", quantity=quantity, unit=unit, source_type="stock_transfer",
                        source_id=document_no, source_line=f"{sequence}-in", operator_uid=operator_uid,
                        remark=str(item.get("remark") or payload.get("remark") or ""), conn=conn,
                    )
        return self.get_order(flow_id)

    def list_orders(self, document_type: str = "", production_no: str = "") -> List[Dict[str, Any]]:
        where = ["1=1"]; params: List[Any] = []
        if document_type:
            where.append("document_type=?"); params.append(document_type)
        if production_no:
            where.append("production_no LIKE ?"); params.append(f"%{production_no.strip()}%")
        return self.db.fetch_all(
            f"""SELECT o.*, COUNT(i.id) AS item_count, COALESCE(SUM(i.quantity),0) AS total_quantity
                FROM material_flow_orders o LEFT JOIN material_flow_items i ON i.flow_order_id=o.id
                WHERE {' AND '.join(where)} GROUP BY o.id ORDER BY o.id DESC LIMIT 300""", params
        )

    def get_order(self, flow_id: int) -> Dict[str, Any]:
        order = self.db.fetch_one("SELECT * FROM material_flow_orders WHERE id=?", (flow_id,))
        if not order:
            raise LookupError("库存作业单不存在")
        order["items"] = self.db.fetch_all(
            """SELECT i.*,m.code AS material_code,m.name AS material_name,m.specification,
                      sw.name AS source_warehouse_name,sl.name AS source_location_name,
                      tw.name AS target_warehouse_name,tl.name AS target_location_name
               FROM material_flow_items i JOIN inventory_materials m ON m.id=i.material_id
               LEFT JOIN inventory_warehouses sw ON sw.id=i.source_warehouse_id
               LEFT JOIN inventory_locations sl ON sl.id=i.source_location_id
               LEFT JOIN inventory_warehouses tw ON tw.id=i.target_warehouse_id
               LEFT JOIN inventory_locations tl ON tl.id=i.target_location_id
               WHERE i.flow_order_id=? ORDER BY i.sequence_no,i.id""", (flow_id,)
        )
        return order

    @staticmethod
    def _create_header(conn: sqlite3.Connection, document_type: str, requirement: sqlite3.Row,
                       remark: str, operator_uid: str, now: str) -> tuple[int, str]:
        next_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 AS value FROM material_flow_orders").fetchone()["value"])
        prefix = "LL" if document_type == "生产发料" else "TL"
        document_no = f"{prefix}{now[:10].replace('-', '')}{next_id:04d}"
        cursor = conn.execute(
            """INSERT INTO material_flow_orders(document_no,document_type,requirement_id,order_id,door_unit_id,
                   production_no,status,remark,created_by,created_at,confirmed_at)
               VALUES(?,?,?,?,?,?,'已确认',?,?,?,?)""",
            (document_no, document_type, requirement["id"], requirement["order_id"], requirement["door_unit_id"],
             requirement["production_no"], remark, operator_uid, now, now),
        )
        return int(cursor.lastrowid), document_no

    @staticmethod
    def _insert_item(conn: sqlite3.Connection, flow_id: int, sequence: int, material_id: int,
                     quantity: float, unit: str, remark: str, **links: Any) -> None:
        conn.execute(
            """INSERT INTO material_flow_items(flow_order_id,requirement_item_id,reservation_id,material_id,
                   source_warehouse_id,source_location_id,target_warehouse_id,target_location_id,
                   quantity,unit,remark,sequence_no) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (flow_id, links.get("requirement_item_id"), links.get("reservation_id"), material_id,
             links.get("source_warehouse_id"), links.get("source_location_id"), links.get("target_warehouse_id"),
             links.get("target_location_id"), quantity, unit, remark, sequence),
        )
