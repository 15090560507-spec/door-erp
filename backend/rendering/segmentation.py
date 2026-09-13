from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image

from .database import render_db
from .storage import save_bytes


ROLES = ("panel", "trim", "frame", "glass", "hardware")
COLORS = {
    "panel": (255, 149, 0),
    "trim": (52, 199, 89),
    "frame": (0, 122, 255),
    "glass": (90, 200, 250),
    "hardware": (175, 82, 222),
}


def create_image_segmentation(data: bytes, filename: str) -> dict:
    image = _decode_image(data)
    height, width = image.shape[:2]
    masks, confidence, warnings = _infer_masks(image)
    source = save_bytes(data, filename or "line-art.png", "segments")
    stored_masks = {role: _store_mask(mask, f"{role}-mask.png") for role, mask in masks.items()}
    overlay = save_bytes(_overlay_png(image, masks), "segmentation-overlay.png", "segments")
    return render_db.create_segmentation({
        "source": {**source, "width": width, "height": height},
        "masks": stored_masks,
        "overlay": overlay,
        "confidence": confidence,
        "confirmed": False,
        "warnings": warnings,
    })


def confirm_image_segmentation(segmentation_id: str, uploads: dict[str, bytes]) -> dict:
    record = render_db.get_segmentation(segmentation_id)
    if not record:
        raise KeyError(segmentation_id)
    source_path = record.get("source", {}).get("filePath", "")
    source = cv2.imread(source_path, cv2.IMREAD_COLOR)
    if source is None:
        raise ValueError("区域识别原图不存在")
    height, width = source.shape[:2]
    masks: dict[str, np.ndarray] = {}
    stored: dict[str, dict] = {}
    for role in ROLES:
        raw = uploads.get(role)
        if raw:
            mask = _decode_mask(raw, width, height)
            stored[role] = _store_mask(mask, f"{segmentation_id}-{role}-confirmed.png")
        else:
            info = record.get("masks", {}).get(role, {})
            mask = cv2.imread(info.get("filePath", ""), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                mask = np.zeros((height, width), dtype=np.uint8)
            stored[role] = info
        masks[role] = mask
    overlay = save_bytes(_overlay_png(source, masks), f"{segmentation_id}-confirmed-overlay.png", "segments")
    updated = render_db.update_segmentation(segmentation_id, {
        "masks": stored,
        "overlay": overlay,
        "confirmed": True,
    })
    return updated or record


def _decode_image(data: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("无法识别图片内容")
    return image


def _decode_mask(data: bytes, width: int, height: int) -> np.ndarray:
    mask = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise ValueError("无法识别区域蒙版")
    if mask.shape[:2] != (height, width):
        mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)
    return np.where(mask >= 128, 255, 0).astype(np.uint8)


def _infer_masks(image: np.ndarray) -> tuple[dict[str, np.ndarray], float, list[str]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    foreground = np.where(gray < 235, 255, 0).astype(np.uint8)
    points = cv2.findNonZero(foreground)
    if points is None:
        raise ValueError("图片中没有识别到有效线稿")
    x, y, width, height = cv2.boundingRect(points)
    pad = max(1, int(min(width, height) * 0.01))
    x, y = max(0, x - pad), max(0, y - pad)
    width = min(image.shape[1] - x, width + pad * 2)
    height = min(image.shape[0] - y, height + pad * 2)

    edges = cv2.Canny(gray, 45, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=2)
    contours, _hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[int, int, int, int]] = []
    outer_area = max(1, width * height)
    for contour in contours:
        rx, ry, rw, rh = cv2.boundingRect(contour)
        area = rw * rh
        if area < outer_area * 0.18 or rw < width * 0.35 or rh < height * 0.35:
            continue
        if rx < x - pad or ry < y - pad or rx + rw > x + width + pad or ry + rh > y + height + pad:
            continue
        candidates.append((rx, ry, rw, rh))
    candidates.sort(key=lambda rect: rect[2] * rect[3], reverse=True)
    unique: list[tuple[int, int, int, int]] = []
    for rect in candidates:
        if all(_rect_distance(rect, existing) > max(4, min(width, height) * 0.012) for existing in unique):
            unique.append(rect)
        if len(unique) == 3:
            break

    outer = unique[0] if unique else (x, y, width, height)
    if len(unique) >= 3:
        trim_inner, frame_inner = unique[1], unique[2]
        confidence = 0.86
        warnings: list[str] = []
    elif len(unique) == 2:
        trim_inner = unique[1]
        frame_inner = _inset_rect(trim_inner, 0.045)
        confidence = 0.68
        warnings = ["仅识别到两层主要边界，请重点检查门框与门扇分界。"]
    else:
        trim_inner = _inset_rect(outer, 0.04)
        frame_inner = _inset_rect(outer, 0.09)
        confidence = 0.48
        warnings = ["主要边界为推测结果，请确认门套、门框和门扇区域。"]

    shape = gray.shape
    outer_mask = _rect_mask(shape, outer)
    trim_inner_mask = _rect_mask(shape, trim_inner)
    frame_inner_mask = _rect_mask(shape, frame_inner)
    trim_mask = cv2.subtract(outer_mask, trim_inner_mask)
    frame_mask = cv2.subtract(trim_inner_mask, frame_inner_mask)
    panel_mask = frame_inner_mask
    blank = np.zeros(shape, dtype=np.uint8)
    return {
        "panel": panel_mask,
        "trim": trim_mask,
        "frame": frame_mask,
        "glass": blank.copy(),
        "hardware": blank.copy(),
    }, confidence, warnings


def _rect_distance(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> float:
    return sum(abs(left[index] - right[index]) for index in range(4)) / 4


def _inset_rect(rect: tuple[int, int, int, int], ratio: float) -> tuple[int, int, int, int]:
    x, y, width, height = rect
    inset = max(2, int(min(width, height) * ratio))
    return x + inset, y + inset, max(1, width - inset * 2), max(1, height - inset * 2)


def _rect_mask(shape: tuple[int, int], rect: tuple[int, int, int, int]) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    x, y, width, height = rect
    cv2.rectangle(mask, (x, y), (x + width - 1, y + height - 1), 255, -1)
    return mask


def _store_mask(mask: np.ndarray, filename: str) -> dict:
    ok, encoded = cv2.imencode(".png", mask)
    if not ok:
        raise ValueError("区域蒙版编码失败")
    return save_bytes(encoded.tobytes(), filename, "segments")


def _overlay_png(image: np.ndarray, masks: dict[str, np.ndarray]) -> bytes:
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32)
    for role, mask in masks.items():
        active = mask > 0
        if not np.any(active):
            continue
        color = np.array(COLORS[role], dtype=np.float32)
        rgb[active] = rgb[active] * 0.62 + color * 0.38
    buffer = io.BytesIO()
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").save(buffer, "PNG")
    return buffer.getvalue()
