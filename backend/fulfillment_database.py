"""Transactional SQLite repository for the new door-unit fulfillment center."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Sequence
from zoneinfo import ZoneInfo

from config import FULFILLMENT_DB_FILE, FULFILLMENT_FILES_DIR
from inventory_database import InventoryDatabase
from requirement_service import RequirementService


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
DOOR_STATUSES = (
    "待生产确认", "技术准备中", "备料与加工中", "可局部装配", "总装中",
    "待成品质检", "返工中", "待成品入库", "已入库待发货", "待财务放行",
    "待出库", "运输中", "已签收",
)
WORK_STATUSES = ("草稿", "待排单", "已排单", "进行中", "待质检", "已完成", "暂停", "异常", "返工", "已取消")
WORK_TRANSITIONS = {
    "待排单": {"已排单", "进行中", "待质检", "暂停", "已取消"},
    "已排单": {"进行中", "待质检", "暂停", "已取消"},
    "进行中": {"待质检", "已完成", "暂停", "异常"},
    "待质检": {"已完成", "返工", "异常"},
    "返工": {"进行中", "待质检", "已完成", "异常"},
    "暂停": {"待排单", "已排单", "进行中", "已取消"},
    "异常": {"待排单", "进行中", "暂停", "已取消"},
}


def fulfillment_now() -> str:
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


class FulfillmentDatabase:
    def __init__(self, db_path: str = FULFILLMENT_DB_FILE, files_dir: str = FULFILLMENT_FILES_DIR):
        self.db_path = db_path
        self.files_dir = files_dir
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)
        self._initialize()
        self.inventory_db = InventoryDatabase(db_path)
        self.requirement_service = RequirementService(self.inventory_db)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
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
                CREATE TABLE IF NOT EXISTS fulfillment_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_no TEXT NOT NULL UNIQUE,
                    source_task_id TEXT NOT NULL,
                    source_revision TEXT NOT NULL,
                    customer TEXT NOT NULL,
                    project TEXT NOT NULL DEFAULT '',
                    due_date TEXT NOT NULL DEFAULT '',
                    sales_note TEXT NOT NULL DEFAULT '',
                    task_snapshot_json TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '进行中'
                );

                CREATE UNIQUE INDEX IF NOT EXISTS ux_fulfillment_source
                ON fulfillment_orders(source_task_id, source_revision)
                WHERE status != '已作废';

                CREATE TABLE IF NOT EXISTS fulfillment_door_units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    production_no TEXT NOT NULL UNIQUE,
                    sequence_no INTEGER NOT NULL,
                    product_name TEXT NOT NULL DEFAULT '',
                    specification TEXT NOT NULL DEFAULT '',
                    opening TEXT NOT NULL DEFAULT '',
                    due_date TEXT NOT NULL DEFAULT '',
                    owner_uid TEXT NOT NULL DEFAULT '',
                    technical_uid TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '待生产确认',
                    progress INTEGER NOT NULL DEFAULT 0,
                    active_version INTEGER NOT NULL DEFAULT 0,
                    risk_tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES fulfillment_orders(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS fulfillment_technical_packages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    door_unit_id INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT '草稿',
                    product_snapshot_json TEXT NOT NULL,
                    product_summary TEXT NOT NULL DEFAULT '',
                    special_requirements TEXT NOT NULL DEFAULT '',
                    source_version_id INTEGER,
                    created_by TEXT NOT NULL,
                    confirmed_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    confirmed_at TEXT,
                    UNIQUE(door_unit_id, version),
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE,
                    FOREIGN KEY(source_version_id) REFERENCES fulfillment_technical_packages(id)
                );

                CREATE TABLE IF NOT EXISTS fulfillment_components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    technical_package_id INTEGER NOT NULL,
                    parent_id INTEGER,
                    material_id INTEGER,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '其他',
                    specification TEXT NOT NULL DEFAULT '',
                    quantity REAL NOT NULL DEFAULT 1,
                    unit TEXT NOT NULL DEFAULT '件',
                    acquisition_method TEXT NOT NULL DEFAULT '待确定',
                    remark TEXT NOT NULL DEFAULT '',
                    sequence_no INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(technical_package_id) REFERENCES fulfillment_technical_packages(id) ON DELETE CASCADE,
                    FOREIGN KEY(parent_id) REFERENCES fulfillment_components(id)
                );

                CREATE TABLE IF NOT EXISTS fulfillment_work_packages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    technical_package_id INTEGER NOT NULL,
                    door_unit_id INTEGER NOT NULL,
                    component_id INTEGER,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '生产',
                    route TEXT NOT NULL DEFAULT '',
                    acquisition_method TEXT NOT NULL DEFAULT '内部加工',
                    executor_uid TEXT NOT NULL DEFAULT '',
                    planned_start TEXT NOT NULL DEFAULT '',
                    planned_end TEXT NOT NULL DEFAULT '',
                    opening_condition TEXT NOT NULL DEFAULT '技术包确认',
                    blocking_node TEXT NOT NULL DEFAULT '',
                    quantity REAL NOT NULL DEFAULT 1,
                    actual_quantity REAL NOT NULL DEFAULT 0,
                    unit TEXT NOT NULL DEFAULT '项',
                    piece_rate REAL NOT NULL DEFAULT 0,
                    inspection_required INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT '草稿',
                    remark TEXT NOT NULL DEFAULT '',
                    sequence_no INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(technical_package_id) REFERENCES fulfillment_technical_packages(id) ON DELETE CASCADE,
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE,
                    FOREIGN KEY(component_id) REFERENCES fulfillment_components(id)
                );

                CREATE TABLE IF NOT EXISTS fulfillment_exceptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    door_unit_id INTEGER NOT NULL,
                    work_package_id INTEGER,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    severity TEXT NOT NULL DEFAULT '一般',
                    owner_uid TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '待处理',
                    resolution TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_by TEXT,
                    resolved_at TEXT,
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE,
                    FOREIGN KEY(work_package_id) REFERENCES fulfillment_work_packages(id)
                );

                CREATE TABLE IF NOT EXISTS fulfillment_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    door_unit_id INTEGER NOT NULL,
                    change_no TEXT NOT NULL UNIQUE,
                    from_version INTEGER NOT NULL,
                    to_version INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    impact_note TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '待评估',
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS fulfillment_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER,
                    door_unit_id INTEGER,
                    entity_type TEXT NOT NULL,
                    entity_id INTEGER,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    operator_uid TEXT NOT NULL,
                    operator_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES fulfillment_orders(id) ON DELETE CASCADE,
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS fulfillment_supplies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    door_unit_id INTEGER NOT NULL,
                    technical_package_id INTEGER NOT NULL,
                    component_id INTEGER,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '其他',
                    specification TEXT NOT NULL DEFAULT '',
                    required_quantity REAL NOT NULL DEFAULT 1,
                    actual_quantity REAL NOT NULL DEFAULT 0,
                    unit TEXT NOT NULL DEFAULT '件',
                    acquisition_method TEXT NOT NULL DEFAULT '待确定',
                    handler_uid TEXT NOT NULL DEFAULT '',
                    supplier TEXT NOT NULL DEFAULT '',
                    unit_cost REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT '待处理',
                    remark TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE,
                    FOREIGN KEY(technical_package_id) REFERENCES fulfillment_technical_packages(id) ON DELETE CASCADE,
                    FOREIGN KEY(component_id) REFERENCES fulfillment_components(id)
                );

                CREATE TABLE IF NOT EXISTS fulfillment_inspections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    door_unit_id INTEGER NOT NULL,
                    inspection_type TEXT NOT NULL,
                    target_name TEXT NOT NULL DEFAULT '',
                    quantity REAL NOT NULL DEFAULT 1,
                    result TEXT NOT NULL,
                    defect_detail TEXT NOT NULL DEFAULT '',
                    remark TEXT NOT NULL DEFAULT '',
                    inspector_uid TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS fulfillment_inventory_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    door_unit_id INTEGER NOT NULL,
                    movement_type TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    warehouse TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    quantity REAL NOT NULL DEFAULT 1,
                    unit TEXT NOT NULL DEFAULT '樘',
                    remark TEXT NOT NULL DEFAULT '',
                    operator_uid TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS fulfillment_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    payment_date TEXT NOT NULL DEFAULT '',
                    reference TEXT NOT NULL DEFAULT '',
                    remark TEXT NOT NULL DEFAULT '',
                    recorded_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES fulfillment_orders(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS fulfillment_shipments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    door_unit_id INTEGER NOT NULL,
                    required_payment REAL NOT NULL DEFAULT 0,
                    paid_amount REAL NOT NULL DEFAULT 0,
                    authorized INTEGER NOT NULL DEFAULT 0,
                    authorization_reason TEXT NOT NULL DEFAULT '',
                    authorized_by TEXT NOT NULL DEFAULT '',
                    carrier TEXT NOT NULL DEFAULT '',
                    vehicle_no TEXT NOT NULL DEFAULT '',
                    contact TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '运输中',
                    remark TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    signed_by TEXT NOT NULL DEFAULT '',
                    signed_at TEXT,
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS fulfillment_payroll_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    door_unit_id INTEGER NOT NULL,
                    work_package_id INTEGER NOT NULL UNIQUE,
                    employee_uid TEXT NOT NULL,
                    work_name TEXT NOT NULL,
                    quantity REAL NOT NULL DEFAULT 0,
                    piece_rate REAL NOT NULL DEFAULT 0,
                    amount REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT '待审核',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE,
                    FOREIGN KEY(work_package_id) REFERENCES fulfillment_work_packages(id) ON DELETE CASCADE
                );
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(fulfillment_components)").fetchall()}
            if "material_id" not in columns:
                conn.execute("ALTER TABLE fulfillment_components ADD COLUMN material_id INTEGER")

    def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def _next_order_no(self, conn: sqlite3.Connection, now: str) -> str:
        prefix = f"DD{now[:10].replace('-', '')}"
        row = conn.execute("SELECT order_no FROM fulfillment_orders WHERE order_no LIKE ? ORDER BY order_no DESC LIMIT 1", (f"{prefix}%",)).fetchone()
        sequence = int(row["order_no"][-3:]) + 1 if row else 1
        return f"{prefix}{sequence:03d}"

    def add_event(self, conn: sqlite3.Connection, *, order_id: Optional[int], door_unit_id: Optional[int], entity_type: str, entity_id: Optional[int], action: str, detail: str, user: Dict[str, Any]) -> None:
        conn.execute(
            """INSERT INTO fulfillment_events(order_id, door_unit_id, entity_type, entity_id, action, detail, operator_uid, operator_name, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (order_id, door_unit_id, entity_type, entity_id, action, detail, str(user.get("uid") or ""), str(user.get("name") or user.get("uid") or ""), fulfillment_now()),
        )

    def source_is_released(self, task_id: str, revision: str) -> bool:
        return bool(self.fetch_one("SELECT id FROM fulfillment_orders WHERE source_task_id=? AND source_revision=? AND status!='已作废'", (task_id, revision)))

    def create_from_task(self, task: Dict[str, Any], revision: str, request: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        params = task.get("params") or {}
        customer = str(params.get("dhdw") or task.get("customer") or "").strip()
        if not customer:
            raise ValueError("订货单位不能为空")
        with self.transaction() as conn:
            order_no = self._next_order_no(conn, now)
            cursor = conn.execute(
                """INSERT INTO fulfillment_orders(order_no, source_task_id, source_revision, customer, project, due_date, sales_note, task_snapshot_json, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (order_no, str(task.get("id") or ""), revision, customer, str(params.get("gdmc") or task.get("project") or ""), request.due_date, request.sales_note, json_dumps(task), str(user.get("uid") or ""), now, now),
            )
            order_id = int(cursor.lastrowid)
            for index in range(1, request.door_count + 1):
                production_no = f"{order_no}-{index:02d}"
                specification = f"{params.get('dw') or ''} x {params.get('dh') or ''}".strip(" x")
                door_cursor = conn.execute(
                    """INSERT INTO fulfillment_door_units(order_id, production_no, sequence_no, product_name, specification, opening, due_date, owner_uid, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (order_id, production_no, index, str(params.get("product_name") or params.get("door_type") or "门"), specification, f"{params.get('sel_kx') or ''}{params.get('sel_nk') or ''}", request.due_date, request.owner_uid, now, now),
                )
                door_id = int(door_cursor.lastrowid)
                package_cursor = conn.execute(
                    """INSERT INTO fulfillment_technical_packages(door_unit_id, version, product_snapshot_json, product_summary, created_by, created_at, updated_at)
                       VALUES (?, 1, ?, ?, ?, ?, ?)""",
                    (door_id, json_dumps(params), self._default_product_summary(params), str(user.get("uid") or ""), now, now),
                )
                package_id = int(package_cursor.lastrowid)
                self._seed_components(conn, package_id, params)
                self._seed_work_packages(conn, package_id, door_id, now)
                self.add_event(conn, order_id=order_id, door_unit_id=door_id, entity_type="door_unit", entity_id=door_id, action="创建门樘生产单", detail=f"创建技术包草稿 V1", user=user)
            self.add_event(conn, order_id=order_id, door_unit_id=None, entity_type="order", entity_id=order_id, action="下达客户订单", detail=f"共 {request.door_count} 樘门", user=user)
        return self.get_order(order_id) or {}

    @staticmethod
    def _default_product_summary(params: Dict[str, Any]) -> str:
        values = [params.get("product_name"), params.get("door_type"), params.get("zzcl"), params.get("zmks"), params.get("fmks")]
        return " / ".join(str(value) for value in values if value)

    def _seed_components(self, conn: sqlite3.Connection, package_id: int, params: Dict[str, Any]) -> None:
        defaults = [
            ("门扇与面板", "门体", "内部加工"), ("门框", "门框", "内部加工"),
            ("锁具与拉手", "配件", "库存/采购"), ("合页与五金", "配件", "库存/采购"),
            ("玻璃与花件", "装饰件", "待确定"), ("包装", "包装", "内部加工"),
        ]
        for sequence, (name, category, method) in enumerate(defaults, start=1):
            conn.execute(
                """INSERT INTO fulfillment_components(technical_package_id, name, category, quantity, unit, acquisition_method, sequence_no)
                   VALUES (?, ?, ?, 1, '套', ?, ?)""", (package_id, name, category, method, sequence),
            )

    def _seed_work_packages(self, conn: sqlite3.Connection, package_id: int, door_id: int, now: str) -> None:
        defaults = [
            ("材料与配件确认", "技术准备", "清单确认", "待确定"),
            ("板件下料与折弯", "内部加工", "下料 → 折弯", "内部加工"),
            ("骨架与门体制作", "内部加工", "备料 → 焊接 → 校正", "内部加工"),
            ("表面与装饰处理", "表面处理", "外协/内部处理", "待确定"),
            ("预拼接与总装", "装配", "预拼接 → 补件 → 总装", "内部加工"),
            ("包装准备", "包装", "包装", "内部加工"),
        ]
        for sequence, (name, category, route, method) in enumerate(defaults, start=1):
            conn.execute(
                """INSERT INTO fulfillment_work_packages(technical_package_id, door_unit_id, name, category, route, acquisition_method, sequence_no, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (package_id, door_id, name, category, route, method, sequence, now),
            )

    def list_orders(self, q: str = "", status: str = "") -> List[Dict[str, Any]]:
        where = ["1=1"]
        params: List[Any] = []
        if q:
            where.append("(o.order_no LIKE ? OR o.customer LIKE ? OR o.project LIKE ? OR d.production_no LIKE ?)")
            term = f"%{q}%"
            params.extend([term, term, term, term])
        if status:
            where.append("d.status=?")
            params.append(status)
        rows = self.fetch_all(
            f"""SELECT o.*, COUNT(d.id) AS door_count,
                SUM(CASE WHEN d.status='已签收' THEN 1 ELSE 0 END) AS completed_count,
                CASE MIN(CASE d.status
                    WHEN '待生产确认' THEN 10 WHEN '技术准备中' THEN 20
                    WHEN '备料与加工中' THEN 30 WHEN '可局部装配' THEN 40
                    WHEN '总装中' THEN 50 WHEN '待成品质检' THEN 60
                    WHEN '返工中' THEN 65 WHEN '待成品入库' THEN 70
                    WHEN '已入库待发货' THEN 80 WHEN '待财务放行' THEN 85
                    WHEN '待出库' THEN 90 WHEN '运输中' THEN 95
                    WHEN '已签收' THEN 100 ELSE 999 END)
                    WHEN 10 THEN '待生产确认' WHEN 20 THEN '技术准备中'
                    WHEN 30 THEN '备料与加工中' WHEN 40 THEN '可局部装配'
                    WHEN 50 THEN '总装中' WHEN 60 THEN '待成品质检'
                    WHEN 65 THEN '返工中' WHEN 70 THEN '待成品入库'
                    WHEN 80 THEN '已入库待发货' WHEN 85 THEN '待财务放行'
                    WHEN 90 THEN '待出库' WHEN 95 THEN '运输中'
                    WHEN 100 THEN '已签收' ELSE '未知' END AS representative_status,
                CAST(AVG(d.progress) AS INTEGER) AS progress
                FROM fulfillment_orders o JOIN fulfillment_door_units d ON d.order_id=o.id
                WHERE {' AND '.join(where)} GROUP BY o.id ORDER BY o.created_at DESC""", params,
        )
        return rows

    def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        order = self.fetch_one("SELECT * FROM fulfillment_orders WHERE id=?", (order_id,))
        if not order:
            return None
        order["task_snapshot"] = json_loads(order.pop("task_snapshot_json", ""), {})
        order["door_units"] = self.fetch_all("SELECT * FROM fulfillment_door_units WHERE order_id=? ORDER BY sequence_no", (order_id,))
        for door in order["door_units"]:
            door["risk_tags"] = json_loads(door.pop("risk_tags_json", ""), [])
        return order

    def get_door_unit(self, door_id: int) -> Optional[Dict[str, Any]]:
        door = self.fetch_one(
            """SELECT d.*, o.order_no, o.customer, o.project, o.sales_note, o.created_by
               FROM fulfillment_door_units d JOIN fulfillment_orders o ON o.id=d.order_id WHERE d.id=?""", (door_id,),
        )
        if not door:
            return None
        door["risk_tags"] = json_loads(door.pop("risk_tags_json", ""), [])
        package = self.fetch_one("SELECT * FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1", (door_id,))
        if package:
            package["product_snapshot"] = json_loads(package.pop("product_snapshot_json", ""), {})
            package["components"] = self.fetch_all(
                """SELECT c.*, m.code AS material_code, m.name AS material_name,
                          m.specification AS material_specification, m.unit AS material_unit
                   FROM fulfillment_components c
                   LEFT JOIN inventory_materials m ON m.id=c.material_id
                   WHERE c.technical_package_id=? ORDER BY c.sequence_no, c.id""",
                (package["id"],),
            )
            package["work_packages"] = self.fetch_all("SELECT * FROM fulfillment_work_packages WHERE technical_package_id=? ORDER BY sequence_no, id", (package["id"],))
        door["unfinished_work_packages"] = [
            {"id": item["id"], "name": item["name"], "status": item["status"]}
            for item in (package.get("work_packages", []) if package else [])
            if item["status"] not in {"已完成", "已取消"}
        ]
        door["technical_package"] = package
        door["exceptions"] = self.fetch_all("SELECT * FROM fulfillment_exceptions WHERE door_unit_id=? ORDER BY created_at DESC", (door_id,))
        door["changes"] = self.fetch_all("SELECT * FROM fulfillment_changes WHERE door_unit_id=? ORDER BY created_at DESC", (door_id,))
        door["supplies"] = self.fetch_all(
            "SELECT * FROM fulfillment_supplies WHERE door_unit_id=? AND technical_package_id=? ORDER BY id",
            (door_id, package["id"] if package else -1),
        )
        requirement = self.fetch_one(
            "SELECT id FROM material_requirements WHERE technical_package_id=? ORDER BY id DESC LIMIT 1",
            (package["id"] if package else -1,),
        )
        door["material_requirement"] = (
            self.requirement_service.get_requirement(int(requirement["id"]))
            if requirement
            else None
        )
        door["inspections"] = self.fetch_all("SELECT * FROM fulfillment_inspections WHERE door_unit_id=? ORDER BY created_at DESC, id DESC", (door_id,))
        door["inventory_movements"] = self.fetch_all("SELECT * FROM fulfillment_inventory_movements WHERE door_unit_id=? ORDER BY created_at DESC, id DESC", (door_id,))
        door["shipments"] = self.fetch_all("SELECT * FROM fulfillment_shipments WHERE door_unit_id=? ORDER BY created_at DESC, id DESC", (door_id,))
        door["payroll_drafts"] = self.fetch_all("SELECT * FROM fulfillment_payroll_drafts WHERE door_unit_id=? ORDER BY id", (door_id,))
        paid = self.fetch_one("SELECT COALESCE(SUM(p.amount), 0) AS total FROM fulfillment_payments p JOIN fulfillment_orders o ON o.id=p.order_id JOIN fulfillment_door_units d ON d.order_id=o.id WHERE d.id=?", (door_id,))
        door["paid_amount"] = float((paid or {"total": 0})["total"] or 0)
        allocated = self.fetch_one(
            """SELECT COALESCE(SUM(s.required_payment), 0) AS total
               FROM fulfillment_shipments s JOIN fulfillment_door_units d2 ON d2.id=s.door_unit_id
               WHERE d2.order_id=(SELECT order_id FROM fulfillment_door_units WHERE id=?) AND s.authorized=0""",
            (door_id,),
        )
        door["allocated_payment"] = float((allocated or {"total": 0})["total"] or 0)
        door["available_payment"] = max(0.0, door["paid_amount"] - door["allocated_payment"])
        door["events"] = self.fetch_all("SELECT * FROM fulfillment_events WHERE door_unit_id=? ORDER BY created_at DESC, id DESC LIMIT 100", (door_id,))
        return door

    def dashboard(self) -> Dict[str, Any]:
        counts = {status: 0 for status in DOOR_STATUSES}
        for row in self.fetch_all("SELECT status, COUNT(*) AS total FROM fulfillment_door_units GROUP BY status"):
            counts[row["status"]] = row["total"]
        return {
            "status_counts": counts,
            "open_exceptions": (self.fetch_one("SELECT COUNT(*) AS total FROM fulfillment_exceptions WHERE status!='已解决'") or {"total": 0})["total"],
            "due_risks": (self.fetch_one("SELECT COUNT(*) AS total FROM fulfillment_door_units WHERE status!='已签收' AND due_date!='' AND due_date < date('now', '+7 day')") or {"total": 0})["total"],
        }

    def save_technical_package(self, door_id: int, payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            package = conn.execute("SELECT * FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1", (door_id,)).fetchone()
            if not package:
                raise LookupError("生产技术包不存在")
            if package["status"] != "草稿":
                raise RuntimeError("技术包已确认冻结，请通过生产变更单创建新版本")
            package_id = int(package["id"])
            conn.execute("UPDATE fulfillment_technical_packages SET product_summary=?, special_requirements=?, updated_at=? WHERE id=?", (payload.product_summary, payload.special_requirements, now, package_id))
            conn.execute("DELETE FROM fulfillment_work_packages WHERE technical_package_id=?", (package_id,))
            conn.execute("DELETE FROM fulfillment_components WHERE technical_package_id=?", (package_id,))
            component_ids: Dict[int, int] = {}
            for sequence, item in enumerate(payload.components, start=1):
                parent_id = component_ids.get(item.parent_id or -1)
                cursor = conn.execute(
                    """INSERT INTO fulfillment_components(technical_package_id, parent_id, material_id, name, category, specification, quantity, unit, acquisition_method, remark, sequence_no)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (package_id, parent_id, item.material_id, item.name.strip(), item.category, item.specification, item.quantity, item.unit, item.acquisition_method, item.remark, sequence),
                )
                if item.id is not None:
                    component_ids[item.id] = int(cursor.lastrowid)
            for sequence, item in enumerate(payload.work_packages, start=1):
                conn.execute(
                    """INSERT INTO fulfillment_work_packages(technical_package_id, door_unit_id, component_id, name, category, route, acquisition_method, executor_uid, planned_start, planned_end, opening_condition, blocking_node, quantity, unit, piece_rate, inspection_required, remark, sequence_no, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (package_id, door_id, component_ids.get(item.component_id or -1), item.name.strip(), item.category, item.route, item.acquisition_method, item.executor_uid, item.planned_start, item.planned_end, item.opening_condition, item.blocking_node, item.quantity, item.unit, item.piece_rate, int(item.inspection_required), item.remark, sequence, now),
                )
            conn.execute(
                """UPDATE fulfillment_door_units
                   SET technical_uid=?, status=CASE WHEN status='待生产确认' THEN '技术准备中' ELSE status END, updated_at=?
                   WHERE id=?""",
                (str(user.get("uid") or ""), now, door_id),
            )
            self.add_event(conn, order_id=None, door_unit_id=door_id, entity_type="technical_package", entity_id=package_id, action="保存技术包草稿", detail=f"构件 {len(payload.components)} 项，工作包 {len(payload.work_packages)} 项", user=user)
        return self.get_door_unit(door_id) or {}

    def confirm_technical_package(self, door_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            package = conn.execute("SELECT * FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1", (door_id,)).fetchone()
            if not package:
                raise LookupError("生产技术包不存在")
            if package["status"] != "草稿":
                raise RuntimeError("技术包已经确认")
            package_id = int(package["id"])
            components = conn.execute("SELECT COUNT(*) AS total FROM fulfillment_components WHERE technical_package_id=?", (package_id,)).fetchone()["total"]
            work_count = conn.execute("SELECT COUNT(*) AS total FROM fulfillment_work_packages WHERE technical_package_id=?", (package_id,)).fetchone()["total"]
            if not components or not work_count:
                raise ValueError("技术包必须至少包含一个构件和一个工作包")
            requirement = self.requirement_service.create_for_package(
                conn=conn,
                door_id=door_id,
                package_id=package_id,
                created_by=str(user.get("uid") or ""),
            )
            conn.execute("UPDATE fulfillment_technical_packages SET status='已确认', confirmed_by=?, confirmed_at=?, updated_at=? WHERE id=?", (str(user.get("uid") or ""), now, now, package_id))
            conn.execute("UPDATE fulfillment_work_packages SET status='待排单', updated_at=? WHERE technical_package_id=? AND status='草稿'", (now, package_id))
            conn.execute(
                """UPDATE fulfillment_supplies SET status='已取消', remark=CASE WHEN remark='' THEN '技术版本已变更' ELSE remark END, updated_at=?
                   WHERE door_unit_id=? AND status NOT IN ('已入库','已取消')""",
                (now, door_id),
            )
            conn.execute(
                """INSERT INTO fulfillment_supplies(door_unit_id, technical_package_id, component_id, name, category, specification, required_quantity, unit, acquisition_method, updated_at)
                   SELECT ?, ?, id, name, category, specification, quantity, unit, acquisition_method, ?
                   FROM fulfillment_components WHERE technical_package_id=?""",
                (door_id, package_id, now, package_id),
            )
            conn.execute("UPDATE fulfillment_door_units SET status='备料与加工中', active_version=?, technical_uid=?, updated_at=? WHERE id=?", (int(package["version"]), str(user.get("uid") or ""), now, door_id))
            self.add_event(conn, order_id=None, door_unit_id=door_id, entity_type="technical_package", entity_id=package_id, action="确认技术包", detail=f"冻结 V{package['version']}，生成需求 {requirement['requirement_no']}，释放工作包", user=user)
        return self.get_door_unit(door_id) or {}

    def update_work_package(self, work_id: int, payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM fulfillment_work_packages WHERE id=?", (work_id,)).fetchone()
            if not row:
                raise LookupError("工作包不存在")
            latest = conn.execute("SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1", (row["door_unit_id"],)).fetchone()
            if not latest or int(latest["id"]) != int(row["technical_package_id"]):
                raise RuntimeError("该工作包属于旧技术版本，已锁定不可继续执行")
            current = str(row["status"])
            target = payload.status
            if target not in WORK_STATUSES:
                raise ValueError("无效的工作包状态")
            if target != current and target not in WORK_TRANSITIONS.get(current, set()):
                raise RuntimeError(f"工作包不能从“{current}”直接变为“{target}”")
            if bool(row["inspection_required"]) and target == "已完成" and current not in {"待质检", "返工"}:
                raise RuntimeError("该工作包要求质检，必须先提交到“待质检”")
            executor = payload.executor_uid or row["executor_uid"] or str(user.get("uid") or "")
            started_at = row["started_at"] or (now if target == "进行中" else None)
            completed_at = now if target == "已完成" else row["completed_at"]
            actual = row["actual_quantity"] if payload.actual_quantity is None else payload.actual_quantity
            conn.execute(
                """UPDATE fulfillment_work_packages SET status=?, executor_uid=?, actual_quantity=?, remark=?, started_at=?, completed_at=?, updated_at=? WHERE id=?""",
                (target, executor, actual, payload.remark, started_at, completed_at, now, work_id),
            )
            door_id = int(row["door_unit_id"])
            if target == "已完成" and float(row["piece_rate"] or 0) > 0:
                quantity = float(actual or row["quantity"] or 0)
                conn.execute(
                    """INSERT INTO fulfillment_payroll_drafts(door_unit_id, work_package_id, employee_uid, work_name, quantity, piece_rate, amount, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(work_package_id) DO UPDATE SET employee_uid=excluded.employee_uid, quantity=excluded.quantity, piece_rate=excluded.piece_rate, amount=excluded.amount""",
                    (door_id, work_id, executor, row["name"], quantity, row["piece_rate"], quantity * float(row["piece_rate"]), now),
                )
            self._refresh_door_progress(conn, door_id, now)
            self.add_event(conn, order_id=None, door_unit_id=door_id, entity_type="work_package", entity_id=work_id, action="更新工作包", detail=f"{row['name']}：{current} → {target}", user=user)
        return self.get_door_unit(int(row["door_unit_id"])) or {}

    def batch_work_packages(self, door_id: int, payload: Any, user: Dict[str, Any]) -> tuple[Dict[str, Any], int]:
        actions = {
            "开始": "进行中",
            "提交质检": "待质检",
            "确认完成": "已完成",
            "跳过": "已取消",
        }
        if payload.action not in actions:
            raise ValueError("无效的批量动作")
        if payload.action == "跳过" and not str(payload.remark or "").strip():
            raise ValueError("跳过工作包必须填写原因")
        now = fulfillment_now()
        requested_ids = {int(item) for item in payload.work_ids}
        with self.transaction() as conn:
            latest = conn.execute(
                "SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
                (door_id,),
            ).fetchone()
            if not latest:
                raise LookupError("生产技术包不存在")
            placeholders = ",".join("?" for _ in requested_ids)
            rows = conn.execute(
                f"""SELECT * FROM fulfillment_work_packages
                    WHERE door_unit_id=? AND technical_package_id=? AND id IN ({placeholders})""",
                (door_id, latest["id"], *sorted(requested_ids)),
            ).fetchall()
            if len(rows) != len(requested_ids):
                raise RuntimeError("所选工作包包含旧技术版本或不存在的记录")
            changed = 0
            for row in rows:
                current = str(row["status"])
                target = actions[payload.action]
                if current in {"已完成", "已取消"}:
                    continue
                if payload.action == "开始" and current not in {"待排单", "已排单", "暂停", "异常", "返工"}:
                    raise RuntimeError(f"{row['name']} 当前为“{current}”，不能批量开始")
                if payload.action == "提交质检" and current not in {"待排单", "已排单", "进行中", "返工"}:
                    raise RuntimeError(f"{row['name']} 当前为“{current}”，不能提交质检")
                if payload.action == "确认完成":
                    if bool(row["inspection_required"]) and current not in {"待质检", "返工"}:
                        raise RuntimeError(f"{row['name']}要求过程检验，请先提交质检")
                    if current not in {"待排单", "已排单", "进行中", "待质检", "返工"}:
                        raise RuntimeError(f"{row['name']} 当前为“{current}”，不能确认完成")
                executor = payload.executor_uid or row["executor_uid"] or str(user.get("uid") or "")
                started_at = row["started_at"] or (now if target in {"进行中", "待质检", "已完成"} else None)
                completed_at = now if target in {"已完成", "已取消"} else row["completed_at"]
                actual = row["quantity"] if target == "已完成" else row["actual_quantity"]
                remark = str(payload.remark or row["remark"] or "")
                conn.execute(
                    """UPDATE fulfillment_work_packages SET status=?, executor_uid=?, actual_quantity=?, remark=?,
                       started_at=?, completed_at=?, updated_at=? WHERE id=?""",
                    (target, executor, actual, remark, started_at, completed_at, now, row["id"]),
                )
                if target == "已完成" and float(row["piece_rate"] or 0) > 0:
                    quantity = float(actual or row["quantity"] or 0)
                    conn.execute(
                        """INSERT INTO fulfillment_payroll_drafts(door_unit_id, work_package_id, employee_uid, work_name, quantity, piece_rate, amount, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(work_package_id) DO UPDATE SET employee_uid=excluded.employee_uid, quantity=excluded.quantity, piece_rate=excluded.piece_rate, amount=excluded.amount""",
                        (door_id, row["id"], executor, row["name"], quantity, row["piece_rate"], quantity * float(row["piece_rate"]), now),
                    )
                self.add_event(
                    conn, order_id=None, door_unit_id=door_id, entity_type="work_package", entity_id=int(row["id"]),
                    action=f"批量{payload.action}", detail=f"{row['name']}：{current} → {target}{'；' + remark if remark else ''}", user=user,
                )
                changed += 1
            self._refresh_door_progress(conn, door_id, now)
        return self.get_door_unit(door_id) or {}, changed

    def _refresh_door_progress(self, conn: sqlite3.Connection, door_id: int, now: str) -> None:
        latest = conn.execute("SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1", (door_id,)).fetchone()
        rows = conn.execute("SELECT status FROM fulfillment_work_packages WHERE door_unit_id=? AND technical_package_id=?", (door_id, latest["id"] if latest else -1)).fetchall()
        if not rows:
            progress = 0
        else:
            weights = {"草稿": 0, "待排单": 0, "已排单": 10, "进行中": 50, "待质检": 80, "已完成": 100, "暂停": 30, "异常": 30, "返工": 60, "已取消": 100}
            progress = int(sum(weights.get(str(row["status"]), 0) for row in rows) / len(rows))
        all_done = bool(rows) and all(str(row["status"]) in {"已完成", "已取消"} for row in rows)
        conn.execute(
            """UPDATE fulfillment_door_units SET progress=?,
               status=CASE WHEN ? AND status IN ('备料与加工中','可局部装配','总装中') THEN '待成品质检' ELSE status END,
               updated_at=? WHERE id=?""",
            (progress, int(all_done), now, door_id),
        )

    def list_supply_workbench(self, scope: str, q: str = "") -> List[Dict[str, Any]]:
        if scope not in {"purchase", "warehouse"}:
            raise ValueError("供应工作台类型不正确")
        where = ["s.technical_package_id=p.id"]
        params: List[Any] = []
        if scope == "purchase":
            where.append("s.acquisition_method NOT IN ('内部加工', '库存领用')")
        else:
            where.append("s.status IN ('到货待检', '已入库', '已发料')")
        if q:
            term = f"%{q}%"
            where.append("(o.order_no LIKE ? OR d.production_no LIKE ? OR o.customer LIKE ? OR o.project LIKE ? OR s.name LIKE ? OR s.supplier LIKE ?)")
            params.extend([term] * 6)
        return self.fetch_all(
            f"""SELECT s.*, d.production_no, d.status AS door_status, o.order_no, o.customer, o.project,
                       EXISTS(SELECT 1 FROM fulfillment_inspections i
                              WHERE i.door_unit_id=d.id AND i.inspection_type='来料检验'
                                AND i.target_name=s.name AND i.result IN ('合格','让步接收')) AS inspection_passed
                FROM fulfillment_supplies s
                JOIN fulfillment_door_units d ON d.id=s.door_unit_id
                JOIN fulfillment_orders o ON o.id=d.order_id
                JOIN fulfillment_technical_packages p ON p.door_unit_id=d.id
                   AND p.id=(SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=d.id ORDER BY version DESC LIMIT 1)
                WHERE {' AND '.join(where)} ORDER BY s.updated_at DESC, s.id DESC""",
            params,
        )

    def create_exception(self, door_id: int, payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            door = conn.execute("SELECT id FROM fulfillment_door_units WHERE id=?", (door_id,)).fetchone()
            if not door:
                raise LookupError("门樘生产单不存在")
            cursor = conn.execute(
                """INSERT INTO fulfillment_exceptions(door_unit_id, category, title, detail, severity, owner_uid, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (door_id, payload.category, payload.title, payload.detail, payload.severity, payload.owner_uid, str(user.get("uid") or ""), now),
            )
            self.add_event(conn, order_id=None, door_unit_id=door_id, entity_type="exception", entity_id=int(cursor.lastrowid), action="登记异常", detail=payload.title, user=user)
        return self.get_door_unit(door_id) or {}

    def resolve_exception(self, exception_id: int, resolution: str, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM fulfillment_exceptions WHERE id=?", (exception_id,)).fetchone()
            if not row:
                raise LookupError("异常记录不存在")
            if row["status"] == "已解决":
                raise RuntimeError("异常已经解决")
            conn.execute("UPDATE fulfillment_exceptions SET status='已解决', resolution=?, resolved_by=?, resolved_at=? WHERE id=?", (resolution, str(user.get("uid") or ""), now, exception_id))
            self.add_event(conn, order_id=None, door_unit_id=int(row["door_unit_id"]), entity_type="exception", entity_id=exception_id, action="解决异常", detail=resolution, user=user)
        return self.get_door_unit(int(row["door_unit_id"])) or {}

    def create_change(self, door_id: int, payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            door = conn.execute("SELECT * FROM fulfillment_door_units WHERE id=?", (door_id,)).fetchone()
            if not door:
                raise LookupError("门樘生产单不存在")
            source = conn.execute("SELECT * FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1", (door_id,)).fetchone()
            if not source or source["status"] != "已确认":
                raise RuntimeError("只有已确认技术包才能发起生产变更")
            self.requirement_service.freeze_for_package(conn, int(source["id"]))
            next_version = int(source["version"]) + 1
            change_no = f"BG{now[:10].replace('-', '')}{door_id:04d}{next_version:02d}"
            change_cursor = conn.execute(
                """INSERT INTO fulfillment_changes(door_unit_id, change_no, from_version, to_version, reason, impact_note, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (door_id, change_no, source["version"], next_version, payload.reason, payload.impact_note, str(user.get("uid") or ""), now),
            )
            package_cursor = conn.execute(
                """INSERT INTO fulfillment_technical_packages(door_unit_id, version, status, product_snapshot_json, product_summary, special_requirements, source_version_id, created_by, created_at, updated_at)
                   VALUES (?, ?, '草稿', ?, ?, ?, ?, ?, ?, ?)""",
                (door_id, next_version, source["product_snapshot_json"], source["product_summary"], source["special_requirements"], source["id"], str(user.get("uid") or ""), now, now),
            )
            new_package_id = int(package_cursor.lastrowid)
            conn.execute(
                """UPDATE fulfillment_work_packages SET status='暂停', remark=CASE WHEN remark='' THEN '等待生产变更确认' ELSE remark END, updated_at=?
                   WHERE technical_package_id=? AND status NOT IN ('已完成','已取消')""",
                (now, source["id"]),
            )
            old_to_new: Dict[int, int] = {}
            for component in conn.execute("SELECT * FROM fulfillment_components WHERE technical_package_id=? ORDER BY sequence_no, id", (source["id"],)).fetchall():
                cursor = conn.execute(
                    """INSERT INTO fulfillment_components(technical_package_id, parent_id, material_id, name, category, specification, quantity, unit, acquisition_method, remark, sequence_no)
                       VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (new_package_id, component["material_id"], component["name"], component["category"], component["specification"], component["quantity"], component["unit"], component["acquisition_method"], component["remark"], component["sequence_no"]),
                )
                old_to_new[int(component["id"])] = int(cursor.lastrowid)
            for work in conn.execute("SELECT * FROM fulfillment_work_packages WHERE technical_package_id=? ORDER BY sequence_no, id", (source["id"],)).fetchall():
                conn.execute(
                    """INSERT INTO fulfillment_work_packages(technical_package_id, door_unit_id, component_id, name, category, route, acquisition_method, executor_uid, planned_start, planned_end, opening_condition, blocking_node, quantity, unit, piece_rate, inspection_required, remark, sequence_no, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (new_package_id, door_id, old_to_new.get(work["component_id"]), work["name"], work["category"], work["route"], work["acquisition_method"], work["executor_uid"], work["planned_start"], work["planned_end"], work["opening_condition"], work["blocking_node"], work["quantity"], work["unit"], work["piece_rate"], work["inspection_required"], work["remark"], work["sequence_no"], now),
                )
            conn.execute("UPDATE fulfillment_door_units SET status='技术准备中', updated_at=? WHERE id=?", (now, door_id))
            self.add_event(conn, order_id=None, door_unit_id=door_id, entity_type="change", entity_id=int(change_cursor.lastrowid), action="发起生产变更", detail=f"V{source['version']} → V{next_version}：{payload.reason}", user=user)
        return self.get_door_unit(door_id) or {}

    def update_supply(self, supply_id: int, payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {"待处理", "办理中", "到货待检", "已入库", "已发料", "暂停", "已取消"}
        if payload.status not in allowed:
            raise ValueError("无效的供应事项状态")
        now = fulfillment_now()
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM fulfillment_supplies WHERE id=?", (supply_id,)).fetchone()
            if not row:
                raise LookupError("供应事项不存在")
            latest = conn.execute("SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1", (row["door_unit_id"],)).fetchone()
            if not latest or int(latest["id"]) != int(row["technical_package_id"]):
                raise RuntimeError("该供应事项属于旧技术版本，已锁定不可修改")
            if payload.status == "已入库":
                inspection = conn.execute(
                    """SELECT result FROM fulfillment_inspections
                       WHERE door_unit_id=? AND inspection_type='来料检验' AND target_name=?
                       ORDER BY id DESC LIMIT 1""",
                    (row["door_unit_id"], row["name"]),
                ).fetchone()
                if not inspection or inspection["result"] not in {"合格", "让步接收"}:
                    raise RuntimeError("该物料尚无合格的来料检验记录，不能入库")
            if payload.status == "已发料" and row["status"] != "已入库":
                raise RuntimeError("只有已入库物料才能由仓库确认发料")
            actual = row["actual_quantity"] if payload.actual_quantity is None else payload.actual_quantity
            unit_cost = row["unit_cost"] if payload.unit_cost is None else payload.unit_cost
            conn.execute(
                """UPDATE fulfillment_supplies SET status=?, handler_uid=?, supplier=?, actual_quantity=?, unit_cost=?, remark=?, updated_at=? WHERE id=?""",
                (payload.status, payload.handler_uid or row["handler_uid"], payload.supplier or row["supplier"], actual, unit_cost, payload.remark, now, supply_id),
            )
            if payload.status == "已入库":
                exists = conn.execute(
                    "SELECT id FROM fulfillment_inventory_movements WHERE door_unit_id=? AND movement_type='来料入库' AND item_name=?",
                    (row["door_unit_id"], row["name"]),
                ).fetchone()
                if not exists:
                    conn.execute(
                        """INSERT INTO fulfillment_inventory_movements(door_unit_id, movement_type, item_name, warehouse, quantity, unit, remark, operator_uid, created_at)
                           VALUES (?, '来料入库', ?, '原料仓', ?, ?, ?, ?, ?)""",
                        (row["door_unit_id"], row["name"], actual or row["required_quantity"], row["unit"], payload.remark, str(user.get("uid") or ""), now),
                    )
            if payload.status == "已发料":
                conn.execute(
                    """INSERT INTO fulfillment_inventory_movements(door_unit_id, movement_type, item_name, warehouse, quantity, unit, remark, operator_uid, created_at)
                       VALUES (?, '生产发料', ?, '原料仓', ?, ?, ?, ?, ?)""",
                    (row["door_unit_id"], row["name"], actual or row["required_quantity"], row["unit"], payload.remark, str(user.get("uid") or ""), now),
                )
            self.add_event(conn, order_id=None, door_unit_id=int(row["door_unit_id"]), entity_type="supply", entity_id=supply_id, action="更新供应事项", detail=f"{row['name']}：{row['status']} → {payload.status}", user=user)
        return self.get_door_unit(int(row["door_unit_id"])) or {}

    def create_inspection(self, door_id: int, payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        if payload.inspection_type not in {"来料检验", "过程检验", "成品质检"}:
            raise ValueError("无效的检验类型")
        if payload.result not in {"合格", "不合格", "让步接收"}:
            raise ValueError("无效的检验结果")
        now = fulfillment_now()
        with self.transaction() as conn:
            door = conn.execute("SELECT * FROM fulfillment_door_units WHERE id=?", (door_id,)).fetchone()
            if not door:
                raise LookupError("门樘生产单不存在")
            if payload.inspection_type == "成品质检":
                unfinished = conn.execute(
                    """SELECT w.name, w.status FROM fulfillment_work_packages w
                       WHERE w.door_unit_id=? AND w.technical_package_id=(
                           SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1
                       ) AND w.status NOT IN ('已完成','已取消') ORDER BY w.sequence_no, w.id""",
                    (door_id, door_id),
                ).fetchall()
                if unfinished:
                    summary = "、".join(f"{item['name']}（{item['status']}）" for item in unfinished[:5])
                    suffix = f"等 {len(unfinished)} 项" if len(unfinished) > 5 else ""
                    raise RuntimeError(f"仍有工作包未完成：{summary}{suffix}")
            cursor = conn.execute(
                """INSERT INTO fulfillment_inspections(door_unit_id, inspection_type, target_name, quantity, result, defect_detail, remark, inspector_uid, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (door_id, payload.inspection_type, payload.target_name, payload.quantity, payload.result, payload.defect_detail, payload.remark, str(user.get("uid") or ""), now),
            )
            if payload.inspection_type == "成品质检":
                next_status = "待成品入库" if payload.result in {"合格", "让步接收"} else "返工中"
                conn.execute("UPDATE fulfillment_door_units SET status=?, updated_at=? WHERE id=?", (next_status, now, door_id))
            self.add_event(conn, order_id=None, door_unit_id=door_id, entity_type="inspection", entity_id=int(cursor.lastrowid), action=payload.inspection_type, detail=f"{payload.target_name or door['production_no']}：{payload.result}", user=user)
        return self.get_door_unit(door_id) or {}

    def finished_inbound(self, door_id: int, payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            door = conn.execute("SELECT * FROM fulfillment_door_units WHERE id=?", (door_id,)).fetchone()
            if not door:
                raise LookupError("门樘生产单不存在")
            if door["status"] != "待成品入库":
                raise RuntimeError("只有成品质检合格的门樘才能入库")
            conn.execute(
                """INSERT INTO fulfillment_inventory_movements(door_unit_id, movement_type, item_name, warehouse, location, quantity, unit, remark, operator_uid, created_at)
                   VALUES (?, '成品入库', ?, ?, ?, ?, '樘', ?, ?, ?)""",
                (door_id, door["production_no"], payload.warehouse, payload.location, payload.quantity, payload.remark, str(user.get("uid") or ""), now),
            )
            conn.execute("UPDATE fulfillment_door_units SET status='已入库待发货', progress=100, updated_at=? WHERE id=?", (now, door_id))
            self.add_event(conn, order_id=int(door["order_id"]), door_unit_id=door_id, entity_type="inventory", entity_id=None, action="成品入库", detail=f"{payload.warehouse} {payload.location}，{payload.quantity} 樘", user=user)
        return self.get_door_unit(door_id) or {}

    def record_payment(self, door_id: int, payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            door = conn.execute("SELECT order_id FROM fulfillment_door_units WHERE id=?", (door_id,)).fetchone()
            if not door:
                raise LookupError("门樘生产单不存在")
            conn.execute(
                """INSERT INTO fulfillment_payments(order_id, amount, payment_date, reference, remark, recorded_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (door["order_id"], payload.amount, payload.payment_date or now[:10], payload.reference, payload.remark, str(user.get("uid") or ""), now),
            )
            self.add_event(conn, order_id=int(door["order_id"]), door_unit_id=door_id, entity_type="payment", entity_id=None, action="登记收款", detail=f"金额 {payload.amount:.2f} 元，凭证 {payload.reference or '未填写'}", user=user)
        return self.get_door_unit(door_id) or {}

    def create_shipment(self, door_id: int, payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            door = conn.execute("SELECT * FROM fulfillment_door_units WHERE id=?", (door_id,)).fetchone()
            if not door:
                raise LookupError("门樘生产单不存在")
            if door["status"] not in {"已入库待发货", "待财务放行", "待出库"}:
                raise RuntimeError("门樘尚未完成成品入库，不能发货")
            paid = float(conn.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM fulfillment_payments WHERE order_id=?", (door["order_id"],)).fetchone()["total"] or 0)
            allocated = float(conn.execute(
                """SELECT COALESCE(SUM(s.required_payment), 0) AS total FROM fulfillment_shipments s
                   JOIN fulfillment_door_units d2 ON d2.id=s.door_unit_id
                   WHERE d2.order_id=? AND s.authorized=0""",
                (door["order_id"],),
            ).fetchone()["total"] or 0)
            available = max(0.0, paid - allocated)
            authorized = bool(payload.authorization_reason.strip() and payload.authorized_by.strip())
            if available < payload.required_payment and not authorized:
                raise RuntimeError(f"当前未占用收款 {available:.2f} 元，未达到本次发货要求 {payload.required_payment:.2f} 元；请登记收款或填写授权放行")
            cursor = conn.execute(
                """INSERT INTO fulfillment_shipments(door_unit_id, required_payment, paid_amount, authorized, authorization_reason, authorized_by, carrier, vehicle_no, contact, remark, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (door_id, payload.required_payment, available, int(authorized), payload.authorization_reason, payload.authorized_by, payload.carrier, payload.vehicle_no, payload.contact, payload.remark, str(user.get("uid") or ""), now),
            )
            conn.execute(
                """INSERT INTO fulfillment_inventory_movements(door_unit_id, movement_type, item_name, warehouse, quantity, unit, remark, operator_uid, created_at)
                   VALUES (?, '发货出库', ?, '成品仓', 1, '樘', ?, ?, ?)""",
                (door_id, door["production_no"], payload.remark, str(user.get("uid") or ""), now),
            )
            conn.execute("UPDATE fulfillment_door_units SET status='运输中', updated_at=? WHERE id=?", (now, door_id))
            detail = f"{payload.carrier or '自送'} {payload.vehicle_no}" + ("；授权放行" if authorized else "")
            self.add_event(conn, order_id=int(door["order_id"]), door_unit_id=door_id, entity_type="shipment", entity_id=int(cursor.lastrowid), action="发货出库", detail=detail, user=user)
        return self.get_door_unit(door_id) or {}

    def sign_shipment(self, shipment_id: int, payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            shipment = conn.execute("SELECT * FROM fulfillment_shipments WHERE id=?", (shipment_id,)).fetchone()
            if not shipment:
                raise LookupError("发货记录不存在")
            if shipment["status"] == "已签收":
                raise RuntimeError("该发货记录已经签收")
            conn.execute("UPDATE fulfillment_shipments SET status='已签收', signed_by=?, signed_at=?, remark=? WHERE id=?", (payload.signed_by, payload.signed_at or now, payload.remark or shipment["remark"], shipment_id))
            conn.execute("UPDATE fulfillment_door_units SET status='已签收', progress=100, updated_at=? WHERE id=?", (now, shipment["door_unit_id"]))
            door = conn.execute("SELECT order_id FROM fulfillment_door_units WHERE id=?", (shipment["door_unit_id"],)).fetchone()
            self.add_event(conn, order_id=int(door["order_id"]), door_unit_id=int(shipment["door_unit_id"]), entity_type="shipment", entity_id=shipment_id, action="客户签收", detail=payload.signed_by or "已签收", user=user)
        return self.get_door_unit(int(shipment["door_unit_id"])) or {}
