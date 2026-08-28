"""Bottom-frame geometry assembled from two independent frozen template groups."""

from __future__ import annotations

from pathlib import Path

from door_cad.models import FrameInput, PartGeometry

from .top_bottom_template import build_template_part


def build_bottom_parts(inputs: FrameInput, template_path: str | Path | None = None) -> list[PartGeometry]:
    short, long = inputs.resolved_bottom_sizes()
    return [
        build_template_part(inputs, "BF-SK", short, long, inputs.bottomPin, template_path),
        build_template_part(inputs, "BF-SKIN", short, long, inputs.bottomPin, template_path),
    ]
