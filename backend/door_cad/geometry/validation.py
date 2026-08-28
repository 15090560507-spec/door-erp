"""Low-level geometry predicates shared by production validation."""

from __future__ import annotations

from door_cad.models import ClosedPolyline, Point2D


def point_in_bounds(point: Point2D, width: float, height: float, *, tolerance: float = 1e-6) -> bool:
    return (
        -tolerance <= point.x <= width + tolerance
        and -tolerance <= point.y <= height + tolerance
    )


def has_duplicate_adjacent_points(polyline: ClosedPolyline) -> bool:
    points = polyline.points
    return any(a == b for a, b in zip(points, points[1:] + points[:1]))
