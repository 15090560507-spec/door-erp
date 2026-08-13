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
                       minimum_stock, remark, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    remark,
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM inventory_materials WHERE id=?", (cursor.lastrowid,)).fetchone()
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
            material = tx.execute("SELECT unit FROM inventory_materials WHERE id=? AND is_active=1", (material_id,)).fetchone()
            location = tx.execute(
                "SELECT warehouse_id FROM inventory_locations WHERE id=? AND is_active=1",
                (location_id,),
            ).fetchone()
            if not material:
                raise LookupError("物料不存在或已停用")
            if not location or int(location["warehouse_id"]) != warehouse_id:
                raise ValueError("库位不存在或不属于所选仓库")
            if str(material["unit"]) != unit:
                raise ValueError("流水单位必须与物料档案一致")
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
