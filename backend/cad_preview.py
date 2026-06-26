import html
import io
import math
from dataclasses import dataclass
from typing import Any

import ezdxf


@dataclass
class Primitive:
    kind: str
    layer: str
    points: list[tuple[float, float]]
    data: dict[str, Any]


LAYER_COLORS = {
    "A-DOOR-FRAME": "#0284c7",
    "A-DOOR-PANEL": "#f59e0b",
    "A-DOOR-TRIM": "#16a34a",
    "A-DOOR-mark": "#dc2626",
    "YQ_DIM": "#65a30d",
    "0": "#475569",
}


def _layer(entity: Any) -> str:
    return str(getattr(entity.dxf, "layer", "0") or "0")


def _color(layer: str) -> str:
    return LAYER_COLORS.get(layer, "#475569")


def _bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    return (
        min(point[0] for point in points),
        max(point[0] for point in points),
        min(point[1] for point in points),
        max(point[1] for point in points),
    )


def _filter_to_door_views(primitives: list[Primitive]) -> list[Primitive]:
    title_points = [
        primitive.points[0]
        for primitive in primitives
        if primitive.kind == "text" and str(primitive.data.get("text", "")).strip() in {"正面", "背面"}
    ]
    if len(title_points) < 2:
        return primitives

    title_points = sorted(title_points, key=lambda point: point[0])[:2]
    title_gap = max(abs(title_points[1][0] - title_points[0][0]), 1)
    half_width = max(1400.0, title_gap * 0.55)
    min_allowed_y = min(point[1] for point in title_points) - 7000
    max_allowed_y = max(point[1] for point in title_points) + 650

    def in_view(primitive: Primitive) -> bool:
        if not primitive.points:
            return False
        min_x, max_x, min_y, max_y = _bbox(primitive.points)
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        if max_x - min_x > half_width * 2.1:
            return False
        if max_y - min_y > 8500:
            return False
        if center_y < min_allowed_y or center_y > max_allowed_y:
            return False
        return any(abs(center_x - title_x) <= half_width for title_x, _title_y in title_points)

    filtered = [primitive for primitive in primitives if in_view(primitive)]
    return filtered or primitives


def _point(value: Any) -> tuple[float, float]:
    return float(value.x), float(value.y)


def _arc_point(center: tuple[float, float], radius: float, angle: float) -> tuple[float, float]:
    radians = math.radians(angle)
    return center[0] + radius * math.cos(radians), center[1] + radius * math.sin(radians)


def _arc_sample_points(
    center: tuple[float, float],
    radius: float,
    start_angle: float,
    end_angle: float,
) -> list[tuple[float, float]]:
    delta = (end_angle - start_angle) % 360
    if delta == 0:
        delta = 360
    steps = max(8, min(72, int(delta / 8)))
    return [_arc_point(center, radius, start_angle + delta * i / steps) for i in range(steps + 1)]


def _collect_entity(entity: Any, primitives: list[Primitive], depth: int = 0) -> None:
    if depth > 3:
        return

    kind = entity.dxftype()
    layer = _layer(entity)

    if kind in {"INSERT", "DIMENSION"}:
        try:
            for virtual_entity in entity.virtual_entities():
                _collect_entity(virtual_entity, primitives, depth + 1)
            return
        except Exception:
            if kind == "INSERT":
                insert = _point(entity.dxf.insert)
                name = str(getattr(entity.dxf, "name", "BLOCK"))
                primitives.append(Primitive("insert", layer, [insert], {"text": name}))
            return

    if kind == "LINE":
        primitives.append(Primitive("line", layer, [_point(entity.dxf.start), _point(entity.dxf.end)], {}))
    elif kind == "LWPOLYLINE":
        points = [(float(p[0]), float(p[1])) for p in entity.get_points("xy")]
        if len(points) >= 2:
            primitives.append(Primitive("polyline", layer, points, {"closed": bool(entity.closed)}))
    elif kind == "POLYLINE":
        try:
            points = [_point(vertex.dxf.location) for vertex in entity.vertices]
        except Exception:
            points = []
        if len(points) >= 2:
            primitives.append(Primitive("polyline", layer, points, {"closed": bool(entity.is_closed)}))
    elif kind == "ARC":
        center = _point(entity.dxf.center)
        radius = float(entity.dxf.radius)
        start_angle = float(entity.dxf.start_angle)
        end_angle = float(entity.dxf.end_angle)
        primitives.append(
            Primitive(
                "arc",
                layer,
                _arc_sample_points(center, radius, start_angle, end_angle),
                {
                    "center": center,
                    "radius": radius,
                    "start_angle": start_angle,
                    "end_angle": end_angle,
                },
            )
        )
    elif kind == "CIRCLE":
        center = _point(entity.dxf.center)
        radius = float(entity.dxf.radius)
        primitives.append(
            Primitive(
                "circle",
                layer,
                [(center[0] - radius, center[1] - radius), (center[0] + radius, center[1] + radius)],
                {"center": center, "radius": radius},
            )
        )
    elif kind == "WIPEOUT":
        try:
            points = [(float(point.x), float(point.y)) for point in entity.boundary_path_wcs()]
        except Exception:
            points = []
        if len(points) >= 3:
            primitives.append(Primitive("wipeout", layer, points, {}))
    elif kind == "TEXT":
        text = str(entity.dxf.text or "")
        insert = _point(entity.dxf.insert)
        height = float(getattr(entity.dxf, "height", 24) or 24)
        rotation = float(getattr(entity.dxf, "rotation", 0) or 0)
        primitives.append(
            Primitive("text", layer, [insert], {"text": text, "height": height, "rotation": rotation})
        )
    elif kind == "MTEXT":
        text = entity.plain_text()
        insert = _point(entity.dxf.insert)
        height = float(getattr(entity.dxf, "char_height", 24) or 24)
        rotation = float(getattr(entity.dxf, "rotation", 0) or 0)
        primitives.append(
            Primitive("text", layer, [insert], {"text": text, "height": height, "rotation": rotation})
        )


