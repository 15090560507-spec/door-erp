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
                    line_code TEXT NOT NULL DEFAULT '',
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
                CREATE TABLE IF NOT EXISTS sales_order_charge_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sales_order_id INTEGER NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
                    sales_order_line_id INTEGER REFERENCES sales_order_door_lines(id) ON DELETE SET NULL,
                    line_no INTEGER NOT NULL,
                    door_line_no INTEGER,
                    source_type TEXT NOT NULL DEFAULT 'manual',
                    quote_item_index INTEGER,
                    item_type TEXT NOT NULL DEFAULT '其他',
                    product_name TEXT NOT NULL DEFAULT '',
                    specification TEXT NOT NULL DEFAULT '',
                    quantity REAL NOT NULL DEFAULT 1,
                    unit TEXT NOT NULL DEFAULT '项',
                    unit_price REAL NOT NULL DEFAULT 0,
                    amount REAL NOT NULL DEFAULT 0,
                    pricing_mode TEXT NOT NULL DEFAULT '',
                    remark TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_sales_order_charges_order
                    ON sales_order_charge_lines(sales_order_id, line_no);
                CREATE TABLE IF NOT EXISTS sales_order_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sales_order_id INTEGER NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    operator TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sales_order_receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    receipt_no TEXT NOT NULL UNIQUE,
                    customer_name TEXT NOT NULL,
                    receipt_date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    payment_method TEXT NOT NULL DEFAULT '',
                    reference TEXT NOT NULL DEFAULT '',
                    remark TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'confirmed',
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    reversed_by TEXT NOT NULL DEFAULT '',
                    reversed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS sales_order_receipt_allocations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    receipt_id INTEGER NOT NULL REFERENCES sales_order_receipts(id) ON DELETE RESTRICT,
                    sales_order_id INTEGER NOT NULL REFERENCES sales_orders(id) ON DELETE RESTRICT,
                    amount REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(receipt_id, sales_order_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sales_receipt_allocations_order
                    ON sales_order_receipt_allocations(sales_order_id, receipt_id);
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
            if "line_code" not in line_columns:
                connection.execute("ALTER TABLE sales_order_door_lines ADD COLUMN line_code TEXT NOT NULL DEFAULT ''")
            connection.execute(
                """UPDATE sales_order_door_lines
                   SET line_code=(SELECT sales_orders.order_no FROM sales_orders
                                  WHERE sales_orders.id=sales_order_door_lines.sales_order_id)
                                 || '-' || printf('%02d', line_no)
                   WHERE line_code=''"""
            )
            connection.execute(
                """INSERT INTO sales_order_charge_lines (
                       sales_order_id, sales_order_line_id, line_no, door_line_no,
                       source_type, item_type, product_name, quantity, unit,
                       unit_price, amount, remark
                   )
                   SELECT line.sales_order_id, line.id, line.line_no, line.line_no,
                          'manual', '主门', line.product_name, line.quantity, line.unit,
                          line.unit_price, line.amount, line.remark
                   FROM sales_order_door_lines line
                   WHERE NOT EXISTS (
                       SELECT 1 FROM sales_order_charge_lines charge
                       WHERE charge.sales_order_id=line.sales_order_id
                   )"""
            )
            connection.execute(
                """UPDATE sales_order_payment_nodes
                   SET due_amount=ROUND((SELECT total_amount FROM sales_orders
                                        WHERE sales_orders.id=sales_order_payment_nodes.sales_order_id)
                                        * due_percent / 100.0, 2)
                   WHERE due_amount=0 AND due_percent>0"""
            )

    def _next_order_no(self, connection: sqlite3.Connection, order_date: str) -> str:
        digits = "".join(character for character in order_date if character.isdigit())
        year = digits[:4] if len(digits) >= 4 else datetime.now().strftime("%Y")
        prefix = f"TM{year[-2:]}"
        row = connection.execute(
            "SELECT order_no FROM sales_orders WHERE order_no LIKE ? ORDER BY order_no DESC LIMIT 1",
            (f"{prefix}%",),
        ).fetchone()
        sequence = int(str(row["order_no"])[-5:]) + 1 if row else 1
        if sequence > 99999:
            raise RuntimeError(f"{year}年度订单编号已经用完")
        return f"{prefix}{sequence:05d}"

    @staticmethod
    def _totals(charge_lines: Iterable[Dict], discount_amount: float) -> tuple[float, float]:
        subtotal = round(sum(
            float(line.get("amount")) if line.get("amount") is not None
            else float(line.get("quantity") or 0) * float(line.get("unit_price") or 0)
            for line in charge_lines
        ), 2)
        discount = round(float(discount_amount or 0), 2)
        if discount > subtotal:
            raise ValueError("优惠金额不能大于订单小计")
        return subtotal, round(subtotal - discount, 2)

    def _replace_lines(self, connection: sqlite3.Connection, order_id: int, order_no: str, lines: List[Dict]) -> Dict[int, int]:
        connection.execute("DELETE FROM sales_order_door_lines WHERE sales_order_id = ?", (order_id,))
        line_ids: Dict[int, int] = {}
        for index, line in enumerate(lines, start=1):
            cursor = connection.execute(
                """
                INSERT INTO sales_order_door_lines (
                    sales_order_id, line_no, line_code, task_id, quote_id, quote_group_index,
                    product_name, door_type, width, height, opening_direction, color,
                    quantity, unit, unit_price, amount, drawing_status, drawing_revision,
                    drawing_snapshot, quote_snapshot, source_type, remark
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id, index, f"{order_no}-{index:02d}", line["task_id"], line.get("quote_id"), line.get("quote_group_index"),
                    line.get("product_name", ""), line.get("door_type", ""), line.get("width", 0),
                    line.get("height", 0), line.get("opening_direction", ""), line.get("color", ""),
                    line.get("quantity", 1), line.get("unit", "樘"), line.get("unit_price", 0),
                    line.get("amount", 0), line.get("drawing_status", ""), line.get("drawing_revision", ""),
                    json.dumps(line.get("drawing_snapshot") or {}, ensure_ascii=False),
                    json.dumps(line.get("quote_snapshot") or {}, ensure_ascii=False),
                    line.get("source_type", "drawing"), line.get("remark", ""),
                ),
            )
            line_ids[index] = int(cursor.lastrowid)
        return line_ids

    def _replace_charge_lines(
        self,
        connection: sqlite3.Connection,
        order_id: int,
        line_ids: Dict[int, int],
        charge_lines: List[Dict],
    ) -> None:
        connection.execute("DELETE FROM sales_order_charge_lines WHERE sales_order_id = ?", (order_id,))
        for index, charge in enumerate(charge_lines, start=1):
            door_line_no = charge.get("door_line_no")
            quantity = float(charge.get("quantity") or 0)
            unit_price = float(charge.get("unit_price") or 0)
            amount = float(charge["amount"]) if charge.get("amount") is not None else round(quantity * unit_price, 2)
            connection.execute(
                """INSERT INTO sales_order_charge_lines (
                       sales_order_id, sales_order_line_id, line_no, door_line_no,
                       source_type, quote_item_index, item_type, product_name,
                       specification, quantity, unit, unit_price, amount,
                       pricing_mode, remark
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_id, line_ids.get(int(door_line_no)) if door_line_no else None,
                    index, door_line_no, charge.get("source_type", "manual"),
                    charge.get("quote_item_index"), charge.get("item_type", "其他"),
                    charge.get("product_name", ""), charge.get("specification", ""),
                    quantity, charge.get("unit", "项"), unit_price, amount,
                    charge.get("pricing_mode", ""), charge.get("remark", ""),
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

    def create(self, data: Dict, lines: List[Dict], charge_lines: List[Dict], operator: str) -> Dict:
        subtotal, total = self._totals(charge_lines, data.get("discount_amount", 0))
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
            line_ids = self._replace_lines(connection, order_id, order_no, lines)
            self._replace_charge_lines(connection, order_id, line_ids, charge_lines)
            self._replace_payment_nodes(connection, order_id, data.get("payment_nodes") or [])
            connection.execute(
                "INSERT INTO sales_order_events (sales_order_id, event_type, detail, operator, created_at) VALUES (?, 'created', ?, ?, ?)",
                (order_id, "创建订单草稿", operator, now),
            )
        return self.get(order_id) or {}

    def update_draft(self, order_id: int, data: Dict, lines: List[Dict], charge_lines: List[Dict], operator: str) -> Dict:
        subtotal, total = self._totals(charge_lines, data.get("discount_amount", 0))
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT status, order_no FROM sales_orders WHERE id = ?", (order_id,)).fetchone()
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
            line_ids = self._replace_lines(connection, order_id, str(current["order_no"]), lines)
            self._replace_charge_lines(connection, order_id, line_ids, charge_lines)
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
            if order["status"] in {"confirmed", "fulfilling"}:
                return self.get(order_id) or {}
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
                    COALESCE(SUM(CASE WHEN lines.drawing_status = '已通过' THEN lines.quantity ELSE 0 END), 0) AS releasable_count,
                    COALESCE((SELECT SUM(allocation.amount)
                              FROM sales_order_receipt_allocations allocation
                              JOIN sales_order_receipts receipt ON receipt.id=allocation.receipt_id
                              WHERE allocation.sales_order_id=orders.id AND receipt.status='confirmed'), 0) AS paid_amount
                FROM sales_orders orders
                LEFT JOIN sales_order_door_lines lines ON lines.sales_order_id = orders.id
                WHERE {' AND '.join(conditions)}
                GROUP BY orders.id ORDER BY orders.id DESC LIMIT ?
                """,
                params,
            ).fetchall()
            results = [dict(row) for row in rows]
            for item in results:
                item["unpaid_amount"] = max(0.0, round(float(item.get("total_amount") or 0) - float(item.get("paid_amount") or 0), 2))
            return results

    def payment_summary(self, order_id: int) -> Dict:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT orders.id, orders.order_no, orders.customer_name, orders.status,
                          orders.total_amount,
                          COALESCE(SUM(CASE WHEN receipt.status='confirmed' THEN allocation.amount ELSE 0 END), 0) AS paid_amount
                   FROM sales_orders orders
                   LEFT JOIN sales_order_receipt_allocations allocation ON allocation.sales_order_id=orders.id
                   LEFT JOIN sales_order_receipts receipt ON receipt.id=allocation.receipt_id
                   WHERE orders.id=? GROUP BY orders.id""",
                (order_id,),
            ).fetchone()
            if not row:
                raise LookupError("订单不存在")
            result = dict(row)
            result["paid_amount"] = round(float(result.get("paid_amount") or 0), 2)
            result["unpaid_amount"] = max(0.0, round(float(result.get("total_amount") or 0) - result["paid_amount"], 2))
            return result

    def receipt_candidates(self, customer_name: str) -> List[Dict]:
        conditions = ["orders.status IN ('confirmed', 'fulfilling', 'completed')"]
        params: List[object] = []
        if customer_name.strip():
            conditions.append("orders.customer_name=?")
            params.append(customer_name.strip())
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT orders.id, orders.order_no, orders.customer_name, orders.project_name,
                           orders.order_date, orders.total_amount,
                           COALESCE(SUM(CASE WHEN receipt.status='confirmed' THEN allocation.amount ELSE 0 END), 0) AS paid_amount
                    FROM sales_orders orders
                    LEFT JOIN sales_order_receipt_allocations allocation ON allocation.sales_order_id=orders.id
                    LEFT JOIN sales_order_receipts receipt ON receipt.id=allocation.receipt_id
                    WHERE {' AND '.join(conditions)}
                    GROUP BY orders.id ORDER BY orders.id DESC""",
                params,
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["paid_amount"] = round(float(item.get("paid_amount") or 0), 2)
            item["unpaid_amount"] = max(0.0, round(float(item.get("total_amount") or 0) - item["paid_amount"], 2))
            if item["unpaid_amount"] > 0.005:
                results.append(item)
        return results

    def get_receipt(self, receipt_id: int) -> Optional[Dict]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM sales_order_receipts WHERE id=?", (receipt_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["allocations"] = [
                dict(item) for item in connection.execute(
                    """SELECT allocation.id, allocation.sales_order_id AS order_id, orders.order_no,
                              orders.project_name, allocation.amount
                       FROM sales_order_receipt_allocations allocation
                       JOIN sales_orders orders ON orders.id=allocation.sales_order_id
                       WHERE allocation.receipt_id=? ORDER BY allocation.id""",
                    (receipt_id,),
                ).fetchall()
            ]
            return result

    def create_receipt(self, data: Dict, operator: str) -> Dict:
        allocations = [item for item in data.get("allocations") or [] if float(item.get("amount") or 0) > 0]
        if not allocations:
            raise ValueError("请至少分配一张订单")
        order_ids = [int(item["order_id"]) for item in allocations]
        if len(order_ids) != len(set(order_ids)):
            raise ValueError("同一订单不能重复分配")
        amount = round(float(data.get("amount") or 0), 2)
        allocated_total = round(sum(float(item.get("amount") or 0) for item in allocations), 2)
        if amount <= 0 or abs(amount - allocated_total) > 0.005:
            raise ValueError("收款金额必须大于0，且必须与订单分配合计一致")
        now = _now()
        receipt_date = str(data.get("receipt_date") or now[:10])
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            placeholders = ",".join("?" for _ in order_ids)
            rows = connection.execute(
                f"SELECT id, order_no, customer_name, status, total_amount FROM sales_orders WHERE id IN ({placeholders})",
                order_ids,
            ).fetchall()
            if len(rows) != len(order_ids):
                raise LookupError("分配的订单不存在")
            orders = {int(row["id"]): dict(row) for row in rows}
            customers = {str(row["customer_name"]) for row in rows}
            if len(customers) != 1:
                raise ValueError("一笔收款只能分配给同一客户的订单")
            if any(row["status"] not in {"confirmed", "fulfilling", "completed"} for row in rows):
                raise RuntimeError("收款只能分配给已确认或履约中的订单")
            for item in allocations:
                order_id = int(item["order_id"])
                paid = float(connection.execute(
                    """SELECT COALESCE(SUM(allocation.amount), 0) AS total
                       FROM sales_order_receipt_allocations allocation
                       JOIN sales_order_receipts receipt ON receipt.id=allocation.receipt_id
                       WHERE allocation.sales_order_id=? AND receipt.status='confirmed'""",
                    (order_id,),
                ).fetchone()["total"] or 0)
                outstanding = max(0.0, float(orders[order_id]["total_amount"] or 0) - paid)
                if float(item["amount"]) - outstanding > 0.005:
                    raise ValueError(f"{orders[order_id]['order_no']} 分配金额超过未收金额 {outstanding:.2f} 元")
            next_id = int(connection.execute("SELECT COALESCE(MAX(id), 0)+1 AS id FROM sales_order_receipts").fetchone()["id"])
            receipt_no = f"SK{''.join(char for char in receipt_date if char.isdigit())[:8]}{next_id:04d}"
            cursor = connection.execute(
                """INSERT INTO sales_order_receipts(
                       receipt_no, customer_name, receipt_date, amount, payment_method,
                       reference, remark, created_by, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (receipt_no, customers.pop(), receipt_date, amount, str(data.get("payment_method") or ""),
                 str(data.get("reference") or ""), str(data.get("remark") or ""), operator, now),
            )
            receipt_id = int(cursor.lastrowid)
            for item in allocations:
                order_id = int(item["order_id"])
                allocation_amount = round(float(item["amount"]), 2)
                connection.execute(
                    "INSERT INTO sales_order_receipt_allocations(receipt_id, sales_order_id, amount, created_at) VALUES (?, ?, ?, ?)",
                    (receipt_id, order_id, allocation_amount, now),
                )
                connection.execute(
                    "INSERT INTO sales_order_events(sales_order_id, event_type, detail, operator, created_at) VALUES (?, 'receipt', ?, ?, ?)",
                    (order_id, f"收款单 {receipt_no} 分配 {allocation_amount:.2f} 元", operator, now),
                )
        return self.get_receipt(receipt_id) or {}

    def reverse_receipt(self, receipt_id: int, operator: str, reason: str) -> Dict:
        if not reason.strip():
            raise ValueError("请填写冲销原因")
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            receipt = connection.execute("SELECT * FROM sales_order_receipts WHERE id=?", (receipt_id,)).fetchone()
            if not receipt:
                raise LookupError("收款单不存在")
            if receipt["status"] == "reversed":
                pass
            else:
                connection.execute(
                    "UPDATE sales_order_receipts SET status='reversed', reversed_by=?, reversed_at=?, remark=CASE WHEN remark='' THEN ? ELSE remark || '；冲销：' || ? END WHERE id=?",
                    (operator, now, reason.strip(), reason.strip(), receipt_id),
                )
                allocations = connection.execute(
                    "SELECT sales_order_id, amount FROM sales_order_receipt_allocations WHERE receipt_id=?", (receipt_id,)
                ).fetchall()
                for allocation in allocations:
                    connection.execute(
                        "INSERT INTO sales_order_events(sales_order_id, event_type, detail, operator, created_at) VALUES (?, 'receipt_reversed', ?, ?, ?)",
                        (allocation["sales_order_id"], f"收款单 {receipt['receipt_no']} 已冲销 {float(allocation['amount']):.2f} 元：{reason.strip()}", operator, now),
                    )
        return self.get_receipt(receipt_id) or {}

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
            receipts = [
                dict(item) for item in connection.execute(
                    """SELECT receipt.*, allocation.amount AS allocation_amount
                       FROM sales_order_receipt_allocations allocation
                       JOIN sales_order_receipts receipt ON receipt.id=allocation.receipt_id
                       WHERE allocation.sales_order_id=? ORDER BY receipt.id DESC""",
                    (order_id,),
                ).fetchall()
            ]
            result["receipts"] = receipts
            paid_amount = round(sum(float(item["allocation_amount"] or 0) for item in receipts if item["status"] == "confirmed"), 2)
            result["paid_amount"] = paid_amount
            result["unpaid_amount"] = max(0.0, round(float(result.get("total_amount") or 0) - paid_amount, 2))
            remaining_paid = paid_amount
            for node in result["payment_nodes"]:
                node_paid = min(float(node.get("due_amount") or 0), remaining_paid)
                node["paid_amount"] = round(node_paid, 2)
                remaining_paid = max(0.0, remaining_paid - node_paid)
                node["status"] = "paid" if node_paid + 0.005 >= float(node.get("due_amount") or 0) else ("partial" if node_paid > 0 else "pending")
            result["charge_lines"] = [
                dict(item) for item in connection.execute(
                    "SELECT * FROM sales_order_charge_lines WHERE sales_order_id = ? ORDER BY line_no", (order_id,)
                ).fetchall()
            ]
            result["events"] = [
                dict(item) for item in connection.execute(
                    "SELECT * FROM sales_order_events WHERE sales_order_id = ? ORDER BY id DESC", (order_id,)
                ).fetchall()
            ]
            return result
