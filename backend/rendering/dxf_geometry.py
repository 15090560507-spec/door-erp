"""DXF component geometry manifest built from one shared CAD-to-pixel transform."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable, Mapping, Optional, Protocol

import cv2
import numpy as np


class GeometryPrimitive(Protocol):
    layer: str
    points: list[tuple[float, float]]
    kind: str
    data: dict


CadBBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class GeometryTransform:
    min_x: float
    max_y: float
    scale: float
    width: int
    height: int
    transform_id: str

    def point(self, x: float, y: float) -> tuple[int, int]:
        return (
            int(round((x - self.min_x) * self.scale)),
            int(round((self.max_y - y) * self.scale)),
        )

    def pixel_bbox(self, bbox: CadBBox) -> list[int]:
        min_x, max_x, min_y, max_y = bbox
        left, top = self.point(min_x, max_y)
        right, bottom = self.point(max_x, min_y)
        return [
            max(0, min(self.width, left)),
            max(0, min(self.height, top)),
            max(0, min(self.width, right)),
            max(0, min(self.height, bottom)),
        ]


def make_geometry_transform(*, min_x: float, max_y: float, scale: float, width: int, height: int) -> GeometryTransform:
    fingerprint = f"{min_x:.6f}|{max_y:.6f}|{scale:.9f}|{width}|{height}"
    transform_id = "cad-" + hashlib.sha256(fingerprint.encode("ascii")).hexdigest()[:16]
    return GeometryTransform(min_x, max_y, scale, width, height, transform_id)


def primitive_bbox(primitives: Iterable[GeometryPrimitive]) -> Optional[CadBBox]:
    points = [point for primitive in primitives for point in primitive.points]
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), max(xs), min(ys), max(ys)


def _bbox_payload(bbox: Optional[CadBBox], transform: GeometryTransform) -> Optional[dict]:
    if bbox is None:
        return None
    return {
        "cad_bbox": [float(value) for value in bbox],
        "pixel_bbox": transform.pixel_bbox(bbox),
    }


def build_geometry_manifest(
    categorized: dict[str, list[GeometryPrimitive]],
    front: dict[str, list[GeometryPrimitive]],
    back: dict[str, list[GeometryPrimitive]],
    transform: GeometryTransform,
) -> dict:
    role_categories = {
        "panel": "panel",
        "frame": "frame",
        "trim": "trim",
        "hardware": "accessory",
    }
    roles = {}
    for role, category in role_categories.items():
        primitives = categorized.get(category, [])
        bbox = primitive_bbox(primitives)
        roles[role] = {
            "transform_id": transform.transform_id,
            "cad_bbox": [float(value) for value in bbox] if bbox else None,
            "pixel_bbox": transform.pixel_bbox(bbox) if bbox else None,
            "layers": sorted({str(primitive.layer) for primitive in primitives if primitive.layer}),
            "side_bboxes": {
                "front": _bbox_payload(primitive_bbox(front.get(category, [])), transform),
                "back": _bbox_payload(primitive_bbox(back.get(category, [])), transform),
            },
        }
    return {
        "units": "mm",
        "transform_id": transform.transform_id,
        "canvas": {"width": transform.width, "height": transform.height},
        "roles": roles,
    }


_ROLE_CATEGORY = {
    "panel": "panel",
    "frame": "frame",
    "trim": "trim",
    "hardware": "accessory",
}

_KNOWN_STRUCTURAL_LAYERS = {
    "A-DOOR-PANEL",
    "A-DOOR-FRAME",
    "A-DOOR-TRIM",
    "A-DOOR-HATCH",
    "A-DOOR-mark",
    "A-DOOR-MASK",
    "A-DOOR-OCCLUSION",
}


def _error(code: str, role: str, message: str, layer: Optional[str] = None) -> dict:
    item = {"code": code, "role": role, "message": message}
    if layer:
        item["layer"] = layer
    return item


def _has_closed_contour(primitives: Iterable[GeometryPrimitive]) -> bool:
    for primitive in primitives:
        if primitive.kind in {"circle", "wipeout"}:
            return True
        if primitive.kind == "polyline" and bool(primitive.data.get("closed")):
            return True
    return False


def _bbox_contains(outer: list[int], inner: list[int], tolerance: int = 2) -> bool:
    return (
        outer[0] <= inner[0] + tolerance
        and outer[1] <= inner[1] + tolerance
        and outer[2] >= inner[2] - tolerance
        and outer[3] >= inner[3] - tolerance
    )


def _mask_alpha(mask: np.ndarray) -> np.ndarray:
    if mask.ndim == 2:
        return mask > 0
    if mask.ndim == 3 and mask.shape[2] >= 4:
        return mask[..., 3] > 0
    raise ValueError("角色遮罩必须是二维 alpha 或 RGBA 数组")


def _validate_mask_pair(
    manifest: dict,
    masks: Mapping[str, np.ndarray],
    left_role: str,
    right_role: str,
    errors: list[dict],
    *,
    check_overlap: bool = True,
) -> None:
    left_mask = masks.get(left_role)
    right_mask = masks.get(right_role)
    left_bbox = manifest["roles"][left_role].get("pixel_bbox")
    right_bbox = manifest["roles"][right_role].get("pixel_bbox")
    if left_mask is None or right_mask is None or not left_bbox or not right_bbox:
        return

    left_alpha = _mask_alpha(left_mask)
    right_alpha = _mask_alpha(right_mask)
    if not np.any(left_alpha) or not np.any(right_alpha):
        return

    overlap = int(np.count_nonzero(left_alpha & right_alpha))
    tolerance = max(4, int(0.0005 * left_alpha.size))
    nested = _bbox_contains(left_bbox, right_bbox) or _bbox_contains(right_bbox, left_bbox)
    if check_overlap and overlap > tolerance and not nested:
        errors.append(
            _error(
                "ROLE_MASK_OVERLAP",
                f"{left_role}/{right_role}",
                f"相邻部件遮罩异常重叠 {overlap} 像素",
            )
        )

    # 只有 CAD 包围盒已经表达为贴边关系时才检查缝隙，避免把设计留缝误判。
    span = max(left_bbox[2] - left_bbox[0], left_bbox[3] - left_bbox[1], 1)
    edge_tolerance = max(2, int(round(span * 0.005)))
    horizontal_gap = min(abs(left_bbox[0] - right_bbox[2]), abs(right_bbox[0] - left_bbox[2]))
    vertical_gap = min(abs(left_bbox[1] - right_bbox[3]), abs(right_bbox[1] - left_bbox[3]))
    expected_adjacent = min(horizontal_gap, vertical_gap) <= edge_tolerance
    if not expected_adjacent:
        return

    kernel = np.ones((5, 5), np.uint8)
    expanded_left = cv2.dilate(left_alpha.astype(np.uint8), kernel) > 0
    if not np.any(expanded_left & right_alpha):
        errors.append(
            _error(
                "ROLE_BOUNDARY_GAP",
                f"{left_role}/{right_role}",
                "相邻部件边界存在异常缝隙",
            )
        )


def validate_geometry_manifest(
    manifest: dict,
    categorized: Mapping[str, list[GeometryPrimitive]],
    masks: Optional[Mapping[str, np.ndarray]] = None,
) -> dict:
    """Validate structural roles before precise rendering or AI material work."""
    errors: list[dict] = []
    warnings: list[dict] = []

    for role, category in _ROLE_CATEGORY.items():
        geometry = manifest.get("roles", {}).get(role, {})
        primitives = categorized.get(category, [])
        required = role in {"panel", "frame"}
        exists = bool(geometry.get("cad_bbox") and primitives)
        if required and not exists:
            errors.append(
                _error(
                    f"MISSING_{role.upper()}_GEOMETRY",
                    role,
                    "门扇无有效几何" if role == "panel" else "门框无有效几何",
                )
            )
            continue
        if not exists:
            continue
        if not _has_closed_contour(primitives):
            role_name = {"panel": "门扇", "frame": "门框", "trim": "门套", "hardware": "五金"}[role]
            errors.append(
                _error(
                    f"{role.upper()}_CONTOUR_NOT_CLOSED",
                    role,
                    f"{role_name}轮廓未闭合",
                    geometry.get("layers", [None])[0] if geometry.get("layers") else None,
                )
            )

        if required:
            sides = geometry.get("side_bboxes", {})
            if not sides.get("front") or not sides.get("back"):
                errors.append(
                    _error(
                        f"{role.upper()}_SIDES_NOT_SEPARATED",
                        role,
                        "正反面结构边界无法分离",
                    )
                )

    for primitive in categorized.get("outline", []):
        layer = str(primitive.layer or "")
        if layer.startswith("A-DOOR-") and layer not in _KNOWN_STRUCTURAL_LAYERS:
            errors.append(
                _error(
                    "UNKNOWN_STRUCTURAL_LAYER",
                    "outline",
                    f"结构图元位于未识别图层 {layer}",
                    layer,
                )
            )

    if masks:
        _validate_mask_pair(manifest, masks, "panel", "frame", errors)
        # 门套通常覆盖门框的一部分，重叠属于正常构造；这里只检查两者是否异常脱离。
        _validate_mask_pair(manifest, masks, "frame", "trim", errors, check_overlap=False)

    # Keep one record per concrete finding when repeated virtual entities share a layer.
    unique_errors = []
    seen = set()
    for item in errors:
        key = (item["code"], item["role"], item.get("layer"), item["message"])
        if key not in seen:
            unique_errors.append(item)
            seen.add(key)
    return {"valid": not unique_errors, "errors": unique_errors, "warnings": warnings}
