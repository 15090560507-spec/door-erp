"""Bounded declarative line graphs, never model-generated executable CAD code."""
from typing import Annotated, Dict, List, Literal, Tuple
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Normalized = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, le=10000, allow_inf_nan=False)]
PatternSlot = Literal["panel_b2", "back_panel_b2", "child_panel_b2", "child_back_panel_b2", "transom"]
REFERENCE_STYLE = "参考图线稿"


class PatternPath(BaseModel):
    model_config = ConfigDict(extra="forbid")
    points: List[Tuple[Normalized, Normalized]] = Field(min_length=2, max_length=64)
    closed: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_closed_endpoint(cls, value):
        if isinstance(value, dict) and value.get("closed") is True:
            points = value.get("points")
            if isinstance(points, list) and len(points) > 2 and points[0] == points[-1]:
                return {**value, "points": points[:-1]}
        return value

    @model_validator(mode="after")
    def orthogonal_only(self):
        if self.closed and len(self.points) < 4:
            raise ValueError("闭合回路至少需要四个顶点")
        pairs = list(zip(self.points, self.points[1:]))
        if self.closed:
            pairs.append((self.points[-1], self.points[0]))
        for first, second in pairs:
            dx, dy = abs(first[0] - second[0]), abs(first[1] - second[1])
            if dx < 1e-7 and dy < 1e-7:
                raise ValueError("线稿包含重复端点")
            if dx > 1e-7 and dy > 1e-7:
                raise ValueError("第一版仅支持水平及竖直线，斜线或曲线需另行处理")
        return self


class PatternDefinition(BaseModel):
    model_config = ConfigDict(extra="ignore")
    version: Literal[1] = 1
    name: str = Field(default="参考图案", max_length=80)
    paths: List[PatternPath] = Field(min_length=1, max_length=128)
    stretch_x: Tuple[Normalized, Normalized] = (0.3, 0.7)
    stretch_y: Tuple[Normalized, Normalized] = (0.3, 0.7)
    warnings: List[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=12)

    @field_validator("stretch_x", "stretch_y")
    @classmethod
    def valid_stretch(cls, value):
        if not 0 < value[0] < value[1] < 1:
            raise ValueError("伸缩区域必须在0与1之间且起点小于终点")
        return value

    @model_validator(mode="after")
    def bounded_total(self):
        if sum(len(path.points) for path in self.paths) > 1024:
            raise ValueError("图案过于复杂，请拆分或简化后重试")
        return self


class PatternPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: PatternDefinition
    band_width: Positive = 20
    inset: Annotated[float, Field(ge=0, le=1000, allow_inf_nan=False)] = 20
    detail_x: Positive = 80
    detail_y: Positive = 80
    mirror: bool = False
    source_job_id: str = Field(default="", pattern=r"^([a-f0-9]{32})?$", max_length=32)


class AppliedPattern(PatternPlacement):
    reviewed: Literal[True]


class PatternPreviewRequest(BaseModel):
    placement: PatternPlacement
    width: Positive = 500
    height: Positive = 1400


class PatternTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    snapshot: AppliedPattern


class ReferencePatternOptions(BaseModel):
    reference_patterns: Dict[PatternSlot, AppliedPattern] = Field(default_factory=dict, max_length=5)
    reference_pattern_jobs: Dict[PatternSlot, Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]] = Field(default_factory=dict, max_length=5)
