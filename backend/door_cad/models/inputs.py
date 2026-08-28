"""Typed production inputs for the new-process door-frame calculator."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrameInput(BaseModel):
    """All dimensions are millimetres unless the field name says otherwise."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doorWidth: float = Field(default=1800.0, gt=0)
    doorHeight: float = Field(default=2700.0, gt=0)

    linkedSideSizes: bool = True
    outerSideShort: float = Field(default=55.0, gt=0)
    outerSideLong: float = Field(default=62.0, gt=0)
    skeletonSideShort: float = Field(default=52.0, gt=0)
    skeletonSideLong: float = Field(default=59.0, gt=0)

    skeletonThickness: float = Field(default=2.0, gt=0)
    skeletonGrooveDepth: float = Field(default=1.0, gt=0)
    skeletonGrooveWidth: float = Field(default=2.0, gt=0)
    skinThickness: float = Field(default=0.8, gt=0)
    skinGrooveDepth: float = Field(default=0.3, gt=0)
    skinGrooveWidth: float = Field(default=0.6, gt=0)

    hingeStyle: str = "可拆卸合页"
    hingeCount: Literal[3, 4] = 3
    hingeMode: Literal["auto", "custom"] = "auto"
    hingeCenterSkeleton: float = Field(default=97.0, gt=0)
    hingeCenterSkin: float = Field(default=98.5, gt=0)
    hingePositions: list[float] = Field(default_factory=list)

    includeLeft: bool = True
    includeRight: bool = True
    includeTop: bool = True
    includeBottom: bool = True

    sameTopBottom: bool = True
    topShort: float = Field(default=55.0, gt=0)
    topLong: float = Field(default=75.0, gt=0)
    bottomShort: float = Field(default=55.0, gt=0)
    bottomLong: float = Field(default=75.0, gt=0)
    topPin: bool = True
    bottomPin: bool = True

    @model_validator(mode="after")
    def validate_production_relationships(self) -> "FrameInput":
        if self.outerSideLong <= self.outerSideShort:
            raise ValueError("左右框外皮大边必须大于小边")
        if not self.linkedSideSizes and self.skeletonSideLong <= self.skeletonSideShort:
            raise ValueError("左右框骨架大边必须大于小边")
        if self.topLong <= self.topShort:
            raise ValueError("上框大边必须大于小边")
        if self.bottomLong <= self.bottomShort:
            raise ValueError("下框大边必须大于小边")
        if self.skeletonGrooveDepth >= self.skeletonThickness:
            raise ValueError("骨架压槽深度必须小于材料厚度")
        if self.skinGrooveDepth >= self.skinThickness:
            raise ValueError("外皮压槽深度必须小于材料厚度")
        if self.hingeMode == "custom":
            if len(self.hingePositions) != self.hingeCount:
                raise ValueError("自定义合页位置数量必须与合页数量一致")
            if any(position <= 0 or position >= self.doorHeight for position in self.hingePositions):
                raise ValueError("合页位置必须在门高范围内")
        return self

    def resolved_skeleton_sizes(self) -> tuple[float, float]:
        if self.linkedSideSizes:
            return self.outerSideShort - 3.0, self.outerSideLong - 3.0
        return self.skeletonSideShort, self.skeletonSideLong

    def resolved_skin_sizes(self) -> tuple[float, float]:
        return self.outerSideShort, self.outerSideLong

    def resolved_bottom_sizes(self) -> tuple[float, float]:
        if self.sameTopBottom:
            return self.topShort, self.topLong
        return self.bottomShort, self.bottomLong
