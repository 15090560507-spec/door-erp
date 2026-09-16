"""Transactional SQLite repository for the new door-unit fulfillment center."""

from __future__ import annotations

import json
import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Sequence
from zoneinfo import ZoneInfo

from config import FULFILLMENT_DB_FILE, FULFILLMENT_FILES_DIR
from inventory_database import InventoryDatabase
from requirement_service import RequirementService
from work_package_service import WorkPackageService


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
DOOR_STATUSES = (
    "待生产确认", "技术准备中", "备料与加工中", "可局部装配", "总装中",
    "待成品质检", "返工中", "待成品入库", "已入库待发货", "待财务放行",
    "待出库", "运输中", "已签收",
)
WORKFLOW_STAGE_STATUSES = {
    "preparation": ("待生产确认", "技术准备中"),
    "materials": ("备料与加工中", "可局部装配"),
    "execution": ("总装中", "返工中"),
    "quality": ("待成品质检", "待成品入库"),
    "delivery": ("已入库待发货", "待财务放行", "待出库", "运输中", "已签收"),
}
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


def build_fulfillment_workflow(door: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the four-stage workflow while keeping material and process facts separate."""
    package = door.get("technical_package") or {}
    calculation = door.get("calculation")
    components = package.get("components") or []
    works = package.get("work_packages") or []
    requirement = door.get("material_requirement") or {}
    material_items = requirement.get("items") or []
    inspections = door.get("inspections") or []
    movements = door.get("inventory_movements") or []
    shipments = door.get("shipments") or []
    open_exceptions = [item for item in (door.get("exceptions") or []) if item.get("status") != "已解决"]

    package_published = package.get("status") == "已确认"
    preparation_blockers: List[str] = []
    if not package:
        preparation_blockers.append("尚未生成BOM草稿")
    else:
        if package.get("generation_status") in {"未生成", "生成失败"}:
            preparation_blockers.append("BOM尚未生成或生成失败")
        unresolved = sum(
            1 for item in components
            if item.get("verification_status") != "已核验"
            or (
                item.get("match_status") not in {"已匹配", "无需物料"}
                or (item.get("match_status") == "已匹配" and not item.get("material_id"))
            )
        )
        if unresolved:
            preparation_blockers.append(f"还有{unresolved}项BOM资料待核验")
        blocking_warnings = int(package.get("blocking_warning_count") or 0)
        if blocking_warnings:
            preparation_blockers.append(f"还有{blocking_warnings}项阻断警告")
        if not package_published:
            preparation_blockers.append("BOM尚未发布")
        if package_published and calculation and calculation.get("status") != "已发布":
            preparation_blockers.append(f"算料{calculation.get('status') or '未开始'}，尚未发布下料单")
        if package_published and not works:
            preparation_blockers.append("执行工作包尚未生成")
    calculation_published = not calculation or calculation.get("status") == "已发布"
    preparation_complete = package_published and calculation_published and bool(works)

    shortage_items = [item for item in material_items if float(item.get("shortage_quantity") or 0) > 0.005]
    pending_issue_items = [
        item for item in material_items
        if float(item.get("required_quantity") or 0)
        - max(0.0, float(item.get("issued_quantity") or 0) - float(item.get("returned_quantity") or 0))
        > 0.005
    ]
    materials_complete = bool(requirement) and not shortage_items
    material_blockers: List[str] = []
    if preparation_complete and not requirement:
        material_blockers.append("BOM已发布，但物料需求尚未生成")
    if shortage_items:
        material_blockers.append(f"{len(shortage_items)}项物料存在缺口")

    terminal_statuses = {"已完成", "已取消"}
    completed_works = [item for item in works if item.get("status") in terminal_statuses]
    unfinished_works = [item for item in works if item.get("status") not in terminal_statuses]
    ready_works = [item for item in unfinished_works if item.get("readiness_status") in {"可执行", "进行中", "待确认", "返工", "暂停", "异常"}]
    work_blockers = [str(item.get("blocked_reason") or item.get("readiness_status") or "") for item in unfinished_works if item.get("blocked_reason")]
    execution_complete = bool(works) and not unfinished_works
    execution_blockers = [] if ready_works or execution_complete else list(dict.fromkeys(work_blockers))[:3]
    if preparation_complete and not requirement:
        execution_blockers.append("BOM已发布，但物料需求尚未生成")
    elif shortage_items and not ready_works:
        execution_blockers.append(f"{len(shortage_items)}项物料缺口阻止当前工序")

    finished_inspections = [item for item in inspections if item.get("inspection_type") == "成品质检"]
    latest_inspection = finished_inspections[0] if finished_inspections else None
    inspection_passed = bool(latest_inspection and latest_inspection.get("result") in {"合格", "让步接收"})
    finished_inbound = any(item.get("movement_type") == "成品入库" for item in movements)
    quality_complete = finished_inbound
    quality_blockers: List[str] = []
    if execution_complete and not inspection_passed:
        quality_blockers.append("尚未通过成品质检")
    if inspection_passed and not finished_inbound:
        quality_blockers.append("质检已通过，尚未办理成品入库")

    signed = any(item.get("status") == "已签收" for item in shipments) or door.get("status") == "已签收"
    shipped = bool(shipments)
    finance = door.get("sales_finance") or {}
    unpaid = float(finance.get("unpaid_amount") or 0)
    delivery_blockers: List[str] = []
    if quality_complete and unpaid > 0.005 and not shipped:
        delivery_blockers.append(f"订单尚有未收款{unpaid:.2f}元")
    if quality_complete and not shipped:
        delivery_blockers.append("尚未办理发货出库")
    if shipped and not signed:
        delivery_blockers.append("货物运输中，尚未签收")

    stage_data = [
        {
            "key": "preparation", "label": "生产准备", "complete": preparation_complete,
            "summary": (
                f"BOM V{package.get('version') or 0} · {'已发布' if package_published else '草稿'}"
                f" · 算料{(calculation or {}).get('status') or '旧流程'} · {len(works)}个工作包"
            ),
            "blockers": preparation_blockers, "action": "open_bom", "action_label": "进入BOM与工艺准备",
        },
        {
            "key": "execution", "label": "部件生产与装配", "complete": execution_complete,
            "summary": f"物料{len(material_items) - len(shortage_items)}/{len(material_items)}项可用 · {len(completed_works)}/{len(works)}个工序完成",
            "blockers": execution_blockers, "action": "manage_work", "action_label": "处理当前工作包",
        },
        {
            "key": "quality", "label": "质检入库", "complete": quality_complete,
            "summary": "成品已入库" if finished_inbound else (f"最近质检：{latest_inspection.get('result')}" if latest_inspection else "等待成品质检"),
            "blockers": quality_blockers, "action": "quality_inbound", "action_label": "办理质检与入库",
        },
        {
            "key": "delivery", "label": "发货完成", "complete": signed,
            "summary": "客户已签收" if signed else ("运输中" if shipped else "等待发货"),
            "blockers": delivery_blockers, "action": "ship", "action_label": "办理发货与签收",
        },
    ]
    current_index = next((index for index, stage in enumerate(stage_data) if not stage["complete"]), len(stage_data) - 1)
    for index, stage in enumerate(stage_data):
        if stage["complete"]:
            stage["state"] = "complete"
        elif index == current_index:
            stage["state"] = "blocked" if stage["blockers"] else "current"
        else:
            stage["state"] = "pending"

    return {
        "current_stage": stage_data[current_index]["key"] if not signed else "complete",
        "current_stage_label": stage_data[current_index]["label"] if not signed else "履约完成",
        "stages": stage_data,
        "open_exception_count": len(open_exceptions),
        "next_action": stage_data[current_index]["action"] if not signed else "view_records",
        "next_action_label": stage_data[current_index]["action_label"] if not signed else "查看全部记录",
    }


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
                    status TEXT NOT NULL DEFAULT '进行中',
                    sales_order_id INTEGER,
                    sales_order_no TEXT NOT NULL DEFAULT ''
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
                    sales_order_line_id INTEGER,
                    source_task_id TEXT NOT NULL DEFAULT '',
                    source_quantity_index INTEGER NOT NULL DEFAULT 1,
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
                    frame_trim_mode TEXT NOT NULL DEFAULT 'separate',
                    generation_status TEXT NOT NULL DEFAULT '未生成',
                    rule_version TEXT NOT NULL DEFAULT '',
                    generated_at TEXT,
                    generation_summary_json TEXT NOT NULL DEFAULT '{}',
                    blocking_warning_count INTEGER NOT NULL DEFAULT 0,
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
                    line_no INTEGER NOT NULL DEFAULT 0,
                    group_code TEXT NOT NULL DEFAULT 'other',
                    theoretical_quantity REAL NOT NULL DEFAULT 0,
                    waste_rate REAL NOT NULL DEFAULT 0,
                    planned_quantity REAL NOT NULL DEFAULT 0,
                    source_type TEXT NOT NULL DEFAULT 'legacy_manual',
                    source_rule_version TEXT NOT NULL DEFAULT '',
                    source_payload_json TEXT NOT NULL DEFAULT '{}',
                    match_status TEXT NOT NULL DEFAULT '待匹配',
                    verification_status TEXT NOT NULL DEFAULT '待核验',
                    operation_code TEXT NOT NULL DEFAULT '',
                    supplier_id INTEGER,
                    required_date TEXT NOT NULL DEFAULT '',
                    attachments_json TEXT NOT NULL DEFAULT '[]',
                    item_kind TEXT NOT NULL DEFAULT 'material',
                    procurement_mode TEXT NOT NULL DEFAULT 'stock',
                    drawing_parameter_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(technical_package_id) REFERENCES fulfillment_technical_packages(id) ON DELETE CASCADE,
                    FOREIGN KEY(parent_id) REFERENCES fulfillment_components(id)
                );

                CREATE TABLE IF NOT EXISTS fulfillment_calculations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    door_unit_id INTEGER NOT NULL,
                    technical_package_id INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT '未算料',
                    remark TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT '',
                    updated_by TEXT NOT NULL DEFAULT '',
                    confirmed_by TEXT NOT NULL DEFAULT '',
                    published_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    confirmed_at TEXT,
                    published_at TEXT,
                    UNIQUE(technical_package_id, version),
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE,
                    FOREIGN KEY(technical_package_id) REFERENCES fulfillment_technical_packages(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS fulfillment_calculation_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    calculation_id INTEGER NOT NULL,
                    component_id INTEGER NOT NULL,
                    line_no INTEGER NOT NULL DEFAULT 0,
                    part_name TEXT NOT NULL,
                    material_specification TEXT NOT NULL DEFAULT '',
                    finished_size TEXT NOT NULL DEFAULT '',
                    cut_length REAL NOT NULL DEFAULT 0,
                    cut_width REAL NOT NULL DEFAULT 0,
                    quantity REAL NOT NULL DEFAULT 1,
                    unit TEXT NOT NULL DEFAULT '件',
                    waste_rate REAL NOT NULL DEFAULT 0,
                    actual_material_quantity REAL NOT NULL DEFAULT 0,
                    grain_direction TEXT NOT NULL DEFAULT '',
                    cutting_method TEXT NOT NULL DEFAULT '',
                    source_type TEXT NOT NULL DEFAULT 'manual',
                    remark TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(calculation_id) REFERENCES fulfillment_calculations(id) ON DELETE CASCADE,
                    FOREIGN KEY(component_id) REFERENCES fulfillment_components(id)
                );

                CREATE INDEX IF NOT EXISTS ix_fulfillment_calculation_door
                ON fulfillment_calculations(door_unit_id, technical_package_id, version);

                CREATE INDEX IF NOT EXISTS ix_fulfillment_calculation_component
                ON fulfillment_calculation_items(calculation_id, component_id, line_no);

                CREATE TABLE IF NOT EXISTS fulfillment_bom_generation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    door_unit_id INTEGER NOT NULL,
                    technical_package_id INTEGER NOT NULL,
                    rule_version TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '进行中',
                    generated_count INTEGER NOT NULL DEFAULT 0,
                    matched_count INTEGER NOT NULL DEFAULT 0,
                    warning_count INTEGER NOT NULL DEFAULT 0,
                    blocking_warning_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    created_by TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(order_id) REFERENCES fulfillment_orders(id) ON DELETE CASCADE,
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE,
                    FOREIGN KEY(technical_package_id) REFERENCES fulfillment_technical_packages(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS fulfillment_bom_generation_warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    order_id INTEGER NOT NULL,
                    door_unit_id INTEGER NOT NULL,
                    technical_package_id INTEGER NOT NULL,
                    rule_version TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'warning',
                    field_path TEXT NOT NULL DEFAULT '',
                    code TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL,
                    blocking INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES fulfillment_bom_generation_runs(id) ON DELETE CASCADE,
                    FOREIGN KEY(order_id) REFERENCES fulfillment_orders(id) ON DELETE CASCADE,
                    FOREIGN KEY(door_unit_id) REFERENCES fulfillment_door_units(id) ON DELETE CASCADE,
                    FOREIGN KEY(technical_package_id) REFERENCES fulfillment_technical_packages(id) ON DELETE CASCADE
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

                CREATE TABLE IF NOT EXISTS fulfillment_work_package_dependencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    predecessor_id INTEGER NOT NULL,
                    successor_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(predecessor_id, successor_id),
                    CHECK(predecessor_id != successor_id),
                    FOREIGN KEY(predecessor_id) REFERENCES fulfillment_work_packages(id) ON DELETE CASCADE,
                    FOREIGN KEY(successor_id) REFERENCES fulfillment_work_packages(id) ON DELETE CASCADE
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

                CREATE TABLE IF NOT EXISTS workforce_employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_no TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    team TEXT NOT NULL DEFAULT '',
                    role_name TEXT NOT NULL DEFAULT '',
                    capabilities_json TEXT NOT NULL DEFAULT '[]',
                    work_center TEXT NOT NULL DEFAULT '',
                    wage_type TEXT NOT NULL DEFAULT '计件',
                    base_salary REAL NOT NULL DEFAULT 0,
                    hire_date TEXT NOT NULL DEFAULT '',
                    leave_date TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    remark TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS process_route_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    target_group TEXT NOT NULL DEFAULT 'door',
                    version INTEGER NOT NULL DEFAULT 1,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS process_route_template_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    step_code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '生产',
                    sequence_no INTEGER NOT NULL,
                    predecessor_codes_json TEXT NOT NULL DEFAULT '[]',
                    material_operations_json TEXT NOT NULL DEFAULT '[]',
                    inspection_required INTEGER NOT NULL DEFAULT 0,
                    standard_minutes REAL NOT NULL DEFAULT 0,
                    piece_rate REAL NOT NULL DEFAULT 0,
                    default_role TEXT NOT NULL DEFAULT '',
                    work_center TEXT NOT NULL DEFAULT '',
                    weight REAL NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(template_id, step_code),
                    FOREIGN KEY(template_id) REFERENCES process_route_templates(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS workforce_attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    work_date TEXT NOT NULL,
                    regular_hours REAL NOT NULL DEFAULT 0,
                    overtime_hours REAL NOT NULL DEFAULT 0,
                    leave_hours REAL NOT NULL DEFAULT 0,
                    remark TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(employee_id, work_date),
                    FOREIGN KEY(employee_id) REFERENCES workforce_employees(id)
                );

                CREATE TABLE IF NOT EXISTS payroll_periods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    month TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT '草稿',
                    created_by TEXT NOT NULL DEFAULT '',
                    approved_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    approved_at TEXT
                );

                CREATE TABLE IF NOT EXISTS payroll_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_id INTEGER NOT NULL,
                    employee_id INTEGER NOT NULL,
                    base_salary REAL NOT NULL DEFAULT 0,
                    piecework_amount REAL NOT NULL DEFAULT 0,
                    overtime_amount REAL NOT NULL DEFAULT 0,
                    allowance REAL NOT NULL DEFAULT 0,
                    bonus REAL NOT NULL DEFAULT 0,
                    deduction REAL NOT NULL DEFAULT 0,
                    social_insurance REAL NOT NULL DEFAULT 0,
                    tax REAL NOT NULL DEFAULT 0,
                    other_withholding REAL NOT NULL DEFAULT 0,
                    payable_amount REAL NOT NULL DEFAULT 0,
                    remark TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    UNIQUE(period_id, employee_id),
                    FOREIGN KEY(period_id) REFERENCES payroll_periods(id) ON DELETE CASCADE,
                    FOREIGN KEY(employee_id) REFERENCES workforce_employees(id)
                );
                """
            )
            package_columns = {row["name"] for row in conn.execute("PRAGMA table_info(fulfillment_technical_packages)").fetchall()}
            for name, definition in (
                ("generation_status", "TEXT NOT NULL DEFAULT '未生成'"),
                ("rule_version", "TEXT NOT NULL DEFAULT ''"),
                ("generated_at", "TEXT"),
                ("generation_summary_json", "TEXT NOT NULL DEFAULT '{}'"),
                ("blocking_warning_count", "INTEGER NOT NULL DEFAULT 0"),
                ("frame_trim_mode", "TEXT NOT NULL DEFAULT 'separate'"),
            ):
                if name not in package_columns:
                    conn.execute(f"ALTER TABLE fulfillment_technical_packages ADD COLUMN {name} {definition}")
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(fulfillment_components)").fetchall()}
            component_definitions = (
                ("material_id", "INTEGER"),
                ("line_no", "INTEGER NOT NULL DEFAULT 0"),
                ("group_code", "TEXT NOT NULL DEFAULT 'other'"),
                ("theoretical_quantity", "REAL NOT NULL DEFAULT 0"),
                ("waste_rate", "REAL NOT NULL DEFAULT 0"),
                ("planned_quantity", "REAL NOT NULL DEFAULT 0"),
                ("source_type", "TEXT NOT NULL DEFAULT 'legacy_manual'"),
                ("source_rule_version", "TEXT NOT NULL DEFAULT ''"),
                ("source_payload_json", "TEXT NOT NULL DEFAULT '{}'"),
                ("match_status", "TEXT NOT NULL DEFAULT '待匹配'"),
                ("verification_status", "TEXT NOT NULL DEFAULT '待核验'"),
                ("operation_code", "TEXT NOT NULL DEFAULT ''"),
                ("supplier_id", "INTEGER"),
                ("required_date", "TEXT NOT NULL DEFAULT ''"),
                ("attachments_json", "TEXT NOT NULL DEFAULT '[]'"),
                ("item_kind", "TEXT NOT NULL DEFAULT 'material'"),
                ("procurement_mode", "TEXT NOT NULL DEFAULT 'stock'"),
                ("drawing_parameter_json", "TEXT NOT NULL DEFAULT '{}'"),
            )
            for name, definition in component_definitions:
                if name not in columns:
                    conn.execute(f"ALTER TABLE fulfillment_components ADD COLUMN {name} {definition}")
            work_columns = {row["name"] for row in conn.execute("PRAGMA table_info(fulfillment_work_packages)").fetchall()}
            for name, definition in (
                ("operation_code", "TEXT NOT NULL DEFAULT ''"),
                ("weight", "REAL NOT NULL DEFAULT 1"),
                ("readiness_status", "TEXT NOT NULL DEFAULT '待前序'"),
                ("material_ready", "INTEGER NOT NULL DEFAULT 0"),
                ("blocked_reason", "TEXT NOT NULL DEFAULT ''"),
                ("ready_at", "TEXT"),
                ("submitted_at", "TEXT"),
                ("scrap_quantity", "REAL NOT NULL DEFAULT 0"),
                ("actual_minutes", "REAL NOT NULL DEFAULT 0"),
                ("skip_reason", "TEXT NOT NULL DEFAULT ''"),
            ):
                if name not in work_columns:
                    conn.execute(f"ALTER TABLE fulfillment_work_packages ADD COLUMN {name} {definition}")
            conn.execute(
                """UPDATE fulfillment_components
                   SET theoretical_quantity=quantity, planned_quantity=quantity
                   WHERE source_type='legacy_manual' AND theoretical_quantity=0 AND planned_quantity=0"""
            )
            conn.execute(
                """UPDATE fulfillment_components SET source_type='seed_default'
                   WHERE source_type='legacy_manual' AND specification='' AND remark=''
                     AND name IN ('门扇与面板','门框','锁具与拉手','合页与五金','玻璃与花件','包装')"""
            )
            order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(fulfillment_orders)").fetchall()}
            for name, definition in (
                ("sales_order_id", "INTEGER"),
                ("sales_order_no", "TEXT NOT NULL DEFAULT ''"),
            ):
                if name not in order_columns:
                    conn.execute(f"ALTER TABLE fulfillment_orders ADD COLUMN {name} {definition}")
            door_columns = {row["name"] for row in conn.execute("PRAGMA table_info(fulfillment_door_units)").fetchall()}
            for name, definition in (
                ("sales_order_line_id", "INTEGER"),
                ("source_task_id", "TEXT NOT NULL DEFAULT ''"),
                ("source_quantity_index", "INTEGER NOT NULL DEFAULT 1"),
                ("assembly_owner_id", "INTEGER"),
                ("assembly_collaborator_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
                ("assembly_work_center", "TEXT NOT NULL DEFAULT ''"),
                ("assembly_planned_date", "TEXT NOT NULL DEFAULT ''"),
                ("assembly_actual_date", "TEXT NOT NULL DEFAULT ''"),
                ("assembly_note", "TEXT NOT NULL DEFAULT ''"),
            ):
                if name not in door_columns:
                    conn.execute(f"ALTER TABLE fulfillment_door_units ADD COLUMN {name} {definition}")
            movement_columns = {row["name"] for row in conn.execute("PRAGMA table_info(fulfillment_inventory_movements)").fetchall()}
            for name, definition in (
                ("technical_package_id", "INTEGER"),
                ("component_id", "INTEGER"),
            ):
                if name not in movement_columns:
                    conn.execute(f"ALTER TABLE fulfillment_inventory_movements ADD COLUMN {name} {definition}")
            conn.execute(
                """CREATE INDEX IF NOT EXISTS ix_fulfillment_component_inventory
                   ON fulfillment_inventory_movements(door_unit_id, technical_package_id, component_id, movement_type)"""
            )
            for name, definition in (
                ("route_template_id", "INTEGER"),
                ("route_step_id", "INTEGER"),
                ("route_snapshot_json", "TEXT NOT NULL DEFAULT '{}'"),
                ("standard_minutes", "REAL NOT NULL DEFAULT 0"),
                ("default_role", "TEXT NOT NULL DEFAULT ''"),
                ("work_center", "TEXT NOT NULL DEFAULT ''"),
                ("employee_id", "INTEGER"),
            ):
                if name not in work_columns:
                    conn.execute(f"ALTER TABLE fulfillment_work_packages ADD COLUMN {name} {definition}")
            self._seed_process_routes(conn)
            conn.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS ux_fulfillment_sales_order
                   ON fulfillment_orders(sales_order_id) WHERE sales_order_id IS NOT NULL"""
            )

    @staticmethod
    def _seed_process_routes(conn: sqlite3.Connection) -> None:
        now = fulfillment_now()
        existing = conn.execute(
            "SELECT id FROM process_route_templates WHERE code='DOOR_STANDARD'"
        ).fetchone()
        if existing:
            return
        cursor = conn.execute(
            """INSERT INTO process_route_templates(
                   code, name, target_group, version, is_default, is_active, updated_at
               ) VALUES ('DOOR_STANDARD', '整樘门标准工艺', 'door', 1, 1, 1, ?)""",
            (now,),
        )
        template_id = int(cursor.lastrowid)
        steps = (
            ("TECH_PREP", "技术准备", "技术", [], [], 0, 20, 0, "技术", "技术中心", 5),
            ("PANEL_PREP", "门板与骨架备料", "备料", ["TECH_PREP"], ["PANEL", "SKELETON", "PANEL_SHEET", "PANEL_PROFILE"], 0, 30, 0, "仓储", "备料区", 10),
            ("PANEL_CUT", "板材下料", "下料", ["PANEL_PREP"], [], 0, 60, 0, "下料", "下料区", 12),
            ("BENDING", "折弯成型", "折弯", ["PANEL_CUT"], [], 0, 60, 0, "折弯", "折弯区", 10),
            ("BODY", "门体焊接与制作", "门体", ["BENDING"], [], 0, 120, 0, "焊接", "焊接区", 20),
            ("SURFACE", "表面处理", "表面", ["BODY"], [], 0, 120, 0, "油漆", "表面处理区", 14),
            ("FITTINGS_PREP", "玻璃五金与门套配套", "配套", ["TECH_PREP"], ["TRIM", "GLASS", "HINGE", "LOCK_BODY", "FINGERPRINT_LOCK", "FRONT_HANDLE", "BACK_HANDLE", "ORNAMENT", "CONSUMABLE"], 0, 30, 0, "仓储", "配套区", 10),
            ("ASSEMBLY", "总装配", "装配", ["SURFACE", "FITTINGS_PREP"], [], 0, 120, 0, "拼装", "总装区", 15),
            ("PACKAGING", "成品包装", "包装", ["ASSEMBLY"], ["PACKAGING"], 0, 30, 0, "包装", "包装区", 5),
            ("QC_HANDOFF", "成品质检交接", "质检", ["PACKAGING"], [], 1, 30, 0, "质检", "质检区", 5),
        )
        for sequence, step in enumerate(steps, start=1):
            code, name, category, predecessors, material_operations, inspection, minutes, piece_rate, role, center, weight = step
            conn.execute(
                """INSERT INTO process_route_template_steps(
                       template_id, step_code, name, category, sequence_no,
                       predecessor_codes_json, material_operations_json,
                       inspection_required, standard_minutes, piece_rate,
                       default_role, work_center, weight, is_active
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    template_id, code, name, category, sequence,
                    json_dumps(predecessors), json_dumps(material_operations),
                    inspection, minutes, piece_rate, role, center, weight,
                ),
            )

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

    def create_from_sales_order(self, sales_order: Dict[str, Any], idempotency_key: str, user: Dict[str, Any]) -> Dict[str, Any]:
        sales_order_id = int(sales_order.get("id") or 0)
        if sales_order_id <= 0:
            raise ValueError("销售订单ID无效")
        existing = self.fetch_one(
            "SELECT id FROM fulfillment_orders WHERE sales_order_id=? AND status!='已作废'",
            (sales_order_id,),
        )
        if existing:
            return self.get_order(int(existing["id"])) or {}

        lines = sales_order.get("lines") or []
        if not lines:
            raise ValueError("销售订单没有可生成的门樘明细")
        now = fulfillment_now()
        customer = str(sales_order.get("customer_name") or "").strip()
        if not customer:
            raise ValueError("销售订单客户不能为空")

        with self.transaction() as conn:
            existing_row = conn.execute(
                "SELECT id FROM fulfillment_orders WHERE sales_order_id=? AND status!='已作废'",
                (sales_order_id,),
            ).fetchone()
            if existing_row:
                order_id = int(existing_row["id"])
            else:
                order_no = self._next_order_no(conn, now)
                cursor = conn.execute(
                    """INSERT INTO fulfillment_orders(
                           order_no, source_task_id, source_revision, customer, project,
                           due_date, sales_note, task_snapshot_json, created_by, created_at,
                           updated_at, sales_order_id, sales_order_no
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        order_no, f"sales-order:{sales_order_id}", idempotency_key, customer,
                        str(sales_order.get("project_name") or ""), str(sales_order.get("delivery_date") or ""),
                        str(sales_order.get("remark") or ""), json_dumps(sales_order),
                        str(user.get("uid") or ""), now, now, sales_order_id,
                        str(sales_order.get("order_no") or ""),
                    ),
                )
                order_id = int(cursor.lastrowid)
                sequence = 0
                for line in lines:
                    quantity = int(line.get("quantity") or 0)
                    if quantity <= 0:
                        raise ValueError(f"订单第{line.get('line_no') or '?'}行数量必须大于0")
                    drawing_snapshot = line.get("drawing_snapshot") or {}
                    if not isinstance(drawing_snapshot, dict):
                        drawing_snapshot = json_loads(str(drawing_snapshot), {})
                    params = dict(drawing_snapshot.get("params") or {})
                    params.update({
                        "product_name": str(line.get("product_name") or params.get("product_name") or "门"),
                        "door_type": str(line.get("door_type") or params.get("door_type") or ""),
                        "dw": float(line.get("width") or params.get("dw") or 0),
                        "dh": float(line.get("height") or params.get("dh") or 0),
                        "ys": str(line.get("color") or params.get("ys") or ""),
                        "opening_direction": str(line.get("opening_direction") or ""),
                        "sales_order_id": sales_order_id,
                        "sales_order_line_id": int(line.get("id") or 0),
                        "source_task_id": str(line.get("task_id") or ""),
                    })
                    for quantity_index in range(1, quantity + 1):
                        sequence += 1
                        door_line_no = int(line.get("line_no") or 0)
                        sales_order_no = str(sales_order.get("order_no") or order_no)
                        production_no = f"{sales_order_no}-{door_line_no:02d}-{quantity_index:02d}"
                        specification = f"{params.get('dw') or ''} x {params.get('dh') or ''}".strip(" x")
                        door_cursor = conn.execute(
                            """INSERT INTO fulfillment_door_units(
                                   order_id, production_no, sequence_no, product_name, specification,
                                   opening, due_date, owner_uid, sales_order_line_id, source_task_id,
                                   source_quantity_index, created_at, updated_at
                               ) VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?)""",
                            (
                                order_id, production_no, sequence, str(params.get("product_name") or "门"),
                                specification, str(line.get("opening_direction") or ""),
                                str(sales_order.get("delivery_date") or ""), int(line.get("id") or 0),
                                str(line.get("task_id") or ""), quantity_index, now, now,
                            ),
                        )
                        door_id = int(door_cursor.lastrowid)
                        package_cursor = conn.execute(
                            """INSERT INTO fulfillment_technical_packages(
                                   door_unit_id, version, product_snapshot_json, product_summary,
                                   created_by, created_at, updated_at
                               ) VALUES (?, 1, ?, ?, ?, ?, ?)""",
                            (
                                door_id, json_dumps(params), self._default_product_summary(params),
                                str(user.get("uid") or ""), now, now,
                            ),
                        )
                        package_id = int(package_cursor.lastrowid)
                        self._seed_components(conn, package_id, params)
                        self._seed_work_packages(conn, package_id, door_id, now)
                        self.add_event(
                            conn, order_id=order_id, door_unit_id=door_id, entity_type="door_unit",
                            entity_id=door_id, action="从销售订单创建门樘",
                            detail=f"{sales_order.get('order_no')} 第{line.get('line_no')}行 第{quantity_index}樘，技术包草稿 V1",
                            user=user,
                        )
                self.add_event(
                    conn, order_id=order_id, door_unit_id=None, entity_type="order", entity_id=order_id,
                    action="销售订单自动下达", detail=f"共生成 {sequence} 樘门", user=user,
                )
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
                """INSERT INTO fulfillment_components(
                       technical_package_id, name, category, quantity, unit,
                       acquisition_method, sequence_no, line_no, group_code,
                       theoretical_quantity, planned_quantity, source_type,
                       match_status, verification_status
                   ) VALUES (?, ?, ?, 1, '套', ?, ?, ?, 'other', 1, 1,
                             'seed_default', '待匹配', '待核验')""",
                (package_id, name, category, method, sequence, sequence),
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

    def list_orders(self, q: str = "", status: str = "", stage: str = "") -> List[Dict[str, Any]]:
        where = ["1=1"]
        params: List[Any] = []
        if q:
            where.append("(o.order_no LIKE ? OR o.customer LIKE ? OR o.project LIKE ? OR d.production_no LIKE ?)")
            term = f"%{q}%"
            params.extend([term, term, term, term])
        if status:
            where.append("d.status=?")
            params.append(status)
        if stage:
            stage_statuses = WORKFLOW_STAGE_STATUSES.get(stage)
            if stage_statuses:
                placeholders = ",".join("?" for _ in stage_statuses)
                where.append(f"d.status IN ({placeholders})")
                params.extend(stage_statuses)
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
        door["assembly_collaborator_ids"] = json_loads(door.pop("assembly_collaborator_ids_json", ""), [])
        employee_ids = ([door.get("assembly_owner_id")] if door.get("assembly_owner_id") else []) + door["assembly_collaborator_ids"]
        employees: Dict[int, Dict[str, Any]] = {}
        if employee_ids:
            placeholders = ",".join("?" for _ in employee_ids)
            employees = {
                int(row["id"]): dict(row)
                for row in self.fetch_all(
                    f"SELECT id, employee_no, name, team, role_name FROM workforce_employees WHERE id IN ({placeholders})",
                    tuple(employee_ids),
                )
            }
        door["assembly_owner"] = employees.get(int(door["assembly_owner_id"])) if door.get("assembly_owner_id") else None
        door["assembly_collaborators"] = [employees[item] for item in door["assembly_collaborator_ids"] if item in employees]
        package = self.fetch_one("SELECT * FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1", (door_id,))
        if package:
            package["product_snapshot"] = json_loads(package.pop("product_snapshot_json", ""), {})
            package["generation_summary"] = json_loads(package.pop("generation_summary_json", ""), {})
            package["components"] = self.fetch_all(
                """SELECT c.*, m.code AS material_code, m.name AS material_name,
                          m.specification AS material_specification, m.unit AS material_unit
                   FROM fulfillment_components c
                   LEFT JOIN inventory_materials m ON m.id=c.material_id
                   WHERE c.technical_package_id=? ORDER BY c.sequence_no, c.id""",
                (package["id"],),
            )
            for component in package["components"]:
                component["source_payload"] = json_loads(component.pop("source_payload_json", ""), {})
                component["attachments"] = json_loads(component.pop("attachments_json", ""), [])
                component["drawing_parameters"] = json_loads(component.pop("drawing_parameter_json", ""), {})
            package["work_packages"] = self.fetch_all("SELECT * FROM fulfillment_work_packages WHERE technical_package_id=? ORDER BY sequence_no, id", (package["id"],))
            for work in package["work_packages"]:
                work["route_snapshot"] = json_loads(work.pop("route_snapshot_json", ""), {})
                work["predecessor_ids"] = [
                    int(item["predecessor_id"])
                    for item in self.fetch_all(
                        "SELECT predecessor_id FROM fulfillment_work_package_dependencies WHERE successor_id=? ORDER BY predecessor_id",
                        (work["id"],),
                    )
                ]
            package["generation_warnings"] = self.fetch_all(
                """SELECT * FROM fulfillment_bom_generation_warnings
                   WHERE technical_package_id=? ORDER BY blocking DESC, id""",
                (package["id"],),
            )
        door["unfinished_work_packages"] = [
            {"id": item["id"], "name": item["name"], "status": item["status"]}
            for item in (package.get("work_packages", []) if package else [])
            if item["status"] not in {"已完成", "已取消"}
        ]
        door["technical_package"] = package
        door["calculation"] = self.calculation_detail(
            int(package["id"]) if package else -1,
        )
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
        door["component_inventory"] = self._component_inventory_rows(
            door_id, int(package["id"]) if package else -1,
        )
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
        door["workflow"] = build_fulfillment_workflow(door)
        return door

    def latest_bom_package(self, door_id: int) -> Dict[str, Any]:
        package = self.fetch_one(
            """SELECT p.*, d.order_id, d.production_no
               FROM fulfillment_technical_packages p
               JOIN fulfillment_door_units d ON d.id=p.door_unit_id
               WHERE p.door_unit_id=? ORDER BY p.version DESC LIMIT 1""",
            (door_id,),
        )
        if not package:
            raise LookupError("门樘生产单或BOM不存在")
        return package

    def calculation_detail(self, package_id: int) -> Optional[Dict[str, Any]]:
        calculation = self.fetch_one(
            """SELECT c.*, p.version AS bom_version
               FROM fulfillment_calculations c
               JOIN fulfillment_technical_packages p ON p.id=c.technical_package_id
               WHERE c.technical_package_id=? ORDER BY c.version DESC LIMIT 1""",
            (package_id,),
        )
        if not calculation:
            return None
        calculation["items"] = self.fetch_all(
            """SELECT i.*, c.name AS component_name, c.category AS component_category,
                      c.group_code AS component_group_code, c.item_kind AS component_item_kind
               FROM fulfillment_calculation_items i
               JOIN fulfillment_components c ON c.id=i.component_id
               WHERE i.calculation_id=? ORDER BY i.line_no, i.id""",
            (calculation["id"],),
        )
        return calculation

    def _initialize_calculation(
        self,
        conn: sqlite3.Connection,
        package: sqlite3.Row,
        user: Dict[str, Any],
        now: str,
    ) -> int:
        existing = conn.execute(
            """SELECT id FROM fulfillment_calculations
               WHERE technical_package_id=? ORDER BY version DESC LIMIT 1""",
            (package["id"],),
        ).fetchone()
        if existing:
            return int(existing["id"])
        version = int((conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS value FROM fulfillment_calculations WHERE technical_package_id=?",
            (package["id"],),
        ).fetchone() or {"value": 1})["value"] or 1)
        uid = str(user.get("uid") or "")
        cursor = conn.execute(
            """INSERT INTO fulfillment_calculations(
                   door_unit_id, technical_package_id, version, status,
                   created_by, updated_by, created_at, updated_at
               ) VALUES (?, ?, ?, '未算料', ?, ?, ?, ?)""",
            (package["door_unit_id"], package["id"], version, uid, uid, now, now),
        )
        calculation_id = int(cursor.lastrowid)
        components = conn.execute(
            """SELECT * FROM fulfillment_components
               WHERE technical_package_id=?
                 AND (item_kind='manufactured_part' OR (procurement_mode='make' AND item_kind!='assembly'))
               ORDER BY sequence_no, id""",
            (package["id"],),
        ).fetchall()
        for line_no, component in enumerate(components, start=1):
            quantity = float(component["planned_quantity"] or component["quantity"] or 1)
            conn.execute(
                """INSERT INTO fulfillment_calculation_items(
                       calculation_id, component_id, line_no, part_name,
                       material_specification, finished_size, quantity, unit,
                       waste_rate, actual_material_quantity, source_type
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')""",
                (
                    calculation_id, component["id"], line_no, component["name"],
                    component["specification"], component["specification"], quantity,
                    component["unit"], float(component["waste_rate"] or 0), quantity,
                ),
            )
        return calculation_id

    def initialize_calculation(self, door_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            package = conn.execute(
                "SELECT * FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
                (door_id,),
            ).fetchone()
            if not package:
                raise LookupError("门樘生产单或BOM不存在")
            if package["status"] != "已确认":
                raise RuntimeError("请先确认并发布BOM，再开始算料")
            existing = conn.execute(
                "SELECT id FROM fulfillment_calculations WHERE technical_package_id=? ORDER BY version DESC LIMIT 1",
                (package["id"],),
            ).fetchone()
            calculation_id = self._initialize_calculation(conn, package, user, now)
            if not existing:
                self.add_event(
                    conn, order_id=None, door_unit_id=door_id, entity_type="calculation",
                    entity_id=calculation_id, action="开始算料",
                    detail=f"基于BOM V{package['version']}建立算料版本", user=user,
                )
        return self.calculation_detail(int(package["id"])) or {}

    def update_calculation(self, door_id: int, payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            package = conn.execute(
                "SELECT * FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
                (door_id,),
            ).fetchone()
            if not package or package["status"] != "已确认":
                raise RuntimeError("请先确认并发布BOM")
            calculation_id = self._initialize_calculation(conn, package, user, now)
            calculation = conn.execute(
                "SELECT * FROM fulfillment_calculations WHERE id=?", (calculation_id,),
            ).fetchone()
            if calculation["status"] == "已发布":
                raise RuntimeError("算料版本已发布冻结，请随新BOM版本重新算料")
            component_ids = {
                int(row["id"]) for row in conn.execute(
                    "SELECT id FROM fulfillment_components WHERE technical_package_id=?",
                    (package["id"],),
                ).fetchall()
            }
            for item_id in payload.delete_item_ids:
                conn.execute(
                    "DELETE FROM fulfillment_calculation_items WHERE id=? AND calculation_id=?",
                    (item_id, calculation_id),
                )
            for line_no, item in enumerate(payload.items, start=1):
                if int(item.component_id) not in component_ids:
                    raise ValueError("算料明细关联的BOM部件不存在")
                values = (
                    item.component_id, line_no, item.part_name.strip(), item.material_specification,
                    item.finished_size, item.cut_length, item.cut_width, item.quantity, item.unit,
                    item.waste_rate, item.actual_material_quantity, item.grain_direction,
                    item.cutting_method, item.source_type, item.remark,
                )
                if item.id:
                    current = conn.execute(
                        "SELECT id FROM fulfillment_calculation_items WHERE id=? AND calculation_id=?",
                        (item.id, calculation_id),
                    ).fetchone()
                    if not current:
                        raise ValueError("算料明细不存在或不属于当前版本")
                    conn.execute(
                        """UPDATE fulfillment_calculation_items SET
                               component_id=?, line_no=?, part_name=?, material_specification=?,
                               finished_size=?, cut_length=?, cut_width=?, quantity=?, unit=?,
                               waste_rate=?, actual_material_quantity=?, grain_direction=?,
                               cutting_method=?, source_type=?, remark=? WHERE id=?""",
                        (*values, item.id),
                    )
                else:
                    conn.execute(
                        """INSERT INTO fulfillment_calculation_items(
                               calculation_id, component_id, line_no, part_name,
                               material_specification, finished_size, cut_length, cut_width,
                               quantity, unit, waste_rate, actual_material_quantity,
                               grain_direction, cutting_method, source_type, remark
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (calculation_id, *values),
                    )
            conn.execute(
                """UPDATE fulfillment_calculations
                   SET status='算料中', remark=?, updated_by=?, updated_at=? WHERE id=?""",
                (payload.remark, str(user.get("uid") or ""), now, calculation_id),
            )
            self.add_event(
                conn, order_id=None, door_unit_id=door_id, entity_type="calculation",
                entity_id=calculation_id, action="保存算料",
                detail=f"保存 {len(payload.items)} 条算料明细", user=user,
            )
        return self.calculation_detail(int(package["id"])) or {}

    def submit_calculation(self, door_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            package = conn.execute(
                "SELECT * FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
                (door_id,),
            ).fetchone()
            if not package:
                raise LookupError("门樘生产单或BOM不存在")
            calculation = conn.execute(
                "SELECT * FROM fulfillment_calculations WHERE technical_package_id=? ORDER BY version DESC LIMIT 1",
                (package["id"],),
            ).fetchone()
            if not calculation:
                raise RuntimeError("尚未建立算料版本")
            if calculation["status"] == "已发布":
                raise RuntimeError("算料版本已经发布")
            items = conn.execute(
                "SELECT * FROM fulfillment_calculation_items WHERE calculation_id=? ORDER BY line_no, id",
                (calculation["id"],),
            ).fetchall()
            if not items:
                raise ValueError("算料明细不能为空")
            invalid = [row for row in items if not str(row["part_name"] or "").strip() or float(row["quantity"] or 0) <= 0]
            if invalid:
                raise ValueError(f"还有{len(invalid)}条算料明细缺少零件名称或有效数量")
            conn.execute(
                """UPDATE fulfillment_calculations SET status='待确认', confirmed_by=?,
                   confirmed_at=?, updated_by=?, updated_at=? WHERE id=?""",
                (str(user.get("uid") or ""), now, str(user.get("uid") or ""), now, calculation["id"]),
            )
            self.add_event(
                conn, order_id=None, door_unit_id=door_id, entity_type="calculation",
                entity_id=int(calculation["id"]), action="提交算料确认",
                detail=f"算料V{calculation['version']}共{len(items)}条", user=user,
            )
        return self.calculation_detail(int(package["id"])) or {}

    def publish_calculation(self, door_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            package = conn.execute(
                "SELECT * FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
                (door_id,),
            ).fetchone()
            if not package:
                raise LookupError("门樘生产单或BOM不存在")
            calculation = conn.execute(
                "SELECT * FROM fulfillment_calculations WHERE technical_package_id=? ORDER BY version DESC LIMIT 1",
                (package["id"],),
            ).fetchone()
            if not calculation:
                raise RuntimeError("尚未建立算料版本")
            if calculation["status"] == "已发布":
                return self.calculation_detail(int(package["id"])) or {}
            if calculation["status"] != "待确认":
                raise RuntimeError("请先保存并提交算料确认")
            conn.execute(
                """UPDATE fulfillment_calculations SET status='已发布', published_by=?,
                   published_at=?, updated_by=?, updated_at=? WHERE id=?""",
                (str(user.get("uid") or ""), now, str(user.get("uid") or ""), now, calculation["id"]),
            )
            conn.execute(
                """UPDATE fulfillment_door_units SET
                   status=CASE WHEN status IN ('待生产确认','技术准备中') THEN '备料与加工中' ELSE status END,
                   updated_at=? WHERE id=?""",
                (now, door_id),
            )
            WorkPackageService().recompute(conn, door_id=door_id, now=now)
            self.add_event(
                conn, order_id=None, door_unit_id=door_id, entity_type="calculation",
                entity_id=int(calculation["id"]), action="发布下料单",
                detail=f"冻结算料V{calculation['version']}，允许部件下料与加工", user=user,
            )
        return self.calculation_detail(int(package["id"])) or {}

    def list_bom_workbench(self, q: str = "", status: str = "", page: int = 1, page_size: int = 30) -> Dict[str, Any]:
        where = [
            "p.id=(SELECT p2.id FROM fulfillment_technical_packages p2 WHERE p2.door_unit_id=d.id ORDER BY p2.version DESC LIMIT 1)"
        ]
        params: List[Any] = []
        if q:
            term = f"%{q}%"
            where.append(
                "(o.order_no LIKE ? OR o.sales_order_no LIKE ? OR d.production_no LIKE ? OR "
                "o.customer LIKE ? OR o.project LIKE ? OR d.product_name LIKE ?)"
            )
            params.extend([term] * 6)
        rows = self.fetch_all(
            f"""SELECT p.id AS technical_package_id, p.version, p.status,
                       p.generation_status, p.rule_version, p.generated_at,
                       p.blocking_warning_count, p.updated_at,
                       d.id AS door_unit_id, d.production_no, d.product_name,
                       d.specification, d.status AS door_status, d.due_date,
                       o.id AS order_id, o.order_no, o.sales_order_no, o.customer, o.project,
                       (SELECT COUNT(*) FROM fulfillment_components c
                        WHERE c.technical_package_id=p.id) AS item_count,
                       (SELECT COUNT(*) FROM fulfillment_components c
                        WHERE c.technical_package_id=p.id
                          AND c.verification_status!='已核验') AS pending_verification_count,
                       (SELECT COUNT(*) FROM fulfillment_components c
                        WHERE c.technical_package_id=p.id
                          AND ((c.match_status NOT IN ('已匹配','无需物料'))
                               OR (c.match_status='已匹配' AND c.material_id IS NULL)
                               OR c.planned_quantity<=0)) AS missing_data_count,
                       COALESCE((SELECT SUM(i.shortage_quantity)
                         FROM material_requirements r
                         JOIN material_requirement_items i ON i.requirement_id=r.id
                         WHERE r.technical_package_id=p.id), 0) AS shortage_quantity
                FROM fulfillment_technical_packages p
                JOIN fulfillment_door_units d ON d.id=p.door_unit_id
                JOIN fulfillment_orders o ON o.id=d.order_id
                WHERE {' AND '.join(where)}
                ORDER BY CASE p.status WHEN '草稿' THEN 0 ELSE 1 END,
                         p.updated_at DESC, d.production_no""",
            params,
        )
        summary = {
            "total": len(rows),
            "pending_generation": 0,
            "pending_verification": 0,
            "missing_data": 0,
            "shortage": 0,
            "published": 0,
            "changed": 0,
        }
        for row in rows:
            row["states"] = []
            if row["generation_status"] in {"未生成", "生成失败"}:
                row["states"].append("待生成")
                summary["pending_generation"] += 1
            if int(row["pending_verification_count"] or 0) > 0:
                row["states"].append("待核验")
                summary["pending_verification"] += 1
            if int(row["missing_data_count"] or 0) > 0 or int(row["blocking_warning_count"] or 0) > 0:
                row["states"].append("缺少资料")
                summary["missing_data"] += 1
            if float(row["shortage_quantity"] or 0) > 1e-9:
                row["states"].append("缺料")
                summary["shortage"] += 1
            if row["status"] == "已确认":
                row["states"].append("已发布")
                summary["published"] += 1
            if int(row["version"] or 1) > 1:
                row["states"].append("已变更")
                summary["changed"] += 1
        filtered = [row for row in rows if not status or status in row["states"]]
        total = len(filtered)
        offset = (page - 1) * page_size
        return {
            "summary": summary,
            "items": filtered[offset:offset + page_size],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size,
            },
        }

    def get_bom_detail(self, door_id: int, version: Optional[int] = None) -> Dict[str, Any]:
        version_clause = "AND p.version=?" if version is not None else ""
        params: Sequence[Any] = (door_id, version) if version is not None else (door_id,)
        package = self.fetch_one(
            f"""SELECT p.*, d.order_id, d.production_no, d.product_name,
                       d.specification, d.status AS door_status, d.due_date,
                       o.order_no, o.sales_order_no, o.customer, o.project
                FROM fulfillment_technical_packages p
                JOIN fulfillment_door_units d ON d.id=p.door_unit_id
                JOIN fulfillment_orders o ON o.id=d.order_id
                WHERE p.door_unit_id=? {version_clause}
                ORDER BY p.version DESC LIMIT 1""",
            params,
        )
        if not package:
            raise LookupError("指定门樘或BOM版本不存在")
        package["product_snapshot"] = json_loads(package.pop("product_snapshot_json", ""), {})
        package["generation_summary"] = json_loads(package.pop("generation_summary_json", ""), {})
        rows = self.fetch_all(
            """SELECT c.*, m.code AS material_code, m.name AS material_name,
                      m.specification AS material_specification, m.unit AS material_unit,
                      s.name AS supplier_name
               FROM fulfillment_components c
               LEFT JOIN inventory_materials m ON m.id=c.material_id
               LEFT JOIN inventory_suppliers s ON s.id=c.supplier_id
               WHERE c.technical_package_id=? ORDER BY c.line_no, c.id""",
            (package["id"],),
        )
        for row in rows:
            row["source_payload"] = json_loads(row.pop("source_payload_json", ""), {})
            row["attachments"] = json_loads(row.pop("attachments_json", ""), [])
            row["drawing_parameters"] = json_loads(row.pop("drawing_parameter_json", ""), {})
        group_labels = {
            "frame": "门框与门槛", "panel": "门扇与面板", "skeleton": "骨架与型材",
            "trim": "门套/门头/门柱", "glass": "玻璃与线条", "hardware": "五金与开启机构",
            "ornament": "花件与外购装饰", "consumable": "辅料与耗材", "packaging": "包装",
            "subcontract": "外协加工", "other": "其他",
        }
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row["group_code"] or "other"), []).append(row)
        groups = [
            {"code": code, "label": group_labels.get(code, code), "count": len(items), "rows": items}
            for code, items in grouped.items()
        ]
        warnings = self.fetch_all(
            """SELECT * FROM fulfillment_bom_generation_warnings
               WHERE technical_package_id=? ORDER BY created_at DESC, blocking DESC, id DESC""",
            (package["id"],),
        )
        history = self.fetch_all(
            """SELECT id AS technical_package_id, version, status, generation_status,
                      rule_version, blocking_warning_count, source_version_id,
                      created_by, confirmed_by, created_at, updated_at, confirmed_at
               FROM fulfillment_technical_packages
               WHERE door_unit_id=? ORDER BY version DESC""",
            (door_id,),
        )
        downstream = {
            "requirement_count": int((self.fetch_one(
                "SELECT COUNT(*) AS value FROM material_requirements WHERE technical_package_id=?",
                (package["id"],),
            ) or {"value": 0})["value"] or 0),
            "supply_count": int((self.fetch_one(
                "SELECT COUNT(*) AS value FROM fulfillment_supplies WHERE technical_package_id=?",
                (package["id"],),
            ) or {"value": 0})["value"] or 0),
            "work_package_count": int((self.fetch_one(
                "SELECT COUNT(*) AS value FROM fulfillment_work_packages WHERE technical_package_id=?",
                (package["id"],),
            ) or {"value": 0})["value"] or 0),
        }
        package.update({
            "rows": rows,
            "groups": groups,
            "warnings": warnings,
            "version_history": history,
            "downstream_impact": downstream,
        })
        return package

    def update_bom_draft(self, door_id: int, payload: Any, user: Dict[str, Any]) -> None:
        now = fulfillment_now()
        with self.transaction() as conn:
            package = conn.execute(
                "SELECT * FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
                (door_id,),
            ).fetchone()
            if not package:
                raise LookupError("门樘生产单或BOM不存在")
            if package["status"] != "草稿":
                raise RuntimeError("BOM版本已确认冻结，请创建新版本后修改")
            package_id = int(package["id"])
            if payload.product_summary is not None or payload.special_requirements is not None or payload.frame_trim_mode is not None:
                conn.execute(
                    """UPDATE fulfillment_technical_packages
                       SET product_summary=COALESCE(?, product_summary),
                           special_requirements=COALESCE(?, special_requirements),
                           frame_trim_mode=COALESCE(?, frame_trim_mode), updated_at=?
                       WHERE id=?""",
                    (payload.product_summary, payload.special_requirements, payload.frame_trim_mode, now, package_id),
                )
            for item_id in payload.delete_item_ids:
                row = conn.execute(
                    "SELECT id FROM fulfillment_components WHERE id=? AND technical_package_id=?",
                    (item_id, package_id),
                ).fetchone()
                if not row:
                    raise ValueError(f"BOM行 {item_id} 不存在或不属于当前版本")
                conn.execute("DELETE FROM fulfillment_components WHERE id=?", (item_id,))

            allowed = {
                "material_id", "name", "category", "specification", "theoretical_quantity",
                "waste_rate", "planned_quantity", "quantity", "unit", "acquisition_method",
                "group_code", "operation_code", "supplier_id", "required_date", "remark",
                "parent_id", "item_kind", "procurement_mode", "drawing_parameter_json",
            }
            for item in payload.items:
                values = item.model_dump(exclude_unset=True)
                item_id = values.pop("id", None)
                if "drawing_parameters" in values:
                    values["drawing_parameter_json"] = json_dumps(values.pop("drawing_parameters") or {})
                current = None
                if item_id is not None:
                    current = conn.execute(
                        "SELECT * FROM fulfillment_components WHERE id=? AND technical_package_id=?",
                        (item_id, package_id),
                    ).fetchone()
                    if not current:
                        raise ValueError(f"BOM行 {item_id} 不存在或不属于当前版本")
                parent_id = values.get("parent_id", current["parent_id"] if current else None)
                if parent_id is not None:
                    if item_id is not None and int(parent_id) == int(item_id):
                        raise ValueError("BOM行不能以自身作为父级")
                    parent = conn.execute(
                        "SELECT id FROM fulfillment_components WHERE id=? AND technical_package_id=?",
                        (parent_id, package_id),
                    ).fetchone()
                    if not parent:
                        raise ValueError(f"父级BOM行 {parent_id} 不存在或不属于当前版本")
                item_kind = str(values.get("item_kind", current["item_kind"] if current else "material") or "material")
                procurement_mode = str(values.get("procurement_mode", current["procurement_mode"] if current else "stock") or "stock")
                is_self_made = procurement_mode == "make" or item_kind in {"assembly", "manufactured_part"}
                material_explicit = "material_id" in values
                if is_self_made:
                    values["material_id"] = None
                if not is_self_made and material_explicit and values["material_id"] is not None:
                    material = conn.execute(
                        "SELECT id FROM inventory_materials WHERE id=? AND is_active=1",
                        (values["material_id"],),
                    ).fetchone()
                    if not material:
                        raise ValueError(f"物料档案 {values['material_id']} 不存在或已停用")
                if item_id is not None:
                    updates = {key: value for key, value in values.items() if key in allowed}
                    if "planned_quantity" in updates:
                        updates["quantity"] = updates["planned_quantity"]
                    elif "quantity" in updates:
                        updates["planned_quantity"] = updates["quantity"]
                    elif "theoretical_quantity" in updates or "waste_rate" in updates:
                        theoretical = float(updates.get("theoretical_quantity", current["theoretical_quantity"]) or 0)
                        waste_rate = float(updates.get("waste_rate", current["waste_rate"]) or 0)
                        calculated = theoretical * (1 + max(0.0, waste_rate) / 100)
                        unit = str(updates.get("unit", current["unit"]) or "件")
                        planned = float(math.ceil(calculated)) if unit in {"个", "件", "扇", "块", "套"} else round(calculated, 4)
                        updates["planned_quantity"] = planned
                        updates["quantity"] = planned
                    if is_self_made:
                        updates["match_status"] = "无需物料"
                    elif material_explicit or "item_kind" in updates or "procurement_mode" in updates:
                        updates["match_status"] = "已匹配" if updates.get("material_id") is not None else "待匹配"
                    if updates:
                        updates["verification_status"] = "已核验" if is_self_made else "待核验"
                        assignments = ", ".join(f"{key}=?" for key in updates)
                        conn.execute(
                            f"UPDATE fulfillment_components SET {assignments} WHERE id=?",
                            (*updates.values(), item_id),
                        )
                else:
                    name = str(values.get("name") or "").strip()
                    if not name:
                        raise ValueError("新增BOM行必须填写名称")
                    line_no = int((conn.execute(
                        "SELECT COALESCE(MAX(line_no), 0) AS value FROM fulfillment_components WHERE technical_package_id=?",
                        (package_id,),
                    ).fetchone() or {"value": 0})["value"] or 0) + 1
                    if "planned_quantity" in values or "quantity" in values:
                        planned = float(values.get("planned_quantity", values.get("quantity", 0)) or 0)
                        theoretical = float(values.get("theoretical_quantity", planned) or 0)
                    else:
                        theoretical = float(values.get("theoretical_quantity") or 0)
                        waste_rate = float(values.get("waste_rate") or 0)
                        calculated = theoretical * (1 + max(0.0, waste_rate) / 100)
                        unit = str(values.get("unit") or "件")
                        planned = float(math.ceil(calculated)) if unit in {"个", "件", "扇", "块", "套"} else round(calculated, 4)
                    material_id = values.get("material_id")
                    match_status = "无需物料" if is_self_made else ("已匹配" if material_id is not None else "待匹配")
                    verification_status = "已核验" if is_self_made else "待核验"
                    conn.execute(
                        """INSERT INTO fulfillment_components(
                               technical_package_id, parent_id, material_id, name, category, specification,
                               quantity, unit, acquisition_method, remark, sequence_no, line_no,
                               group_code, theoretical_quantity, waste_rate, planned_quantity,
                               source_type, source_payload_json, match_status, verification_status,
                               operation_code, supplier_id, required_date, attachments_json,
                               item_kind, procurement_mode, drawing_parameter_json
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                     'manual', '{}', ?, ?, ?, ?, ?, '[]', ?, ?, ?)""",
                        (
                            package_id, parent_id, material_id, name, str(values.get("category") or "其他"),
                            str(values.get("specification") or ""), planned,
                            str(values.get("unit") or "件"), str(values.get("acquisition_method") or "待确定"),
                            str(values.get("remark") or ""), line_no, line_no,
                            str(values.get("group_code") or "other"), theoretical,
                            float(values.get("waste_rate") or 0), planned,
                            match_status, verification_status,
                            str(values.get("operation_code") or "MANUAL"), values.get("supplier_id"),
                            str(values.get("required_date") or ""), item_kind, procurement_mode,
                            str(values.get("drawing_parameter_json") or "{}"),
                        ),
                    )
            unresolved = int((conn.execute(
                """SELECT COUNT(*) AS value FROM fulfillment_components
                   WHERE technical_package_id=?
                     AND ((match_status NOT IN ('已匹配','无需物料'))
                          OR (match_status='已匹配' AND material_id IS NULL)
                          OR planned_quantity<=0)""",
                (package_id,),
            ).fetchone() or {"value": 0})["value"] or 0)
            conn.execute(
                """UPDATE fulfillment_technical_packages
                   SET blocking_warning_count=?, generation_status=CASE WHEN ?>0 THEN '待完善' ELSE '已生成' END,
                       updated_at=? WHERE id=?""",
                (unresolved, unresolved, now, package_id),
            )
            self.add_event(
                conn, order_id=None, door_unit_id=door_id, entity_type="technical_package",
                entity_id=package_id, action="保存BOM草稿",
                detail=f"更新 {len(payload.items)} 项，删除 {len(payload.delete_item_ids)} 项",
                user=user,
            )

    def verify_bom_items(self, door_id: int, item_ids: List[int], user: Dict[str, Any]) -> None:
        now = fulfillment_now()
        with self.transaction() as conn:
            package = conn.execute(
                "SELECT * FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
                (door_id,),
            ).fetchone()
            if not package:
                raise LookupError("门樘生产单或BOM不存在")
            if package["status"] != "草稿":
                raise RuntimeError("BOM版本已确认冻结，不能继续核验")
            placeholders = ",".join("?" for _ in item_ids)
            conn.execute(
                f"""UPDATE fulfillment_components SET verification_status='已核验'
                    WHERE technical_package_id=? AND id IN ({placeholders})""",
                (package["id"], *item_ids),
            )
            self.add_event(
                conn, order_id=None, door_unit_id=door_id, entity_type="technical_package",
                entity_id=int(package["id"]), action="核验BOM明细",
                detail=f"核验 {len(item_ids)} 项", user=user,
            )

    def publish_bom(self, door_id: int, remark: str, user: Dict[str, Any]) -> bool:
        now = fulfillment_now()
        with self.transaction() as conn:
            package = conn.execute(
                "SELECT * FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
                (door_id,),
            ).fetchone()
            if not package:
                raise LookupError("门樘生产单或BOM不存在")
            if package["status"] not in {"草稿", "已确认"}:
                raise RuntimeError("当前BOM状态不能发布")
            already_published = package["status"] == "已确认"
            requirement = self.requirement_service.create_for_package(
                conn=conn,
                door_id=door_id,
                package_id=int(package["id"]),
                created_by=str(user.get("uid") or ""),
            )
            from purchasing_service import PurchasingService

            PurchasingService(self.inventory_db).sync_demands(conn)
            generated_work_count = WorkPackageService().generate_for_package(
                conn, door_id=door_id, package_id=int(package["id"]), now=now,
            )
            if not already_published:
                self._initialize_calculation(conn, package, user, now)
                conn.execute(
                    """UPDATE fulfillment_technical_packages
                       SET status='已确认', confirmed_by=?, confirmed_at=?, updated_at=? WHERE id=?""",
                    (str(user.get("uid") or ""), now, now, package["id"]),
                )
                conn.execute(
                    """UPDATE fulfillment_door_units
                       SET active_version=?, technical_uid=?,
                           status=CASE WHEN status='待生产确认' THEN '技术准备中' ELSE status END,
                           updated_at=? WHERE id=?""",
                    (package["version"], str(user.get("uid") or ""), now, door_id),
                )
                self.add_event(
                    conn, order_id=None, door_unit_id=door_id, entity_type="technical_package",
                    entity_id=int(package["id"]), action="发布BOM版本",
                    detail=(
                        f"冻结 V{package['version']}，生成需求 {requirement['requirement_no']}，"
                        f"建立算料版本并预生成工作包 {generated_work_count} 项"
                        f"{'；' + remark if remark else ''}"
                    ),
                    user=user,
                )
            WorkPackageService().recompute(conn, door_id=door_id, now=now)
            return already_published

    def diff_bom_versions(self, door_id: int, from_version: int, to_version: int) -> Dict[str, Any]:
        packages = self.fetch_all(
            """SELECT id, version FROM fulfillment_technical_packages
               WHERE door_unit_id=? AND version IN (?, ?)""",
            (door_id, from_version, to_version),
        )
        package_ids = {int(row["version"]): int(row["id"]) for row in packages}
        if from_version not in package_ids or to_version not in package_ids:
            raise LookupError("对比的BOM版本不存在")

        def version_rows(package_id: int) -> Dict[str, Dict[str, Any]]:
            result: Dict[str, Dict[str, Any]] = {}
            for row in self.fetch_all(
                "SELECT * FROM fulfillment_components WHERE technical_package_id=? ORDER BY line_no, id",
                (package_id,),
            ):
                source = json_loads(row.pop("source_payload_json", ""), {})
                row.pop("attachments_json", None)
                key = str(source.get("geometry_ref") or "")
                if not key:
                    key = "|".join((
                        str(row.get("line_no") or ""), str(row.get("group_code") or ""),
                        str(row.get("operation_code") or ""), str(row.get("name") or ""),
                    ))
                row["source_payload"] = source
                result[key] = row
            return result

        before = version_rows(package_ids[from_version])
        after = version_rows(package_ids[to_version])
        comparable = (
            "material_id", "name", "category", "specification", "theoretical_quantity",
            "waste_rate", "planned_quantity", "unit", "acquisition_method", "group_code",
            "operation_code", "supplier_id", "required_date", "remark", "parent_id",
            "item_kind", "procurement_mode", "drawing_parameter_json",
        )
        changed = []
        for key in sorted(before.keys() & after.keys()):
            fields = {
                field: {"from": before[key].get(field), "to": after[key].get(field)}
                for field in comparable if before[key].get(field) != after[key].get(field)
            }
            if fields:
                changed.append({"key": key, "fields": fields, "from": before[key], "to": after[key]})
        return {
            "door_unit_id": door_id,
            "from_version": from_version,
            "to_version": to_version,
            "added": [after[key] for key in sorted(after.keys() - before.keys())],
            "removed": [before[key] for key in sorted(before.keys() - after.keys())],
            "changed": changed,
            "unchanged_count": len(before.keys() & after.keys()) - len(changed),
        }

    def dashboard(self) -> Dict[str, Any]:
        counts = {status: 0 for status in DOOR_STATUSES}
        for row in self.fetch_all("SELECT status, COUNT(*) AS total FROM fulfillment_door_units GROUP BY status"):
            counts[row["status"]] = row["total"]
        stage_counts = {
            key: sum(int(counts.get(status) or 0) for status in statuses)
            for key, statuses in WORKFLOW_STAGE_STATUSES.items()
        }
        return {
            "status_counts": counts,
            "stage_counts": stage_counts,
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
                    """INSERT INTO fulfillment_components(
                           technical_package_id, parent_id, material_id, name, category,
                           specification, quantity, unit, acquisition_method, remark,
                           sequence_no, line_no, group_code, theoretical_quantity,
                           waste_rate, planned_quantity, source_type, source_rule_version,
                           source_payload_json, match_status, verification_status,
                           operation_code, supplier_id, required_date, attachments_json,
                           item_kind, procurement_mode, drawing_parameter_json
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        package_id, parent_id,
                        None if item.procurement_mode == "make" or item.item_kind in {"assembly", "manufactured_part"} else item.material_id,
                        item.name.strip(), item.category,
                        item.specification, item.planned_quantity if item.planned_quantity is not None else item.quantity,
                        item.unit, item.acquisition_method, item.remark, sequence,
                        item.line_no or sequence, item.group_code,
                        item.theoretical_quantity if item.theoretical_quantity is not None else item.quantity,
                        item.waste_rate,
                        item.planned_quantity if item.planned_quantity is not None else item.quantity,
                        item.source_type, item.source_rule_version, json_dumps(item.source_payload),
                        "无需物料" if item.procurement_mode == "make" or item.item_kind in {"assembly", "manufactured_part"} else item.match_status,
                        "已核验" if item.procurement_mode == "make" or item.item_kind in {"assembly", "manufactured_part"} else item.verification_status,
                        item.operation_code, item.supplier_id, item.required_date, json_dumps(item.attachments),
                        item.item_kind, item.procurement_mode, json_dumps(item.drawing_parameters),
                    ),
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
            WorkPackageService().recompute(conn, door_id=door_id, now=now)
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
            if target == "进行中" and current != "进行中":
                row = WorkPackageService().ensure_startable(conn, work_id=work_id, now=now)
            if bool(row["inspection_required"]) and target == "已完成" and current not in {"待质检", "返工"}:
                raise RuntimeError("该工作包要求质检，必须先提交到“待质检”")
            executor = payload.executor_uid or row["executor_uid"] or str(user.get("uid") or "")
            employee = conn.execute(
                "SELECT id FROM workforce_employees WHERE employee_no=? AND is_active=1",
                (executor,),
            ).fetchone()
            started_at = row["started_at"] or (now if target == "进行中" else None)
            completed_at = now if target == "已完成" else row["completed_at"]
            actual = row["actual_quantity"] if payload.actual_quantity is None else payload.actual_quantity
            scrap = row["scrap_quantity"] if payload.scrap_quantity is None else payload.scrap_quantity
            actual_minutes = row["actual_minutes"] if payload.actual_minutes is None else payload.actual_minutes
            submitted_at = now if target in {"待质检", "已完成"} else row["submitted_at"]
            conn.execute(
                """UPDATE fulfillment_work_packages
                   SET status=?, executor_uid=?, employee_id=?, actual_quantity=?, scrap_quantity=?, actual_minutes=?,
                       remark=?, started_at=?, submitted_at=?, completed_at=?, updated_at=? WHERE id=?""",
                (target, executor, employee["id"] if employee else None, actual, scrap, actual_minutes, payload.remark, started_at, submitted_at, completed_at, now, work_id),
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
            WorkPackageService().recompute(conn, door_id=door_id, now=now)
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
                    WHERE door_unit_id=? AND technical_package_id=? AND id IN ({placeholders})
                    ORDER BY sequence_no, id""",
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
                if payload.action == "开始":
                    row = WorkPackageService().ensure_startable(conn, work_id=int(row["id"]), now=now)
                if payload.action == "提交质检" and current not in {"待排单", "已排单", "进行中", "返工"}:
                    raise RuntimeError(f"{row['name']} 当前为“{current}”，不能提交质检")
                if payload.action == "提交质检" and current in {"待排单", "已排单", "返工"}:
                    row = WorkPackageService().ensure_startable(conn, work_id=int(row["id"]), now=now)
                if payload.action == "确认完成":
                    if bool(row["inspection_required"]) and current not in {"待质检", "返工"}:
                        raise RuntimeError(f"{row['name']}要求过程检验，请先提交质检")
                    if current not in {"待排单", "已排单", "进行中", "待质检", "返工"}:
                        raise RuntimeError(f"{row['name']} 当前为“{current}”，不能确认完成")
                    if current in {"待排单", "已排单", "返工"}:
                        row = WorkPackageService().ensure_startable(conn, work_id=int(row["id"]), now=now)
                executor = payload.executor_uid or row["executor_uid"] or str(user.get("uid") or "")
                employee = conn.execute(
                    "SELECT id FROM workforce_employees WHERE employee_no=? AND is_active=1",
                    (executor,),
                ).fetchone()
                started_at = row["started_at"] or (now if target in {"进行中", "待质检", "已完成"} else None)
                completed_at = now if target in {"已完成", "已取消"} else row["completed_at"]
                submitted_at = now if target in {"待质检", "已完成"} else row["submitted_at"]
                actual = row["quantity"] if target == "已完成" else row["actual_quantity"]
                scrap = row["scrap_quantity"] if payload.scrap_quantity is None else payload.scrap_quantity
                actual_minutes = row["actual_minutes"] if payload.actual_minutes is None else payload.actual_minutes
                remark = str(payload.remark or row["remark"] or "")
                conn.execute(
                    """UPDATE fulfillment_work_packages SET status=?, executor_uid=?, employee_id=?, actual_quantity=?,
                       scrap_quantity=?, actual_minutes=?, remark=?,
                       started_at=?, submitted_at=?, completed_at=?, skip_reason=?, updated_at=? WHERE id=?""",
                    (target, executor, employee["id"] if employee else None, actual, scrap, actual_minutes, remark, started_at, submitted_at, completed_at,
                     remark if payload.action == "跳过" else str(row["skip_reason"] or ""), now, row["id"]),
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
                WorkPackageService().recompute(conn, door_id=door_id, now=now)
        return self.get_door_unit(door_id) or {}, changed

    def _refresh_door_progress(self, conn: sqlite3.Connection, door_id: int, now: str) -> None:
        WorkPackageService().refresh_progress(conn, door_id=door_id, now=now)

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
                """INSERT INTO fulfillment_technical_packages(
                       door_unit_id, version, status, product_snapshot_json,
                       product_summary, special_requirements, frame_trim_mode, generation_status,
                       rule_version, generation_summary_json, blocking_warning_count,
                       source_version_id, created_by, created_at, updated_at
                   ) VALUES (?, ?, '草稿', ?, ?, ?, ?, '已复制', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    door_id, next_version, source["product_snapshot_json"], source["product_summary"],
                    source["special_requirements"], source["frame_trim_mode"], source["rule_version"],
                    source["generation_summary_json"], source["blocking_warning_count"],
                    source["id"], str(user.get("uid") or ""), now, now,
                ),
            )
            new_package_id = int(package_cursor.lastrowid)
            conn.execute(
                """UPDATE fulfillment_work_packages SET status='暂停', remark=CASE WHEN remark='' THEN '等待生产变更确认' ELSE remark END, updated_at=?
                   WHERE technical_package_id=? AND status NOT IN ('已完成','已取消')""",
                (now, source["id"]),
            )
            old_to_new: Dict[int, int] = {}
            source_components = conn.execute(
                "SELECT * FROM fulfillment_components WHERE technical_package_id=? ORDER BY sequence_no, id",
                (source["id"],),
            ).fetchall()
            for component in source_components:
                cursor = conn.execute(
                    """INSERT INTO fulfillment_components(
                           technical_package_id, parent_id, material_id, name, category,
                           specification, quantity, unit, acquisition_method, remark,
                           sequence_no, line_no, group_code, theoretical_quantity,
                           waste_rate, planned_quantity, source_type, source_rule_version,
                           source_payload_json, match_status, verification_status,
                           operation_code, supplier_id, required_date, attachments_json,
                           item_kind, procurement_mode, drawing_parameter_json
                       ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        new_package_id, component["material_id"], component["name"], component["category"],
                        component["specification"], component["quantity"], component["unit"],
                        component["acquisition_method"], component["remark"], component["sequence_no"],
                        component["line_no"], component["group_code"], component["theoretical_quantity"],
                        component["waste_rate"], component["planned_quantity"], component["source_type"],
                        component["source_rule_version"], component["source_payload_json"],
                        component["match_status"], component["verification_status"], component["operation_code"],
                        component["supplier_id"], component["required_date"], component["attachments_json"],
                        component["item_kind"], component["procurement_mode"], component["drawing_parameter_json"],
                    ),
                )
                old_to_new[int(component["id"])] = int(cursor.lastrowid)
            for component in source_components:
                parent_id = component["parent_id"]
                if parent_id is not None and int(parent_id) in old_to_new:
                    conn.execute(
                        "UPDATE fulfillment_components SET parent_id=? WHERE id=?",
                        (old_to_new[int(parent_id)], old_to_new[int(component["id"])]),
                    )
            for work in conn.execute("SELECT * FROM fulfillment_work_packages WHERE technical_package_id=? ORDER BY sequence_no, id", (source["id"],)).fetchall():
                conn.execute(
                    """INSERT INTO fulfillment_work_packages(technical_package_id, door_unit_id, component_id, name, category, route, acquisition_method, executor_uid, planned_start, planned_end, opening_condition, blocking_node, quantity, unit, piece_rate, inspection_required, remark, sequence_no, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (new_package_id, door_id, old_to_new.get(work["component_id"]), work["name"], work["category"], work["route"], work["acquisition_method"], work["executor_uid"], work["planned_start"], work["planned_end"], work["opening_condition"], work["blocking_node"], work["quantity"], work["unit"], work["piece_rate"], work["inspection_required"], work["remark"], work["sequence_no"], now),
                )
            conn.execute("UPDATE fulfillment_door_units SET status='技术准备中', updated_at=? WHERE id=?", (now, door_id))
            WorkPackageService().recompute(conn, door_id=door_id, now=now)
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
            WorkPackageService().recompute(conn, door_id=door_id, now=now)
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
            package = conn.execute(
                "SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
                (door_id,),
            ).fetchone()
            conn.execute(
                """INSERT INTO fulfillment_inventory_movements(
                       door_unit_id, technical_package_id, movement_type, item_name,
                       warehouse, location, quantity, unit, remark, operator_uid, created_at
                   ) VALUES (?, ?, '成品入库', ?, ?, ?, ?, '樘', ?, ?, ?)""",
                (door_id, package["id"] if package else None, door["production_no"], payload.warehouse,
                 payload.location, payload.quantity, payload.remark, str(user.get("uid") or ""), now),
            )
            conn.execute("UPDATE fulfillment_door_units SET status='已入库待发货', progress=100, updated_at=? WHERE id=?", (now, door_id))
            self.add_event(conn, order_id=int(door["order_id"]), door_unit_id=door_id, entity_type="inventory", entity_id=None, action="成品入库", detail=f"{payload.warehouse} {payload.location}，{payload.quantity} 樘", user=user)
        return self.get_door_unit(door_id) or {}

    def _component_inventory_rows(self, door_id: int, package_id: int) -> List[Dict[str, Any]]:
        if package_id <= 0:
            return []
        rows = self.fetch_all(
            """SELECT c.id AS component_id, c.name, c.category, c.specification,
                      c.planned_quantity, c.unit, c.operation_code,
                      COALESCE(SUM(CASE WHEN m.movement_type='半成品入库' THEN m.quantity ELSE 0 END), 0) AS inbound_quantity,
                      COALESCE(SUM(CASE WHEN m.movement_type='拼装领用' THEN m.quantity ELSE 0 END), 0) AS issued_quantity,
                      MAX(CASE WHEN m.movement_type='半成品入库' THEN m.warehouse ELSE '' END) AS warehouse,
                      MAX(CASE WHEN m.movement_type='半成品入库' THEN m.location ELSE '' END) AS location
               FROM fulfillment_components c
               LEFT JOIN fulfillment_inventory_movements m
                 ON m.component_id=c.id AND m.technical_package_id=c.technical_package_id
               WHERE c.technical_package_id=? AND c.item_kind='manufactured_part'
               GROUP BY c.id ORDER BY c.sequence_no, c.id""",
            (package_id,),
        )
        for row in rows:
            row["planned_quantity"] = float(row["planned_quantity"] or 0)
            row["inbound_quantity"] = float(row["inbound_quantity"] or 0)
            row["issued_quantity"] = float(row["issued_quantity"] or 0)
            row["available_quantity"] = max(0.0, row["inbound_quantity"] - row["issued_quantity"])
            row["remaining_inbound_quantity"] = max(0.0, row["planned_quantity"] - row["inbound_quantity"])
        return rows

    def component_inbound(self, door_id: int, payload: Any, user: Dict[str, Any]) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            component = conn.execute(
                """SELECT c.*, d.production_no, d.order_id
                   FROM fulfillment_components c
                   JOIN fulfillment_technical_packages p ON p.id=c.technical_package_id
                   JOIN fulfillment_door_units d ON d.id=p.door_unit_id
                   WHERE c.id=? AND d.id=?
                     AND p.id=(SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1)""",
                (payload.component_id, door_id, door_id),
            ).fetchone()
            if not component:
                raise LookupError("当前生产版本中不存在该部件")
            if component["item_kind"] != "manufactured_part" or component["procurement_mode"] != "make":
                raise ValueError("只有按图自制部件可以转入半成品仓")
            inbound = float((conn.execute(
                """SELECT COALESCE(SUM(quantity), 0) AS total FROM fulfillment_inventory_movements
                   WHERE technical_package_id=? AND component_id=? AND movement_type='半成品入库'""",
                (component["technical_package_id"], component["id"]),
            ).fetchone() or {"total": 0})["total"] or 0)
            planned = float(component["planned_quantity"] or component["quantity"] or 0)
            if inbound + float(payload.quantity) > planned + 1e-6:
                raise ValueError(f"入库数量超过计划数：计划 {planned:g} {component['unit']}，已入 {inbound:g} {component['unit']}")
            conn.execute(
                """INSERT INTO fulfillment_inventory_movements(
                       door_unit_id, technical_package_id, component_id, movement_type,
                       item_name, warehouse, location, quantity, unit, remark, operator_uid, created_at
                   ) VALUES (?, ?, ?, '半成品入库', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (door_id, component["technical_package_id"], component["id"], component["name"],
                 payload.warehouse, payload.location, payload.quantity, component["unit"], payload.remark,
                 str(user.get("uid") or ""), now),
            )
            self.add_event(
                conn, order_id=int(component["order_id"]), door_unit_id=door_id,
                entity_type="inventory", entity_id=int(component["id"]), action="半成品入库",
                detail=f"{component['name']} {payload.quantity:g} {component['unit']} → {payload.warehouse} {payload.location}".strip(),
                user=user,
            )
        return self.get_door_unit(door_id) or {}

    def issue_assembly_components(self, door_id: int, remark: str, user: Dict[str, Any]) -> tuple[Dict[str, Any], int]:
        now = fulfillment_now()
        with self.transaction() as conn:
            door = conn.execute("SELECT * FROM fulfillment_door_units WHERE id=?", (door_id,)).fetchone()
            if not door:
                raise LookupError("门樘生产单不存在")
            package = conn.execute(
                "SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
                (door_id,),
            ).fetchone()
            if not package:
                raise LookupError("生产BOM不存在")
            parts = conn.execute(
                """SELECT c.*,
                          COALESCE(SUM(CASE WHEN m.movement_type='半成品入库' THEN m.quantity ELSE 0 END), 0) AS inbound_quantity,
                          COALESCE(SUM(CASE WHEN m.movement_type='拼装领用' THEN m.quantity ELSE 0 END), 0) AS issued_quantity
                   FROM fulfillment_components c
                   LEFT JOIN fulfillment_inventory_movements m
                     ON m.component_id=c.id AND m.technical_package_id=c.technical_package_id
                   WHERE c.technical_package_id=? AND c.item_kind='manufactured_part'
                   GROUP BY c.id ORDER BY c.sequence_no, c.id""",
                (package["id"],),
            ).fetchall()
            if not parts:
                raise RuntimeError("当前BOM没有需要领用的自制半成品")
            shortages = []
            for part in parts:
                planned = float(part["planned_quantity"] or part["quantity"] or 0)
                inbound = float(part["inbound_quantity"] or 0)
                issued = float(part["issued_quantity"] or 0)
                if inbound - issued + 1e-6 < planned - issued:
                    shortages.append(f"{part['name']} {max(0.0, inbound-issued):g}/{max(0.0, planned-issued):g}{part['unit']}")
            if shortages:
                raise RuntimeError("以下半成品尚未备齐：" + "；".join(shortages[:6]))
            changed = 0
            for part in parts:
                planned = float(part["planned_quantity"] or part["quantity"] or 0)
                issued = float(part["issued_quantity"] or 0)
                quantity = max(0.0, planned - issued)
                if quantity <= 1e-6:
                    continue
                conn.execute(
                    """INSERT INTO fulfillment_inventory_movements(
                           door_unit_id, technical_package_id, component_id, movement_type,
                           item_name, warehouse, quantity, unit, remark, operator_uid, created_at
                       ) VALUES (?, ?, ?, '拼装领用', ?, '半成品仓', ?, ?, ?, ?, ?)""",
                    (door_id, package["id"], part["id"], part["name"], quantity, part["unit"], remark,
                     str(user.get("uid") or ""), now),
                )
                changed += 1
            if not changed:
                raise RuntimeError("当前半成品已经全部领用，无需重复操作")
            self.add_event(
                conn, order_id=int(door["order_id"]), door_unit_id=door_id,
                entity_type="inventory", entity_id=None, action="拼装领用",
                detail=f"领用 {changed} 项自制半成品进入整门拼装" + (f"；{remark}" if remark else ""),
                user=user,
            )
        return self.get_door_unit(door_id) or {}, changed

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

    def create_shipment(
        self,
        door_id: int,
        payload: Any,
        user: Dict[str, Any],
        sales_finance: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = fulfillment_now()
        with self.transaction() as conn:
            door = conn.execute("SELECT * FROM fulfillment_door_units WHERE id=?", (door_id,)).fetchone()
            if not door:
                raise LookupError("门樘生产单不存在")
            if door["status"] not in {"已入库待发货", "待财务放行", "待出库"}:
                raise RuntimeError("门樘尚未完成成品入库，不能发货")
            authorized = bool(payload.authorization_reason.strip() and payload.authorized_by.strip())
            if sales_finance is not None:
                paid = float(sales_finance.get("paid_amount") or 0)
                unpaid = float(sales_finance.get("unpaid_amount") or 0)
                required_payment = float(sales_finance.get("total_amount") or 0)
                available = paid
                if unpaid > 0.005 and not authorized:
                    raise RuntimeError(f"订单尚有未收款 {unpaid:.2f} 元；请先在订单确认登记收款，或填写授权原因和授权人放行")
            else:
                paid = float(conn.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM fulfillment_payments WHERE order_id=?", (door["order_id"],)).fetchone()["total"] or 0)
                allocated = float(conn.execute(
                    """SELECT COALESCE(SUM(s.required_payment), 0) AS total FROM fulfillment_shipments s
                       JOIN fulfillment_door_units d2 ON d2.id=s.door_unit_id
                       WHERE d2.order_id=? AND s.authorized=0""",
                    (door["order_id"],),
                ).fetchone()["total"] or 0)
                available = max(0.0, paid - allocated)
                required_payment = float(payload.required_payment or 0)
                if available < required_payment and not authorized:
                    raise RuntimeError(f"当前未占用收款 {available:.2f} 元，未达到本次发货要求 {required_payment:.2f} 元；请登记收款或填写授权放行")
            cursor = conn.execute(
                """INSERT INTO fulfillment_shipments(door_unit_id, required_payment, paid_amount, authorized, authorization_reason, authorized_by, carrier, vehicle_no, contact, remark, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (door_id, required_payment, available, int(authorized), payload.authorization_reason, payload.authorized_by, payload.carrier, payload.vehicle_no, payload.contact, payload.remark, str(user.get("uid") or ""), now),
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
