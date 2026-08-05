"""Optional CAD structural occlusion without deleting source geometry."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence


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
        wipeout = self.modelspace.add_wipeout(points)
        wipeout.dxf.layer = "A-DOOR-OCCLUSION"
        return self.register(wipeout, f"{tier}_mask")

    def apply(self):
        if not self.enabled:
            return
        self.doc.set_wipeout_variables(frame=0)

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
        self.modelspace.set_redraw_order(redraw_order)


def structural_group_for_layer(layer: str) -> str:
    if layer == "A-DOOR-FRAME":
        return "frame"
    if layer == "A-DOOR-TRIM":
        return "trim"
    return "panel"

