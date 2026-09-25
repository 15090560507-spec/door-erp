"""Render clean, independent front/back line art from generated DXF text."""

from __future__ import annotations

import io

import cv2
import ezdxf
import numpy as np

from cad_preview import Primitive, _bbox, _collect_entity
from .storage import save_bytes


IGNORED_LAYERS = {"YQ_DIM", "A-DOOR-mark", "ORDER_FORM"}
STRUCTURAL_LAYERS = {"A-DOOR-PANEL", "A-DOOR-FRAME", "A-DOOR-TRIM", "A-DOOR-GLASS"}


def export_dxf_line_art(dxf_text: str, minimum_long_edge: int = 2400) -> dict:
    doc = ezdxf.read(io.StringIO(dxf_text))
    primitives: list[Primitive] = []
    for entity in doc.modelspace().entities_in_redraw_order():
        _collect_entity(entity, primitives)
    titles = {
        str(primitive.data.get("text", "")).strip(): primitive.points[0]
        for primitive in primitives
        if primitive.kind == "text" and str(primitive.data.get("text", "")).strip() in {"正面", "背面"}
    }
    if "正面" not in titles or "背面" not in titles:
        raise ValueError("CAD中未找到正面和背面视图标题")
    title_gap = abs(titles["背面"][0] - titles["正面"][0])
    half_width = max(1200.0, title_gap * 0.48)
    result = {}
    for label, key in (("正面", "front"), ("背面", "back")):
        title_x, title_y = titles[label]
        view_primitives = [
            primitive for primitive in primitives
            if _is_view_geometry(primitive, title_x, title_y, half_width)
        ]
        structural = [primitive for primitive in view_primitives if primitive.layer in STRUCTURAL_LAYERS]
        structural_points = [point for primitive in structural for point in primitive.points]
        if not structural_points:
            raise ValueError(f"{label}视图没有可识别的门体结构边界")
        structural_bbox = _bbox(structural_points)
        canvas_bbox = _expanded_bbox(structural_bbox)
        selected = [primitive for primitive in view_primitives if _inside_bbox(primitive, canvas_bbox)]
        png, metadata = _render_primitives(selected, minimum_long_edge, canvas_bbox)
        saved = save_bytes(png, f"{key}-cad-line-art.png", "temp")
        result[key] = {
            "url": saved["url"],
            "filePath": saved["filePath"],
            "geometry": metadata,
        }
    return result


def _is_view_geometry(primitive: Primitive, title_x: float, title_y: float, half_width: float) -> bool:
    if primitive.kind in {"text", "insert"} or primitive.layer in IGNORED_LAYERS or not primitive.points:
        return False
    min_x, max_x, min_y, max_y = _bbox(primitive.points)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    if abs(center_x - title_x) > half_width:
        return False
    if center_y < title_y - 6000 or center_y > title_y + 250:
        return False
    if max_x - min_x > half_width * 1.95 or max_y - min_y > 7000:
        return False
    return True


def _expanded_bbox(
    bbox: tuple[float, float, float, float],
    ratio: float = 0.025,
) -> tuple[float, float, float, float]:
    min_x, max_x, min_y, max_y = bbox
    margin = max(max_x - min_x, max_y - min_y, 1.0) * ratio
    return min_x - margin, max_x + margin, min_y - margin, max_y + margin


def _inside_bbox(primitive: Primitive, bbox: tuple[float, float, float, float]) -> bool:
    if primitive.kind == "text" or not primitive.points:
        return False
    min_x, max_x, min_y, max_y = _bbox(primitive.points)
    left, right, bottom, top = bbox
    return min_x >= left and max_x <= right and min_y >= bottom and max_y <= top


def _render_primitives(
    primitives: list[Primitive],
    minimum_long_edge: int,
    bbox: tuple[float, float, float, float],
) -> tuple[bytes, dict]:
    if not primitives:
        raise ValueError("视图中没有可导出的门体线条")
    min_x, max_x, min_y, max_y = bbox
    width = max(max_x - min_x, 1)
    height = max(max_y - min_y, 1)
    scale = max(1.0, minimum_long_edge / max(width, height))
    canvas_width = max(64, int(round(width * scale)))
    canvas_height = max(64, int(round(height * scale)))
    canvas = np.full((canvas_height, canvas_width, 3), 255, dtype=np.uint8)

    def point(value: tuple[float, float]) -> tuple[int, int]:
        return (
            int(round((value[0] - min_x) * scale)),
            int(round((max_y - value[1]) * scale)),
        )

    line_width = max(1, min(3, int(round(scale * 0.9))))
    for primitive in primitives:
        mapped = np.array([point(value) for value in primitive.points], dtype=np.int32)
        if primitive.kind == "wipeout" and len(mapped) >= 3:
            cv2.fillPoly(canvas, [mapped], (255, 255, 255), lineType=cv2.LINE_AA)
        elif primitive.kind == "line" and len(mapped) == 2:
            cv2.line(canvas, tuple(mapped[0]), tuple(mapped[1]), (20, 20, 20), line_width, cv2.LINE_AA)
        elif primitive.kind in {"polyline", "arc"} and len(mapped) >= 2:
            cv2.polylines(
                canvas,
                [mapped],
                bool(primitive.data.get("closed", False)),
                (20, 20, 20),
                line_width,
                cv2.LINE_AA,
            )
        elif primitive.kind == "circle" and len(mapped) == 2:
            center = point(primitive.data["center"])
            radius = max(1, int(round(float(primitive.data["radius"]) * scale)))
            cv2.circle(canvas, center, radius, (20, 20, 20), line_width, cv2.LINE_AA)
    encoded, output = cv2.imencode(".png", canvas, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    if not encoded:
        raise ValueError("CAD线稿图片编码失败")
    metadata = {
        "cadWidth": float(width),
        "cadHeight": float(height),
        "aspectRatio": float(width / height),
        "pixelWidth": canvas_width,
        "pixelHeight": canvas_height,
        "cadBBox": [float(value) for value in bbox],
    }
    return output.tobytes(), metadata
