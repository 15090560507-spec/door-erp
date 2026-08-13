"""Pydantic contracts for shared inventory APIs."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class MaterialCreate(BaseModel):
    code: str
    name: str
    category: str = ""
    specification: str = ""
    unit: str
    material_type: str
    default_warehouse_id: Optional[int] = None
    default_location_id: Optional[int] = None
    default_supplier: str = ""
    minimum_stock: float = Field(default=0, ge=0)
    remark: str = ""


class MaterialUpdate(MaterialCreate):
    is_active: bool = True


class WarehouseCreate(BaseModel):
    code: str
    name: str
    warehouse_type: str = ""
    remark: str = ""


class LocationCreate(BaseModel):
    code: str
    name: str
    remark: str = ""


class AdjustmentItem(BaseModel):
    material_id: int
    warehouse_id: int
    location_id: int
    quantity: float
    unit: str
    remark: str = ""


class AdjustmentCreate(BaseModel):
    remark: str = ""
    items: List[AdjustmentItem]


class InventoryTransactionCreate(BaseModel):
    material_id: int
    warehouse_id: int
    location_id: int
    transaction_type: str
    quantity: float
    unit: str
    source_type: str
    source_id: str
    source_line: str = ""
    order_id: Optional[int] = None
    door_unit_id: Optional[int] = None
    production_no: str = ""
    remark: str = ""


class RequirementSupplement(BaseModel):
    material_id: int
    quantity: float = Field(gt=0)
    remark: str = ""


class PurchaseAllocationInput(BaseModel):
    requirement_item_id: int
    quantity: float = Field(gt=0)


class PurchaseOrderItemInput(BaseModel):
    material_id: int
    quantity: float = Field(gt=0)
    unit: str
    unit_price: float = Field(default=0, ge=0)
    remark: str = ""
    allocations: List[PurchaseAllocationInput]


class PurchaseOrderCreate(BaseModel):
    supplier: str
    expected_date: str = ""
    remark: str = ""
    items: List[PurchaseOrderItemInput]


class PurchaseReceiptItemInput(BaseModel):
    purchase_order_item_id: int
    quantity: float = Field(gt=0)


class PurchaseReceiptCreate(BaseModel):
    arrival_date: str = ""
    remark: str = ""
    items: List[PurchaseReceiptItemInput]


class IncomingInspectionCreate(BaseModel):
    qualified_quantity: float = Field(default=0, ge=0)
    concession_quantity: float = Field(default=0, ge=0)
    rejected_quantity: float = Field(default=0, ge=0)
    warehouse_id: int
    location_id: int
    remark: str = ""


class MaterialIssueItemInput(BaseModel):
    requirement_item_id: int
    reservation_id: int
    quantity: float = Field(gt=0)
    remark: str = ""


class MaterialIssueCreate(BaseModel):
    requirement_id: int
    remark: str = ""
    items: List[MaterialIssueItemInput]


class MaterialReturnItemInput(BaseModel):
    requirement_item_id: int
    material_id: int
    warehouse_id: int
    location_id: int
    quantity: float = Field(gt=0)
    unit: str
    remark: str = ""


class MaterialReturnCreate(BaseModel):
    requirement_id: int
    remark: str = ""
    items: List[MaterialReturnItemInput]


class StockTransferItemInput(BaseModel):
    material_id: int
    source_warehouse_id: int
    source_location_id: int
    target_warehouse_id: int
    target_location_id: int
    quantity: float = Field(gt=0)
    unit: str
    remark: str = ""


class StockTransferCreate(BaseModel):
    remark: str = ""
    items: List[StockTransferItemInput]


class StockScrapItemInput(BaseModel):
    material_id: int
    warehouse_id: int
    location_id: int
    quantity: float = Field(gt=0)
    unit: str
    remark: str = ""


class StockScrapCreate(BaseModel):
    production_no: str = ""
    remark: str = ""
    items: List[StockScrapItemInput]


class SubcontractSendItemInput(BaseModel):
    material_id: int
    source_warehouse_id: int
    source_location_id: int
    quantity: float = Field(gt=0)
    unit: str
    production_no: str = ""
    remark: str = ""


class SubcontractSendCreate(BaseModel):
    supplier: str
    work_package: str = ""
    expected_return_date: str = ""
    remark: str = ""
    items: List[SubcontractSendItemInput]


class SubcontractReceiptItemInput(BaseModel):
    subcontract_item_id: int
    quantity: float = Field(gt=0)


class SubcontractReceiptCreate(BaseModel):
    return_date: str = ""
    remark: str = ""
    items: List[SubcontractReceiptItemInput]


class SubcontractInspectionCreate(BaseModel):
    accepted_quantity: float = Field(default=0, ge=0)
    rejected_quantity: float = Field(default=0, ge=0)
    warehouse_id: int
    location_id: int
    remark: str = ""
