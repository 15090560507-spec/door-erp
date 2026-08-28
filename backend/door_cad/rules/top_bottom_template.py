"""Independent top/bottom-frame rules ported from the frozen v1.4.3 template."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil, cos, pi, sin
from pathlib import Path

import ezdxf

from door_cad.baseline import BASELINE_DIR
from door_cad.geometry import closed_polyline, point, polyline
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


DEFAULT_TEMPLATE = BASELINE_DIR / "top_bottom_double_door_template.dxf"
OLD_LONG = 1740.0
OLD_SHORT_START = 7.0
OLD_SHORT_END = 1733.0


class TemplateRuleError(RuntimeError):
    """The frozen manufacturing template cannot be interpreted safely."""


@dataclass(frozen=True)
class TemplateGroup:
    part_id: str
    name: str
    position: str
    material_type: str
    src_x0: float
    src_x1: float
    src_chain: tuple[float, ...]
    source_grooves: tuple[tuple[float, str], ...]
    pin_x_source: float
    outer_side: str
    short_tab_range: tuple[float, float] | None = None


GROUPS = {
    "TF-SK": TemplateGroup(
        "TF-SK", "上框骨架", "top", "skeleton", 2465.5, 2754.5,
        (0, 13, 63, 186, 206, 276, 289),
        ((13, "BACK"), (63, "BACK"), (166, "FRONT"), (186, "BACK"), (206, "BACK"), (276, "BACK")),
        102.0, "left", (190.5, 198.5),
    ),
    "BF-SK": TemplateGroup(
        "BF-SK", "下框骨架", "bottom", "skeleton", 3545.5, 3834.5,
        (0, 13, 83, 103, 226, 276, 289),
        ((13, "BACK"), (83, "BACK"), (103, "BACK"), (123, "FRONT"), (226, "BACK"), (276, "BACK")),
        187.0, "right", (90.5, 98.5),
    ),
    "TF-SKIN": TemplateGroup(
        "TF-SKIN", "上框外皮", "top", "skin", 4890.576315665818, 5214.776315665818,
        (0, 14.5, 68.5, 186.7, 197.7, 233.7, 307.7, 324.2),
        ((14.5, "BACK"), (68.5, "BACK"), (168.3, "FRONT"), (176.9, "FRONT"), (186.7, "BACK"), (197.7, "BACK"), (233.7, "BACK"), (307.7, "BACK")),
        108.5, "left",
    ),
    "BF-SKIN": TemplateGroup(
        "BF-SKIN", "下框外皮", "bottom", "skin", 6007.5765, 6331.7765,
        (0, 16.5, 90.5, 126.5, 137.5, 255.7, 309.7, 324.2),
        ((16.5, "BACK"), (90.5, "BACK"), (126.5, "BACK"), (137.5, "BACK"), (147.3, "FRONT"), (155.9, "FRONT"), (255.7, "BACK"), (309.7, "BACK")),
        215.7, "right",
    ),
}


def _target_chain(group: TemplateGroup, short: float, long: float) -> list[float]:
    if group.material_type == "skeleton":
        small = short - 3.0
        large = long - 3.0
        segments = (
            [13.0, small - 2.0, 123.0, 20.0, large - 2.0, 13.0]
            if group.position == "top"
            else [13.0, large - 2.0, 20.0, 123.0, small - 2.0, 13.0]
        )
    else:
        segments = (
            [14.5, short - 1.0, 118.2, 11.0, 36.0, long - 1.0, 16.5]
            if group.position == "top"
            else [16.5, long - 1.0, 36.0, 11.0, 118.2, short - 1.0, 14.5]
        )
    chain = [0.0]
    for segment in segments:
        chain.append(chain[-1] + segment)
    return chain


def _piecewise_mapper(source: tuple[float, ...], target: list[float]) -> Callable[[float], float]:
    def mapper(value: float) -> float:
        if value <= source[0]:
            return target[0] + value - source[0]
        if value >= source[-1]:
            return target[-1] + value - source[-1]
        for s0, s1, t0, t1 in zip(source[:-1], source[1:], target[:-1], target[1:]):
            if s0 - 1e-9 <= value <= s1 + 1e-9:
                return t0 + (value - s0) * (t1 - t0) / (s1 - s0)
        return value

    return mapper


def _y_mapper(long_length: float, short_length: float, protrusion: float, group: TemplateGroup):
    short_end = protrusion + short_length

    def base(y: float) -> float:
        if y < 0:
            return y
        if y <= OLD_SHORT_START:
            return y * protrusion / OLD_SHORT_START
        if y <= OLD_SHORT_END:
            return protrusion + (y - OLD_SHORT_START) * short_length / (OLD_SHORT_END - OLD_SHORT_START)
        if y <= OLD_LONG:
            return short_end + (y - OLD_SHORT_END) * (long_length - short_end) / (OLD_LONG - OLD_SHORT_END)
        return long_length + y - OLD_LONG

    def mapper(x: float, y: float) -> float:
        tab = group.short_tab_range
        if group.material_type == "skeleton" and tab and tab[0] - 0.01 <= x <= tab[1] + 0.01:
            if -1.01 <= y <= OLD_SHORT_START + 0.01:
                return protrusion + y - OLD_SHORT_START
            if OLD_SHORT_END - 0.01 <= y <= 1741.01:
                return short_end + y - OLD_SHORT_END
        return base(y)

    return mapper


def _arc_segments(entity, group: TemplateGroup) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    start = float(entity.dxf.start_angle)
    end = float(entity.dxf.end_angle)
    while end <= start:
        end += 360.0
    steps = max(2, ceil((end - start) / 6.0))
    center = entity.dxf.center
    radius = float(entity.dxf.radius)
    points: list[tuple[float, float]] = []
    for index in range(steps + 1):
        angle = (start + (end - start) * index / steps) * pi / 180.0
        points.append((float(center.x) + radius * cos(angle) - group.src_x0, float(center.y) + radius * sin(angle)))
    return list(zip(points[:-1], points[1:]))


def _read_source_segments(path: Path, group: TemplateGroup) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    try:
        modelspace = ezdxf.readfile(path).modelspace()
    except Exception as exc:
        raise TemplateRuleError(f"上下框模板无法读取：{path.name}：{exc}") from exc

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for entity in modelspace:
        if entity.dxf.layer != "0":
            continue
        if entity.dxftype() == "LINE":
            start = entity.dxf.start
            end = entity.dxf.end
            if not (group.src_x0 - 1 <= start.x <= group.src_x1 + 1 and group.src_x0 - 1 <= end.x <= group.src_x1 + 1):
                continue
            if min(start.y, end.y) < -30 or max(start.y, end.y) > 1770:
                continue
            segments.append(((float(start.x) - group.src_x0, float(start.y)), (float(end.x) - group.src_x0, float(end.y))))
        elif entity.dxftype() == "ARC":
            center = entity.dxf.center
            radius = float(entity.dxf.radius)
            if not group.src_x0 - 1 <= center.x <= group.src_x1 + 1:
                continue
            if center.y - radius < -30 or center.y + radius > 1770:
                continue
            segments.extend(_arc_segments(entity, group))
    if not segments:
        raise TemplateRuleError(f"上下框模板源组无法识别：{group.name}")
    return segments


def _near(a: tuple[float, float], b: tuple[float, float], tolerance: float = 0.03) -> bool:
    return abs(a[0] - b[0]) <= tolerance and abs(a[1] - b[1]) <= tolerance


def _stitch_contour(segments: list[tuple[tuple[float, float], tuple[float, float]]], group: TemplateGroup) -> list[tuple[float, float]]:
    remaining = segments.copy()
    start, end = remaining.pop(0)
    points = [start, end]
    while remaining:
        current = points[-1]
        for index, (a, b) in enumerate(remaining):
            if _near(current, a):
                points.append(b)
                remaining.pop(index)
                break
            if _near(current, b):
                points.append(a)
                remaining.pop(index)
                break
        else:
            raise TemplateRuleError(f"上下框模板源组轮廓未闭合：{group.name}")
    if not _near(points[0], points[-1]):
        raise TemplateRuleError(f"上下框模板源组轮廓未闭合：{group.name}")
    return points[:-1]


def _fold_profile(group: TemplateGroup, short: float, long: float) -> list[tuple[float, float]]:
    if group.material_type == "skeleton":
        small, large = short - 3.0, long - 3.0
        return [(0, 0), (0, 14), (small, 14), (small, -88), (large, -88), (large, -111), (0, -111), (0, -97)]
    return [(0, 0), (0, 15), (short, 15), (short, -85), (short + 8, -85), (short + 8, -75), (long, -75), (long, -112), (0, -112), (0, -95)]


def _shape_holes(group: TemplateGroup, width: float, long_length: float, short_length: float, protrusion: float, pin_center: float, pin_x: float, include_pin: bool) -> list[Shape]:
    holes: list[Shape] = []
    long_x = 6.0 if group.outer_side == "left" else width - 6.0
    short_x = width - 6.0 if group.outer_side == "left" else 6.0
    short_end = protrusion + short_length
    for side_name, x, positions in (
        ("long", long_x, (30.0, long_length / 2.0, long_length - 30.0)),
        ("short", short_x, (protrusion + 30.0, (protrusion + short_end) / 2.0, short_end - 30.0)),
    ):
        for index, y in enumerate(positions, start=1):
            if group.material_type == "skeleton":
                holes.append(Shape(shapeId=f"edge-{side_name}-{index}", kind="circle", center=Point2D(x=x, y=y), diameter=4.5))
            else:
                holes.append(Shape(shapeId=f"edge-{side_name}-{index}", kind="obround", center=Point2D(x=x, y=y), width=5.0, height=9.0))
    if include_pin:
        if group.material_type == "skeleton":
            holes.append(Shape(shapeId="pin", kind="rectangle", center=Point2D(x=pin_x, y=pin_center), width=34.5, height=38.0))
        else:
            holes.append(Shape(shapeId="pin", kind="obround", center=Point2D(x=pin_x, y=pin_center), width=35.5, height=72.5))
    return holes


def build_template_part(inputs: FrameInput, part_id: str, short: float, long: float, include_pin: bool, template_path: str | Path | None = None) -> PartGeometry:
    group = GROUPS[part_id]
    path = Path(template_path) if template_path else DEFAULT_TEMPLATE
    if not path.exists():
        raise TemplateRuleError(f"上下框模板不存在：{path}")

    side_short, side_long = inputs.resolved_skin_sizes()
    long_length = inputs.doorWidth - side_short * 2.0
    short_length = inputs.doorWidth - side_long * 2.0
    protrusion = side_long - side_short
    if short_length <= 0:
        raise TemplateRuleError("门宽不足，计算后的上下框短边长度小于等于0")
    pin_center = long_length / 2.0 - 54.0

    target_chain = _target_chain(group, short, long)
    x_mapper = _piecewise_mapper(group.src_chain, target_chain)
    y_mapper = _y_mapper(long_length, short_length, protrusion, group)
    contour = _stitch_contour(_read_source_segments(path, group), group)
    transformed = [(x_mapper(x), y_mapper(x, y)) for x, y in contour]

    groove_depth = inputs.skeletonGrooveDepth if group.material_type == "skeleton" else inputs.skinGrooveDepth
    groove_width = inputs.skeletonGrooveWidth if group.material_type == "skeleton" else inputs.skinGrooveWidth
    grooves: list[Groove] = []
    for index, (source_x, face_name) in enumerate(group.source_grooves, start=1):
        x = x_mapper(source_x)
        face = "outer" if face_name == "FRONT" else "inner"
        grooves.append(Groove(
            grooveId=f"groove-{index}", face=face,
            segments=[Segment(start=Point2D(x=x, y=y_mapper(source_x, 0)), end=Point2D(x=x, y=y_mapper(source_x, OLD_LONG)))],
            depth=groove_depth, width=groove_width,
        ))

    flat_width = target_chain[-1]
    holes = _shape_holes(group, flat_width, long_length, short_length, protrusion, pin_center, x_mapper(group.pin_x_source), include_pin)
    dimensions = [
        GeometryDimension(dimensionId="flat-width", label="展开宽", start=point((0, 0)), end=point((flat_width, 0)), orientation="horizontal", value=flat_width),
        GeometryDimension(dimensionId="long-length", label="长边", start=point((0, 0)), end=point((0, long_length)), orientation="vertical", value=long_length),
        GeometryDimension(dimensionId="short-length", label="短边", start=point((flat_width, protrusion)), end=point((flat_width, protrusion + short_length)), orientation="vertical", value=short_length),
    ]
    thickness = inputs.skeletonThickness if group.material_type == "skeleton" else inputs.skinThickness
    return PartGeometry(
        partId=group.part_id, name=group.name, position=group.position,
        materialType=group.material_type, length=long_length, thickness=thickness,
        flatWidth=flat_width, cutOuter=closed_polyline(transformed), holes=holes, grooves=grooves,
        foldSection=polyline(_fold_profile(group, short, long)), flatSection=polyline([(0, 0), (flat_width, 0)]),
        dimensions=dimensions,
        process=PartProcessMeta(
            sourceTemplate=path.name, mirrored=group.outer_side == "right",
            grooveFaces=[groove.face for groove in grooves],
            foldNodes=[FoldNode(x=x_mapper(source_x), angle=90, direction="up" if face == "FRONT" else "down") for source_x, face in group.source_grooves],
            notes=[f"长边 {long_length:g}", f"短边 {short_length:g}", f"端差 {protrusion:g}"],
        ),
    )
