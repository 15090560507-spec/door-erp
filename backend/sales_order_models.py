"""Pydantic contracts for sales-order confirmation."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SalesOrderLineInput(BaseModel):
    source_type: Literal["drawing", "manual"] = "drawing"
    task_id: str = ""
    quote_id: Optional[int] = None
    quote_group_index: Optional[int] = None
    product_name: str = ""
    door_type: str = ""
    width: Optional[float] = None
    height: Optional[float] = None
    opening_direction: str = ""
    color: str = ""
    quantity: int = Field(default=1, ge=1, le=999)
    unit: str = "樘"
    unit_price: Optional[float] = Field(default=None, ge=0)
    remark: str = ""


class SalesOrderChargeLineInput(BaseModel):
    door_line_no: Optional[int] = Field(default=None, ge=1, le=100)
    source_type: Literal["quote", "manual"] = "manual"
    quote_item_index: Optional[int] = Field(default=None, ge=0)
    item_type: str = "其他"
    product_name: str
    specification: str = ""
    quantity: float = Field(default=1, gt=0)
    unit: str = "项"
    unit_price: float = Field(default=0, ge=0)
    pricing_mode: str = ""
    remark: str = ""


class SalesOrderPaymentNodeInput(BaseModel):
    name: str
    # Kept for backward-compatible imports. New forms only submit due_amount.
    due_percent: float = Field(default=0, ge=0, le=100)
    due_amount: float = Field(default=0, ge=0)
    planned_date: str = ""
    remark: str = ""


class SalesOrderCreate(BaseModel):
    order_date: str
    customer_name: str = ""
    project_name: str = ""
    delivery_address: str = ""
    salesperson: str = ""
    delivery_date: str = ""
    payment_template: str = ""
    remark: str = ""
    discount_amount: float = Field(default=0, ge=0)
    lines: List[SalesOrderLineInput] = Field(min_length=1, max_length=100)
    charge_lines: List[SalesOrderChargeLineInput] = Field(default_factory=list, max_length=500)
    payment_nodes: List[SalesOrderPaymentNodeInput] = Field(default_factory=list, max_length=20)


class SalesOrderUpdate(SalesOrderCreate):
    pass


class SalesOrderCancel(BaseModel):
    reason: str = ""


class SalesOrderReceiptAllocationInput(BaseModel):
    order_id: int = Field(gt=0)
    amount: float = Field(gt=0)


class SalesOrderReceiptCreate(BaseModel):
    receipt_date: str = ""
    amount: float = Field(gt=0)
    payment_method: str = ""
    reference: str = ""
    remark: str = ""
    allocations: List[SalesOrderReceiptAllocationInput] = Field(min_length=1, max_length=100)


class SalesOrderReceiptReverse(BaseModel):
    reason: str
