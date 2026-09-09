"""Material demand and stock reservation rules for confirmed technical packages."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from inventory_database import InventoryDatabase, inventory_now


EPSILON = 1e-9


class RequirementService:
    def __init__(self, db: InventoryDatabase):
        self.db = db

    @staticmethod
    def _requirement_no(conn: sqlite3.Connection, now: str) -> str:
        prefix = f"XQ{now[:10].replace('-', '')}"
        row = conn.execute(
            "SELECT requirement_no FROM material_requirements WHERE requirement_no LIKE ? ORDER BY requirement_no DESC LIMIT 1",
            (f"{prefix}%",),
        ).fetchone()
        sequence = int(str(row["requirement_no"])[-4:]) + 1 if row else 1
        return f"{prefix}{sequence:04d}"

    def create_for_package(
        self,
        *,
        conn: sqlite3.Connection,
        door_id: int,
        package_id: int,
        created_by: str,
    ) -> Dict[str, Any]:
        existing = conn.execute(
            "SELECT * FROM material_requirements WHERE technical_package_id=?",
            (package_id,),
        ).fetchone()
        if existing:
            return dict(existing)

        package = conn.execute(
            "SELECT id, version FROM fulfillment_technical_packages WHERE id=? AND door_unit_id=?",
            (package_id, door_id),
        ).fetchone()
        door = conn.execute(
            """SELECT d.id, d.order_id, d.production_no, d.due_date, o.due_date AS order_due_date
               FROM fulfillment_door_units d JOIN fulfillment_orders o ON o.id=d.order_id
               WHERE d.id=?""",
            (door_id,),
        ).fetchone()
        if not package or not door:
            raise LookupError("技术包或门樘生产单不存在")

        all_components = conn.execute(
            """SELECT c.*, m.code AS material_code, m.name AS material_name,
                      m.specification AS material_specification, m.unit AS material_unit,
                      m.is_active, m.default_warehouse_id, m.default_location_id
               FROM fulfillment_components c
               LEFT JOIN inventory_materials m ON m.id=c.material_id
               WHERE c.technical_package_id=? ORDER BY c.sequence_no, c.id""",
            (package_id,),
        ).fetchall()
        components = [row for row in all_components if str(row["match_status"] or "") != "无需物料"]
        missing = [str(row["name"]) for row in components if row["material_id"] is None]
        invalid = [str(row["name"]) for row in components if row["material_id"] is not None and row["material_code"] is None]
        inactive = [str(row["name"]) for row in components if row["material_code"] is not None and not bool(row["is_active"])]
        if missing:
            raise ValueError(f"以下构件尚未关联物料档案：{'、'.join(missing)}")
        if invalid:
            raise ValueError(f"以下构件关联的物料不存在：{'、'.join(invalid)}")
        if inactive:
            raise ValueError(f"以下构件关联的物料已停用：{'、'.join(inactive)}")
        unit_mismatch = [str(row["name"]) for row in components if str(row["unit"]) != str(row["material_unit"])]
        if unit_mismatch:
            raise ValueError(f"以下构件单位与物料档案不一致：{'、'.join(unit_mismatch)}")

        now = inventory_now()
        due_date = str(door["due_date"] or door["order_due_date"] or "")
        requirement_no = self._requirement_no(conn, now)
        cursor = conn.execute(
            """INSERT INTO material_requirements(
                   requirement_no, order_id, door_unit_id, technical_package_id,
                   production_no, version, due_date, status, created_by,
                   confirmed_at, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, '有缺口', ?, ?, ?, ?)""",
            (
                requirement_no,
                door["order_id"],
                door_id,
                package_id,
                door["production_no"],
                package["version"],
                due_date,
                created_by,
                now,
                now,
                now,
            ),
        )
        requirement_id = int(cursor.lastrowid)
        affected_material_ids: set[int] = set()
        for sequence, component in enumerate(components, start=1):
            required = float(component["planned_quantity"] or component["quantity"] or 0)
            item_cursor = conn.execute(
                """INSERT INTO material_requirement_items(
                       requirement_id, component_id, bom_item_id, technical_package_id,
                       bom_version, door_unit_id, production_no, material_id, material_code,
                       material_name, specification, required_quantity, planned_quantity, unit,
                       acquisition_method,
                       shortage_quantity, sequence_no, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    requirement_id,
                    component["id"],
                    component["id"],
                    package_id,
                    package["version"],
                    door_id,
                    door["production_no"],
                    component["material_id"],
                    component["material_code"],
                    component["material_name"],
                    component["material_specification"] or component["specification"],
                    required,
                    required,
                    component["material_unit"],
                    component["acquisition_method"],
                    required,
                    sequence,
                    now,
                    now,
                ),
            )
            affected_material_ids.add(int(component["material_id"]))
            conn.execute(
                """INSERT INTO material_component_links(
                       component_name, component_category, component_specification,
                       material_id, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(component_name, component_category, component_specification)
                   DO UPDATE SET material_id=excluded.material_id, updated_at=excluded.updated_at""",
                (
                    component["name"],
                    component["category"],
                    component["specification"],
                    component["material_id"],
                    now,
                    now,
                ),
            )
        for material_id in affected_material_ids:
            self._reallocate_material(conn, material_id, now)
        return dict(conn.execute("SELECT * FROM material_requirements WHERE id=?", (requirement_id,)).fetchone())

    def _reallocate_material(self, conn: sqlite3.Connection, material_id: int, now: str) -> None:
        active = conn.execute(
            """SELECT r.* FROM inventory_reservations r
               JOIN material_requirement_items i ON i.id=r.requirement_item_id
               JOIN material_requirements q ON q.id=i.requirement_id
               WHERE r.material_id=? AND r.status='有效' AND q.status!='已冻结'""",
            (material_id,),
        ).fetchall()
        for reservation in active:
            releasable = max(0.0, float(reservation["quantity"] or 0) - float(reservation["issued_quantity"] or 0))
            if releasable > EPSILON:
                conn.execute(
                    """UPDATE inventory_balances SET reserved=MAX(0, reserved-?), updated_at=?
                       WHERE material_id=? AND warehouse_id=? AND location_id=?""",
                    (releasable, now, material_id, reservation["warehouse_id"], reservation["location_id"]),
                )
            conn.execute("UPDATE inventory_reservations SET status='已重排', updated_at=? WHERE id=?", (now, reservation["id"]))

        items = conn.execute(
            """SELECT i.*, q.due_date, q.production_no,
                      m.default_warehouse_id, m.default_location_id
               FROM material_requirement_items i
               JOIN material_requirements q ON q.id=i.requirement_id
               JOIN inventory_materials m ON m.id=i.material_id
               WHERE i.material_id=? AND q.status!='已冻结'
               ORDER BY CASE WHEN q.due_date='' THEN 1 ELSE 0 END,
                        q.due_date, q.created_at, q.production_no, i.sequence_no, i.id""",
            (material_id,),
        ).fetchall()
        affected_requirement_ids: set[int] = set()
        for item in items:
            issued = max(0.0, float(item["issued_quantity"] or 0) - float(item["returned_quantity"] or 0))
            required_to_reserve = max(0.0, float(item["required_quantity"] or 0) - issued)
            reserved = self._allocate_item(
                conn=conn,
                item_id=int(item["id"]),
                material_id=material_id,
                required=required_to_reserve,
                due_date=str(item["due_date"] or ""),
                production_no=str(item["production_no"] or ""),
                preferred_warehouse_id=item["default_warehouse_id"],
                preferred_location_id=item["default_location_id"],
                now=now,
            )
            purchased_in_transit = max(
                0.0,
                float(item["purchased_quantity"] or 0) - float(item["received_quantity"] or 0),
            )
            shortage = max(0.0, float(item["required_quantity"] or 0) - issued - reserved - purchased_in_transit)
            if shortage <= EPSILON:
                status = "采购覆盖" if purchased_in_transit > EPSILON else "已预留"
            else:
                status = "部分缺料" if reserved > EPSILON or purchased_in_transit > EPSILON else "全部缺料"
            conn.execute(
                """UPDATE material_requirement_items
                   SET reserved_quantity=?, shortage_quantity=?, status=?, updated_at=? WHERE id=?""",
                (reserved, shortage, status, now, item["id"]),
            )
            affected_requirement_ids.add(int(item["requirement_id"]))
        for requirement_id in affected_requirement_ids:
            shortage = float(conn.execute(
                "SELECT COALESCE(SUM(shortage_quantity), 0) AS total FROM material_requirement_items WHERE requirement_id=?",
                (requirement_id,),
            ).fetchone()["total"] or 0)
            in_transit = float(conn.execute(
                """SELECT COALESCE(SUM(MAX(0, purchased_quantity-received_quantity)), 0) AS total
                   FROM material_requirement_items WHERE requirement_id=?""",
                (requirement_id,),
            ).fetchone()["total"] or 0)
            conn.execute(
                "UPDATE material_requirements SET status=?, updated_at=? WHERE id=?",
                ("有缺口" if shortage > EPSILON else ("采购覆盖" if in_transit > EPSILON else "已预留"), now, requirement_id),
            )

    @staticmethod
    def _allocate_item(
        *,
        conn: sqlite3.Connection,
        item_id: int,
        material_id: int,
        required: float,
        due_date: str,
        production_no: str,
        preferred_warehouse_id: Any,
        preferred_location_id: Any,
        now: str,
    ) -> float:
        remaining = required
        reserved = 0.0
        rows = conn.execute(
            """SELECT b.material_id, b.warehouse_id, b.location_id,
                      b.on_hand, b.reserved, (b.on_hand-b.reserved) AS available
               FROM inventory_balances b
               JOIN inventory_warehouses w ON w.id=b.warehouse_id AND w.is_active=1
               JOIN inventory_locations l ON l.id=b.location_id AND l.is_active=1
               WHERE b.material_id=? AND (b.on_hand-b.reserved)>?
               ORDER BY CASE WHEN b.location_id=? THEN 0
                             WHEN b.warehouse_id=? THEN 1 ELSE 2 END,
                        b.warehouse_id, b.location_id""",
            (material_id, EPSILON, preferred_location_id or -1, preferred_warehouse_id or -1),
        ).fetchall()
        for row in rows:
            if remaining <= EPSILON:
                break
            quantity = min(remaining, float(row["available"] or 0))
            if quantity <= EPSILON:
                continue
            conn.execute(
                """UPDATE inventory_balances SET reserved=reserved+?, updated_at=?
                   WHERE material_id=? AND warehouse_id=? AND location_id=?""",
                (quantity, now, material_id, row["warehouse_id"], row["location_id"]),
            )
            conn.execute(
                """INSERT INTO inventory_reservations(
                       requirement_item_id, material_id, warehouse_id, location_id,
                       quantity, due_date, production_no, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_id, material_id, row["warehouse_id"], row["location_id"], quantity, due_date, production_no, now, now),
            )
            reserved += quantity
            remaining -= quantity
        return reserved

    def freeze_for_package(self, conn: sqlite3.Connection, package_id: int) -> Dict[str, Any] | None:
        requirement = conn.execute(
            "SELECT * FROM material_requirements WHERE technical_package_id=?",
            (package_id,),
        ).fetchone()
        if not requirement or requirement["status"] == "已冻结":
            return dict(requirement) if requirement else None
        now = inventory_now()
        reservations = conn.execute(
            """SELECT r.* FROM inventory_reservations r
               JOIN material_requirement_items i ON i.id=r.requirement_item_id
               WHERE i.requirement_id=? AND r.status='有效'""",
            (requirement["id"],),
        ).fetchall()
        affected_material_ids: set[int] = set()
        for reservation in reservations:
            affected_material_ids.add(int(reservation["material_id"]))
            releasable = max(0.0, float(reservation["quantity"] or 0) - float(reservation["issued_quantity"] or 0))
            if releasable > EPSILON:
                conn.execute(
                    """UPDATE inventory_balances
                       SET reserved=MAX(0, reserved-?), updated_at=?
                       WHERE material_id=? AND warehouse_id=? AND location_id=?""",
                    (releasable, now, reservation["material_id"], reservation["warehouse_id"], reservation["location_id"]),
                )
            conn.execute(
                "UPDATE inventory_reservations SET status='已释放', updated_at=? WHERE id=?",
                (now, reservation["id"]),
            )
        conn.execute(
            "UPDATE material_requirements SET status='已冻结', frozen_at=?, updated_at=? WHERE id=?",
            (now, now, requirement["id"]),
        )
        for material_id in affected_material_ids:
            self._reallocate_material(conn, material_id, now)
        return dict(conn.execute("SELECT * FROM material_requirements WHERE id=?", (requirement["id"],)).fetchone())

    def list_requirements(self, *, q: str = "", status: str = "") -> List[Dict[str, Any]]:
        where = ["1=1"]
        params: List[Any] = []
        if status:
            where.append("r.status=?")
            params.append(status)
        if q:
            term = f"%{q.strip()}%"
            where.append("(r.requirement_no LIKE ? OR r.production_no LIKE ? OR i.material_code LIKE ? OR i.material_name LIKE ?)")
            params.extend([term, term, term, term])
        return self.db.fetch_all(
            f"""SELECT r.*, COUNT(i.id) AS item_count,
                       COALESCE(SUM(CASE WHEN i.reserved_quantity > 0 THEN 1 ELSE 0 END), 0) AS reserved_item_count,
                       COALESCE(SUM(CASE WHEN i.shortage_quantity > 0 THEN 1 ELSE 0 END), 0) AS shortage_item_count,
                       COALESCE(SUM(i.required_quantity), 0) AS required_quantity,
                       COALESCE(SUM(i.reserved_quantity), 0) AS reserved_quantity,
                       COALESCE(SUM(i.shortage_quantity), 0) AS shortage_quantity
                FROM material_requirements r
                LEFT JOIN material_requirement_items i ON i.requirement_id=r.id
                WHERE {' AND '.join(where)}
                GROUP BY r.id ORDER BY CASE WHEN r.due_date='' THEN 1 ELSE 0 END,
                         r.due_date, r.created_at, r.production_no""",
            params,
        )

    def get_requirement(self, requirement_id: int) -> Dict[str, Any]:
        requirement = self.db.fetch_one(
            """SELECT r.*, COUNT(i.id) AS item_count,
                      COALESCE(SUM(CASE WHEN i.reserved_quantity > 0 THEN 1 ELSE 0 END), 0) AS reserved_item_count,
                      COALESCE(SUM(CASE WHEN i.shortage_quantity > 0 THEN 1 ELSE 0 END), 0) AS shortage_item_count,
                      COALESCE(SUM(i.required_quantity), 0) AS required_quantity,
                      COALESCE(SUM(i.reserved_quantity), 0) AS reserved_quantity,
                      COALESCE(SUM(i.shortage_quantity), 0) AS shortage_quantity
               FROM material_requirements r
               LEFT JOIN material_requirement_items i ON i.requirement_id=r.id
               WHERE r.id=? GROUP BY r.id""",
            (requirement_id,),
        )
        if not requirement:
            raise LookupError("物料需求单不存在")
        requirement["items"] = self.db.fetch_all(
            """SELECT i.* FROM material_requirement_items i
               WHERE i.requirement_id=? ORDER BY i.sequence_no, i.id""",
            (requirement_id,),
        )
        for item in requirement["items"]:
            item["reservations"] = self.db.fetch_all(
                """SELECT r.*, w.name AS warehouse_name, l.name AS location_name
                   FROM inventory_reservations r
                   JOIN inventory_warehouses w ON w.id=r.warehouse_id
                   JOIN inventory_locations l ON l.id=r.location_id
                   WHERE r.requirement_item_id=? ORDER BY r.id""",
                (item["id"],),
            )
        return requirement

    def reallocate_requirement(self, requirement_id: int) -> Dict[str, Any]:
        now = inventory_now()
        with self.db.transaction() as conn:
            requirement = conn.execute("SELECT * FROM material_requirements WHERE id=?", (requirement_id,)).fetchone()
            if not requirement:
                raise LookupError("物料需求单不存在")
            if requirement["status"] == "已冻结":
                raise RuntimeError("已冻结的旧版本需求不能重新分配")
            material_ids = conn.execute(
                "SELECT DISTINCT material_id FROM material_requirement_items WHERE requirement_id=?",
                (requirement_id,),
            ).fetchall()
            for row in material_ids:
                self._reallocate_material(conn, int(row["material_id"]), now)
        return self.get_requirement(requirement_id)

    def supplement_item(self, item_id: int, *, material_id: int, quantity: float, remark: str = "") -> Dict[str, Any]:
        if quantity <= EPSILON:
            raise ValueError("补料数量必须大于零")
        now = inventory_now()
        with self.db.transaction() as conn:
            source = conn.execute(
                """SELECT i.*, q.status AS requirement_status, q.id AS requirement_id,
                          m.code AS material_code, m.name AS material_name,
                          m.specification AS material_specification, m.unit AS material_unit
                   FROM material_requirement_items i
                   JOIN material_requirements q ON q.id=i.requirement_id
                   JOIN inventory_materials m ON m.id=? AND m.is_active=1
                   WHERE i.id=?""",
                (material_id, item_id),
            ).fetchone()
            if not source:
                raise LookupError("原需求明细或补料物料不存在")
            if source["requirement_status"] == "已冻结":
                raise RuntimeError("已冻结的旧版本需求不能补料")
            sequence = int(conn.execute(
                "SELECT COALESCE(MAX(sequence_no), 0) + 1 AS value FROM material_requirement_items WHERE requirement_id=?",
                (source["requirement_id"],),
            ).fetchone()["value"])
            conn.execute(
                """INSERT INTO material_requirement_items(
                       requirement_id, component_id, material_id, material_code,
                       material_name, specification, required_quantity, unit,
                       shortage_quantity, status, sequence_no, created_at, updated_at
                   ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, '全部缺料', ?, ?, ?)""",
                (
                    source["requirement_id"], material_id, source["material_code"],
                    f"{source['material_name']}（补料）", source["material_specification"],
                    quantity, source["material_unit"], quantity, sequence, now, now,
                ),
            )
            self._reallocate_material(conn, material_id, now)
        result = self.get_requirement(int(source["requirement_id"]))
        result["supplement_remark"] = remark
        return result
