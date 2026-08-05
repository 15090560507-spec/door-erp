"""SQLite persistence for the isolated production-fulfillment module."""

from __future__ import annotations

import base64
import copy
import json
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence
from zoneinfo import ZoneInfo

from config import PRODUCTION_DB_FILE, PRODUCTION_FILES_DIR


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_OPERATIONS = ["下料", "激光/冲孔", "折弯", "焊接组装", "表面处理", "装配", "包装"]


def production_now() -> str:
    return datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def json_loads(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


class ProductionDatabase:
    """Small transactional repository backed by a dedicated SQLite file."""

    def __init__(self, db_path: str = PRODUCTION_DB_FILE, files_dir: str = PRODUCTION_FILES_DIR):
        self.db_path = db_path
        self.files_dir = files_dir
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self.transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS production_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_no TEXT NOT NULL UNIQUE,
                    source_task_id TEXT,
                    source_revision TEXT,
                    source_order_id INTEGER,
                    direct_release INTEGER NOT NULL DEFAULT 1,
                    customer TEXT NOT NULL,
                    project TEXT NOT NULL DEFAULT '',
                    due_date TEXT NOT NULL DEFAULT '',
                    sales_note TEXT NOT NULL DEFAULT '',
                    include_quote INTEGER NOT NULL DEFAULT 0,
                    task_snapshot_json TEXT NOT NULL,
                    quote_snapshot_json TEXT,
                    dxf_path TEXT NOT NULL,
                    stage TEXT NOT NULL DEFAULT 'BOM准备',
                    status TEXT NOT NULL DEFAULT '进行中',
                    shortage_status TEXT NOT NULL DEFAULT '未知',
                    cutting_started INTEGER NOT NULL DEFAULT 0,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    withdrawn_at TEXT,
                    FOREIGN KEY(source_order_id) REFERENCES production_orders(id)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS ux_production_direct_source
                ON production_orders(source_task_id, source_revision)
                WHERE direct_release = 1 AND status != '已作废';

                CREATE TABLE IF NOT EXISTS production_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    operator_uid TEXT NOT NULL,
                    operator_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES production_orders(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS production_materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '其他',
                    material TEXT NOT NULL DEFAULT '',
                    specification TEXT NOT NULL DEFAULT '',
                    thickness TEXT NOT NULL DEFAULT '',
                    unit TEXT NOT NULL DEFAULT '',
                    supplier TEXT NOT NULL DEFAULT '',
                    warehouse_location TEXT NOT NULL DEFAULT '',
                    remark TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS production_bom_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    material_id INTEGER,
                    category TEXT NOT NULL DEFAULT '其他',
                    name TEXT NOT NULL,
                    specification TEXT NOT NULL DEFAULT '',
                    material TEXT NOT NULL DEFAULT '',
                    thickness TEXT NOT NULL DEFAULT '',
                    quantity REAL NOT NULL DEFAULT 0,
                    unit TEXT NOT NULL DEFAULT '',
                    supply_type TEXT NOT NULL DEFAULT '自制',
                    remark TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES production_orders(id) ON DELETE CASCADE,
                    FOREIGN KEY(material_id) REFERENCES production_materials(id)
                );

                CREATE TABLE IF NOT EXISTS production_bom_status (
                    order_id INTEGER PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT '草稿',
                    published_by TEXT,
                    published_at TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES production_orders(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS production_purchase_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    purchase_no TEXT NOT NULL UNIQUE,
                    supplier TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '草稿',
                    expected_date TEXT NOT NULL DEFAULT '',
                    remark TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS production_purchase_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    purchase_id INTEGER NOT NULL,
                    order_id INTEGER,
                    material_id INTEGER,
                    name TEXT NOT NULL,
                    specification TEXT NOT NULL DEFAULT '',
                    quantity REAL NOT NULL DEFAULT 0,
                    received_quantity REAL NOT NULL DEFAULT 0,
                    unit TEXT NOT NULL DEFAULT '',
                    unit_price REAL NOT NULL DEFAULT 0,
                    remark TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(purchase_id) REFERENCES production_purchase_orders(id) ON DELETE CASCADE,
                    FOREIGN KEY(order_id) REFERENCES production_orders(id),
                    FOREIGN KEY(material_id) REFERENCES production_materials(id)
                );

                CREATE TABLE IF NOT EXISTS production_inventory_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_id INTEGER,
                    order_id INTEGER,
                    purchase_id INTEGER,
                    finished_good_id INTEGER,
                    transaction_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    unit TEXT NOT NULL DEFAULT '',
                    warehouse_location TEXT NOT NULL DEFAULT '',
                    remark TEXT NOT NULL DEFAULT '',
                    operator_uid TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(material_id) REFERENCES production_materials(id),
                    FOREIGN KEY(order_id) REFERENCES production_orders(id),
                    FOREIGN KEY(purchase_id) REFERENCES production_purchase_orders(id)
                );

                CREATE TABLE IF NOT EXISTS production_cutting_sheets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT '草稿',
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES production_orders(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS production_cutting_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sheet_id INTEGER NOT NULL,
                    bom_item_id INTEGER,
                    name TEXT NOT NULL,
                    specification TEXT NOT NULL DEFAULT '',
                    quantity REAL NOT NULL DEFAULT 0,
                    actual_quantity REAL NOT NULL DEFAULT 0,
                    unit TEXT NOT NULL DEFAULT '',
                    cutter TEXT NOT NULL DEFAULT '',
                    completed INTEGER NOT NULL DEFAULT 0,
                    remark TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(sheet_id) REFERENCES production_cutting_sheets(id) ON DELETE CASCADE,
                    FOREIGN KEY(bom_item_id) REFERENCES production_bom_items(id)
                );

                CREATE TABLE IF NOT EXISTS production_schedules (
                    order_id INTEGER PRIMARY KEY,
                    planned_start TEXT NOT NULL DEFAULT '',
                    planned_end TEXT NOT NULL DEFAULT '',
                    producer TEXT NOT NULL DEFAULT '',
                    shortage_status TEXT NOT NULL DEFAULT '未知',
                    owner TEXT NOT NULL DEFAULT '',
                    updated_by TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES production_orders(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS production_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    sequence_no INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '待开始',
                    operator_name TEXT NOT NULL DEFAULT '',
                    started_at TEXT,
                    completed_at TEXT,
                    remark TEXT NOT NULL DEFAULT '',
                    UNIQUE(order_id, sequence_no),
                    FOREIGN KEY(order_id) REFERENCES production_orders(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS production_quality_inspections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    result TEXT NOT NULL,
                    inspector TEXT NOT NULL,
                    return_operation TEXT NOT NULL DEFAULT '',
                    photos_json TEXT NOT NULL DEFAULT '[]',
                    remark TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES production_orders(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS production_finished_goods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    finished_no TEXT NOT NULL UNIQUE,
                    order_id INTEGER NOT NULL UNIQUE,
                    warehouse_location TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '已入库',
                    inbound_by TEXT NOT NULL,
                    inbound_at TEXT NOT NULL,
                    outbound_at TEXT,
                    FOREIGN KEY(order_id) REFERENCES production_orders(id)
                );

                CREATE TABLE IF NOT EXISTS production_shipments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shipment_no TEXT NOT NULL UNIQUE,
                    customer TEXT NOT NULL,
                    project TEXT NOT NULL DEFAULT '',
                    address TEXT NOT NULL DEFAULT '',
                    contact TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    logistics TEXT NOT NULL DEFAULT '',
                    tracking_no TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '待发货',
                    photos_json TEXT NOT NULL DEFAULT '[]',
                    remark TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS production_shipment_items (
                    shipment_id INTEGER NOT NULL,
                    order_id INTEGER NOT NULL UNIQUE,
                    finished_good_id INTEGER NOT NULL,
                    PRIMARY KEY(shipment_id, order_id),
                    FOREIGN KEY(shipment_id) REFERENCES production_shipments(id) ON DELETE CASCADE,
                    FOREIGN KEY(order_id) REFERENCES production_orders(id),
                    FOREIGN KEY(finished_good_id) REFERENCES production_finished_goods(id)
                );
                """
            )

    def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        with self.transaction() as conn:
            cursor = conn.execute(sql, params)
            return int(cursor.lastrowid or 0)

    @staticmethod
    def _next_number(conn: sqlite3.Connection, table: str, field: str, prefix: str) -> str:
        row = conn.execute(
            f"SELECT {field} FROM {table} WHERE {field} LIKE ? ORDER BY {field} DESC LIMIT 1",
            (f"{prefix}%",),
        ).fetchone()
        suffix = int(str(row[field])[-3:]) + 1 if row else 1
        return f"{prefix}{suffix:03d}"

    def create_order(
        self,
        *,
        source_task_id: str,
        source_revision: str,
        customer: str,
        project: str,
        due_date: str,
        sales_note: str,
        include_quote: bool,
        task_snapshot: Dict[str, Any],
        quote_snapshot: Optional[Dict[str, Any]],
        dxf_bytes: bytes,
        created_by: str,
        direct_release: bool = True,
        source_order_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        now = production_now()
        date_prefix = datetime.now(SHANGHAI_TZ).strftime("SC%Y%m%d")
        with self.transaction() as conn:
            order_no = self._next_number(conn, "production_orders", "order_no", date_prefix)
            order_dir = Path(self.files_dir) / order_no
            order_dir.mkdir(parents=True, exist_ok=False)
            dxf_path = order_dir / "approved.dxf"
            snapshot_path = order_dir / "task_snapshot.json"
            try:
                stored_snapshot = self._persist_snapshot_assets(order_no, order_dir, task_snapshot)
                dxf_path.write_bytes(dxf_bytes)
                snapshot_path.write_text(json.dumps(stored_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
                cursor = conn.execute(
                    """
                    INSERT INTO production_orders (
                        order_no, source_task_id, source_revision, source_order_id, direct_release,
                        customer, project, due_date, sales_note, include_quote,
                        task_snapshot_json, quote_snapshot_json, dxf_path,
                        created_by, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_no, source_task_id, source_revision, source_order_id, int(direct_release),
                        customer, project, due_date, sales_note, int(include_quote),
                        json_dumps(stored_snapshot), json_dumps(quote_snapshot) if quote_snapshot else None,
                        str(dxf_path.relative_to(self.files_dir)), created_by, now, now,
                    ),
                )
                order_id = int(cursor.lastrowid)
                conn.execute(
                    "INSERT INTO production_bom_status(order_id, status, updated_at) VALUES (?, '草稿', ?)",
                    (order_id, now),
                )
                conn.executemany(
                    "INSERT INTO production_operations(order_id, sequence_no, name) VALUES (?, ?, ?)",
                    [(order_id, index + 1, name) for index, name in enumerate(DEFAULT_OPERATIONS)],
                )
                conn.execute(
                    """
                    INSERT INTO production_events(order_id, action, detail, operator_uid, operator_name, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (order_id, "下达生产订单" if direct_release else "复制生产订单", "", created_by, created_by, now),
                )
            except Exception:
                shutil.rmtree(order_dir, ignore_errors=True)
                raise
        return self.get_order(order_id) or {}

    def _persist_snapshot_assets(
        self, order_no: str, order_dir: Path, task_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        snapshot = copy.deepcopy(task_snapshot)

        def save_image(value: Any, filename: str) -> Any:
            if not isinstance(value, str) or len(value) < 200:
                return value
            encoded = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
            try:
                image_bytes = base64.b64decode(encoded)
            except Exception:
                return value
            path = order_dir / filename
            path.write_bytes(image_bytes)
            return str(path.relative_to(self.files_dir))

        snapshot["drawing_img_b64"] = save_image(snapshot.get("drawing_img_b64"), "drawing.png")
        references = snapshot.get("ref_images")
        if isinstance(references, list):
            snapshot["ref_images"] = [
                save_image(value, f"reference_{index + 1}.png") for index, value in enumerate(references)
            ]
        return snapshot

    def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        order = self.fetch_one("SELECT * FROM production_orders WHERE id = ?", (order_id,))
        if not order:
            return None
        order["task_snapshot"] = json_loads(order.pop("task_snapshot_json", None), {})
        order["quote_snapshot"] = json_loads(order.pop("quote_snapshot_json", None), None)
        order["include_quote"] = bool(order.get("include_quote"))
        order["cutting_started"] = bool(order.get("cutting_started"))
        order["direct_release"] = bool(order.get("direct_release"))
        return order

    def list_orders(
        self,
        stage: str = "",
        status: str = "",
        query: str = "",
        owner: str = "",
        shortage: str = "",
        due_from: str = "",
        due_to: str = "",
    ) -> List[Dict[str, Any]]:
        where: List[str] = []
        params: List[Any] = []
        if stage == "缺料":
            where.append("o.shortage_status = '缺料'")
        elif stage:
            where.append("o.stage = ?")
            params.append(stage)
        if status:
            where.append("o.status = ?")
            params.append(status)
        if query:
            where.append("(o.order_no LIKE ? OR o.customer LIKE ? OR o.project LIKE ?)")
            term = f"%{query}%"
            params.extend([term, term, term])
        if owner:
            where.append("s.owner = ?")
            params.append(owner)
        if shortage:
            where.append("o.shortage_status = ?")
            params.append(shortage)
        if due_from:
            where.append("o.due_date >= ?")
            params.append(due_from)
        if due_to:
            where.append("o.due_date <= ?")
            params.append(due_to)
        sql = """
            SELECT o.*, COALESCE(s.owner, '') AS owner,
                   COALESCE(s.producer, '') AS producer,
                   COALESCE(s.planned_start, '') AS planned_start,
                   COALESCE(s.planned_end, '') AS planned_end
            FROM production_orders o
            LEFT JOIN production_schedules s ON s.order_id = o.id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY o.id DESC"
        rows = self.fetch_all(sql, params)
        for row in rows:
            row.pop("task_snapshot_json", None)
            row.pop("quote_snapshot_json", None)
            row["include_quote"] = bool(row.get("include_quote"))
            row["cutting_started"] = bool(row.get("cutting_started"))
        return rows

    def add_event(self, order_id: int, action: str, detail: str, user: Dict[str, Any]) -> None:
        self.execute(
            """
            INSERT INTO production_events(order_id, action, detail, operator_uid, operator_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (order_id, action, detail, user.get("uid", ""), user.get("name", user.get("uid", "")), production_now()),
        )

    def events(self, order_id: int) -> List[Dict[str, Any]]:
        return self.fetch_all(
            "SELECT * FROM production_events WHERE order_id = ? ORDER BY id DESC", (order_id,)
        )

    def timeline(self, order_id: int) -> List[Dict[str, Any]]:
        return [
            {
                "id": f"event-{row['id']}",
                "type": "event",
                "title": row["action"],
                "detail": row["detail"],
                "operator": row["operator_name"],
                "created_at": row["created_at"],
            }
            for row in self.events(order_id)
        ]

    def update_order(self, order_id: int, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {"stage", "status", "shortage_status", "due_date", "sales_note", "cutting_started", "withdrawn_at"}
        data = {key: value for key, value in values.items() if key in allowed}
        if not data:
            return self.get_order(order_id) or {}
        data["updated_at"] = production_now()
        assignments = ", ".join(f"{key} = ?" for key in data)
        self.execute(f"UPDATE production_orders SET {assignments} WHERE id = ?", [*data.values(), order_id])
        return self.get_order(order_id) or {}

    def dashboard(self) -> Dict[str, int]:
        rows = self.fetch_all(
            "SELECT stage, COUNT(*) AS count FROM production_orders WHERE status = '进行中' GROUP BY stage"
        )
        result = {row["stage"]: int(row["count"]) for row in rows}
        result["缺料"] = int(
            (self.fetch_one(
                "SELECT COUNT(*) AS count FROM production_orders WHERE status = '进行中' AND shortage_status = '缺料'"
            ) or {"count": 0})["count"]
        )
        result["完成"] = int(
            (self.fetch_one(
                "SELECT COUNT(*) AS count FROM production_orders WHERE status = '已完成'"
            ) or {"count": 0})["count"]
        )
        today = datetime.now(SHANGHAI_TZ).date()
        near_due = today + timedelta(days=3)
        active_clause = "status NOT IN ('已完成', '已作废', '已撤回')"
        result["今日下达"] = int(
            (self.fetch_one(
                "SELECT COUNT(*) AS count FROM production_orders WHERE substr(created_at, 1, 10)=?",
                (today.isoformat(),),
            ) or {"count": 0})["count"]
        )
        result["即将到期"] = int(
            (self.fetch_one(
                f"""
                SELECT COUNT(*) AS count FROM production_orders
                WHERE {active_clause} AND due_date >= ? AND due_date <= ?
                """,
                (today.isoformat(), near_due.isoformat()),
            ) or {"count": 0})["count"]
        )
        result["已逾期"] = int(
            (self.fetch_one(
                f"""
                SELECT COUNT(*) AS count FROM production_orders
                WHERE {active_clause} AND due_date != '' AND due_date < ?
                """,
                (today.isoformat(),),
            ) or {"count": 0})["count"]
        )
        return result
