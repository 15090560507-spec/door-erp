"""Public typed contract for the door-frame cutting module."""

from .geometry import (
    AssemblyGeometry,
    ClosedPolyline,
    FoldNode,
    GeometryDimension,
    Groove,
    PartGeometry,
    PartPlacement,
    PartProcessMeta,
    Point2D,
    Polyline,
    ProjectGeometry,
    ProjectMeta,
    Segment,
    Shape,
    ValidationIssue,
    ValidationReport,
)
from .inputs import FrameInput

__all__ = [
    "AssemblyGeometry",
    "ClosedPolyline",
    "FoldNode",
    "FrameInput",
    "GeometryDimension",
    "Groove",
    "PartGeometry",
    "PartPlacement",
    "PartProcessMeta",
    "Point2D",
    "Polyline",
    "ProjectGeometry",
    "ProjectMeta",
    "Segment",
    "Shape",
    "ValidationIssue",
    "ValidationReport",
]
