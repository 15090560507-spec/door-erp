"""Request models for the production-fulfillment API."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ProductionReleaseRequest(BaseModel):
    due_date: str = ""
    sales_note: str = ""
    include_quote: bool = False
    quote_id: Optional[int] = None


class ProductionOrderActionRequest(BaseModel):
    reason: str = ""


class MaterialRequest(BaseModel):
    code: str
    name: str
    category: str = "其他"
    material: str = ""
    specification: str = ""
    thickness: str = ""
    unit: str = ""
    supplier: str = ""
    warehouse_location: str = ""
    remark: str = ""
    active: bool = True


class BomItemRequest(BaseModel):
    id: Optional[int] = None
    material_id: Optional[int] = None
    category: str = "其他"
    name: str
    specification: str = ""
    material: str = ""
    thickness: str = ""
    quantity: float = Field(default=0, ge=0)
    unit: str = ""
    supply_type: str = "自制"
    remark: str = ""


class BomReplaceRequest(BaseModel):
    items: List[BomItemRequest] = Field(default_factory=list)


class PurchaseItemRequest(BaseModel):
    order_id: Optional[int] = None
    material_id: Optional[int] = None
    name: str
    specification: str = ""
    quantity: float = Field(default=0, ge=0)
    unit: str = ""
    unit_price: float = Field(default=0, ge=0)
    remark: str = ""
    requirement_item_id: Optional[int] = None


class PurchaseRequest(BaseModel):
    supplier: str = ""
    expected_date: str = ""
    remark: str = ""
    items: List[PurchaseItemRequest] = Field(default_factory=list)


class PurchaseStatusRequest(BaseModel):
    status: str


class PurchaseReceiveItem(BaseModel):
    item_id: int
    quantity: float = Field(gt=0)
    warehouse_location: str = ""


class PurchaseReceiveRequest(BaseModel):
    items: List[PurchaseReceiveItem]
    remark: str = ""


class InventoryTransactionRequest(BaseModel):
    material_id: Optional[int] = None
    order_id: Optional[int] = None
    transaction_type: str
    quantity: float
    unit: str = ""
    warehouse_location: str = ""
    remark: str = ""


class RequirementPurchaseItem(BaseModel):
    requirement_item_id: int
    quantity: Optional[float] = Field(default=None, gt=0)


class RequirementPurchaseRequest(BaseModel):
    supplier: str = ""
    expected_date: str = ""
    remark: str = ""
    items: List[RequirementPurchaseItem]


class MaterialMovementItem(BaseModel):
    requirement_item_id: int
    quantity: float = Field(gt=0)
    warehouse_location: str = ""


class MaterialMovementRequest(BaseModel):
    items: List[MaterialMovementItem]
    remark: str = ""


class CuttingItemUpdate(BaseModel):
    id: int
    actual_quantity: float = Field(default=0, ge=0)
    cutter: str = ""
    completed: bool = False
    remark: str = ""


class CuttingSheetUpdate(BaseModel):
    status: Optional[str] = None
    items: List[CuttingItemUpdate] = Field(default_factory=list)


class ScheduleRequest(BaseModel):
    planned_start: str = ""
    planned_end: str = ""
    producer: str = ""
    shortage_status: str = "未知"
    owner: str = ""
    allow_shortage: bool = False


class OperationUpdateRequest(BaseModel):
    status: str
    operator_name: str = ""
    remark: str = ""


class QualityRequest(BaseModel):
    result: str
    inspector: str
    return_operation: str = ""
    photos: List[str] = Field(default_factory=list)
    remark: str = ""


class FinishedGoodInboundRequest(BaseModel):
    warehouse_location: str = ""


class ShipmentRequest(BaseModel):
    order_ids: List[int]
    customer: str
    project: str = ""
    address: str = ""
    contact: str = ""
    phone: str = ""
    logistics: str = ""
    tracking_no: str = ""
    photos: List[str] = Field(default_factory=list)
    remark: str = ""


class ShipmentStatusRequest(BaseModel):
    status: str
    tracking_no: str = ""
    remark: str = ""
