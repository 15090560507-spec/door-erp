"""Pure new-process side-frame skeleton rule."""

from __future__ import annotations

from door_cad.geometry import point, polyline, rectangle
from door_cad.models import (
    FoldNode,
    FrameInput,
    GeometryDimension,
    Groove,
    PartGeometry,
    PartProcessMeta,
    Point2D,
    Segment,
    Shape,
)

from .opening import edge_fixing_positions, resolve_hinge_positions


def _running_positions(segments: list[float]) -> list[float]:
    result: list[float] = []
    total = 0.0
    for segment in segments[:-1]:
        total += segment
        result.append(round(total, 4))
    return result


def build_left_skeleton(inputs: FrameInput) -> PartGeometry:
    short, long = inputs.resolved_skeleton_sizes()
    delta = short - 52.0
    long_delta = long - 59.0
    segments = [13.0, 50.0 + delta, 50.0, 13.0, 52.0, 20.0, 21.0, 57.0 + long_delta, 13.0]
    faces = ["inner", "inner", "inner", "outer", "outer", "inner", "inner", "inner"]
    positions = _running_positions(segments)
    flat_width = sum(segments)
    length = inputs.doorHeight

    grooves = [
        Groove(
            grooveId=f"groove-{index + 1}",
            face=face,
            segments=[Segment(start=Point2D(x=x, y=0), end=Point2D(x=x, y=length))],
            depth=inputs.skeletonGrooveDepth,
            width=inputs.skeletonGrooveWidth,
        )
        for index, (x, face) in enumerate(zip(positions, faces))
    ]

    holes: list[Shape] = []
    for side_index, x in enumerate((6.0, flat_width - 6.0), start=1):
        for row_index, y in enumerate(edge_fixing_positions(length), start=1):
            holes.append(
                Shape(
                    shapeId=f"edge-{side_index}-{row_index}",
                    kind="circle",
                    center=Point2D(x=x, y=y),
                    diameter=4.5,
                )
            )

    hinge_positions = resolve_hinge_positions(
        length,
        inputs.hingeCount,
        inputs.hingePositions if inputs.hingeMode == "custom" else None,
    )
    hinge_x = inputs.hingeCenterSkeleton + delta
    for index, top_distance in enumerate(hinge_positions, start=1):
        center = Point2D(x=hinge_x, y=length - top_distance)
        holes.append(
            Shape(
                shapeId=f"hinge-body-{index}",
                kind="rectangle",
                center=center,
                width=68.0,
                height=192.0,
            )
        )
        holes.append(
            Shape(
                shapeId=f"hinge-upper-{index}",
                kind="circle",
                center=Point2D(x=hinge_x, y=center.y + 83.0),
                diameter=6.0,
            )
        )
        holes.append(
            Shape(
                shapeId=f"hinge-lower-{index}",
                kind="circle",
                center=Point2D(x=hinge_x, y=center.y - 78.0),
                diameter=16.0,
            )
        )

    end_hole_xs = [88.0 + delta, 151.0 + delta, 207.5 + delta + long_delta]
    for end_name, y in (("bottom", 29.7), ("top", length - 29.7)):
        for index, x in enumerate(end_hole_xs, start=1):
            holes.append(
                Shape(
                    shapeId=f"end-{end_name}-{index}",
                    kind="circle",
                    center=Point2D(x=x, y=y),
                    diameter=9.0,
                )
            )

    slot_xs = [88.0 + delta, 207.5 + delta + long_delta]
    for end_name, distances in (("top", [52.95, 72.95]), ("bottom", [52.95, 72.95])):
        for index, (x, distance) in enumerate(zip(slot_xs, distances), start=1):
            y = length - distance if end_name == "top" else distance
            holes.append(
                Shape(
                    shapeId=f"slot-{end_name}-{index}",
                    kind="rectangle",
                    center=Point2D(x=x, y=y),
                    width=15.0,
                    height=2.5,
                )
            )

    fold_profile = [
        (0.0, 0.0),
        (0.0, 14.0),
        (short, 14.0),
        (short, -38.0),
        (short - 13.0, -38.0),
        (short - 13.0, -88.0),
        (long, -88.0),
        (long, -111.0),
        (0.0, -111.0),
        (0.0, -97.0),
    ]
    dimensions = [
        GeometryDimension(
            dimensionId="flat-width",
            label="展开宽",
            start=point((0, 0)),
            end=point((flat_width, 0)),
            orientation="horizontal",
            value=flat_width,
        ),
        GeometryDimension(
            dimensionId="length",
            label="长度",
            start=point((flat_width, 0)),
            end=point((flat_width, length)),
            orientation="vertical",
            value=length,
        ),
    ]

    return PartGeometry(
        partId="LF-SK",
        name="左框骨架",
        position="left",
        materialType="skeleton",
        length=length,
        thickness=inputs.skeletonThickness,
        flatWidth=flat_width,
        cutOuter=rectangle(flat_width, length),
        holes=holes,
        grooves=grooves,
        foldSection=polyline(fold_profile),
        flatSection=polyline([(0, 0), (flat_width, 0)]),
        dimensions=dimensions,
        process=PartProcessMeta(
            grooveFaces=[groove.face for groove in grooves],
            foldNodes=[
                FoldNode(x=x, angle=90, direction="up" if face == "outer" else "down")
                for x, face in zip(positions, faces)
            ],
        ),
    )
