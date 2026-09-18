"""Configurable process routes, workforce, assembly assignment, and monthly payroll."""

from __future__ import annotations

import json
import sqlite3
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from fulfillment_database import fulfillment_now, json_dumps
from fulfillment_routes import fulfillment_db
from operations_models import (
    AssemblyAssignmentInput,
    AttendanceInput,
    EmployeeInput,
    PayrollCalculateInput,
    PayrollEntryUpdate,
    PayrollStatusUpdate,
    RouteTemplateUpdate,
)


router = APIRouter(prefix="/api/operations", tags=["operations"])


def _fail(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (ValueError, sqlite3.IntegrityError)):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail=f"经营数据操作失败：{exc}")


def _route_payload(template: Dict) -> Dict:
    steps = fulfillment_db.fetch_all(
        "SELECT * FROM process_route_template_steps WHERE template_id=? ORDER BY sequence_no, id",
        (template["id"],),
    )
    for step in steps:
        step["predecessor_codes"] = json.loads(step.pop("predecessor_codes_json") or "[]")
        step["material_operations"] = json.loads(step.pop("material_operations_json") or "[]")
        step["inspection_required"] = bool(step["inspection_required"])
        step["is_active"] = bool(step["is_active"])
    return {**template, "is_default": bool(template["is_default"]), "is_active": bool(template["is_active"]), "steps": steps}


@router.get("/route-templates")
def list_route_templates(current_user: Dict = Depends(get_current_user)):
    templates = fulfillment_db.fetch_all("SELECT * FROM process_route_templates ORDER BY is_default DESC, id")
    return {"templates": [_route_payload(item) for item in templates]}


