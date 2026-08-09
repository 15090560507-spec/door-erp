"""Optional CAD structural occlusion without deleting source geometry."""

from __future__ import annotations

from collections import defaultdict
import logging
import math
from typing import Iterable, Sequence


logger = logging.getLogger(__name__)


DRAW_ORDER = {
    "panel": "10",
    "frame_mask": "20",
    "frame": "30",
    "trim_mask": "40",
    "trim": "50",
    "hardware_mask": "60",
    "hardware": "70",
    "annotation": "80",
}


class CadOcclusionManager:
    """Track newly drawn entities and apply a stable CAD redraw order."""

    def __init__(self, doc, modelspace, enabled: bool = False):
        self.doc = doc
        self.modelspace = modelspace
        self.enabled = bool(enabled)
        self._groups: dict[str, list] = defaultdict(list)

    def register(self, entity, group: str):
        if entity is not None:
            self._groups[group].append(entity)
        return entity

    def add_mask(self, points: Sequence[tuple[float, float]], tier: str):
        if not self.enabled or len(points) < 3:
            return None
        boundary: list[tuple[float, float]] = []
        for point in points:
            try:
                x, y = float(point[0]), float(point[1])
            except (IndexError, TypeError, ValueError):
                continue
            if not math.isfinite(x) or not math.isfinite(y):
                continue
            if not boundary or (x, y) != boundary[-1]:
                boundary.append((x, y))
        if len(boundary) > 1 and boundary[0] == boundary[-1]:
            boundary.pop()
        if len(boundary) < 3:
            return None
        try:
            wipeout = self.modelspace.add_wipeout(boundary)
            wipeout.dxf.layer = "A-DOOR-OCCLUSION"
        except Exception as exc:
            # 遮挡是显示增强项，个别无效边界不能阻断整张 CAD 的生成。
            logger.warning("Skip invalid structural wipeout (%s): %s", tier, exc)
            return None
        return self.register(wipeout, f"{tier}_mask")

    def apply(self):
        if not self.enabled:
            return
        try:
            self.doc.set_wipeout_variables(frame=0)
        except Exception as exc:
            # Older ezdxf releases may not expose this helper. The WIPEOUT
            # entity itself remains valid, so retain the output and redraw order.
            logger.warning("Unable to configure wipeout frame: %s", exc)

        registered_handles = {
            entity.dxf.handle
            for entities in self._groups.values()
            for entity in entities
            if entity.is_alive and entity.dxf.handle
        }
        redraw_order: dict[str, str] = {}
        for entity in self.modelspace:
            handle = entity.dxf.handle
            if handle and handle not in registered_handles:
                redraw_order[handle] = DRAW_ORDER["annotation"]
        for group, entities in self._groups.items():
            sort_handle = DRAW_ORDER.get(group, DRAW_ORDER["annotation"])
            for entity in entities:
                if entity.is_alive and entity.dxf.handle:
                    redraw_order[entity.dxf.handle] = sort_handle
        try:
            self.modelspace.set_redraw_order(redraw_order)
        except Exception as exc:
            # A redraw-table failure must not turn the optional display setting
            # into a CAD export failure. Source geometry and wipeouts still exist.
            logger.warning("Unable to apply structural redraw order: %s", exc)


def structural_group_for_layer(layer: str) -> str:
    if layer == "A-DOOR-FRAME":
        return "frame"
    if layer == "A-DOOR-TRIM":
        return "trim"
    return "panel"
