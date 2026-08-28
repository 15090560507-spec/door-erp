"""Small pure geometry constructors used by rule modules."""

from __future__ import annotations

from collections.abc import Iterable

from door_cad.models import ClosedPolyline, Point2D, Polyline


def point(value: tuple[float, float]) -> Point2D:
    return Point2D(x=float(value[0]), y=float(value[1]))


def polyline(values: Iterable[tuple[float, float]], *, closed: bool = False) -> Polyline:
    return Polyline(points=[point(value) for value in values], closed=closed)


def closed_polyline(values: Iterable[tuple[float, float]]) -> ClosedPolyline:
    return ClosedPolyline(points=[point(value) for value in values])


def rectangle(width: float, height: float) -> ClosedPolyline:
    return closed_polyline([(0, 0), (width, 0), (width, height), (0, height)])