def render_dxf_svg(dxf_text: str) -> str:
    doc = ezdxf.read(io.StringIO(dxf_text))
    primitives: list[Primitive] = []
    ms = doc.modelspace()
    try:
        entities = list(ms.entities_in_redraw_order())
    except Exception:
        entities = list(ms)
    for entity in entities:
        _collect_entity(entity, primitives)
    primitives = _filter_to_door_views(primitives)

    all_points = [point for primitive in primitives for point in primitive.points]
    if not all_points:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600"><text x="24" y="40">No preview geometry</text></svg>'

    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_y = min(point[1] for point in all_points)
    max_y = max(point[1] for point in all_points)
    width = max(max_x - min_x, 1)
    height = max(max_y - min_y, 1)
    pad = max(width, height) * 0.05
    view_width = width + pad * 2
    view_height = height + pad * 2

    def sx(x: float) -> float:
        return x - min_x + pad

    def sy(y: float) -> float:
        return max_y - y + pad

    def fmt(value: float) -> str:
        return f"{value:.3f}".rstrip("0").rstrip(".")

    parts: list[str] = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(view_width)} {fmt(view_height)}" '
            'role="img" aria-label="CAD preview">'
        ),
        "<style>",
        ".cad-bg{fill:#f8fafc}.cad-line{fill:none;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}.cad-text{font-family:'Microsoft YaHei',SimSun,sans-serif;fill:#0f172a;dominant-baseline:middle;font-weight:600}.cad-note{fill:#64748b;font-size:32px}",
        "</style>",
        f'<rect class="cad-bg" x="0" y="0" width="{fmt(view_width)}" height="{fmt(view_height)}"/>',
    ]

    for primitive in primitives:
        color = _color(primitive.layer)
        stroke_width = "1.6"
        if primitive.layer == "YQ_DIM":
            stroke_width = "1.2"
        elif primitive.layer == "A-DOOR-FRAME":
            stroke_width = "2"

        if primitive.kind == "line":
            (x1, y1), (x2, y2) = primitive.points
            parts.append(
                f'<line class="cad-line" x1="{fmt(sx(x1))}" y1="{fmt(sy(y1))}" x2="{fmt(sx(x2))}" y2="{fmt(sy(y2))}" stroke="{color}" stroke-width="{stroke_width}"/>'
            )
        elif primitive.kind == "polyline":
            points = " ".join(f"{fmt(sx(x))},{fmt(sy(y))}" for x, y in primitive.points)
            close = " Z" if primitive.data.get("closed") else ""
            parts.append(
                f'<path class="cad-line" d="M {points}{close}" stroke="{color}" stroke-width="{stroke_width}"/>'
            )
        elif primitive.kind == "arc":
            center = primitive.data["center"]
            radius = float(primitive.data["radius"])
            start_angle = float(primitive.data["start_angle"])
            end_angle = float(primitive.data["end_angle"])
            delta = (end_angle - start_angle) % 360
            if delta == 0:
                delta = 360
            start = _arc_point(center, radius, start_angle)
            end = _arc_point(center, radius, end_angle)
            large_arc = 1 if delta > 180 else 0
            parts.append(
                f'<path class="cad-line" d="M {fmt(sx(start[0]))} {fmt(sy(start[1]))} A {fmt(radius)} {fmt(radius)} 0 {large_arc} 0 {fmt(sx(end[0]))} {fmt(sy(end[1]))}" stroke="{color}" stroke-width="{stroke_width}"/>'
            )
        elif primitive.kind == "circle":
            center = primitive.data["center"]
            radius = float(primitive.data["radius"])
            parts.append(
                f'<circle class="cad-line" cx="{fmt(sx(center[0]))}" cy="{fmt(sy(center[1]))}" r="{fmt(radius)}" stroke="{color}" stroke-width="{stroke_width}"/>'
            )
        elif primitive.kind == "wipeout":
            points = " ".join(f"{fmt(sx(x))},{fmt(sy(y))}" for x, y in primitive.points)
            parts.append(f'<polygon points="{points}" fill="#f8fafc" stroke="none"/>')
        elif primitive.kind in {"text", "insert"}:
            x, y = primitive.points[0]
            raw_text = primitive.data.get("text", "")
            text = html.escape(str(raw_text).replace("\n", " ")[:80])
            if not text:
                continue
            font_size = max(16, min(76, float(primitive.data.get("height", 24)) * 1.15))
            rotation = float(primitive.data.get("rotation", 0) or 0)
            transform = ""
            if rotation:
                transform = f' transform="rotate({fmt(-rotation)} {fmt(sx(x))} {fmt(sy(y))})"'
            parts.append(
                f'<text class="cad-text" x="{fmt(sx(x))}" y="{fmt(sy(y))}" font-size="{fmt(font_size)}"{transform}>{text}</text>'
            )

    parts.append(
        f'<text class="cad-note" x="{fmt(pad)}" y="{fmt(view_height - pad * 0.25)}">Preview is generated from DXF geometry.</text>'
    )
    parts.append("</svg>")
    return "".join(parts)
