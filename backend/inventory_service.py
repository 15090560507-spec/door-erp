"""Transactional business rules for factory-wide inventory."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from inventory_database import InventoryDatabase, inventory_now


EPSILON = 1e-9


class InventoryService:
    def __init__(self, db: InventoryDatabase):
        self.db = db

    def create_material(
        self,
        *,
        code: str,
        name: str,
        category: str,
        specification: str,
        unit: str,
        material_type: str,
        default_warehouse_id: Optional[int] = None,
        default_location_id: Optional[int] = None,
        default_supplier: str = "",
        minimum_stock: float = 0,
        brand: str = "",
        purchase_unit: str = "",
        purchase_conversion: float = 1,
        standard_sale_price: float = 0,
        reference_purchase_price: float = 0,
        safety_stock: float = 0,
        can_sell: bool = False,
        can_purchase: bool = True,
        manage_stock: bool = True,
        can_subcontract: bool = False,
        remark: str = "",
    ) -> Dict[str, Any]:
        code = code.strip()
        name = name.strip()
        unit = unit.strip()
        if not code or not name or not unit or not material_type.strip():
            raise ValueError("物料编码、名称、单位和类型不能为空")
        if minimum_stock < 0:
            raise ValueError("最低库存不能小于零")
        now = inventory_now()
        with self.db.transaction() as conn:
            if default_location_id is not None:
                location = conn.execute(
                    "SELECT warehouse_id FROM inventory_locations WHERE id=?",
                    (default_location_id,),
                ).fetchone()
                if not location:
                    raise LookupError("默认库位不存在")
                if default_warehouse_id is not None and int(location["warehouse_id"]) != default_warehouse_id:
                    raise ValueError("默认库位不属于所选仓库")
            cursor = conn.execute(
                """INSERT INTO inventory_materials(
                       code, name, category, specification, unit, material_type,
                       default_warehouse_id, default_location_id, default_supplier,
                       minimum_stock, brand, purchase_unit, purchase_conversion,
                       standard_sale_price, reference_purchase_price, safety_stock,
                       can_sell, can_purchase, manage_stock, can_subcontract,
                       remark, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    code,
                    name,
                    category.strip(),
                    specification.strip(),
                    unit,
                    material_type.strip(),
                    default_warehouse_id,
                    default_location_id,
                    default_supplier.strip(),
                    minimum_stock,
                    brand.strip(),
                    purchase_unit.strip(),
                    purchase_conversion,
                    standard_sale_price,
                    reference_purchase_price,
                    safety_stock,
                    int(can_sell),
                    int(can_purchase),
                    int(manage_stock),
                    int(can_subcontract),
                    remark,
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM inventory_materials WHERE id=?", (cursor.lastrowid,)).fetchone()
            return dict(row)

    def update_material(self, material_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        code = str(payload.get("code") or "").strip()
        name = str(payload.get("name") or "").strip()
        unit = str(payload.get("unit") or "").strip()
        material_type = str(payload.get("material_type") or "").strip()
        if not code or not name or not unit or not material_type:
            raise ValueError("物料编码、名称、单位和类型不能为空")
        minimum_stock = float(payload.get("minimum_stock") or 0)
        if minimum_stock < 0:
            raise ValueError("最低库存不能小于零")
        now = inventory_now()
        with self.db.transaction() as conn:
            current = conn.execute("SELECT * FROM inventory_materials WHERE id=?", (material_id,)).fetchone()
            if not current:
                raise LookupError("物料不存在")
            balance = conn.execute(
                "SELECT COALESCE(SUM(ABS(on_hand)), 0) AS quantity FROM inventory_balances WHERE material_id=?",
                (material_id,),
            ).fetchone()
            if float(balance["quantity"] or 0) > EPSILON and unit != str(current["unit"]):
                raise RuntimeError("已有库存流水的物料不能修改单位")
            conn.execute(
                """UPDATE inventory_materials SET
                       code=?, name=?, category=?, specification=?, unit=?, material_type=?,
                       default_warehouse_id=?, default_location_id=?, default_supplier=?,
                       minimum_stock=?, brand=?, purchase_unit=?, purchase_conversion=?,
                       standard_sale_price=?, reference_purchase_price=?, safety_stock=?,
                       can_sell=?, can_purchase=?, manage_stock=?, can_subcontract=?,
                       is_active=?, remark=?, updated_at=?
                   WHERE id=?""",
                (
                    code,
                    name,
                    str(payload.get("category") or "").strip(),
                    str(payload.get("specification") or "").strip(),
                    unit,
                    material_type,
                    payload.get("default_warehouse_id"),
                    payload.get("default_location_id"),
                    str(payload.get("default_supplier") or "").strip(),
                    minimum_stock,
                    str(payload.get("brand") or "").strip(),
                    str(payload.get("purchase_unit") or "").strip(),
                    float(payload.get("purchase_conversion") or 1),
                    float(payload.get("standard_sale_price") or 0),
                    float(payload.get("reference_purchase_price") or 0),
                    float(payload.get("safety_stock") or 0),
                    int(bool(payload.get("can_sell", False))),
                    int(bool(payload.get("can_purchase", True))),
                    int(bool(payload.get("manage_stock", True))),
                    int(bool(payload.get("can_subcontract", False))),
                    int(bool(payload.get("is_active", True))),
                    str(payload.get("remark") or ""),
                    now,
                    material_id,
                ),
            )
            row = conn.execute("SELECT * FROM inventory_materials WHERE id=?", (material_id,)).fetchone()
            return dict(row)

    def list_materials(
        self,
        *,
        q: str = "",
        category: str = "",
        material_type: str = "",
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        where: List[str] = []
        params: List[Any] = []
        if active_only:
            where.append("m.is_active=1")
        if category:
            where.append("m.category=?")
            params.append(category)
        if material_type:
            where.append("m.material_type=?")
            params.append(material_type)
        if q:
            term = f"%{q.strip()}%"
            where.append("(m.code LIKE ? OR m.name LIKE ? OR m.specification LIKE ?)")
            params.extend([term, term, term])
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        return self.db.fetch_all(
            f"""SELECT m.*, w.name AS default_warehouse_name, l.name AS default_location_name
                FROM inventory_materials m
                LEFT JOIN inventory_warehouses w ON w.id=m.default_warehouse_id
                LEFT JOIN inventory_locations l ON l.id=m.default_location_id
                {clause}
                ORDER BY m.category, m.code, m.id""",
            params,
        )

    def list_suppliers(self, q: str = "", active_only: bool = True) -> List[Dict[str, Any]]:
        where: List[str] = []
        params: List[Any] = []
        if active_only:
            where.append("s.is_active=1")
        if q:
            keyword = f"%{q.strip()}%"
            where.append("(s.code LIKE ? OR s.name LIKE ? OR s.short_name LIKE ? OR s.phone LIKE ?)")
            params.extend([keyword, keyword, keyword, keyword])
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        return self.db.fetch_all(
            f"""SELECT s.*, COUNT(si.id) AS item_count
                FROM inventory_suppliers s
                LEFT JOIN inventory_supplier_items si ON si.supplier_id=s.id AND si.is_active=1
                {clause}
                GROUP BY s.id ORDER BY s.is_active DESC, s.name, s.id""",
            params,
        )

    def create_supplier(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        code = str(payload.get("code") or "").strip()
        name = str(payload.get("name") or "").strip()
        if not code or not name:
            raise ValueError("供应商编码和名称不能为空")
        now = inventory_now()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO inventory_suppliers(
                       code, name, short_name, contact_name, phone, address, invoice_title,
                       tax_no, default_tax_rate, settlement_method, payment_days,
                       default_lead_days, supply_category, remark, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    code, name, str(payload.get("short_name") or "").strip(),
                    str(payload.get("contact_name") or "").strip(), str(payload.get("phone") or "").strip(),
                    str(payload.get("address") or "").strip(), str(payload.get("invoice_title") or "").strip(),
                    str(payload.get("tax_no") or "").strip(), float(payload.get("default_tax_rate") or 0),
                    str(payload.get("settlement_method") or "").strip(), int(payload.get("payment_days") or 0),
                    int(payload.get("default_lead_days") or 0), str(payload.get("supply_category") or "").strip(),
                    str(payload.get("remark") or ""), now, now,
                ),
            )
            return dict(conn.execute("SELECT * FROM inventory_suppliers WHERE id=?", (cursor.lastrowid,)).fetchone())

    def update_supplier(self, supplier_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        code = str(payload.get("code") or "").strip()
        name = str(payload.get("name") or "").strip()
        if not code or not name:
            raise ValueError("供应商编码和名称不能为空")
        now = inventory_now()
        with self.db.transaction() as conn:
            if not conn.execute("SELECT id FROM inventory_suppliers WHERE id=?", (supplier_id,)).fetchone():
                raise LookupError("供应商不存在")
            conn.execute(
                """UPDATE inventory_suppliers SET code=?, name=?, short_name=?, contact_name=?,
                       phone=?, address=?, invoice_title=?, tax_no=?, default_tax_rate=?,
                       settlement_method=?, payment_days=?, default_lead_days=?, supply_category=?,
                       is_active=?, remark=?, updated_at=? WHERE id=?""",
                (
                    code, name, str(payload.get("short_name") or "").strip(),
                    str(payload.get("contact_name") or "").strip(), str(payload.get("phone") or "").strip(),
                    str(payload.get("address") or "").strip(), str(payload.get("invoice_title") or "").strip(),
                    str(payload.get("tax_no") or "").strip(), float(payload.get("default_tax_rate") or 0),
                    str(payload.get("settlement_method") or "").strip(), int(payload.get("payment_days") or 0),
                    int(payload.get("default_lead_days") or 0), str(payload.get("supply_category") or "").strip(),
                    int(bool(payload.get("is_active", True))), str(payload.get("remark") or ""), now, supplier_id,
                ),
            )
            return dict(conn.execute("SELECT * FROM inventory_suppliers WHERE id=?", (supplier_id,)).fetchone())

    def list_supplier_items(self, supplier_id: Optional[int] = None, material_id: Optional[int] = None) -> List[Dict[str, Any]]:
        where = ["si.is_active=1"]
        params: List[Any] = []
        if supplier_id is not None:
            where.append("si.supplier_id=?")
            params.append(supplier_id)
        if material_id is not None:
            where.append("si.material_id=?")
            params.append(material_id)
        return self.db.fetch_all(
            f"""SELECT si.*, s.code AS supplier_code, s.name AS supplier_name,
                       m.code AS material_code, m.name AS material_name, m.specification AS material_specification
                FROM inventory_supplier_items si
                JOIN inventory_suppliers s ON s.id=si.supplier_id
                JOIN inventory_materials m ON m.id=si.material_id
                WHERE {' AND '.join(where)}
                ORDER BY si.is_preferred DESC, s.name, m.name""",
            params,
        )

    def save_supplier_item(self, payload: Dict[str, Any], operator_uid: str, supplier_item_id: Optional[int] = None) -> Dict[str, Any]:
        supplier_id = int(payload.get("supplier_id") or 0)
        material_id = int(payload.get("material_id") or 0)
        if not supplier_id or not material_id:
            raise ValueError("供应商和商品不能为空")
        now = inventory_now()
        with self.db.transaction() as conn:
            if not conn.execute("SELECT id FROM inventory_suppliers WHERE id=? AND is_active=1", (supplier_id,)).fetchone():
                raise LookupError("供应商不存在或已停用")
            material = conn.execute("SELECT * FROM inventory_materials WHERE id=? AND is_active=1", (material_id,)).fetchone()
            if not material:
                raise LookupError("物料或商品不存在或已停用")
            if bool(payload.get("is_preferred")):
                conn.execute("UPDATE inventory_supplier_items SET is_preferred=0, updated_at=? WHERE material_id=?", (now, material_id))
            values = (
                supplier_id, material_id, str(payload.get("supplier_item_code") or "").strip(),
                str(payload.get("supplier_item_name") or "").strip(), str(payload.get("purchase_specification") or "").strip(),
                str(payload.get("purchase_unit") or material["unit"]).strip(), float(payload.get("conversion_rate") or 1),
                float(payload.get("tax_inclusive_price") or 0), float(payload.get("tax_rate") or 0),
                float(payload.get("minimum_order_quantity") or 0), int(payload.get("lead_days") or 0),
                int(bool(payload.get("is_preferred"))), int(bool(payload.get("is_active", True))),
                str(payload.get("remark") or ""), now,
            )
            old_price = None
            if supplier_item_id is None:
                cursor = conn.execute(
                    """INSERT INTO inventory_supplier_items(
                           supplier_id, material_id, supplier_item_code, supplier_item_name,
                           purchase_specification, purchase_unit, conversion_rate, tax_inclusive_price,
                           tax_rate, minimum_order_quantity, lead_days, is_preferred, is_active,
                           remark, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (*values, now),
                )
                supplier_item_id = int(cursor.lastrowid)
            else:
                current = conn.execute("SELECT * FROM inventory_supplier_items WHERE id=?", (supplier_item_id,)).fetchone()
                if not current:
                    raise LookupError("供应商供货关系不存在")
                old_price = float(current["tax_inclusive_price"] or 0)
                conn.execute(
                    """UPDATE inventory_supplier_items SET supplier_id=?, material_id=?, supplier_item_code=?,
                           supplier_item_name=?, purchase_specification=?, purchase_unit=?, conversion_rate=?,
                           tax_inclusive_price=?, tax_rate=?, minimum_order_quantity=?, lead_days=?,
                           is_preferred=?, is_active=?, remark=?, updated_at=? WHERE id=?""",
                    (*values, supplier_item_id),
                )
            new_price = float(payload.get("tax_inclusive_price") or 0)
            if old_price is None or abs(old_price - new_price) > EPSILON:
                conn.execute(
                    """INSERT INTO inventory_supplier_item_prices(
                           supplier_item_id, tax_inclusive_price, tax_rate, effective_date, operator_uid, created_at
                       ) VALUES (?, ?, ?, ?, ?, ?)""",
                    (supplier_item_id, new_price, float(payload.get("tax_rate") or 0), now[:10], operator_uid, now),
                )
            row = conn.execute("SELECT * FROM inventory_supplier_items WHERE id=?", (supplier_item_id,)).fetchone()
            return dict(row)

    def create_warehouse(self, code: str, name: str, warehouse_type: str = "", remark: str = "") -> Dict[str, Any]:
        code = code.strip()
        name = name.strip()
        if not code or not name:
            raise ValueError("仓库编码和名称不能为空")
        now = inventory_now()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO inventory_warehouses(
                       code, name, warehouse_type, remark, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (code, name, warehouse_type.strip(), remark, now, now),
            )
            row = conn.execute("SELECT * FROM inventory_warehouses WHERE id=?", (cursor.lastrowid,)).fetchone()
            return dict(row)

    def create_location(self, warehouse_id: int, code: str, name: str, remark: str = "") -> Dict[str, Any]:
        code = code.strip()
        name = name.strip()
        if not code or not name:
            raise ValueError("库位编码和名称不能为空")
        now = inventory_now()
        with self.db.transaction() as conn:
            warehouse = conn.execute(
                "SELECT id FROM inventory_warehouses WHERE id=? AND is_active=1",
                (warehouse_id,),
            ).fetchone()
            if not warehouse:
                raise LookupError("仓库不存在或已停用")
            cursor = conn.execute(
                """INSERT INTO inventory_locations(
                       warehouse_id, code, name, remark, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (warehouse_id, code, name, remark, now, now),
            )
            row = conn.execute("SELECT * FROM inventory_locations WHERE id=?", (cursor.lastrowid,)).fetchone()
            return dict(row)

    def list_warehouses(self) -> List[Dict[str, Any]]:
        warehouses = self.db.list_warehouses()
        for warehouse in warehouses:
            warehouse["locations"] = self.db.fetch_all(
                "SELECT * FROM inventory_locations WHERE warehouse_id=? ORDER BY code, id",
                (warehouse["id"],),
            )
        return warehouses

    def create_adjustment(self, items: List[Dict[str, Any]], remark: str, created_by: str) -> Dict[str, Any]:
        if not items:
            raise ValueError("盘点调整至少需要一条明细")
        now = inventory_now()
        with self.db.transaction() as conn:
            next_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM inventory_documents").fetchone()["next_id"])
            document_no = f"PD{now[:10].replace('-', '')}{next_id:04d}"
            cursor = conn.execute(
                """INSERT INTO inventory_documents(
                       document_no, document_type, status, remark, created_by, created_at, updated_at
                   ) VALUES (?, '盘点调整', '草稿', ?, ?, ?, ?)""",
                (document_no, remark, created_by, now, now),
            )
            document_id = int(cursor.lastrowid)
            for item in items:
                quantity = float(item.get("quantity") or 0)
                if abs(quantity) <= EPSILON:
                    raise ValueError("盘点调整数量不能为零")
                self._validate_stock_keys(
                    conn,
                    int(item["material_id"]),
                    int(item["warehouse_id"]),
                    int(item["location_id"]),
                    str(item.get("unit") or ""),
                )
                conn.execute(
                    """INSERT INTO inventory_document_items(
                           document_id, material_id, warehouse_id, location_id, quantity, unit, remark
                       ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        document_id,
                        item["material_id"],
                        item["warehouse_id"],
                        item["location_id"],
                        quantity,
                        item["unit"],
                        str(item.get("remark") or ""),
                    ),
                )
        return self.get_adjustment(document_id)

    def get_adjustment(self, document_id: int) -> Dict[str, Any]:
        document = self.db.fetch_one("SELECT * FROM inventory_documents WHERE id=?", (document_id,))
        if not document:
            raise LookupError("盘点调整单不存在")
        document["items"] = self.db.fetch_all(
            """SELECT i.*, m.code AS material_code, m.name AS material_name,
                      w.name AS warehouse_name, l.name AS location_name
               FROM inventory_document_items i
               JOIN inventory_materials m ON m.id=i.material_id
               JOIN inventory_warehouses w ON w.id=i.warehouse_id
               JOIN inventory_locations l ON l.id=i.location_id
               WHERE i.document_id=? ORDER BY i.id""",
            (document_id,),
        )
        return document

    def confirm_adjustment(self, document_id: int, confirmed_by: str) -> Dict[str, Any]:
        now = inventory_now()
        with self.db.transaction() as conn:
            document = conn.execute("SELECT * FROM inventory_documents WHERE id=?", (document_id,)).fetchone()
            if not document:
                raise LookupError("盘点调整单不存在")
            if document["document_type"] != "盘点调整":
                raise ValueError("单据类型不是盘点调整")
            if document["status"] != "草稿":
                raise RuntimeError("盘点调整单已经确认，不能重复入账")
            items = conn.execute(
                "SELECT * FROM inventory_document_items WHERE document_id=? ORDER BY id",
                (document_id,),
            ).fetchall()
            for index, item in enumerate(items, start=1):
                self.post_transaction(
                    material_id=int(item["material_id"]),
                    warehouse_id=int(item["warehouse_id"]),
                    location_id=int(item["location_id"]),
                    transaction_type="盘盈" if float(item["quantity"]) > 0 else "盘亏",
                    quantity=float(item["quantity"]),
                    unit=str(item["unit"]),
                    source_type="inventory_adjustment",
                    source_id=str(document["document_no"]),
                    source_line=str(index),
                    operator_uid=confirmed_by,
                    remark=str(item["remark"] or document["remark"]),
                    conn=conn,
                )
            conn.execute(
                """UPDATE inventory_documents SET
                       status='已确认', confirmed_by=?, confirmed_at=?, updated_at=? WHERE id=?""",
                (confirmed_by, now, now, document_id),
            )
        return self.get_adjustment(document_id)

    @staticmethod
    def _validate_stock_keys(
        conn: sqlite3.Connection,
        material_id: int,
        warehouse_id: int,
        location_id: int,
        unit: str,
    ) -> None:
        material = conn.execute("SELECT unit FROM inventory_materials WHERE id=? AND is_active=1", (material_id,)).fetchone()
        location = conn.execute(
            "SELECT warehouse_id FROM inventory_locations WHERE id=? AND is_active=1",
            (location_id,),
        ).fetchone()
        if not material:
            raise LookupError("物料不存在或已停用")
        if str(material["unit"]) != unit:
            raise ValueError("明细单位必须与物料档案一致")
        if not location or int(location["warehouse_id"]) != warehouse_id:
            raise ValueError("库位不存在或不属于所选仓库")

    def post_transaction(
        self,
        *,
        material_id: int,
        warehouse_id: int,
        location_id: int,
        transaction_type: str,
        quantity: float,
        unit: str,
        source_type: str,
        source_id: str,
        source_line: str = "",
        order_id: Optional[int] = None,
        door_unit_id: Optional[int] = None,
        production_no: str = "",
        operator_uid: str = "",
        remark: str = "",
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        if abs(quantity) <= EPSILON:
            raise ValueError("库存流水数量不能为零")
        if not transaction_type.strip() or not source_type.strip() or not source_id.strip():
            raise ValueError("流水类型和来源单据不能为空")
        now = inventory_now()
        with self.db.transaction(conn) as tx:
            self._validate_stock_keys(tx, material_id, warehouse_id, location_id, unit)
            current = tx.execute(
                """SELECT on_hand, reserved FROM inventory_balances
                   WHERE material_id=? AND warehouse_id=? AND location_id=?""",
                (material_id, warehouse_id, location_id),
            ).fetchone()
            on_hand = float(current["on_hand"] if current else 0)
            reserved = float(current["reserved"] if current else 0)
            next_on_hand = on_hand + float(quantity)
            if next_on_hand < -EPSILON:
                raise ValueError(f"库存不足：现存 {on_hand:g} {unit}，本次出库 {abs(quantity):g} {unit}")
            cursor = tx.execute(
                """INSERT INTO inventory_transactions(
                       material_id, warehouse_id, location_id, transaction_type,
                       quantity, unit, source_type, source_id, source_line,
                       order_id, door_unit_id, production_no, operator_uid, remark, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    material_id,
                    warehouse_id,
                    location_id,
                    transaction_type.strip(),
                    quantity,
                    unit,
                    source_type.strip(),
                    source_id.strip(),
                    source_line,
                    order_id,
                    door_unit_id,
                    production_no,
                    operator_uid,
                    remark,
                    now,
                ),
            )
            tx.execute(
                """INSERT INTO inventory_balances(
                       material_id, warehouse_id, location_id, on_hand, reserved, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(material_id, warehouse_id, location_id)
                   DO UPDATE SET on_hand=excluded.on_hand, updated_at=excluded.updated_at""",
                (material_id, warehouse_id, location_id, next_on_hand, reserved, now),
            )
            row = tx.execute("SELECT * FROM inventory_transactions WHERE id=?", (cursor.lastrowid,)).fetchone()
            return dict(row)

    def get_balance(self, material_id: int, warehouse_id: int, location_id: int) -> Dict[str, Any]:
        row = self.db.fetch_one(
            """SELECT b.*, m.code AS material_code, m.name AS material_name,
                      m.specification, m.unit, w.code AS warehouse_code,
                      w.name AS warehouse_name, l.code AS location_code, l.name AS location_name
               FROM inventory_balances b
               JOIN inventory_materials m ON m.id=b.material_id
               JOIN inventory_warehouses w ON w.id=b.warehouse_id
               JOIN inventory_locations l ON l.id=b.location_id
               WHERE b.material_id=? AND b.warehouse_id=? AND b.location_id=?""",
            (material_id, warehouse_id, location_id),
        )
        if not row:
            return {
                "material_id": material_id,
                "warehouse_id": warehouse_id,
                "location_id": location_id,
                "on_hand": 0.0,
                "reserved": 0.0,
                "available": 0.0,
            }
        row["on_hand"] = float(row["on_hand"] or 0)
        row["reserved"] = float(row["reserved"] or 0)
        row["available"] = row["on_hand"] - row["reserved"]
        return row

    def list_balances(
        self,
        *,
        q: str = "",
        warehouse_id: Optional[int] = None,
        low_stock_only: bool = False,
    ) -> List[Dict[str, Any]]:
        where: List[str] = ["m.is_active=1"]
        params: List[Any] = []
        if warehouse_id is not None:
            where.append("b.warehouse_id=?")
            params.append(warehouse_id)
        if q:
            term = f"%{q.strip()}%"
            where.append("(m.code LIKE ? OR m.name LIKE ? OR m.specification LIKE ? OR l.code LIKE ?)")
            params.extend([term, term, term, term])
        if low_stock_only:
            where.append("(b.on_hand-b.reserved) < m.minimum_stock")
        rows = self.db.fetch_all(
            f"""SELECT b.*, (b.on_hand-b.reserved) AS available,
                       m.code AS material_code, m.name AS material_name, m.category,
                       m.specification, m.unit, m.material_type, m.minimum_stock,
                       w.code AS warehouse_code, w.name AS warehouse_name,
                       l.code AS location_code, l.name AS location_name
                FROM inventory_balances b
                JOIN inventory_materials m ON m.id=b.material_id
                JOIN inventory_warehouses w ON w.id=b.warehouse_id
                JOIN inventory_locations l ON l.id=b.location_id
                WHERE {' AND '.join(where)}
                ORDER BY m.category, m.code, w.code, l.code""",
            params,
        )
        in_transit_rows = self.db.fetch_all(
            """SELECT i.material_id,
                      COALESCE(SUM(MAX(0, i.ordered_quantity-i.received_quantity-i.rejected_quantity-i.cancelled_quantity)), 0) AS quantity
               FROM purchase_order_items i
               JOIN purchase_orders o ON o.id=i.purchase_order_id
               WHERE o.status IN ('已下单', '部分到货')
                 AND i.status NOT IN ('已完成', '已取消')
               GROUP BY i.material_id"""
        )
        in_transit_by_material = {int(item["material_id"]): float(item["quantity"] or 0) for item in in_transit_rows}
        for row in rows:
            row["on_hand"] = float(row["on_hand"] or 0)
            row["reserved"] = float(row["reserved"] or 0)
            row["available"] = float(row["available"] or 0)
            row["purchase_in_transit"] = in_transit_by_material.get(int(row["material_id"]), 0.0)
            row["subcontract_in_transit"] = row["on_hand"] if row["warehouse_code"] == "SUBCONTRACT" else 0.0
        return rows

    def list_transactions(self, material_id: Optional[int] = None, limit: int = 200) -> List[Dict[str, Any]]:
        params: List[Any] = []
        where = ""
        if material_id is not None:
            where = "WHERE t.material_id=?"
            params.append(material_id)
        params.append(max(1, min(limit, 1000)))
        return self.db.fetch_all(
            f"""SELECT t.*, m.code AS material_code, m.name AS material_name,
                       w.name AS warehouse_name, l.name AS location_name
                FROM inventory_transactions t
                JOIN inventory_materials m ON m.id=t.material_id
                JOIN inventory_warehouses w ON w.id=t.warehouse_id
                JOIN inventory_locations l ON l.id=t.location_id
                {where}
                ORDER BY t.id DESC LIMIT ?""",
            params,
        )
