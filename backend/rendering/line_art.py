"""Extract independent front/back door line art from an uploaded order sheet."""

from __future__ import annotations

import io
import os
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps

from .database import render_db
from .storage import public_file_url, save_bytes


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    width: int
    height: int

    def as_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


def extract_uploaded_line_art(data: bytes, filename: str) -> dict:
    source_png = _normalize_png(data)
    source = save_bytes(source_png, f"source-{filename or 'order-sheet'}.png", "temp")
    image = _decode(source_png)
    height, width = image.shape[:2]
    boxes, review_required, warnings = _detect_door_boxes(image)
    front = _render_view(image, boxes[0], "front")
    back = _render_view(image, boxes[1], "back")
    return render_db.create_line_art_extraction({
        "sourcePath": source["filePath"],
        "sourceUrl": source["url"],
        "originalSourcePath": source["filePath"],
        "originalSourceUrl": source["url"],
        "sourceWidth": width,
        "sourceHeight": height,
        "front": {**front, "crop": boxes[0].as_dict()},
        "back": {**back, "crop": boxes[1].as_dict()},
        "reviewRequired": review_required,
        "warnings": warnings,
    })


def recrop_uploaded_line_art(extraction_id: str, front: dict, back: dict, rotation: int = 0) -> dict:
    item = render_db.get_line_art_extraction(extraction_id)
    if not item:
        raise KeyError(extraction_id)
    with Image.open(item["sourcePath"]) as source_image:
        normalized_rotation = int(rotation or 0) % 360
        if normalized_rotation not in {0, 90, 180, 270}:
            normalized_rotation = 0
        rotated = source_image.rotate(-normalized_rotation, expand=True, fillcolor="white")
        output = io.BytesIO()
        rotated.save(output, "PNG", optimize=False)
    working_source = save_bytes(output.getvalue(), "rotated-order-sheet.png", "temp")
    image = _decode(output.getvalue())
    front_box = _clamp_box(Box(**front), image.shape[1], image.shape[0])
    back_box = _clamp_box(Box(**back), image.shape[1], image.shape[0])
    patch = {
        "sourcePath": working_source["filePath"],
        "sourceUrl": working_source["url"],
        "rotation": 0,
        "sourceWidth": image.shape[1],
        "sourceHeight": image.shape[0],
        "front": {**_render_view(image, front_box, "front"), "crop": front_box.as_dict()},
        "back": {**_render_view(image, back_box, "back"), "crop": back_box.as_dict()},
        "reviewRequired": False,
        "warnings": [],
    }
    return render_db.update_line_art_extraction(extraction_id, patch) or item


def _normalize_png(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode not in {"RGB", "RGBA", "L"}:
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, "PNG", optimize=False)
        return output.getvalue()


def _decode(data: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("无法读取上传图片")
    return image


def _detect_door_boxes(image: np.ndarray) -> tuple[list[Box], bool, list[str]]:
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 45, 140)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    connected = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _hierarchy = cv2.findContours(connected, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[Box] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        area_ratio = (box_width * box_height) / max(width * height, 1)
        aspect = box_height / max(box_width, 1)
        if not (0.025 <= area_ratio <= 0.42 and 0.75 <= aspect <= 4.8):
            continue
        if box_width < width * 0.10 or box_height < height * 0.22:
            continue
        candidates.append(_expand_box(Box(x, y, box_width, box_height), width, height, 0.015))

    candidates = _deduplicate(candidates)
    best_pair = None
    best_score = float("-inf")
    for index, left in enumerate(candidates):
        for right in candidates[index + 1:]:
            first, second = sorted((left, right), key=lambda box: box.x)
            center_distance = abs((first.x + first.width / 2) - (second.x + second.width / 2))
            if center_distance < width * 0.16:
                continue
            y_similarity = 1 - min(1, abs(first.y - second.y) / max(first.height, second.height, 1))
            h_similarity = min(first.height, second.height) / max(first.height, second.height, 1)
            area_score = (first.width * first.height + second.width * second.height) / max(width * height, 1)
            score = y_similarity * 2 + h_similarity * 2 + area_score
            if score > best_score:
                best_score = score
                best_pair = [first, second]
    if best_pair:
        return best_pair, False, []

    margin_x = max(1, int(width * 0.04))
    top = max(0, int(height * 0.20))
    fallback_width = max(1, int((width - margin_x * 3) / 2))
    fallback_height = max(1, int(height * 0.72))
    return [
        _clamp_box(Box(margin_x, top, fallback_width, fallback_height), width, height),
        _clamp_box(Box(margin_x * 2 + fallback_width, top, fallback_width, fallback_height), width, height),
    ], True, ["未能可靠识别正反面门体，请检查并调整两个裁剪框。"]


def _render_view(image: np.ndarray, box: Box, side: str) -> dict:
    crop = image[box.y:box.y + box.height, box.x:box.x + box.width]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    line_art = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
    encoded, output = cv2.imencode(".png", line_art, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    if not encoded:
        raise ValueError("线稿图片编码失败")
    saved = save_bytes(output.tobytes(), f"{side}-line-art.png", "temp")
    return {"url": saved["url"], "filePath": saved["filePath"]}


def _expand_box(box: Box, width: int, height: int, ratio: float) -> Box:
    pad_x = int(box.width * ratio)
    pad_y = int(box.height * ratio)
    return _clamp_box(Box(box.x - pad_x, box.y - pad_y, box.width + pad_x * 2, box.height + pad_y * 2), width, height)


def _clamp_box(box: Box, width: int, height: int) -> Box:
    x = max(0, min(int(box.x), max(width - 1, 0)))
    y = max(0, min(int(box.y), max(height - 1, 0)))
    box_width = max(1, min(int(box.width), width - x))
    box_height = max(1, min(int(box.height), height - y))
    return Box(x, y, box_width, box_height)


def _deduplicate(boxes: list[Box]) -> list[Box]:
    result: list[Box] = []
    for box in sorted(boxes, key=lambda item: item.width * item.height, reverse=True):
        if any(_intersection_ratio(box, existing) > 0.82 for existing in result):
            continue
        result.append(box)
    return result[:30]


def _intersection_ratio(first: Box, second: Box) -> float:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    intersection = max(0, right - left) * max(0, bottom - top)
    return intersection / max(min(first.width * first.height, second.width * second.height), 1)
