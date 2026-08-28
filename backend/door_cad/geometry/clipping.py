"""Material-boundary clipping for unfolded plans."""

from __future__ import annotations


def vertical_material_interval(
    x: float,
    length: float,
    notch: tuple[float, float, float] | None,
) -> tuple[float, float]:
    if notch is None:
        return 0.0, float(length)
    x1, x2, depth = notch
    if x1 < float(x) < x2:
        return float(depth), float(length) - float(depth)
    return 0.0, float(length)
