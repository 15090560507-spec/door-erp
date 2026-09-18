"""DXF component geometry manifest built from one shared CAD-to-pixel transform."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable, Optional, Protocol


class GeometryPrimitive(Protocol):
    layer: str
    points: list[tuple[float, float]]


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
