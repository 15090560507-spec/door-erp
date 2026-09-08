"""SQLite persistence for sales orders and immutable source snapshots."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from config import SALES_ORDER_DB_FILE


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class SalesOrderDatabase:
    def __init__(self, db_path: str = SALES_ORDER_DB_FILE):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30, factory=_ClosingConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS sales_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_no TEXT NOT NULL UNIQUE,
                    order_date TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    project_name TEXT NOT NULL DEFAULT '',
                    delivery_address TEXT NOT NULL DEFAULT '',
                    salesperson TEXT NOT NULL DEFAULT '',
                    delivery_date TEXT NOT NULL DEFAULT '',
                    payment_template TEXT NOT NULL DEFAULT '',
                    remark TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'draft',
                    subtotal REAL NOT NULL DEFAULT 0,
                    discount_amount REAL NOT NULL DEFAULT 0,
                    total_amount REAL NOT NULL DEFAULT 0,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    confirmed_at TEXT,
                    cancelled_at TEXT,
                    cancel_reason TEXT NOT NULL DEFAULT '',
                    provisioning_status TEXT NOT NULL DEFAULT 'not_started',
                    provisioning_error TEXT NOT NULL DEFAULT '',
                    provisioning_attempts INTEGER NOT NULL DEFAULT 0,
                    provisioning_key TEXT NOT NULL DEFAULT '',
                    provisioned_at TEXT,
                    fulfillment_order_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS sales_order_door_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sales_order_id INTEGER NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
                    line_no INTEGER NOT NULL,
                    task_id TEXT NOT NULL,
                    quote_id INTEGER,
                    quote_group_index INTEGER,
                    product_name TEXT NOT NULL DEFAULT '',
                    door_type TEXT NOT NULL DEFAULT '',
                    width REAL NOT NULL DEFAULT 0,
                    height REAL NOT NULL DEFAULT 0,
                    opening_direction TEXT NOT NULL DEFAULT '',
                    color TEXT NOT NULL DEFAULT '',
                    quantity INTEGER NOT NULL DEFAULT 1,
                    unit TEXT NOT NULL DEFAULT '樘',
                    unit_price REAL NOT NULL DEFAULT 0,
                    amount REAL NOT NULL DEFAULT 0,
                    drawing_status TEXT NOT NULL DEFAULT '',
                    drawing_revision TEXT NOT NULL DEFAULT '',
                    drawing_snapshot TEXT NOT NULL DEFAULT '{}',
                    quote_snapshot TEXT NOT NULL DEFAULT '{}',
                    source_type TEXT NOT NULL DEFAULT 'drawing',
                    remark TEXT NOT NULL DEFAULT '',
                    UNIQUE(sales_order_id, task_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sales_order_lines_task
                    ON sales_order_door_lines(task_id);
                CREATE TABLE IF NOT EXISTS sales_order_payment_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sales_order_id INTEGER NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
                    line_no INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    due_percent REAL NOT NULL DEFAULT 0,
                    due_amount REAL NOT NULL DEFAULT 0,
                    planned_date TEXT NOT NULL DEFAULT '',
                    paid_amount REAL NOT NULL DEFAULT 0,
                    paid_date TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    remark TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS sales_order_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sales_order_id INTEGER NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    operator TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                """
            )
            order_columns = {row["name"] for row in connection.execute("PRAGMA table_info(sales_orders)").fetchall()}
            for name, definition in (
                ("provisioning_status", "TEXT NOT NULL DEFAULT 'not_started'"),
                ("provisioning_error", "TEXT NOT NULL DEFAULT ''"),
                ("provisioning_attempts", "INTEGER NOT NULL DEFAULT 0"),
                ("provisioning_key", "TEXT NOT NULL DEFAULT ''"),
                ("provisioned_at", "TEXT"),
                ("fulfillment_order_id", "INTEGER"),
            ):
                if name not in order_columns:
                    connection.execute(f"ALTER TABLE sales_orders ADD COLUMN {name} {definition}")
            line_columns = {row["name"] for row in connection.execute("PRAGMA table_info(sales_order_door_lines)").fetchall()}
            if "source_type" not in line_columns:
                connection.execute("ALTER TABLE sales_order_door_lines ADD COLUMN source_type TEXT NOT NULL DEFAULT 'drawing'")

    def _next_order_no(self, connection: sqlite3.Connection, order_date: str) -> str:
        day = "".join(character for character in order_date if character.isdigit())[:8]
        if len(day) != 8:
            day = datetime.now().strftime("%Y%m%d")
        prefix = f"SO{day}"
        row = connection.execute(
            "SELECT order_no FROM sales_orders WHERE order_no LIKE ? ORDER BY order_no DESC LIMIT 1",
            (f"{prefix}%",),
        ).fetchone()
        sequence = int(str(row["order_no"])[-3:]) + 1 if row else 1
        return f"{prefix}{sequence:03d}"

    @staticmethod
    def _totals(lines: Iterable[Dict], discount_amount: float) -> tuple[float, float]:
        subtotal = round(sum(float(line.get("amount") or 0) for line in lines), 2)
        discount = round(float(discount_amount or 0), 2)
        if discount > subtotal:
            raise ValueError("优惠金额不能大于订单小计")
        return subtotal, round(subtotal - discount, 2)

    def _replace_lines(self, connection: sqlite3.Connection, order_id: int, lines: List[Dict]) -> None:
        connection.execute("DELETE FROM sales_order_door_lines WHERE sales_order_id = ?", (order_id,))
        for index, line in enumerate(lines, start=1):
            connection.execute(
                """
                INSERT INTO sales_order_door_lines (
                    sales_order_id, line_no, task_id, quote_id, quote_group_index,
                    product_name, door_type, width, height, opening_direction, color,
                    quantity, unit, unit_price, amount, drawing_status, drawing_revision,
                    drawing_snapshot, quote_snapshot, source_type, remark
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id, index, line["task_id"], line.get("quote_id"), line.get("quote_group_index"),
                    line.get("product_name", ""), line.get("door_type", ""), line.get("width", 0),
                    line.get("height", 0), line.get("opening_direction", ""), line.get("color", ""),
                    line.get("quantity", 1), line.get("unit", "樘"), line.get("unit_price", 0),
                    line.get("amount", 0), line.get("drawing_status", ""), line.get("drawing_revision", ""),
                    json.dumps(line.get("drawing_snapshot") or {}, ensure_ascii=False),
                    json.dumps(line.get("quote_snapshot") or {}, ensure_ascii=False),
                    line.get("source_type", "drawing"), line.get("remark", ""),
                ),
            )

    def _replace_payment_nodes(self, connection: sqlite3.Connection, order_id: int, nodes: List[Dict]) -> None:
        connection.execute("DELETE FROM sales_order_payment_nodes WHERE sales_order_id = ?", (order_id,))
        for index, node in enumerate(nodes, start=1):
            connection.execute(
                """
                INSERT INTO sales_order_payment_nodes (
                    sales_order_id, line_no, name, due_percent, due_amount, planned_date, remark
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (order_id, index, node["name"], node.get("due_percent", 0), node.get("due_amount", 0), node.get("planned_date", ""), node.get("remark", "")),
            )

    def create(self, data: Dict, lines: List[Dict], operator: str) -> Dict:
        subtotal, total = self._totals(lines, data.get("discount_amount", 0))
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            order_no = self._next_order_no(connection, data["order_date"])
            cursor = connection.execute(
                """
                INSERT INTO sales_orders (
                    order_no, order_date, customer_name, project_name, delivery_address,
                    salesperson, delivery_date, payment_template, remark, status,
                    subtotal, discount_amount, total_amount, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_no, data["order_date"], data["customer_name"], data.get("project_name", ""),
                    data.get("delivery_address", ""), data.get("salesperson", ""), data.get("delivery_date", ""),
                    data.get("payment_template", ""), data.get("remark", ""), subtotal,
                    data.get("discount_amount", 0), total, operator, now, now,
                ),
            )
            order_id = int(cursor.lastrowid)
            self._replace_lines(connection, order_id, lines)
            self._replace_payment_nodes(connection, order_id, data.get("payment_nodes") or [])
            connection.execute(
                "INSERT INTO sales_order_events (sales_order_id, event_type, detail, operator, created_at) VALUES (?, 'created', ?, ?, ?)",
                (order_id, "创建订单草稿", operator, now),
            )
        return self.get(order_id) or {}

    def update_draft(self, order_id: int, data: Dict, lines: List[Dict], operator: str) -> Dict:
        subtotal, total = self._totals(lines, data.get("discount_amount", 0))
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT status FROM sales_orders WHERE id = ?", (order_id,)).fetchone()
            if not current:
                raise LookupError("订单不存在")
            if current["status"] != "draft":
                raise RuntimeError("只有草稿订单可以直接修改；已确认订单请走订单变更")
            connection.execute(
                """
                UPDATE sales_orders SET order_date = ?, customer_name = ?, project_name = ?,
                    delivery_address = ?, salesperson = ?, delivery_date = ?, payment_template = ?,
                    remark = ?, subtotal = ?, discount_amount = ?, total_amount = ?,
                    version = version + 1, updated_at = ? WHERE id = ?
                """,
                (
                    data["order_date"], data["customer_name"], data.get("project_name", ""),
                    data.get("delivery_address", ""), data.get("salesperson", ""), data.get("delivery_date", ""),
                    data.get("payment_template", ""), data.get("remark", ""), subtotal,
                    data.get("discount_amount", 0), total, now, order_id,
                ),
            )
            self._replace_lines(connection, order_id, lines)
            self._replace_payment_nodes(connection, order_id, data.get("payment_nodes") or [])
            connection.execute(
                "INSERT INTO sales_order_events (sales_order_id, event_type, detail, operator, created_at) VALUES (?, 'updated', ?, ?, ?)",
                (order_id, "更新订单草稿", operator, now),
            )
        return self.get(order_id) or {}

    def confirm(self, order_id: int, operator: str) -> Dict:
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            order = connection.execute("SELECT * FROM sales_orders WHERE id = ?", (order_id,)).fetchone()
            if not order:
                raise LookupError("订单不存在")
            if order["status"] != "draft":
                raise RuntimeError("只有草稿订单可以正式确认")
            connection.execute(
                """UPDATE sales_orders SET status = 'confirmed', confirmed_at = ?, updated_at = ?,
                       version = version + 1, provisioning_status = 'pending', provisioning_error = '',
                       provisioning_key = ? WHERE id = ?""",
                (now, now, f"sales-order:{order_id}", order_id),
            )
            connection.execute(
                "INSERT INTO sales_order_events (sales_order_id, event_type, detail, operator, created_at) VALUES (?, 'confirmed', ?, ?, ?)",
                (order_id, "订单正式确认", operator, now),
            )
        return self.get(order_id) or {}

    def mark_provisioning_started(self, order_id: int, operator: str) -> Dict:
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            order = connection.execute("SELECT status FROM sales_orders WHERE id = ?", (order_id,)).fetchone()
            if not order:
                raise LookupError("订单不存在")
            if order["status"] not in {"confirmed", "fulfilling"}:
                raise RuntimeError("只有已确认订单可以生成履约门樘")
            connection.execute(
                """UPDATE sales_orders SET provisioning_status='processing', provisioning_error='',
                       provisioning_attempts=provisioning_attempts+1, updated_at=? WHERE id=?""",
                (now, order_id),
            )
            connection.execute(
                """INSERT INTO sales_order_events
                       (sales_order_id, event_type, detail, operator, created_at)
                       VALUES (?, 'provisioning_started', '开始生成门樘和BOM草稿', ?, ?)""",
                (order_id, operator, now),
            )
        return self.get(order_id) or {}

    def mark_provisioned(self, order_id: int, fulfillment_order_id: int, operator: str) -> Dict:
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE sales_orders SET status='fulfilling', provisioning_status='ready',
                       provisioning_error='', fulfillment_order_id=?, provisioned_at=?, updated_at=?
                   WHERE id=?""",
                (fulfillment_order_id, now, now, order_id),
            )
            connection.execute(
                """INSERT INTO sales_order_events
                       (sales_order_id, event_type, detail, operator, created_at)
                       VALUES (?, 'provisioned', ?, ?, ?)""",
                (order_id, f"已生成履约订单 #{fulfillment_order_id}", operator, now),
            )
        return self.get(order_id) or {}

    def mark_provisioning_failed(self, order_id: int, message: str, operator: str) -> Dict:
        now = _now()
        detail = str(message or "履约生成失败")[:1000]
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE sales_orders SET provisioning_status='failed', provisioning_error=?,
                       updated_at=? WHERE id=?""",
                (detail, now, order_id),
            )
            connection.execute(
                """INSERT INTO sales_order_events
                       (sales_order_id, event_type, detail, operator, created_at)
                       VALUES (?, 'provisioning_failed', ?, ?, ?)""",
                (order_id, detail, operator, now),
            )
        return self.get(order_id) or {}

    def cancel(self, order_id: int, reason: str, operator: str) -> Dict:
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            order = connection.execute("SELECT status FROM sales_orders WHERE id = ?", (order_id,)).fetchone()
            if not order:
                raise LookupError("订单不存在")
            if order["status"] not in {"draft", "confirmed"}:
                raise RuntimeError("订单已进入生产，不能直接取消；请先在生产管理中处理在制门樘")
            connection.execute(
                "UPDATE sales_orders SET status = 'cancelled', cancel_reason = ?, cancelled_at = ?, updated_at = ?, version = version + 1 WHERE id = ?",
                (reason, now, now, order_id),
            )
            connection.execute(
                "INSERT INTO sales_order_events (sales_order_id, event_type, detail, operator, created_at) VALUES (?, 'cancelled', ?, ?, ?)",
                (order_id, reason or "取消订单", operator, now),
            )
        return self.get(order_id) or {}

    def active_task_ids(self, exclude_order_id: Optional[int] = None) -> set[str]:
        sql = """
            SELECT DISTINCT line.task_id
            FROM sales_order_door_lines line
            JOIN sales_orders orders ON orders.id = line.sales_order_id
            WHERE orders.status != 'cancelled' AND line.source_type = 'drawing'
        """
        params: List[object] = []
        if exclude_order_id is not None:
            sql += " AND orders.id != ?"
            params.append(exclude_order_id)
        with self._connect() as connection:
            return {str(row["task_id"]) for row in connection.execute(sql, params).fetchall()}

    def confirmed_line_for_task(self, task_id: str) -> Optional[Dict]:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT line.*, orders.order_no AS sales_order_no, orders.delivery_date,
                          orders.customer_name, orders.project_name, orders.status AS sales_order_status
                   FROM sales_order_door_lines line
                   JOIN sales_orders orders ON orders.id=line.sales_order_id
                   WHERE line.task_id=? AND line.source_type='drawing'
                         AND orders.status IN ('confirmed', 'fulfilling')
                   ORDER BY orders.id DESC LIMIT 1""",
                (task_id,),
            ).fetchone()
            return dict(row) if row else None

    def mark_fulfilling(self, order_id: int, operator: str) -> None:
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT status FROM sales_orders WHERE id=?", (order_id,)).fetchone()
            if not current or current["status"] not in {"confirmed", "fulfilling"}:
                return
            connection.execute(
                "UPDATE sales_orders SET status='fulfilling', updated_at=? WHERE id=?",
                (now, order_id),
            )
            connection.execute(
                "INSERT INTO sales_order_events (sales_order_id, event_type, detail, operator, created_at) VALUES (?, 'production_released', ?, ?, ?)",
                (order_id, "门樘已下达生产", operator, now),
            )

    def list(self, q: str = "", status: str = "", limit: int = 100) -> List[Dict]:
        conditions = ["1 = 1"]
        params: List[object] = []
        if status:
            conditions.append("orders.status = ?")
            params.append(status)
        if q:
            conditions.append("(orders.order_no LIKE ? OR orders.customer_name LIKE ? OR orders.project_name LIKE ?)")
            keyword = f"%{q}%"
            params.extend([keyword, keyword, keyword])
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT orders.*, COUNT(lines.id) AS line_count,
                    COALESCE(SUM(lines.quantity), 0) AS door_count,
                    COALESCE(SUM(CASE WHEN lines.drawing_status = '已通过' THEN lines.quantity ELSE 0 END), 0) AS releasable_count
                FROM sales_orders orders
                LEFT JOIN sales_order_door_lines lines ON lines.sales_order_id = orders.id
                WHERE {' AND '.join(conditions)}
                GROUP BY orders.id ORDER BY orders.id DESC LIMIT ?
                """,
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    def get(self, order_id: int) -> Optional[Dict]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM sales_orders WHERE id = ?", (order_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            line_rows = connection.execute(
                "SELECT * FROM sales_order_door_lines WHERE sales_order_id = ? ORDER BY line_no", (order_id,)
            ).fetchall()
            result["lines"] = []
            for item in line_rows:
                line = dict(item)
                line["drawing_snapshot"] = json.loads(line.get("drawing_snapshot") or "{}")
                line["quote_snapshot"] = json.loads(line.get("quote_snapshot") or "{}")
                result["lines"].append(line)
            result["payment_nodes"] = [
                dict(item) for item in connection.execute(
                    "SELECT * FROM sales_order_payment_nodes WHERE sales_order_id = ? ORDER BY line_no", (order_id,)
                ).fetchall()
            ]
            result["events"] = [
                dict(item) for item in connection.execute(
                    "SELECT * FROM sales_order_events WHERE sales_order_id = ? ORDER BY id DESC", (order_id,)
                ).fetchall()
            ]
            return result
