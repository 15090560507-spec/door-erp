"""Merged purchasing, receipt inspection, and inventory posting rules."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from inventory_database import InventoryDatabase, inventory_now
from inventory_service import InventoryService
from requirement_service import EPSILON, RequirementService


class PurchasingService:
    def __init__(self, db: InventoryDatabase):
        self.db = db
        self.inventory = InventoryService(db)
        self.requirements = RequirementService(db)

    def sync_demands(self, conn: sqlite3.Connection | None = None) -> None:
        now = inventory_now()
        with self.db.transaction(conn) as tx:
            rows = tx.execute(
                """SELECT i.id, i.material_id, i.shortage_quantity, i.unit,
                          q.due_date, q.production_no, q.status AS requirement_status
                   FROM material_requirement_items i
                   JOIN material_requirements q ON q.id=i.requirement_id"""
            ).fetchall()
            for row in rows:
                quantity = max(0.0, float(row["shortage_quantity"] or 0))
                status = "已冻结" if row["requirement_status"] == "已冻结" else ("待采购" if quantity > EPSILON else "已覆盖")
                tx.execute(
                    """INSERT INTO purchase_demands(
                           requirement_item_id, material_id, demand_quantity, unit,
                           due_date, production_no, status, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(requirement_item_id) DO UPDATE SET
                           material_id=excluded.material_id,
                           demand_quantity=excluded.demand_quantity,
                           unit=excluded.unit,
                           due_date=excluded.due_date,
                           production_no=excluded.production_no,
                           status=excluded.status,
                           updated_at=excluded.updated_at""",
                    (row["id"], row["material_id"], quantity, row["unit"], row["due_date"], row["production_no"], status, now, now),
                )

    def list_shortages(self, q: str = "") -> List[Dict[str, Any]]:
        self.sync_demands()
        params: List[Any] = [EPSILON]
        where = ["d.status='待采购'", "d.demand_quantity>?"]
        if q.strip():
            term = f"%{q.strip()}%"
            where.append("(d.production_no LIKE ? OR m.code LIKE ? OR m.name LIKE ? OR m.specification LIKE ?)")
            params.extend([term, term, term, term])
        return self.db.fetch_all(
            f"""SELECT d.*, m.code AS material_code, m.name AS material_name,
                       m.specification, m.default_supplier, i.requirement_id
                FROM purchase_demands d
                JOIN inventory_materials m ON m.id=d.material_id
                JOIN material_requirement_items i ON i.id=d.requirement_item_id
                WHERE {' AND '.join(where)}
                ORDER BY CASE WHEN d.due_date='' THEN 1 ELSE 0 END,
                         d.due_date, d.material_id, d.production_no""",
            params,
        )

    def create_order(self, payload: Dict[str, Any], created_by: str) -> Dict[str, Any]:
        supplier = str(payload.get("supplier") or "").strip()
        items = list(payload.get("items") or [])
        if not supplier:
            raise ValueError("供应商不能为空")
        if not items:
            raise ValueError("采购单至少需要一条物料")
        now = inventory_now()
        with self.db.transaction() as conn:
            next_id = int(conn.execute("SELECT COALESCE(MAX(id), 0)+1 AS id FROM purchase_orders").fetchone()["id"])
            order_no = f"CG{now[:10].replace('-', '')}{next_id:04d}"
            total = 0.0
            cursor = conn.execute(
                """INSERT INTO purchase_orders(
                       order_no, supplier, expected_date, status, total_amount,
                       remark, created_by, created_at, updated_at
                   ) VALUES (?, ?, ?, '草稿', 0, ?, ?, ?, ?)""",
                (order_no, supplier, str(payload.get("expected_date") or ""), str(payload.get("remark") or ""), created_by, now, now),
            )
            order_id = int(cursor.lastrowid)
            for sequence, item in enumerate(items, start=1):
                material = conn.execute(
                    "SELECT * FROM inventory_materials WHERE id=? AND is_active=1",
                    (int(item["material_id"]),),
                ).fetchone()
                if not material:
                    raise LookupError("采购物料不存在或已停用")
                quantity = float(item.get("quantity") or 0)
                unit = str(item.get("unit") or "").strip()
                unit_price = float(item.get("unit_price") or 0)
                if quantity <= EPSILON:
                    raise ValueError("采购数量必须大于零")
                if unit != str(material["unit"]):
                    raise ValueError(f"{material['name']} 的采购单位必须为 {material['unit']}")
                allocations = list(item.get("allocations") or [])
                allocated = sum(float(entry.get("quantity") or 0) for entry in allocations)
                if allocated - quantity > EPSILON:
                    raise ValueError("需求分配数量不能超过采购数量")
                item_cursor = conn.execute(
                    """INSERT INTO purchase_order_items(
                           purchase_order_id, material_id, material_code, material_name,
                           specification, ordered_quantity, unit, unit_price, status,
                           remark, sequence_no, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '草稿', ?, ?, ?, ?)""",
                    (order_id, material["id"], material["code"], material["name"], material["specification"], quantity, unit, unit_price, str(item.get("remark") or ""), sequence, now, now),
                )
                purchase_item_id = int(item_cursor.lastrowid)
                for allocation in allocations:
                    requirement_item = conn.execute(
                        """SELECT i.*, q.status AS requirement_status
                           FROM material_requirement_items i
                           JOIN material_requirements q ON q.id=i.requirement_id
                           WHERE i.id=?""",
                        (int(allocation["requirement_item_id"]),),
                    ).fetchone()
                    if not requirement_item or requirement_item["requirement_status"] == "已冻结":
                        raise LookupError("分配的物料需求不存在或已经冻结")
                    if int(requirement_item["material_id"]) != int(material["id"]):
                        raise ValueError("采购物料与分配需求的物料不一致")
                    conn.execute(
                        """INSERT INTO purchase_allocations(
                               purchase_order_item_id, requirement_item_id,
                               allocated_quantity, status, created_at, updated_at
                           ) VALUES (?, ?, ?, '草稿', ?, ?)""",
                        (purchase_item_id, requirement_item["id"], float(allocation["quantity"]), now, now),
                    )
                total += quantity * unit_price
            conn.execute("UPDATE purchase_orders SET total_amount=? WHERE id=?", (round(total, 2), order_id))
        return self.get_order(order_id)

    def confirm_order(self, order_id: int, confirmed_by: str) -> Dict[str, Any]:
        now = inventory_now()
        with self.db.transaction() as conn:
            order = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (order_id,)).fetchone()
            if not order:
                raise LookupError("采购单不存在")
            if order["status"] != "草稿":
                raise RuntimeError("只有草稿采购单可以确认")
            allocations = conn.execute(
                """SELECT a.requirement_item_id, SUM(a.allocated_quantity) AS quantity
                   FROM purchase_allocations a
                   JOIN purchase_order_items p ON p.id=a.purchase_order_item_id
                   WHERE p.purchase_order_id=? GROUP BY a.requirement_item_id""",
                (order_id,),
            ).fetchall()
            for allocation in allocations:
                requirement_item = conn.execute(
                    """SELECT i.*, q.status AS requirement_status
                       FROM material_requirement_items i
                       JOIN material_requirements q ON q.id=i.requirement_id WHERE i.id=?""",
                    (allocation["requirement_item_id"],),
                ).fetchone()
                if not requirement_item or requirement_item["requirement_status"] == "已冻结":
                    raise RuntimeError("采购单包含已失效的物料需求")
                if float(allocation["quantity"] or 0) - float(requirement_item["shortage_quantity"] or 0) > EPSILON:
                    raise RuntimeError(f"{requirement_item['material_name']} 的分配数量超过当前缺口，请刷新后重新制单")
            affected_materials: set[int] = set()
            for allocation in allocations:
                conn.execute(
                    """UPDATE material_requirement_items
                       SET purchased_quantity=purchased_quantity+?, updated_at=? WHERE id=?""",
                    (allocation["quantity"], now, allocation["requirement_item_id"]),
                )
            material_rows = conn.execute("SELECT DISTINCT material_id FROM purchase_order_items WHERE purchase_order_id=?", (order_id,)).fetchall()
            affected_materials.update(int(row["material_id"]) for row in material_rows)
            conn.execute("UPDATE purchase_order_items SET status='已下单', updated_at=? WHERE purchase_order_id=?", (now, order_id))
            conn.execute(
                "UPDATE purchase_allocations SET status='有效', updated_at=? WHERE purchase_order_item_id IN (SELECT id FROM purchase_order_items WHERE purchase_order_id=?)",
                (now, order_id),
            )
            conn.execute(
                """UPDATE purchase_orders SET status='已下单', confirmed_by=?,
                       confirmed_at=?, updated_at=? WHERE id=?""",
                (confirmed_by, now, now, order_id),
            )
            for material_id in affected_materials:
                self.requirements._reallocate_material(conn, material_id, now)
            self.sync_demands(conn)
        return self.get_order(order_id)

    def cancel_order(self, order_id: int) -> Dict[str, Any]:
        now = inventory_now()
        with self.db.transaction() as conn:
            order = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (order_id,)).fetchone()
            if not order:
                raise LookupError("采购单不存在")
            if order["status"] in {"已取消", "已完成"}:
                raise RuntimeError("当前采购单不能取消")
            affected_materials: set[int] = set()
            if order["status"] != "草稿":
                allocations = conn.execute(
                    """SELECT a.*, p.material_id FROM purchase_allocations a
                       JOIN purchase_order_items p ON p.id=a.purchase_order_item_id
                       WHERE p.purchase_order_id=? AND a.status='有效'""",
                    (order_id,),
                ).fetchall()
                for allocation in allocations:
                    cancellable = max(0.0, float(allocation["allocated_quantity"]) - float(allocation["received_quantity"]) - float(allocation["cancelled_quantity"]))
                    if cancellable > EPSILON:
                        conn.execute(
                            "UPDATE material_requirement_items SET purchased_quantity=MAX(received_quantity, purchased_quantity-?), updated_at=? WHERE id=?",
                            (cancellable, now, allocation["requirement_item_id"]),
                        )
                        conn.execute(
                            "UPDATE purchase_allocations SET cancelled_quantity=cancelled_quantity+?, status='已取消', updated_at=? WHERE id=?",
                            (cancellable, now, allocation["id"]),
                        )
                        affected_materials.add(int(allocation["material_id"]))
            conn.execute(
                """UPDATE purchase_order_items SET
                       cancelled_quantity=MAX(cancelled_quantity, ordered_quantity-received_quantity-rejected_quantity),
                       status='已取消', updated_at=? WHERE purchase_order_id=?""",
                (now, order_id),
            )
            conn.execute("UPDATE purchase_orders SET status='已取消', updated_at=? WHERE id=?", (now, order_id))
            for material_id in affected_materials:
                self.requirements._reallocate_material(conn, material_id, now)
            self.sync_demands(conn)
        return self.get_order(order_id)

    def list_orders(self, status: str = "", q: str = "") -> List[Dict[str, Any]]:
        where = ["1=1"]
        params: List[Any] = []
        if status:
            where.append("o.status=?")
            params.append(status)
        if q.strip():
            term = f"%{q.strip()}%"
            where.append("(o.order_no LIKE ? OR o.supplier LIKE ? OR EXISTS (SELECT 1 FROM purchase_order_items pi WHERE pi.purchase_order_id=o.id AND (pi.material_code LIKE ? OR pi.material_name LIKE ?)))")
            params.extend([term, term, term, term])
        rows = self.db.fetch_all(
            f"""SELECT o.*, COUNT(i.id) AS item_count,
                       COALESCE(SUM(i.ordered_quantity), 0) AS ordered_quantity,
                       COALESCE(SUM(i.received_quantity), 0) AS received_quantity
                FROM purchase_orders o LEFT JOIN purchase_order_items i ON i.purchase_order_id=o.id
                WHERE {' AND '.join(where)} GROUP BY o.id ORDER BY o.created_at DESC, o.id DESC""",
            params,
        )
        return rows

    def get_order(self, order_id: int) -> Dict[str, Any]:
        order = self.db.fetch_one("SELECT * FROM purchase_orders WHERE id=?", (order_id,))
        if not order:
            raise LookupError("采购单不存在")
        order["items"] = self.db.fetch_all("SELECT * FROM purchase_order_items WHERE purchase_order_id=? ORDER BY sequence_no, id", (order_id,))
        for item in order["items"]:
            item["allocations"] = self.db.fetch_all(
                """SELECT a.*, i.material_name AS requirement_material_name,
                          q.requirement_no, q.production_no, q.due_date
                   FROM purchase_allocations a
                   JOIN material_requirement_items i ON i.id=a.requirement_item_id
                   JOIN material_requirements q ON q.id=i.requirement_id
                   WHERE a.purchase_order_item_id=? ORDER BY q.due_date, q.production_no""",
                (item["id"],),
            )
        return order

    def create_receipt(self, order_id: int, payload: Dict[str, Any], created_by: str) -> Dict[str, Any]:
        items = list(payload.get("items") or [])
        if not items:
            raise ValueError("到货单至少需要一条物料")
        now = inventory_now()
        with self.db.transaction() as conn:
            order = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (order_id,)).fetchone()
            if not order:
                raise LookupError("采购单不存在")
            if order["status"] not in {"已下单", "部分到货"}:
                raise RuntimeError("只有已下单的采购单可以登记到货")
            next_id = int(conn.execute("SELECT COALESCE(MAX(id), 0)+1 AS id FROM purchase_receipts").fetchone()["id"])
            receipt_no = f"SH{now[:10].replace('-', '')}{next_id:04d}"
            cursor = conn.execute(
                """INSERT INTO purchase_receipts(
                       receipt_no, purchase_order_id, supplier, arrival_date,
                       status, remark, created_by, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, '待检', ?, ?, ?, ?)""",
                (receipt_no, order_id, order["supplier"], str(payload.get("arrival_date") or now[:10]), str(payload.get("remark") or ""), created_by, now, now),
            )
            receipt_id = int(cursor.lastrowid)
            for item in items:
                purchase_item = conn.execute(
                    "SELECT * FROM purchase_order_items WHERE id=? AND purchase_order_id=?",
                    (int(item["purchase_order_item_id"]), order_id),
                ).fetchone()
                if not purchase_item:
                    raise LookupError("采购明细不存在")
                registered = float(conn.execute(
                    """SELECT COALESCE(SUM(ri.received_quantity), 0) AS total
                       FROM purchase_receipt_items ri
                       JOIN purchase_receipts r ON r.id=ri.receipt_id
                       WHERE ri.purchase_order_item_id=? AND r.status!='已取消'""",
                    (purchase_item["id"],),
                ).fetchone()["total"] or 0)
                quantity = float(item.get("quantity") or 0)
                remaining = float(purchase_item["ordered_quantity"]) - float(purchase_item["cancelled_quantity"]) - registered
                if quantity <= EPSILON or quantity - remaining > EPSILON:
                    raise ValueError(f"{purchase_item['material_name']} 的到货数量超过未登记数量 {max(0, remaining):g}")
                conn.execute(
                    """INSERT INTO purchase_receipt_items(
                           receipt_id, purchase_order_item_id, material_id,
                           received_quantity, unit, status, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, '待检', ?, ?)""",
                    (receipt_id, purchase_item["id"], purchase_item["material_id"], quantity, purchase_item["unit"], now, now),
                )
            conn.execute("UPDATE purchase_orders SET status='部分到货', updated_at=? WHERE id=?", (now, order_id))
        return self.get_receipt(receipt_id)

    def list_receipts(self, status: str = "") -> List[Dict[str, Any]]:
        where = "WHERE r.status=?" if status else ""
        params = [status] if status else []
        return self.db.fetch_all(
            f"""SELECT r.*, o.order_no, COUNT(i.id) AS item_count,
                       COALESCE(SUM(i.received_quantity), 0) AS received_quantity
                FROM purchase_receipts r
                JOIN purchase_orders o ON o.id=r.purchase_order_id
                LEFT JOIN purchase_receipt_items i ON i.receipt_id=r.id
                {where} GROUP BY r.id ORDER BY r.created_at DESC, r.id DESC""",
            params,
        )

    def get_receipt(self, receipt_id: int) -> Dict[str, Any]:
        receipt = self.db.fetch_one(
            """SELECT r.*, o.order_no FROM purchase_receipts r
               JOIN purchase_orders o ON o.id=r.purchase_order_id WHERE r.id=?""",
            (receipt_id,),
        )
        if not receipt:
            raise LookupError("到货单不存在")
        receipt["items"] = self.db.fetch_all(
            """SELECT ri.*, pi.material_code, pi.material_name, pi.specification
               FROM purchase_receipt_items ri
               JOIN purchase_order_items pi ON pi.id=ri.purchase_order_item_id
               WHERE ri.receipt_id=? ORDER BY ri.id""",
            (receipt_id,),
        )
        return receipt

    def inspect_receipt_item(self, receipt_item_id: int, payload: Dict[str, Any], inspector_uid: str) -> Dict[str, Any]:
        now = inventory_now()
        qualified = float(payload.get("qualified_quantity") or 0)
        concession = float(payload.get("concession_quantity") or 0)
        rejected = float(payload.get("rejected_quantity") or 0)
        with self.db.transaction() as conn:
            item = conn.execute(
                """SELECT ri.*, r.receipt_no, r.id AS receipt_id, r.purchase_order_id,
                          pi.material_name, pi.unit, pi.ordered_quantity,
                          pi.cancelled_quantity, pi.received_quantity AS po_received,
                          pi.rejected_quantity AS po_rejected
                   FROM purchase_receipt_items ri
                   JOIN purchase_receipts r ON r.id=ri.receipt_id
                   JOIN purchase_order_items pi ON pi.id=ri.purchase_order_item_id
                   WHERE ri.id=?""",
                (receipt_item_id,),
            ).fetchone()
            if not item:
                raise LookupError("待检明细不存在")
            if item["status"] != "待检":
                raise RuntimeError("该到货明细已经检验，不能重复提交")
            if abs((qualified + concession + rejected) - float(item["received_quantity"])) > EPSILON:
                raise ValueError("合格、让步接收和不合格数量之和必须等于到货数量")
            accepted = qualified + concession
            if accepted > EPSILON:
                self.inventory.post_transaction(
                    material_id=int(item["material_id"]),
                    warehouse_id=int(payload["warehouse_id"]),
                    location_id=int(payload["location_id"]),
                    transaction_type="采购入库",
                    quantity=accepted,
                    unit=str(item["unit"]),
                    source_type="purchase_receipt",
                    source_id=str(item["receipt_no"]),
                    source_line=str(receipt_item_id),
                    operator_uid=inspector_uid,
                    remark=str(payload.get("remark") or ""),
                    conn=conn,
                )
            result = "不合格" if accepted <= EPSILON else ("合格" if rejected <= EPSILON and concession <= EPSILON else ("让步接收" if rejected <= EPSILON else "部分合格"))
            conn.execute(
                """INSERT INTO incoming_inspections(
                       receipt_item_id, result, qualified_quantity, concession_quantity,
                       rejected_quantity, inspector_uid, remark, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (receipt_item_id, result, qualified, concession, rejected, inspector_uid, str(payload.get("remark") or ""), now),
            )
            conn.execute(
                """UPDATE purchase_receipt_items SET qualified_quantity=?, concession_quantity=?,
                       rejected_quantity=?, inbound_quantity=?, status=?, remark=?, updated_at=? WHERE id=?""",
                (qualified, concession, rejected, accepted, "已入库" if accepted > EPSILON else "已拒收", str(payload.get("remark") or ""), now, receipt_item_id),
            )
            conn.execute(
                """UPDATE purchase_order_items SET received_quantity=received_quantity+?,
                       rejected_quantity=rejected_quantity+?, updated_at=? WHERE id=?""",
                (accepted, rejected, now, item["purchase_order_item_id"]),
            )
            remaining_accepted = accepted
            allocations = conn.execute(
                """SELECT a.* FROM purchase_allocations a
                   JOIN material_requirement_items i ON i.id=a.requirement_item_id
                   JOIN material_requirements q ON q.id=i.requirement_id
                   WHERE a.purchase_order_item_id=? AND a.status='有效'
                   ORDER BY CASE WHEN q.due_date='' THEN 1 ELSE 0 END, q.due_date, q.production_no, a.id""",
                (item["purchase_order_item_id"],),
            ).fetchall()
            for allocation in allocations:
                if remaining_accepted <= EPSILON:
                    break
                remaining_allocation = max(0.0, float(allocation["allocated_quantity"]) - float(allocation["received_quantity"]) - float(allocation["cancelled_quantity"]))
                assigned = min(remaining_accepted, remaining_allocation)
                if assigned <= EPSILON:
                    continue
                conn.execute("UPDATE purchase_allocations SET received_quantity=received_quantity+?, updated_at=? WHERE id=?", (assigned, now, allocation["id"]))
                conn.execute("UPDATE material_requirement_items SET received_quantity=received_quantity+?, updated_at=? WHERE id=?", (assigned, now, allocation["requirement_item_id"]))
                remaining_accepted -= assigned
            registered = float(conn.execute(
                "SELECT COALESCE(SUM(received_quantity),0) AS total FROM purchase_receipt_items WHERE purchase_order_item_id=?",
                (item["purchase_order_item_id"],),
            ).fetchone()["total"] or 0)
            pending_for_line = int(conn.execute(
                "SELECT COUNT(*) AS total FROM purchase_receipt_items WHERE purchase_order_item_id=? AND status='待检'",
                (item["purchase_order_item_id"],),
            ).fetchone()["total"])
            if pending_for_line == 0 and registered + float(item["cancelled_quantity"] or 0) >= float(item["ordered_quantity"]) - EPSILON:
                open_allocations = conn.execute(
                    "SELECT * FROM purchase_allocations WHERE purchase_order_item_id=? AND status='有效'",
                    (item["purchase_order_item_id"],),
                ).fetchall()
                for allocation in open_allocations:
                    cancellable = max(0.0, float(allocation["allocated_quantity"]) - float(allocation["received_quantity"]) - float(allocation["cancelled_quantity"]))
                    if cancellable > EPSILON:
                        conn.execute("UPDATE purchase_allocations SET cancelled_quantity=cancelled_quantity+?, status='已完成', updated_at=? WHERE id=?", (cancellable, now, allocation["id"]))
                        conn.execute("UPDATE material_requirement_items SET purchased_quantity=MAX(received_quantity, purchased_quantity-?), updated_at=? WHERE id=?", (cancellable, now, allocation["requirement_item_id"]))
                    else:
                        conn.execute("UPDATE purchase_allocations SET status='已完成', updated_at=? WHERE id=?", (now, allocation["id"]))
                conn.execute("UPDATE purchase_order_items SET status='已完成', updated_at=? WHERE id=?", (now, item["purchase_order_item_id"]))
            receipt_open = int(conn.execute("SELECT COUNT(*) AS total FROM purchase_receipt_items WHERE receipt_id=? AND status='待检'", (item["receipt_id"],)).fetchone()["total"])
            if receipt_open == 0:
                conn.execute("UPDATE purchase_receipts SET status='已检验', updated_at=? WHERE id=?", (now, item["receipt_id"]))
            open_lines = int(conn.execute("SELECT COUNT(*) AS total FROM purchase_order_items WHERE purchase_order_id=? AND status NOT IN ('已完成','已取消')", (item["purchase_order_id"],)).fetchone()["total"])
            order_status = "已完成" if open_lines == 0 else "部分到货"
            conn.execute("UPDATE purchase_orders SET status=?, updated_at=? WHERE id=?", (order_status, now, item["purchase_order_id"]))
            self.requirements._reallocate_material(conn, int(item["material_id"]), now)
            self.sync_demands(conn)
        return self.get_receipt(int(item["receipt_id"]))
