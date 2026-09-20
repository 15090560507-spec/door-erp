"""Shared door-trim geometry used by CAD drawing and quote calculation."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Sequence, Tuple


Point = Tuple[float, float]


def _number(value: Any, fallback: float = 0.0) -> float:
    if value is None:
        return float(fallback)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    return parsed if math.isfinite(parsed) else float(fallback)


def polygon_area(points: Sequence[Point]) -> float:
    """Return the absolute shoelace area for a closed or open point list."""
    if len(points) < 3:
        return 0.0
    return abs(
        sum(
            points[index][0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * points[index][1]
            for index in range(len(points))
        )
    ) / 2.0


@dataclass(frozen=True)
class TrimGeometry:
    side: str
    valid: bool
    error: str
    outer_contour: List[Point]
    inner_contour: List[Point]
    band_contour: List[Point]
    component_contours: List[List[Point]]
    lintel_contour: List[Point]
    outer_area_mm2: float
    inner_area_mm2: float
    base_area_mm2: float
    lintel_area_mm2: float
    included_lintel_area_mm2: float = 0.0

    @property
    def quote_area_mm2(self) -> float:
        return self.base_area_mm2 + self.included_lintel_area_mm2

    def include_lintel(self, included: bool) -> "TrimGeometry":
        return replace(
            self,
            included_lintel_area_mm2=self.lintel_area_mm2 if included else 0.0,
        )

    def to_quote_dict(self) -> Dict[str, Any]:
        def bounds(points: Sequence[Point]) -> Dict[str, float] | None:
            if not points:
                return None
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            return {
                "left": min(xs),
                "bottom": min(ys),
                "right": max(xs),
                "top": max(ys),
                "width": max(xs) - min(xs),
                "height": max(ys) - min(ys),
            }

        return {
            "side": self.side,
            "valid": self.valid,
            "error": self.error,
            "outerBounds": bounds(self.outer_contour),
            "innerBounds": bounds(self.inner_contour),
            "outerArea": round(self.outer_area_mm2 / 1_000_000, 6),
            "innerArea": round(self.inner_area_mm2 / 1_000_000, 6),
            "baseArea": round(self.base_area_mm2 / 1_000_000, 6),
            "lintelArea": round(self.lintel_area_mm2 / 1_000_000, 6),
            "includedLintelArea": round(self.included_lintel_area_mm2 / 1_000_000, 6),
            "quoteArea": round(self.quote_area_mm2 / 1_000_000, 6),
        }


def _rectangle(left: float, bottom: float, right: float, top: float) -> List[Point]:
    return [(left, bottom), (left, top), (right, top), (right, bottom)]


def _arch_geometry(left_x: float, right_x: float, spring_y: float, apex_y: float) -> Dict[str, float] | None:
    span = right_x - left_x
    sagitta = apex_y - spring_y
    if span <= 0 or sagitta <= 0:
        return None
    half = span / 2
    radius = (half * half + sagitta * sagitta) / (2 * sagitta)
    center_x = left_x + half
    center_y = spring_y - (radius - sagitta)
    return {
        "center_x": center_x,
        "center_y": center_y,
        "radius": radius,
        "start_angle": math.degrees(math.atan2(spring_y - center_y, right_x - center_x)),
        "end_angle": math.degrees(math.atan2(spring_y - center_y, left_x - center_x)),
    }


def _arc_point(geom: Dict[str, float], angle_key: str, radius_delta: float = 0.0) -> Point:
    angle = math.radians(geom[angle_key])
    radius = geom["radius"] + radius_delta
    return (
        geom["center_x"] + radius * math.cos(angle),
        geom["center_y"] + radius * math.sin(angle),
    )


def _arc_top_point_at_x(geom: Dict[str, float], x: float, radius_delta: float = 0.0) -> Point | None:
    radius = geom["radius"] + radius_delta
    if radius <= 0:
        return None
    dx = x - geom["center_x"]
    if abs(dx) > radius:
        return None
    return (x, geom["center_y"] + math.sqrt(max(0.0, radius * radius - dx * dx)))


def _arch_extended_shape(
    geom: Dict[str, float] | None,
    left_x: float,
    right_x: float,
    radius_delta: float = 0.0,
) -> Tuple[Point | None, Point | None, Dict[str, float] | None, float]:
    if not geom or right_x <= left_x or geom["radius"] + radius_delta <= 0:
        return None, None, None, 0.0
    left_point = _arc_top_point_at_x(geom, left_x, radius_delta)
    right_point = _arc_top_point_at_x(geom, right_x, radius_delta)
    if left_point and right_point:
        return left_point, right_point, geom, radius_delta

    left_base = _arc_point(geom, "end_angle", radius_delta)
    right_base = _arc_point(geom, "start_angle", radius_delta)
    spring_y = (left_base[1] + right_base[1]) / 2
    apex_y = geom["center_y"] + geom["radius"] + radius_delta
    extended = _arch_geometry(left_x, right_x, spring_y, apex_y)
    if not extended:
        return None, None, None, 0.0
    return (left_x, spring_y), (right_x, spring_y), extended, 0.0


def _arch_points_between(
    geom: Dict[str, float] | None,
    left_point: Point | None,
    right_point: Point | None,
    radius_delta: float = 0.0,
    segments: int = 512,
) -> List[Point]:
    if not geom or not left_point or not right_point:
        return []
    radius = geom["radius"] + radius_delta
    if radius <= 0:
        return []
    left_angle = math.degrees(math.atan2(left_point[1] - geom["center_y"], left_point[0] - geom["center_x"]))
    right_angle = math.degrees(math.atan2(right_point[1] - geom["center_y"], right_point[0] - geom["center_x"]))
    if right_angle > left_angle:
        right_angle -= 360
    return [
        (
            geom["center_x"] + radius * math.cos(math.radians(left_angle + (right_angle - left_angle) * index / segments)),
            geom["center_y"] + radius * math.sin(math.radians(left_angle + (right_angle - left_angle) * index / segments)),
        )
        for index in range(segments + 1)
    ]


def _empty(side: str) -> TrimGeometry:
    return TrimGeometry(side, True, "", [], [], [], [], [], 0.0, 0.0, 0.0, 0.0)


def _invalid(side: str, message: str) -> TrimGeometry:
    return TrimGeometry(side, False, message, [], [], [], [], [], 0.0, 0.0, 0.0, 0.0)


def calculate_trim_geometry(params: Dict[str, Any], is_back: bool = False) -> TrimGeometry:
    """Build the same trim contour geometry used by the front/back CAD view."""
    side = "inner" if is_back else "outer"
    dw = _number(params.get("dw"))
    dh = _number(params.get("dh"))
    trim_width = _number(params.get("trim_back" if is_back else "trim_front"))
    trim_top_width = _number(
        params.get("trim_back_top" if is_back else "trim_front_top"),
        trim_width,
    )
    if trim_width <= 0:
        return _empty(side)
    if dw <= 0 or dh <= 0 or trim_top_width <= 0:
        return _invalid(side, "门套轮廓尺寸无效")

    overlap_default = _number(params.get("overlap_back" if is_back else "overlap_front"), params.get("overlap", 20))
    overlap_lr = _number(
        params.get("overlap_back_lr" if is_back else "overlap_front_lr"),
        overlap_default,
    )
    overlap_top = _number(
        params.get("overlap_back_top" if is_back else "overlap_front_top"),
        overlap_default,
    )
    qc_height = _number(params.get("qc_height"), 400)
    qc_enabled = str(params.get("qc") or "无") in {"玻璃", "封闭"}
    qc_height = qc_height if qc_enabled else 0.0
    is_integrated_door = bool(params.get("is_integrated_door", False))
    integrated_extra = (
        _number(params.get("integrated_panel_height"), 300)
        + _number(params.get("integrated_glass_height"), 500)
        if is_integrated_door
        else 0.0
    )
    total_height = dh + (integrated_extra if is_integrated_door else qc_height)
    lintel_height = _number(params.get("mm_height"), 200) if bool(params.get("has_mm", False)) else 0.0
    lintel_offset = lintel_height if lintel_height > 0 else 0.0

    inner_left = overlap_lr
    inner_right = dw - overlap_lr
    inner_top = total_height - overlap_top + lintel_offset
    outer_left = overlap_lr - trim_width
    outer_right = dw - overlap_lr + trim_width
    outer_top = total_height - overlap_top + trim_top_width + lintel_offset
    if inner_right <= inner_left or inner_top <= 0 or outer_right <= outer_left or outer_top <= 0:
        return _invalid(side, "门套内外轮廓无法形成有效闭合区域")

    has_outer_portal = bool(params.get("has_outer_portal", False)) and not is_back
    has_outer_portal2 = bool(params.get("has_outer_portal2", False)) and not is_back
    has_outer_landscape = bool(params.get("has_outer_landscape", False)) and not is_back
    component_contours: List[List[Point]] = []

    if has_outer_landscape or has_outer_portal2:
        left_width = max(_number(params.get("trim_front"), trim_width), 0.0)
        right_width = max(_number(params.get("trim_front_right"), left_width), 0.0)
        top_width = max(_number(params.get("trim_front_top"), trim_top_width), 0.0)
        if has_outer_portal2:
            left_overlap = right_overlap = max(_number(params.get("outer_portal2_lr_overlap"), overlap_lr), 0.0)
            top_overlap = max(_number(params.get("outer_portal2_top_overlap"), overlap_top), 0.0)
        else:
            left_overlap = max(_number(params.get("outer_landscape_left_overlap"), overlap_lr), 0.0)
            right_overlap = max(_number(params.get("outer_landscape_right_overlap"), overlap_lr), 0.0)
            top_overlap = max(_number(params.get("outer_landscape_top_overlap"), overlap_top), 0.0)
        inner_left = left_overlap
        inner_right = dw - right_overlap
        inner_top = total_height - top_overlap + lintel_offset
        outer_left = inner_left - left_width
        outer_right = inner_right + right_width
        outer_top = inner_top + top_width
        if inner_right <= inner_left or min(left_width, right_width, top_width) <= 0:
            return _invalid(side, "门头门柱轮廓尺寸无效")
        component_contours = [
            _rectangle(outer_left, 0.0, inner_left, outer_top),
            _rectangle(inner_right, 0.0, outer_right, outer_top),
            _rectangle(inner_left, inner_top, inner_right, outer_top),
        ]
        outer_contour = _rectangle(outer_left, 0.0, outer_right, outer_top)
        inner_contour = _rectangle(inner_left, 0.0, inner_right, inner_top)
    elif has_outer_portal:
        component_contours = [
            _rectangle(outer_left, 0.0, inner_left, inner_top),
            _rectangle(inner_right, 0.0, outer_right, inner_top),
            _rectangle(outer_left, inner_top, outer_right, outer_top),
        ]
        outer_contour = _rectangle(outer_left, 0.0, outer_right, outer_top)
        inner_contour = _rectangle(inner_left, 0.0, inner_right, inner_top)
    else:
        if is_back and str(params.get("door_type") or "单门") == "单门":
            left_frame = _number(params.get("right_width_back"))
            right_frame = _number(params.get("left_width_back"))
        else:
            left_frame = _number(params.get("left_width_back" if is_back else "left_width_front"))
            right_frame = _number(params.get("right_width_back" if is_back else "right_width_front"))
        top_frame = _number(params.get("fw_top_back" if is_back else "fw_top_front"))
        is_arch_qc = qc_height > 0 and str(params.get("qc_shape") or "") == "弧形气窗"
        is_arch_door = bool(params.get("is_arch_door", False)) and qc_height <= 0 and not is_integrated_door
        if is_arch_qc or is_arch_door:
            spring_y = total_height - qc_height if is_arch_qc else _number(params.get("arch_spring_height"), dh - 400)
            if is_arch_door:
                spring_y = max(1.0, min(spring_y, dh - top_frame - 1.0))
            frame_arch = _arch_geometry(left_frame, dw - right_frame, spring_y, total_height - top_frame)
            _, _, trim_base_arch, trim_base_delta = _arch_extended_shape(frame_arch, 0.0, dw, top_frame)
            inner_shape = _arch_extended_shape(trim_base_arch, inner_left, inner_right, trim_base_delta - overlap_lr)
            outer_shape = _arch_extended_shape(trim_base_arch, outer_left, outer_right, trim_base_delta - overlap_lr + trim_top_width)
            inner_arch_left, inner_arch_right, inner_arch, inner_delta = inner_shape
            outer_arch_left, outer_arch_right, outer_arch, outer_delta = outer_shape
            inner_arc = _arch_points_between(inner_arch, inner_arch_left, inner_arch_right, inner_delta)
            outer_arc = _arch_points_between(outer_arch, outer_arch_left, outer_arch_right, outer_delta)
            if not inner_arc or not outer_arc:
                return _invalid(side, "圆弧门套轮廓计算失败")
            outer_contour = [(outer_left, 0.0), *outer_arc, (outer_right, 0.0)]
            inner_contour = [(inner_left, 0.0), *inner_arc, (inner_right, 0.0)]
        else:
            outer_contour = _rectangle(outer_left, 0.0, outer_right, outer_top)
            inner_contour = _rectangle(inner_left, 0.0, inner_right, inner_top)

    outer_area = polygon_area(outer_contour)
    inner_area = polygon_area(inner_contour)
    base_area = outer_area - inner_area
    if outer_area <= 0 or inner_area <= 0 or base_area <= 0:
        return _invalid(side, "门套外轮廓必须大于内轮廓")

    band_contour = [*outer_contour, *reversed(inner_contour)]
    lintel_contour: List[Point] = []
    lintel_area = 0.0
    if lintel_height > 0:
        lintel_bottom = total_height - overlap_top
        lintel_left = overlap_lr
        lintel_right = dw - overlap_lr
        if lintel_right > lintel_left:
            lintel_contour = _rectangle(
                lintel_left,
                lintel_bottom,
                lintel_right,
                lintel_bottom + lintel_height,
            )
            lintel_area = polygon_area(lintel_contour)

    return TrimGeometry(
        side=side,
        valid=True,
        error="",
        outer_contour=outer_contour,
        inner_contour=inner_contour,
        band_contour=band_contour,
        component_contours=component_contours,
        lintel_contour=lintel_contour,
        outer_area_mm2=outer_area,
        inner_area_mm2=inner_area,
        base_area_mm2=base_area,
        lintel_area_mm2=lintel_area,
    )


def calculate_quote_trim_metrics(
    params: Dict[str, Any],
) -> Tuple[TrimGeometry, TrimGeometry, str]:
    """Apply the quote-only rule that a lintel belongs to exactly one trim side."""
    outer = calculate_trim_geometry(params, is_back=False)
    inner = calculate_trim_geometry(params, is_back=True)
    lintel_target = "none"
    if outer.lintel_area_mm2 > 0 and outer.base_area_mm2 > 0:
        outer = outer.include_lintel(True)
        lintel_target = "outer"
    elif inner.lintel_area_mm2 > 0 and inner.base_area_mm2 > 0:
        inner = inner.include_lintel(True)
        lintel_target = "inner"
    return outer, inner, lintel_target
