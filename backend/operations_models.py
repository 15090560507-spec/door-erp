"""Contracts for route configuration, workforce, assembly, attendance, and payroll."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RouteStepInput(BaseModel):
    id: Optional[int] = None
    step_code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str = "生产"
    sequence_no: int = Field(default=0, ge=0)
    predecessor_codes: list[str] = Field(default_factory=list)
    material_operations: list[str] = Field(default_factory=list)
    inspection_required: bool = False
    standard_minutes: float = Field(default=0, ge=0)
    piece_rate: float = Field(default=0, ge=0)
    default_role: str = ""
    work_center: str = ""
    weight: float = Field(default=1, ge=0)
    is_active: bool = True


class RouteTemplateUpdate(BaseModel):
    name: str = Field(min_length=1)
    target_group: str = "door"
    is_default: bool = True
    is_active: bool = True
    steps: list[RouteStepInput] = Field(default_factory=list)


class EmployeeInput(BaseModel):
    employee_no: str = Field(min_length=1)
    name: str = Field(min_length=1)
    team: str = ""
    role_name: str = ""
    capabilities: list[str] = Field(default_factory=list)
    work_center: str = ""
    wage_type: str = "计件"
    base_salary: float = Field(default=0, ge=0)
    hire_date: str = ""
    leave_date: str = ""
    is_active: bool = True
    remark: str = ""


class AssemblyAssignmentInput(BaseModel):
    owner_id: Optional[int] = None
    collaborator_ids: list[int] = Field(default_factory=list)
    work_center: str = ""
    planned_date: str = ""
    actual_date: str = ""
    note: str = ""


class AttendanceInput(BaseModel):
    employee_id: int
    work_date: str = Field(min_length=1)
    regular_hours: float = Field(default=0, ge=0)
    overtime_hours: float = Field(default=0, ge=0)
    leave_hours: float = Field(default=0, ge=0)
    remark: str = ""


class PayrollCalculateInput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")


class PayrollEntryUpdate(BaseModel):
    overtime_amount: float = 0
    allowance: float = 0
    bonus: float = 0
    deduction: float = 0
    social_insurance: float = 0
    tax: float = 0
    other_withholding: float = 0
    remark: str = ""


class PayrollStatusUpdate(BaseModel):
    status: str
