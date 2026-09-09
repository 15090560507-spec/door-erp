"""Request contracts for the whole-order BOM workbench."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BomDraftItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Optional[int] = None
    material_id: Optional[int] = None
    name: Optional[str] = None
    category: Optional[str] = None
    specification: Optional[str] = None
    theoretical_quantity: Optional[float] = Field(default=None, ge=0)
    waste_rate: Optional[float] = Field(default=None, ge=0, le=100)
    planned_quantity: Optional[float] = Field(default=None, ge=0)
    quantity: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = None
    acquisition_method: Optional[str] = None
    group_code: Optional[str] = None
    operation_code: Optional[str] = None
    supplier_id: Optional[int] = None
    required_date: Optional[str] = None
    remark: Optional[str] = None

    @model_validator(mode="after")
    def validate_new_item(self):
        if self.id is None and not str(self.name or "").strip():
            raise ValueError("新增BOM行必须填写名称")
        return self


class BomDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[BomDraftItem] = Field(default_factory=list)
    delete_item_ids: list[int] = Field(default_factory=list)
    product_summary: Optional[str] = None
    special_requirements: Optional[str] = None


class BomVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_ids: list[int] = Field(min_length=1)


class BomPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remark: str = ""


class BomNewVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)
    impact_note: str = ""
