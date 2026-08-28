"""Compute every selected frame part once and expose one geometry snapshot."""

from __future__ import annotations

from door_cad.models import (
    AssemblyGeometry,
    FrameInput,
    PartGeometry,
    PartPlacement,
    ProjectGeometry,
    ProjectMeta,
    ValidationReport,
)
from door_cad.rules import build_bottom_parts, build_side_parts, build_top_parts

from .validation import validate_project_geometry


def _calculate_parts(inputs: FrameInput) -> list[PartGeometry]:
    parts: list[PartGeometry] = []
    if inputs.includeLeft:
        parts.extend(build_side_parts(inputs, "left"))
    if inputs.includeRight:
        parts.extend(build_side_parts(inputs, "right"))
    if inputs.includeTop:
        parts.extend(build_top_parts(inputs))
    if inputs.includeBottom:
        parts.extend(build_bottom_parts(inputs))
    return parts


def _placement(part: PartGeometry, inputs: FrameInput) -> PartPlacement:
    side_width = inputs.outerSideShort
    if part.position == "left":
        return PartPlacement(partId=part.partId, x=0, y=0, width=side_width, height=inputs.doorHeight)
    if part.position == "right":
        return PartPlacement(
            partId=part.partId,
            x=inputs.doorWidth - side_width,
            y=0,
            width=side_width,
            height=inputs.doorHeight,
        )
    short, _ = (inputs.topShort, inputs.topLong) if part.position == "top" else inputs.resolved_bottom_sizes()
    return PartPlacement(
        partId=part.partId,
        x=inputs.outerSideShort,
        y=inputs.doorHeight - short if part.position == "top" else 0,
        width=inputs.doorWidth - inputs.outerSideShort * 2,
        height=short,
    )


def calculate_frame_project(
    inputs: FrameInput,
    project: ProjectMeta | None = None,
) -> ProjectGeometry:
    """Return the canonical geometry consumed by preview, DXF, BOM and JSON."""

    parts = _calculate_parts(inputs)
    assembly = AssemblyGeometry(
        width=inputs.doorWidth,
        height=inputs.doorHeight,
        placements=[_placement(part, inputs) for part in parts],
    )
    geometry = ProjectGeometry(
        project=project or ProjectMeta(),
        inputs=inputs,
        assembly=assembly,
        parts=parts,
        validation=ValidationReport(),
    )
    return geometry.model_copy(update={"validation": validate_project_geometry(geometry)})
