"""Pure new-process side-frame skin rule, including real CUT_OUTER notches."""

from __future__ import annotations

from door_cad.geometry import closed_polyline, point, polyline, vertical_material_interval
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


def build_skin_cut_outer(
    flat_width: float,
    length: float,
    x1: float,
    x2: float,
    depth: float,
):
    return closed_polyline(
        [
            (0, 0),
            (x1, 0),
            (x1, depth),
            (x2, depth),
            (x2, 0),
            (flat_width, 0),
            (flat_width, length),
            (x2, length),
            (x2, length - depth),
            (x1, length - depth),
            (x1, length),
            (0, length),
        ]
    )


def _running_positions(segments: list[float]) -> list[float]:
    result: list[float] = []
    total = 0.0
    for segment in segments[:-1]:
        total += segment
        result.append(round(total, 4))
    return result


def build_left_skin(inputs: FrameInput) -> PartGeometry:
    short, long = inputs.resolved_skin_sizes()
    delta = short - 55.0
    long_delta = long - 62.0
    segments = [
        14.5,
        54.0 + delta,
        58.0,
        12.8,
        42.6,
        8.6,
        9.8,
        11.0,
        36.0,
        61.0 + long_delta,
        16.5,
    ]
    faces = ["inner", "inner", "inner", "outer", "outer", "outer", "inner", "inner", "inner", "inner"]
    positions = _running_positions(segments)
    flat_width = sum(segments)
    length = inputs.doorHeight
    notch = (76.0 + delta, 239.8 + delta + long_delta, 47.0)

    grooves = []
    for index, (x, face) in enumerate(zip(positions, faces), start=1):
        y1, y2 = vertical_material_interval(x, length, notch)
        grooves.append(
            Groove(
                grooveId=f"groove-{index}",
                face=face,
                segments=[Segment(start=Point2D(x=x, y=y1), end=Point2D(x=x, y=y2))],
                depth=inputs.skinGrooveDepth,
                width=inputs.skinGrooveWidth,
            )
        )

    holes: list[Shape] = []
    for side_index, x in enumerate((6.0, flat_width - 6.0), start=1):
        for row_index, y in enumerate(edge_fixing_positions(length), start=1):
            holes.append(
                Shape(
                    shapeId=f"edge-{side_index}-{row_index}",
                    kind="obround",
                    center=Point2D(x=x, y=y),
                    width=5.0,
                    height=9.0,
                )
            )

    hinge_positions = resolve_hinge_positions(
        length,
        inputs.hingeCount,
        inputs.hingePositions if inputs.hingeMode == "custom" else None,
    )
    hinge_x = inputs.hingeCenterSkin + delta
    for index, top_distance in enumerate(hinge_positions, start=1):
        holes.append(
            Shape(
                shapeId=f"hinge-body-{index}",
                kind="obround",
                center=Point2D(x=hinge_x, y=length - top_distance),
                width=46.0,
                height=190.0,
            )
        )

    slot_xs = [95.5 + delta, 232.8 + delta + long_delta]
    for end_name, distances in (("top", [52.325, 72.325]), ("bottom", [52.325, 72.325])):
        for index, (x, distance) in enumerate(zip(slot_xs, distances), start=1):
            y = length - distance if end_name == "top" else distance
            holes.append(
                Shape(
                    shapeId=f"slot-{end_name}-{index}",
                    kind="rectangle",
                    center=Point2D(x=x, y=y),
                    width=20.0,
                    height=3.75,
                )
            )

    fold_profile = [
        (0.0, 0.0),
        (0.0, 15.0),
        (short, 15.0),
        (short, -44.0),
        (short - 13.0, -44.0),
        (short - 13.0, -86.0),
        (short - 5.0, -86.0),
        (short - 5.0, -76.0),
        (long, -76.0),
        (long, -113.0),
        (0.0, -113.0),
        (0.0, -96.0),
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
        partId="LF-SKIN",
        name="左框外皮",
        position="left",
        materialType="skin",
        length=length,
        thickness=inputs.skinThickness,
        flatWidth=flat_width,
        cutOuter=build_skin_cut_outer(flat_width, length, *notch),
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
            notes=[f"端部异形缺口 {notch[0]:g}-{notch[1]:g}，深 {notch[2]:g}"],
        ),
    )
