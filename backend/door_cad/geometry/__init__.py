from .clipping import vertical_material_interval
from .mirror import mirror_part, mirror_point
from .primitives import closed_polyline, point, polyline, rectangle
from .validation import has_duplicate_adjacent_points, point_in_bounds

__all__ = [
    "closed_polyline",
    "has_duplicate_adjacent_points",
    "mirror_part",
    "mirror_point",
    "point",
    "point_in_bounds",
    "polyline",
    "rectangle",
    "vertical_material_interval",
]