@router.put("/route-templates/{template_id}")
def update_route_template(template_id: int, req: RouteTemplateUpdate, current_user: Dict = Depends(get_current_user)):
    now = fulfillment_now()
    try:
        with fulfillment_db.transaction() as conn:
            template = conn.execute("SELECT * FROM process_route_templates WHERE id=?", (template_id,)).fetchone()
            if not template:
                raise LookupError("工艺路线模板不存在")
            if req.is_default:
                conn.execute("UPDATE process_route_templates SET is_default=0")
            conn.execute(
                """UPDATE process_route_templates SET name=?, target_group=?, version=version+1,
                       is_default=?, is_active=?, updated_at=? WHERE id=?""",
                (req.name, req.target_group, int(req.is_default), int(req.is_active), now, template_id),
            )
            conn.execute("DELETE FROM process_route_template_steps WHERE template_id=?", (template_id,))
            codes = {step.step_code for step in req.steps}
            for sequence, step in enumerate(req.steps, start=1):
                unknown = [code for code in step.predecessor_codes if code not in codes]
                if unknown:
                    raise ValueError(f"工序 {step.name} 的前序编码不存在：{'、'.join(unknown)}")
                conn.execute(
                    """INSERT INTO process_route_template_steps(
                           template_id, step_code, name, category, sequence_no,
                           predecessor_codes_json, material_operations_json,
                           inspection_required, standard_minutes, piece_rate,
                           default_role, work_center, weight, is_active
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        template_id, step.step_code, step.name, step.category,
                        step.sequence_no or sequence, json_dumps(step.predecessor_codes),
                        json_dumps(step.material_operations), int(step.inspection_required),
                        step.standard_minutes, step.piece_rate, step.default_role,
                        step.work_center, step.weight, int(step.is_active),
                    ),
                )
    except Exception as exc:
        raise _fail(exc) from exc
    template = fulfillment_db.fetch_one("SELECT * FROM process_route_templates WHERE id=?", (template_id,))
    return {"template": _route_payload(template or {}), "message": "工艺路线模板已更新；已发布门樘仍使用原快照"}


def _employee_payload(row: Dict) -> Dict:
    return {
        **row,
        "capabilities": json.loads(row.pop("capabilities_json", "[]") or "[]"),
        "is_active": bool(row["is_active"]),
    }


@router.get("/employees")
def list_employees(current_user: Dict = Depends(get_current_user)):
    rows = fulfillment_db.fetch_all("SELECT * FROM workforce_employees ORDER BY is_active DESC, employee_no")
    return {"employees": [_employee_payload(row) for row in rows]}


@router.get("/personnel-work")
def list_personnel_work(current_user: Dict = Depends(get_current_user)):
    employees = fulfillment_db.fetch_all(
        """SELECT id, employee_no, name, team, role_name
           FROM workforce_employees
           WHERE is_active=1
           ORDER BY CASE WHEN team='' THEN 1 ELSE 0 END, team, employee_no"""
    )
    works = fulfillment_db.fetch_all(
        """SELECT w.id AS work_package_id, w.employee_id, w.executor_uid,
                  w.name AS operation_name, w.status, w.sequence_no,
                  d.id AS door_unit_id, d.order_id, d.production_no
           FROM fulfillment_work_packages w
           JOIN fulfillment_door_units d ON d.id=w.door_unit_id
           WHERE w.status NOT IN ('已完成', '已取消')
             AND (w.employee_id IS NOT NULL OR w.executor_uid!='')
           ORDER BY CASE w.status
                      WHEN '进行中' THEN 1
                      WHEN '待质检' THEN 2
                      WHEN '已排单' THEN 3
                      WHEN '待排单' THEN 4
                      ELSE 5
                    END,
                    w.sequence_no, w.id"""
    )
    employee_by_no = {str(row["employee_no"]): int(row["id"]) for row in employees}
    current_by_employee: Dict[int, Dict] = {}
    for work in works:
        employee_id = work.get("employee_id") or employee_by_no.get(str(work.get("executor_uid") or ""))
        if not employee_id or int(employee_id) in current_by_employee:
            continue
        current_by_employee[int(employee_id)] = {
            "work_package_id": work["work_package_id"],
            "door_unit_id": work["door_unit_id"],
            "order_id": work["order_id"],
            "production_no": work["production_no"],
            "operation_name": work["operation_name"],
            "status": work["status"],
        }

    departments: Dict[str, list] = {}
    for employee in employees:
        department = str(employee.get("team") or "未分部门")
        current_work = current_by_employee.get(int(employee["id"]))
        departments.setdefault(department, []).append({
            "id": employee["id"],
            "employee_no": employee["employee_no"],
            "name": employee["name"],
            "role_name": employee.get("role_name") or "",
            "status": "工作中" if current_work else "空闲",
            "current_work": current_work,
        })
    return {"departments": [{"name": name, "employees": rows} for name, rows in departments.items()]}


@router.post("/employees")
def create_employee(req: EmployeeInput, current_user: Dict = Depends(get_current_user)):
    now = fulfillment_now()
    try:
        with fulfillment_db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO workforce_employees(
                       employee_no, name, team, role_name, capabilities_json, work_center,
                       wage_type, base_salary, hire_date, leave_date, is_active, remark,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (req.employee_no.strip(), req.name.strip(), req.team, req.role_name,
                 json_dumps(req.capabilities), req.work_center, req.wage_type, req.base_salary,
                 req.hire_date, req.leave_date, int(req.is_active), req.remark, now, now),
            )
            employee_id = int(cursor.lastrowid)
    except Exception as exc:
        raise _fail(exc) from exc
    row = fulfillment_db.fetch_one("SELECT * FROM workforce_employees WHERE id=?", (employee_id,)) or {}
    return {"employee": _employee_payload(row), "message": "员工档案已建立"}


@router.put("/employees/{employee_id}")
def update_employee(employee_id: int, req: EmployeeInput, current_user: Dict = Depends(get_current_user)):
    now = fulfillment_now()
    try:
        with fulfillment_db.transaction() as conn:
            if not conn.execute("SELECT id FROM workforce_employees WHERE id=?", (employee_id,)).fetchone():
                raise LookupError("员工档案不存在")
            conn.execute(
                """UPDATE workforce_employees SET employee_no=?, name=?, team=?, role_name=?,
                       capabilities_json=?, work_center=?, wage_type=?, base_salary=?, hire_date=?,
                       leave_date=?, is_active=?, remark=?, updated_at=? WHERE id=?""",
                (req.employee_no.strip(), req.name.strip(), req.team, req.role_name,
                 json_dumps(req.capabilities), req.work_center, req.wage_type, req.base_salary,
                 req.hire_date, req.leave_date, int(req.is_active), req.remark, now, employee_id),
            )
    except Exception as exc:
        raise _fail(exc) from exc
    row = fulfillment_db.fetch_one("SELECT * FROM workforce_employees WHERE id=?", (employee_id,)) or {}
    return {"employee": _employee_payload(row), "message": "员工档案已更新"}


@router.delete("/employees/{employee_id}")
def deactivate_employee(employee_id: int, current_user: Dict = Depends(get_current_user)):
    with fulfillment_db.transaction() as conn:
        cursor = conn.execute("UPDATE workforce_employees SET is_active=0, updated_at=? WHERE id=?", (fulfillment_now(), employee_id))
        if not cursor.rowcount:
            raise HTTPException(status_code=404, detail="员工档案不存在")
    return {"message": "员工已停用，历史生产和工资记录保留"}


@router.put("/door-units/{door_id}/assembly-assignment")
def save_assembly_assignment(door_id: int, req: AssemblyAssignmentInput, current_user: Dict = Depends(get_current_user)):
    now = fulfillment_now()
    try:
        with fulfillment_db.transaction() as conn:
            if not conn.execute("SELECT id FROM fulfillment_door_units WHERE id=?", (door_id,)).fetchone():
                raise LookupError("门樘生产单不存在")
            employee_ids = ([req.owner_id] if req.owner_id else []) + req.collaborator_ids
            if len(employee_ids) != len(set(employee_ids)):
                raise ValueError("拼装负责人和协作人员不能重复")
            if employee_ids:
                placeholders = ",".join("?" for _ in employee_ids)
                found = conn.execute(f"SELECT COUNT(*) AS total FROM workforce_employees WHERE id IN ({placeholders}) AND is_active=1", employee_ids).fetchone()
                if int(found["total"] or 0) != len(set(employee_ids)):
                    raise ValueError("拼装负责人或协作人员不存在、重复或已停用")
            conn.execute(
                """UPDATE fulfillment_door_units SET assembly_owner_id=?,
                       assembly_collaborator_ids_json=?, assembly_work_center=?,
                       assembly_planned_date=?, assembly_actual_date=?, assembly_note=?, updated_at=?
                   WHERE id=?""",
                (req.owner_id, json_dumps(req.collaborator_ids), req.work_center,
                 req.planned_date, req.actual_date, req.note, now, door_id),
            )
            owner = conn.execute("SELECT employee_no FROM workforce_employees WHERE id=?", (req.owner_id,)).fetchone() if req.owner_id else None
            if owner:
                conn.execute(
                    """UPDATE fulfillment_work_packages SET employee_id=?, executor_uid=?, work_center=?, updated_at=?
                       WHERE door_unit_id=? AND operation_code='ASSEMBLY'""",
                    (req.owner_id, owner["employee_no"], req.work_center, now, door_id),
                )
            fulfillment_db.add_event(
                conn, order_id=None, door_unit_id=door_id, entity_type="assembly_assignment",
                entity_id=req.owner_id, action="更新拼装分配", detail=req.note or "拼装负责人已更新",
                user=current_user,
            )
    except Exception as exc:
        raise _fail(exc) from exc
    return {"door_unit": fulfillment_db.get_door_unit(door_id), "message": "拼装分配已保存"}


@router.get("/attendance")
def list_attendance(month: str = "", current_user: Dict = Depends(get_current_user)):
    where = "WHERE a.work_date LIKE ?" if month else ""
    rows = fulfillment_db.fetch_all(
        f"""SELECT a.*, e.employee_no, e.name FROM workforce_attendance a
            JOIN workforce_employees e ON e.id=a.employee_id {where}
            ORDER BY a.work_date DESC, e.employee_no""",
        (f"{month}%",) if month else (),
    )
    return {"attendance": rows}


@router.post("/attendance")
def save_attendance(req: AttendanceInput, current_user: Dict = Depends(get_current_user)):
    now = fulfillment_now()
    try:
        with fulfillment_db.transaction() as conn:
            conn.execute(
                """INSERT INTO workforce_attendance(employee_id, work_date, regular_hours,
                       overtime_hours, leave_hours, remark, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(employee_id, work_date) DO UPDATE SET
                       regular_hours=excluded.regular_hours, overtime_hours=excluded.overtime_hours,
                       leave_hours=excluded.leave_hours, remark=excluded.remark, updated_at=excluded.updated_at""",
                (req.employee_id, req.work_date, req.regular_hours, req.overtime_hours,
                 req.leave_hours, req.remark, now, now),
            )
    except Exception as exc:
        raise _fail(exc) from exc
    return {"message": "考勤记录已保存"}


def _payroll_payload(period_id: int) -> Dict:
    period = fulfillment_db.fetch_one("SELECT * FROM payroll_periods WHERE id=?", (period_id,))
    if not period:
        raise LookupError("工资期间不存在")
    entries = fulfillment_db.fetch_all(
        """SELECT p.*, e.employee_no, e.name, e.team, e.wage_type
           FROM payroll_entries p JOIN workforce_employees e ON e.id=p.employee_id
           WHERE p.period_id=? ORDER BY e.employee_no""",
        (period_id,),
    )
    return {**period, "entries": entries}


@router.get("/payroll")
def list_payroll(current_user: Dict = Depends(get_current_user)):
    return {"periods": fulfillment_db.fetch_all("SELECT * FROM payroll_periods ORDER BY month DESC")}


@router.get("/payroll/{period_id}")
def get_payroll(period_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        return {"period": _payroll_payload(period_id)}
    except Exception as exc:
        raise _fail(exc) from exc


@router.post("/payroll/calculate")
def calculate_payroll(req: PayrollCalculateInput, current_user: Dict = Depends(get_current_user)):
    now = fulfillment_now()
    try:
        with fulfillment_db.transaction() as conn:
            period = conn.execute("SELECT * FROM payroll_periods WHERE month=?", (req.month,)).fetchone()
            if period and period["status"] == "已锁定":
                raise RuntimeError("该工资期间已锁定，不能重新计算")
            if not period:
                cursor = conn.execute(
                    "INSERT INTO payroll_periods(month, status, created_by, created_at, updated_at) VALUES (?, '草稿', ?, ?, ?)",
                    (req.month, str(current_user.get("uid") or ""), now, now),
                )
                period_id = int(cursor.lastrowid)
            else:
                period_id = int(period["id"])
            employees = conn.execute("SELECT * FROM workforce_employees WHERE is_active=1 OR leave_date LIKE ?", (f"{req.month}%",)).fetchall()
            for employee in employees:
                piecework = conn.execute(
                    """SELECT COALESCE(SUM(d.amount), 0) AS total FROM fulfillment_payroll_drafts d
                       JOIN fulfillment_work_packages w ON w.id=d.work_package_id
                       WHERE d.employee_uid=? AND w.completed_at LIKE ? AND d.status!='已冲销'""",
                    (employee["employee_no"], f"{req.month}%"),
                ).fetchone()["total"]
                current = conn.execute("SELECT * FROM payroll_entries WHERE period_id=? AND employee_id=?", (period_id, employee["id"])).fetchone()
                values = {key: float(current[key] or 0) if current else 0 for key in ("overtime_amount", "allowance", "bonus", "deduction", "social_insurance", "tax", "other_withholding")}
                base_salary = float(employee["base_salary"] or 0)
                payable = base_salary + float(piecework or 0) + values["overtime_amount"] + values["allowance"] + values["bonus"] - values["deduction"] - values["social_insurance"] - values["tax"] - values["other_withholding"]
                conn.execute(
                    """INSERT INTO payroll_entries(period_id, employee_id, base_salary, piecework_amount,
                           overtime_amount, allowance, bonus, deduction, social_insurance, tax,
                           other_withholding, payable_amount, remark, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(period_id, employee_id) DO UPDATE SET base_salary=excluded.base_salary,
                           piecework_amount=excluded.piecework_amount, payable_amount=excluded.payable_amount,
                           updated_at=excluded.updated_at""",
                    (period_id, employee["id"], base_salary, float(piecework or 0),
                     values["overtime_amount"], values["allowance"], values["bonus"], values["deduction"],
                     values["social_insurance"], values["tax"], values["other_withholding"], payable,
                     str(current["remark"] if current else ""), now),
                )
            conn.execute("UPDATE payroll_periods SET updated_at=? WHERE id=?", (now, period_id))
    except Exception as exc:
        raise _fail(exc) from exc
    return {"period": _payroll_payload(period_id), "message": "月度工资已计算"}


@router.put("/payroll/entries/{entry_id}")
def update_payroll_entry(entry_id: int, req: PayrollEntryUpdate, current_user: Dict = Depends(get_current_user)):
    now = fulfillment_now()
    try:
        with fulfillment_db.transaction() as conn:
            row = conn.execute("SELECT p.*, period.status AS period_status FROM payroll_entries p JOIN payroll_periods period ON period.id=p.period_id WHERE p.id=?", (entry_id,)).fetchone()
            if not row:
                raise LookupError("工资明细不存在")
            if row["period_status"] == "已锁定":
                raise RuntimeError("工资期间已锁定，不能修改")
            payable = float(row["base_salary"] or 0) + float(row["piecework_amount"] or 0) + req.overtime_amount + req.allowance + req.bonus - req.deduction - req.social_insurance - req.tax - req.other_withholding
            conn.execute(
                """UPDATE payroll_entries SET overtime_amount=?, allowance=?, bonus=?, deduction=?,
                       social_insurance=?, tax=?, other_withholding=?, payable_amount=?, remark=?, updated_at=?
                   WHERE id=?""",
                (req.overtime_amount, req.allowance, req.bonus, req.deduction,
                 req.social_insurance, req.tax, req.other_withholding, payable, req.remark, now, entry_id),
            )
            period_id = int(row["period_id"])
    except Exception as exc:
        raise _fail(exc) from exc
    return {"period": _payroll_payload(period_id), "message": "工资调整已保存"}


@router.put("/payroll/{period_id}/status")
def update_payroll_status(period_id: int, req: PayrollStatusUpdate, current_user: Dict = Depends(get_current_user)):
    transitions = {"草稿": {"待审核"}, "待审核": {"草稿", "已审批"}, "已审批": {"已锁定"}, "已锁定": {"草稿"}}
    now = fulfillment_now()
    try:
        with fulfillment_db.transaction() as conn:
            row = conn.execute("SELECT * FROM payroll_periods WHERE id=?", (period_id,)).fetchone()
            if not row:
                raise LookupError("工资期间不存在")
            if req.status not in transitions.get(str(row["status"]), set()):
                raise RuntimeError(f"工资期间不能从“{row['status']}”直接变为“{req.status}”")
            conn.execute(
                """UPDATE payroll_periods SET status=?, approved_by=CASE WHEN ?='已审批' THEN ? ELSE approved_by END,
                       approved_at=CASE WHEN ?='已审批' THEN ? ELSE approved_at END, updated_at=? WHERE id=?""",
                (req.status, req.status, str(current_user.get("uid") or ""), req.status, now, now, period_id),
            )
    except Exception as exc:
        raise _fail(exc) from exc
    return {"period": _payroll_payload(period_id), "message": f"工资期间已更新为{req.status}"}
