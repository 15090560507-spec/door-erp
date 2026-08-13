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
