"""Render a printable JPEG directly from the generated DXF order sheet."""

from __future__ import annotations

import io
import os
from typing import Iterable, Optional

import cv2
import ezdxf
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from cad_preview import LAYER_COLORS, Primitive, _bbox, _collect_entity


ORDER_FORM_NAMES = {"ORDERFORM", "ORDER_FORM"}
MAX_CANVAS_EDGE = 10000
FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def render_dxf_sheet_jpg(dxf_text: str, minimum_long_edge: int = 4200) -> dict:
    """Return a white-background JPEG cropped to the ORDER_FORM outer frame."""
    doc = ezdxf.read(io.StringIO(dxf_text))
    primitives = _modelspace_primitives(doc)
    if not primitives:
        raise ValueError("DXF 中没有可导出的图纸内容")

    order_bbox = _order_form_bbox(doc)
    used_order_form = order_bbox is not None
    crop_bbox = order_bbox or _primitive_bbox(primitives)
    if crop_bbox is None:
        raise ValueError("DXF 中没有可识别的图框边界")

    selected = [primitive for primitive in primitives if _intersects(primitive, crop_bbox)]
    content, width, height = _render(selected, crop_bbox, minimum_long_edge)
    return {
        "content": content,
        "width": width,
        "height": height,
        "usedOrderForm": used_order_form,
        "cadBBox": [float(value) for value in crop_bbox],
    }


def _modelspace_primitives(doc) -> list[Primitive]:
    primitives: list[Primitive] = []
    for entity in doc.modelspace().entities_in_redraw_order():
        _collect_entity(entity, primitives)
    return primitives


def _order_form_bbox(doc) -> Optional[tuple[float, float, float, float]]:
    candidates: list[tuple[float, float, float, float]] = []
    for entity in doc.modelspace().query("INSERT"):
        name = str(getattr(entity.dxf, "name", "") or "").upper().replace(" ", "")
        if name not in ORDER_FORM_NAMES:
            continue
        primitives: list[Primitive] = []
        _collect_entity(entity, primitives)
        geometry = [item for item in primitives if item.kind != "text" and item.points]
        bbox = _primitive_bbox(geometry)
        if bbox:
            candidates.append(bbox)
    if not candidates:
        return None
    return max(candidates, key=_bbox_area)


def _primitive_bbox(primitives: Iterable[Primitive]) -> Optional[tuple[float, float, float, float]]:
    points = [point for primitive in primitives for point in primitive.points]
    return _bbox(points) if points else None


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    min_x, max_x, min_y, max_y = bbox
    return max(max_x - min_x, 0) * max(max_y - min_y, 0)


def _intersects(primitive: Primitive, bbox: tuple[float, float, float, float]) -> bool:
    if not primitive.points:
        return False
    min_x, max_x, min_y, max_y = _bbox(primitive.points)
    left, right, bottom, top = bbox
    return max_x >= left and min_x <= right and max_y >= bottom and min_y <= top


def _render(
    primitives: list[Primitive],
    bbox: tuple[float, float, float, float],
    minimum_long_edge: int,
) -> tuple[bytes, int, int]:
    min_x, max_x, min_y, max_y = bbox
    content_width = max(max_x - min_x, 1.0)
    content_height = max(max_y - min_y, 1.0)
    margin_units = max(content_width, content_height) * 0.006
    total_width = content_width + margin_units * 2
    total_height = content_height + margin_units * 2
    scale = max(0.01, minimum_long_edge / max(total_width, total_height))
    scale = min(scale, MAX_CANVAS_EDGE / max(total_width, total_height))
    width = max(64, int(round(total_width * scale)))
    height = max(64, int(round(total_height * scale)))
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)

    def point(value: tuple[float, float]) -> tuple[int, int]:
        return (
            int(round((value[0] - min_x + margin_units) * scale)),
            int(round((max_y - value[1] + margin_units) * scale)),
        )

    for primitive in primitives:
        if primitive.kind == "text" or not primitive.points:
            continue
        mapped = np.array([point(value) for value in primitive.points], dtype=np.int32)
        color = _layer_color(primitive.layer)
        line_width = _line_width(primitive.layer, scale)
        if primitive.kind == "wipeout" and len(mapped) >= 3:
            cv2.fillPoly(canvas, [mapped], (255, 255, 255), lineType=cv2.LINE_AA)
        elif primitive.kind == "line" and len(mapped) == 2:
            cv2.line(canvas, tuple(mapped[0]), tuple(mapped[1]), color, line_width, cv2.LINE_AA)
        elif primitive.kind in {"polyline", "arc"} and len(mapped) >= 2:
            cv2.polylines(
                canvas,
                [mapped],
                bool(primitive.data.get("closed", False)),
                color,
                line_width,
                cv2.LINE_AA,
            )
        elif primitive.kind == "circle" and len(mapped) == 2:
            center = point(primitive.data["center"])
            radius = max(1, int(round(float(primitive.data["radius"]) * scale)))
            cv2.circle(canvas, center, radius, color, line_width, cv2.LINE_AA)

    image = Image.fromarray(canvas, "RGB")
    draw = ImageDraw.Draw(image)
    for primitive in primitives:
        if primitive.kind != "text" or not primitive.points:
            continue
        text = str(primitive.data.get("text", "") or "").strip()
        if not text:
            continue
        x, y = point(primitive.points[0])
        size = max(8, min(96, int(round(float(primitive.data.get("height", 24) or 24) * scale))))
        font = _font(size)
        color = _layer_color(primitive.layer)
        rotation = float(primitive.data.get("rotation", 0) or 0) % 360
        if abs(rotation) < 0.5:
            draw.text((x, y), text, fill=color, font=font, anchor="lm")
        else:
            _draw_rotated_text(image, (x, y), text, font, color, rotation)

    output = io.BytesIO()
    image.save(output, "JPEG", quality=96, subsampling=0, optimize=True)
    return output.getvalue(), width, height


def _layer_color(layer: str) -> tuple[int, int, int]:
    value = LAYER_COLORS.get(layer, "#334155").lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _line_width(layer: str, scale: float) -> int:
    factor = 1.15 if layer == "A-DOOR-FRAME" else 0.8 if layer == "YQ_DIM" else 1.0
    return max(1, min(5, int(round(scale * factor))))


def _font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_rotated_text(
    image: Image.Image,
    origin: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    color: tuple[int, int, int],
    rotation: float,
) -> None:
    bounds = font.getbbox(text)
    text_width = max(1, bounds[2] - bounds[0] + 8)
    text_height = max(1, bounds[3] - bounds[1] + 8)
    layer = Image.new("RGBA", (text_width, text_height), (255, 255, 255, 0))
    ImageDraw.Draw(layer).text((4, 4), text, fill=(*color, 255), font=font, anchor="la")
    rotated = layer.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
    image.paste(rotated, origin, rotated)
