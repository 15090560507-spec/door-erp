"""Shared hole spacing and opening rules from v1.4.3."""

from __future__ import annotations

import math


def edge_fixing_positions(
    length: float,
    *,
    end_margin: float = 15.0,
    max_spacing: float = 540.0,
) -> list[float]:
    length = float(length)
    if length <= 2 * end_margin:
        return [length / 2.0]
    usable = length - 2 * end_margin
    segments = max(1, math.ceil(usable / max_spacing))
    spacing = usable / segments
    return [round(end_margin + index * spacing, 4) for index in range(segments + 1)]


def resolve_hinge_positions(
    length: float,
    count: int,
    custom_positions: list[float] | None = None,
) -> list[float]:
    if custom_positions:
        return sorted(round(float(value), 3) for value in custom_positions if 0 < value < length)
    if int(count) <= 3:
        return [280.0, 680.0, max(780.0, float(length) - 280.0)]
    return [280.0, 680.0, float(length) / 2.0, max(float(length) / 2.0 + 250.0, float(length) - 280.0)]
