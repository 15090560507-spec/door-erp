"""Top-frame geometry assembled from two independent frozen template groups."""

from __future__ import annotations

from pathlib import Path

from door_cad.models import FrameInput, PartGeometry

from .top_bottom_template import build_template_part


def build_top_parts(inputs: FrameInput, template_path: str | Path | None = None) -> list[PartGeometry]:
    return [
        build_template_part(inputs, "TF-SK", inputs.topShort, inputs.topLong, inputs.topPin, template_path),
        build_template_part(inputs, "TF-SKIN", inputs.topShort, inputs.topLong, inputs.topPin, template_path),
    ]
