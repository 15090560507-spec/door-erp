"""Material requirement, reservation, purchase and issue workflow."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Iterable, List, Optional

from production_database import ProductionDatabase, production_now


EPSILON = 1e-9


class ProductionMaterialService:
    def __init__(self, db: ProductionDatabase):
        self.db = db

    @staticmethod
    def _on_hand(conn: sqlite3.Connection, material_id: int) -> float:
        row = conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS quantity "
            "FROM production_inventory_transactions WHERE material_id=?",
            (material_id,),
        ).fetchone()
        return float(row["quantity"] or 0)

    @staticmethod
    def _reserved(conn: sqlite3.Connection, material_id: int) -> float:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(quantity), 0) AS quantity
            FROM production_inventory_reservations
            WHERE material_id=? AND status='有效'
            """,
            (material_id,),
        ).fetchone()
        return float(row["quantity"] or 0)

    @staticmethod
    def _shortage(item: sqlite3.Row | Dict[str, Any]) -> float:
        required = float(item["required_quantity"] or 0)
        issued = float(item["issued_quantity"] or 0)
        reserved = float(item["reserved_quantity"] or 0)
        purchased = float(item["purchased_quantity"] or 0)
        received = float(item["received_quantity"] or 0)
        outstanding_purchase = max(0.0, purchased - received)
        return max(0.0, required - issued - reserved - outstanding_purchase)

    def _refresh_item(self, conn: sqlite3.Connection, item_id: int) -> None:
        item = conn.execute(
            "SELECT * FROM production_material_requirement_items WHERE id=?", (item_id,)
        ).fetchone()
        if not item:
            return
        required = float(item["required_quantity"] or 0)
        issued = float(item["issued_quantity"] or 0)
        reserved = float(item["reserved_quantity"] or 0)
        outstanding = max(
            0.0,
            float(item["purchased_quantity"] or 0) - float(item["received_quantity"] or 0),
        )
        remaining = max(0.0, required - issued)
        if remaining <= EPSILON:
            status = "已领料"
        elif reserved + EPSILON >= remaining:
            status = "已备料"
        elif reserved > EPSILON:
            status = "部分备料"
        elif outstanding > EPSILON:
            status = "采购中"
        elif not item["material_id"]:
            status = "未关联物料"
        else:
            status = "缺料"
        conn.execute(
            "UPDATE production_material_requirement_items SET status=?, updated_at=? WHERE id=?",
            (status, production_now(), item_id),
        )

    def _refresh_requirement(self, conn: sqlite3.Connection, requirement_id: int) -> None:
        rows = conn.execute(
            "SELECT * FROM production_material_requirement_items WHERE requirement_id=? ORDER BY id",
            (requirement_id,),
        ).fetchall()
        for row in rows:
            self._refresh_item(conn, int(row["id"]))
        rows = conn.execute(
            "SELECT * FROM production_material_requirement_items WHERE requirement_id=? ORDER BY id",
            (requirement_id,),
        ).fetchall()
        statuses = {str(row["status"]) for row in rows}
        if rows and statuses <= {"已领料"}:
            status = "已领料"
        elif rows and statuses <= {"已备料", "已领料"}:
            status = "已备料"
        elif any(float(row["reserved_quantity"] or 0) > EPSILON for row in rows):
            status = "部分备料"
        elif "采购中" in statuses:
            status = "采购中"
        else:
            status = "缺料"
        now = production_now()
        requirement = conn.execute(
            "SELECT order_id FROM production_material_requirements WHERE id=?", (requirement_id,)
        ).fetchone()
        conn.execute(
            "UPDATE production_material_requirements SET status=?, updated_at=? WHERE id=?",
            (status, now, requirement_id),
        )
        if requirement:
            shortage_status = "不缺料" if status in {"已备料", "已领料"} else status
            conn.execute(
                "UPDATE production_orders SET shortage_status=?, updated_at=? WHERE id=?",
                (shortage_status, now, int(requirement["order_id"])),
            )

    def _allocate_requirement(self, conn: sqlite3.Connection, requirement_id: int) -> None:
        items = conn.execute(
            "SELECT * FROM production_material_requirement_items WHERE requirement_id=? ORDER BY id",
            (requirement_id,),
        ).fetchall()
        for item in items:
            material_id = item["material_id"]
            if not material_id:
                continue
            needed = max(
                0.0,
                float(item["required_quantity"] or 0)
                - float(item["issued_quantity"] or 0)
                - float(item["reserved_quantity"] or 0),
            )
            if needed <= EPSILON:
                continue
            available = max(0.0, self._on_hand(conn, int(material_id)) - self._reserved(conn, int(material_id)))
            allocation = min(needed, available)
            if allocation <= EPSILON:
                continue
            reservation = conn.execute(
                "SELECT * FROM production_inventory_reservations WHERE requirement_item_id=?",
                (item["id"],),
            ).fetchone()
            now = production_now()
            if reservation:
                conn.execute(
                    """
                    UPDATE production_inventory_reservations
                    SET quantity=quantity+?, status='有效', updated_at=? WHERE id=?
                    """,
                    (allocation, now, reservation["id"]),
                )
            else:
                requirement = conn.execute(
                    "SELECT order_id FROM production_material_requirements WHERE id=?",
                    (requirement_id,),
                ).fetchone()
                conn.execute(
                    """
                    INSERT INTO production_inventory_reservations(
                        requirement_item_id, order_id, material_id, quantity, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, '有效', ?, ?)
                    """,
                    (item["id"], requirement["order_id"], material_id, allocation, now, now),
                )
            conn.execute(
                """
                UPDATE production_material_requirement_items
                SET reserved_quantity=reserved_quantity+?, updated_at=? WHERE id=?
                """,
                (allocation, now, item["id"]),
            )
        self._refresh_requirement(conn, requirement_id)

    def allocate_open_requirements(
        self, conn: sqlite3.Connection, preferred_order_ids: Iterable[int] = ()
    ) -> None:
        preferred = list(dict.fromkeys(int(value) for value in preferred_order_ids))
        ids: List[int] = []
        for order_id in preferred:
            row = conn.execute(
                "SELECT id FROM production_material_requirements WHERE order_id=?", (order_id,)
            ).fetchone()
            if row:
                ids.append(int(row["id"]))
        rows = conn.execute(
            """
            SELECT id FROM production_material_requirements
            WHERE status NOT IN ('已备料', '已领料') ORDER BY created_at, id
            """
        ).fetchall()
        ids.extend(int(row["id"]) for row in rows if int(row["id"]) not in ids)
        for requirement_id in ids:
            self._allocate_requirement(conn, requirement_id)

    def create_requirement_for_order(self, conn: sqlite3.Connection, order_id: int) -> int:
        existing = conn.execute(
            "SELECT id FROM production_material_requirements WHERE order_id=?", (order_id,)
        ).fetchone()
        if existing:
            self._allocate_requirement(conn, int(existing["id"]))
            return int(existing["id"])
        bom_status = conn.execute(
            "SELECT published_at FROM production_bom_status WHERE order_id=?", (order_id,)
        ).fetchone()
        bom_items = conn.execute(
            "SELECT * FROM production_bom_items WHERE order_id=? ORDER BY id", (order_id,)
        ).fetchall()
        now = production_now()
        cursor = conn.execute(
            """
            INSERT INTO production_material_requirements(
                order_id, bom_published_at, status, created_at, updated_at
            ) VALUES (?, ?, '待备料', ?, ?)
            """,
            (order_id, str(bom_status["published_at"] or "") if bom_status else "", now, now),
        )
        requirement_id = int(cursor.lastrowid)
        conn.executemany(
            """
            INSERT INTO production_material_requirement_items(
                requirement_id, bom_item_id, material_id, name, specification,
                required_quantity, unit, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    requirement_id, item["id"], item["material_id"], item["name"],
                    item["specification"], item["quantity"], item["unit"], now, now,
                )
                for item in bom_items
            ],
        )
        self._allocate_requirement(conn, requirement_id)
        return requirement_id

    def list_requirements(self) -> List[Dict[str, Any]]:
        rows = self.db.fetch_all(
            """
            SELECT r.*, o.order_no, o.customer, o.project, o.due_date, o.shortage_status
            FROM production_material_requirements r
            JOIN production_orders o ON o.id=r.order_id
            ORDER BY r.id DESC
            """
        )
        for row in rows:
            row["items"] = self.requirement_items(int(row["id"]))
        return rows

    def requirement_items(self, requirement_id: int) -> List[Dict[str, Any]]:
        rows = self.db.fetch_all(
            """
            SELECT i.*, m.code AS material_code,
                   MAX(0, i.required_quantity-i.issued_quantity-i.reserved_quantity-
                       MAX(0, i.purchased_quantity-i.received_quantity)) AS shortage_quantity
            FROM production_material_requirement_items i
            LEFT JOIN production_materials m ON m.id=i.material_id
            WHERE i.requirement_id=? ORDER BY i.id
            """,
            (requirement_id,),
        )
        return rows

    def get_requirement_for_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.fetch_one(
            """
            SELECT r.*, o.order_no, o.customer, o.project, o.due_date, o.shortage_status
            FROM production_material_requirements r
            JOIN production_orders o ON o.id=r.order_id WHERE r.order_id=?
            """,
            (order_id,),
        )
        if row:
            row["items"] = self.requirement_items(int(row["id"]))
        return row

    def inventory_balances(self) -> List[Dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT m.id AS material_id, m.code, m.name, m.specification, m.unit,
                   m.warehouse_location,
                   COALESCE(SUM(t.quantity), 0) AS on_hand,
                   COALESCE((SELECT SUM(r.quantity) FROM production_inventory_reservations r
                             WHERE r.material_id=m.id AND r.status='有效'), 0) AS reserved,
                   COALESCE(SUM(t.quantity), 0) -
                   COALESCE((SELECT SUM(r.quantity) FROM production_inventory_reservations r
                             WHERE r.material_id=m.id AND r.status='有效'), 0) AS available
            FROM production_materials m
            LEFT JOIN production_inventory_transactions t ON t.material_id=m.id
            WHERE m.active=1 GROUP BY m.id ORDER BY m.id DESC
            """
        )

    def issue(self, order_id: int, items: List[Dict[str, Any]], user_uid: str, remark: str) -> None:
        now = production_now()
        with self.db.transaction() as conn:
            requirement = conn.execute(
                "SELECT * FROM production_material_requirements WHERE order_id=?", (order_id,)
            ).fetchone()
            if not requirement:
                raise ValueError("该生产订单尚未生成物料需求")
            for movement in items:
                item = conn.execute(
                    """
                    SELECT * FROM production_material_requirement_items
                    WHERE id=? AND requirement_id=?
                    """,
                    (movement["requirement_item_id"], requirement["id"]),
                ).fetchone()
                if not item:
                    raise ValueError("物料需求明细不存在")
                quantity = float(movement["quantity"])
                if quantity <= EPSILON or quantity > float(item["reserved_quantity"] or 0) + EPSILON:
                    raise ValueError(f"{item['name']} 本次最多可领 {float(item['reserved_quantity'] or 0):g}{item['unit']}")
                reservation = conn.execute(
                    "SELECT * FROM production_inventory_reservations WHERE requirement_item_id=?",
                    (item["id"],),
                ).fetchone()
                conn.execute(
                    """
                    INSERT INTO production_inventory_transactions(
                        material_id, order_id, transaction_type, quantity, unit,
                        warehouse_location, remark, operator_uid, created_at
                    ) VALUES (?, ?, '生产领料', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["material_id"], order_id, -quantity, item["unit"],
                        movement.get("warehouse_location", ""), remark, user_uid, now,
                    ),
                )
                remaining = max(0.0, float(reservation["quantity"] or 0) - quantity)
                conn.execute(
                    "UPDATE production_inventory_reservations SET quantity=?, status=?, updated_at=? WHERE id=?",
                    (remaining, "有效" if remaining > EPSILON else "已释放", now, reservation["id"]),
                )
                conn.execute(
                    """
                    UPDATE production_material_requirement_items
                    SET reserved_quantity=MAX(0, reserved_quantity-?),
                        issued_quantity=issued_quantity+?, updated_at=? WHERE id=?
                    """,
                    (quantity, quantity, now, item["id"]),
                )
            self._refresh_requirement(conn, int(requirement["id"]))

    def return_materials(
        self, order_id: int, items: List[Dict[str, Any]], user_uid: str, remark: str
    ) -> None:
        now = production_now()
        with self.db.transaction() as conn:
            requirement = conn.execute(
                "SELECT * FROM production_material_requirements WHERE order_id=?", (order_id,)
            ).fetchone()
            if not requirement:
                raise ValueError("该生产订单尚未生成物料需求")
            for movement in items:
                item = conn.execute(
                    "SELECT * FROM production_material_requirement_items WHERE id=? AND requirement_id=?",
                    (movement["requirement_item_id"], requirement["id"]),
                ).fetchone()
                if not item:
                    raise ValueError("物料需求明细不存在")
                quantity = float(movement["quantity"])
                if quantity <= EPSILON or quantity > float(item["issued_quantity"] or 0) + EPSILON:
                    raise ValueError(f"{item['name']} 本次最多可退 {float(item['issued_quantity'] or 0):g}{item['unit']}")
                conn.execute(
                    """
                    INSERT INTO production_inventory_transactions(
                        material_id, order_id, transaction_type, quantity, unit,
                        warehouse_location, remark, operator_uid, created_at
                    ) VALUES (?, ?, '生产退料', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["material_id"], order_id, quantity, item["unit"],
                        movement.get("warehouse_location", ""), remark, user_uid, now,
                    ),
                )
                conn.execute(
                    """
                    UPDATE production_material_requirement_items
                    SET issued_quantity=MAX(0, issued_quantity-?), updated_at=? WHERE id=?
                    """,
                    (quantity, now, item["id"]),
                )
            self.allocate_open_requirements(conn, [order_id])
