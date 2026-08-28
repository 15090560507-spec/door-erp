"""Single JSON geometry contract consumed by every door-frame output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer

from .inputs import FrameInput


class GeometryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_serializer(mode="wrap")
    def serialize_geometry(self, handler: SerializerFunctionWrapHandler):
        return _round_geometry_numbers(handler(self))


def _round_geometry_numbers(value):
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, list):
        return [_round_geometry_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: _round_geometry_numbers(item) for key, item in value.items()}
    return value


class Point2D(GeometryModel):
    x: float
    y: float


class Segment(GeometryModel):
    start: Point2D
    end: Point2D


class Polyline(GeometryModel):
    points: list[Point2D]
    closed: bool = False


class ClosedPolyline(GeometryModel):
    points: list[Point2D] = Field(min_length=3)
    closed: Literal[True] = True


class Shape(GeometryModel):
    shapeId: str
    kind: Literal["circle", "rectangle", "obround", "polyline"]
    center: Point2D | None = None
    width: float | None = None
    height: float | None = None
    diameter: float | None = None
    points: list[Point2D] = Field(default_factory=list)
    layer: str = "INNER_CUT"


class Groove(GeometryModel):
    grooveId: str
    face: Literal["inner", "outer"]
    segments: list[Segment]
    depth: float
    width: float
    layer: str = "GROOVE"


class GeometryDimension(GeometryModel):
    dimensionId: str
    label: str
    start: Point2D
    end: Point2D
    offset: float = 0.0
    orientation: Literal["horizontal", "vertical", "aligned"] = "aligned"
    value: float | None = None


class FoldNode(GeometryModel):
    x: float
    angle: float
    direction: Literal["up", "down", "none"] = "none"


class PartProcessMeta(GeometryModel):
    sourceRule: str = "frame-new-v1.4.3"
    sourceTemplate: str | None = None
    mirrored: bool = False
    grooveFaces: list[Literal["inner", "outer"]] = Field(default_factory=list)
    foldNodes: list[FoldNode] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PartGeometry(GeometryModel):
    partId: str
    name: str
    position: Literal["left", "right", "top", "bottom"]
    materialType: Literal["skeleton", "skin"]
    length: float = Field(gt=0)
    thickness: float = Field(gt=0)
    flatWidth: float = Field(gt=0)
    cutOuter: ClosedPolyline
    holes: list[Shape] = Field(default_factory=list)
    grooves: list[Groove] = Field(default_factory=list)
    foldSection: Polyline
    flatSection: Polyline
    dimensions: list[GeometryDimension] = Field(default_factory=list)
    process: PartProcessMeta


class PartPlacement(GeometryModel):
    partId: str
    x: float
    y: float
    width: float
    height: float


class AssemblyGeometry(GeometryModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    placements: list[PartPlacement] = Field(default_factory=list)


class ValidationIssue(GeometryModel):
    code: str
    message: str
    field: str | None = None
    severity: Literal["error", "warning"]


class ValidationReport(GeometryModel):
    status: Literal["PASSED", "WARNING", "ERROR"] = "PASSED"
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)


class ProjectMeta(GeometryModel):
    orderNo: str = ""
    projectName: str = ""
    taskId: str | None = None


class ProjectGeometry(GeometryModel):
    schemaVersion: Literal["1.0"] = "1.0"
    ruleVersion: Literal["frame-new-v1.4.3"] = "frame-new-v1.4.3"
    project: ProjectMeta
    inputs: FrameInput
    assembly: AssemblyGeometry
    parts: list[PartGeometry]
    validation: ValidationReport
