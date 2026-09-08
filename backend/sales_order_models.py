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


class SalesOrderPaymentNodeInput(BaseModel):
    name: str
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
    payment_nodes: List[SalesOrderPaymentNodeInput] = Field(default_factory=list, max_length=20)


class SalesOrderUpdate(SalesOrderCreate):
    pass


class SalesOrderCancel(BaseModel):
    reason: str = ""
