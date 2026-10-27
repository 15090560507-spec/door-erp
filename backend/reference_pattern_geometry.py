"""Fixed physical edge details with a stretchable middle and true-width contours."""
from math import isfinite
from shapely.geometry import LineString, box
from shapely.ops import unary_union
from reference_pattern_models import PatternPlacement


def axis_position(value, size, margin, detail, stretch):
    low, high = stretch
    span = size - 2 * margin
    if span <= 2 * detail:
        raise ValueError(f"目标区域过小，需增大区域或减小边距/造型区尺寸（当前区域{size:g}mm）")
    if value <= low:
        return margin + value / low * detail
    if value >= high:
        return size - margin - (1 - value) / (1 - high) * detail
    return margin + detail + (value - low) / (high - low) * (span - 2 * detail)


def pattern_contours(placement: PatternPlacement | dict, width: float, height: float):
    placement = PatternPlacement.model_validate(placement) if isinstance(placement, dict) else placement
    if not all(isfinite(value) and 0 < value <= 10000 for value in (width, height)):
        raise ValueError("区域宽高无效")
    margin = placement.inset + placement.band_width / 2
    strokes, paths = [], []
    for path in placement.definition.paths:
        points = []
        for x, y in path.points:
            mapped_x = axis_position(x, width, margin, placement.detail_x, placement.definition.stretch_x)
            points.append((width - mapped_x if placement.mirror else mapped_x,
                           axis_position(y, height, margin, placement.detail_y, placement.definition.stretch_y)))
        if path.closed:
            points.append(points[0])
        paths.append(points)
        strokes.append(LineString(points).buffer(placement.band_width / 2, cap_style="square", join_style="mitre"))
    # Avoid silently merging nearby independent parallel bands when a target is
    # too small or the requested band is wider than the available detail spacing.
    segments = {"horizontal": [], "vertical": []}
    for points in paths:
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if abs(y1 - y2) < 1e-7:
                segments["horizontal"].append((y1, min(x1, x2), max(x1, x2)))
            else:
                segments["vertical"].append((x1, min(y1, y2), max(y1, y2)))
    for group in segments.values():
        group.sort()
        for index, (normal, start, end) in enumerate(group):
            for other_normal, other_start, other_end in group[index + 1:]:
                distance = other_normal - normal
                if distance >= placement.band_width - 1e-6:
                    break
                if distance > 1e-6 and min(end, other_end) - max(start, other_start) > placement.band_width:
                    raise ValueError("线宽超过局部线距，请减小线宽或增大固定造型区")
    geometry = unary_union(strokes)
    if geometry.is_empty or not geometry.is_valid or not box(0, 0, width, height).buffer(1e-6).covers(geometry):
        raise ValueError("生成的图案无效或超出区域，请调整边距/造型尺寸")
    polygons = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
    loops = []
    for polygon in polygons:
        for ring in (polygon.exterior, *polygon.interiors):
            loops.append([[round(x, 6), round(y, 6)] for x, y in list(ring.coords)[:-1]])
    if sum(len(loop) for loop in loops) > 10000:
        raise ValueError("生成轮廓过于复杂")
    return {"loops": loops, "centerlines": paths, "bounds": list(geometry.bounds),
            "band_width": placement.band_width, "width": width, "height": height}
