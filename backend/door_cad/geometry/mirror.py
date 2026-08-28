"""Horizontal mirroring of real geometry and dimension witness points."""

from __future__ import annotations

from door_cad.models import (
    ClosedPolyline,
    GeometryDimension,
    Groove,
    PartGeometry,
    Point2D,
    Polyline,
    Segment,
    Shape,
)


def mirror_point(value: Point2D, width: float) -> Point2D:
    return Point2D(x=float(width) - value.x, y=value.y)


def mirror_polyline(value: Polyline, width: float) -> Polyline:
    return value.model_copy(update={"points": [mirror_point(item, width) for item in value.points]})


def mirror_closed_polyline(value: ClosedPolyline, width: float) -> ClosedPolyline:
    return value.model_copy(update={"points": [mirror_point(item, width) for item in value.points]})


def mirror_shape(value: Shape, width: float) -> Shape:
    updates = {"points": [mirror_point(item, width) for item in value.points]}
    if value.center is not None:
        updates["center"] = mirror_point(value.center, width)
    return value.model_copy(update=updates)


def mirror_groove(value: Groove, width: float) -> Groove:
    segments = [
        Segment(start=mirror_point(item.start, width), end=mirror_point(item.end, width))
        for item in value.segments
    ]
    return value.model_copy(update={"segments": segments})


def mirror_dimension(value: GeometryDimension, width: float) -> GeometryDimension:
    return value.model_copy(
        update={
            "start": mirror_point(value.start, width),
            "end": mirror_point(value.end, width),
        }
    )


def mirror_part(
    source: PartGeometry,
    *,
    part_id: str,
    name: str,
    position: str,
) -> PartGeometry:
    width = source.flatWidth
    process = source.process.model_copy(update={"mirrored": True})
    fold_nodes = [node.model_copy(update={"x": width - node.x}) for node in process.foldNodes]
    process = process.model_copy(update={"foldNodes": fold_nodes})
    return source.model_copy(
        update={
            "partId": part_id,
            "name": name,
            "position": position,
            "cutOuter": mirror_closed_polyline(source.cutOuter, width),
            "holes": [mirror_shape(item, width) for item in source.holes],
            "grooves": [mirror_groove(item, width) for item in source.grooves],
            "foldSection": mirror_polyline(source.foldSection, width),
            "flatSection": mirror_polyline(source.flatSection, width),
            "dimensions": [mirror_dimension(item, width) for item in source.dimensions],
            "process": process,
        }
    )
