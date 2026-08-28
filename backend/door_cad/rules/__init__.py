"""Production geometry rules for the independent door-frame module."""

from __future__ import annotations

from door_cad.geometry import mirror_part
from door_cad.models import FrameInput, PartGeometry

from .frame_new_skeleton import build_left_skeleton
from .frame_new_skin import build_left_skin, build_skin_cut_outer
from .bottom_frame import build_bottom_parts
from .opening import edge_fixing_positions, resolve_hinge_positions
from .top_frame import build_top_parts


def build_side_parts(inputs: FrameInput, side: str) -> list[PartGeometry]:
    left_skeleton = build_left_skeleton(inputs)
    left_skin = build_left_skin(inputs)
    if side == "left":
        return [left_skeleton, left_skin]
    if side != "right":
        raise ValueError("side must be left or right")
    return [
        mirror_part(
            left_skeleton,
            part_id="RF-SK",
            name="右框骨架",
            position="right",
        ),
        mirror_part(
            left_skin,
            part_id="RF-SKIN",
            name="右框外皮",
            position="right",
        ),
    ]


__all__ = [
    "build_side_parts",
    "build_skin_cut_outer",
    "build_top_parts",
    "build_bottom_parts",
    "edge_fixing_positions",
    "resolve_hinge_positions",
]
