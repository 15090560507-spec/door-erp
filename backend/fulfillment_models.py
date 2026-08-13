"""Request models for the door-unit fulfillment center."""

from typing import List, Optional

from pydantic import BaseModel, Field


class FulfillmentReleaseRequest(BaseModel):
    due_date: str = ""
    sales_note: str = ""
    door_count: int = Field(default=1, ge=1, le=50)
    owner_uid: str = ""


class ComponentInput(BaseModel):
    id: Optional[int] = None
    parent_id: Optional[int] = None
    material_id: Optional[int] = None
    name: str
    category: str = "其他"
    specification: str = ""
    quantity: float = Field(default=1, gt=0)
    unit: str = "件"
    acquisition_method: str = "待确定"
    remark: str = ""


class WorkPackageInput(BaseModel):
    id: Optional[int] = None
    component_id: Optional[int] = None
    name: str
    category: str = "生产"
    route: str = ""
    acquisition_method: str = "内部加工"
    executor_uid: str = ""
    planned_start: str = ""
    planned_end: str = ""
    opening_condition: str = "技术包确认"
    blocking_node: str = ""
    quantity: float = Field(default=1, gt=0)
    unit: str = "项"
    piece_rate: float = Field(default=0, ge=0)
    inspection_required: bool = False
    remark: str = ""


class TechnicalPackageUpdate(BaseModel):
    product_summary: str = ""
    special_requirements: str = ""
    components: List[ComponentInput] = Field(default_factory=list)
    work_packages: List[WorkPackageInput] = Field(default_factory=list)


class WorkPackageAction(BaseModel):
    status: str
    executor_uid: str = ""
    actual_quantity: Optional[float] = Field(default=None, ge=0)
    remark: str = ""


class WorkPackageBatchAction(BaseModel):
    work_ids: List[int] = Field(min_length=1)
    action: str
    executor_uid: str = ""
    remark: str = ""


class ExceptionCreate(BaseModel):
    category: str
    title: str
    detail: str = ""
    severity: str = "一般"
    owner_uid: str = ""


class ExceptionResolve(BaseModel):
    resolution: str


class ChangeCreate(BaseModel):
    reason: str
    impact_note: str = ""


class SupplyAction(BaseModel):
    status: str
    handler_uid: str = ""
    supplier: str = ""
    actual_quantity: Optional[float] = Field(default=None, ge=0)
    unit_cost: Optional[float] = Field(default=None, ge=0)
    remark: str = ""


class InspectionCreate(BaseModel):
    inspection_type: str
    result: str
    target_name: str = ""
    quantity: float = Field(default=1, ge=0)
    defect_detail: str = ""
    remark: str = ""


class FinishedInboundCreate(BaseModel):
    warehouse: str = "成品仓"
    location: str = ""
    quantity: float = Field(default=1, gt=0)
    remark: str = ""


class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    payment_date: str = ""
    reference: str = ""
    remark: str = ""


class ShipmentCreate(BaseModel):
    required_payment: float = Field(default=0, ge=0)
    carrier: str = ""
    vehicle_no: str = ""
    contact: str = ""
    authorization_reason: str = ""
    authorized_by: str = ""
    remark: str = ""


class ShipmentSign(BaseModel):
    signed_by: str = ""
    signed_at: str = ""
    remark: str = ""
