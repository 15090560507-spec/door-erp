import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from door_cad.models import FrameInput
from door_cad.rules import build_side_parts, resolve_hinge_positions


def _part(parts, part_id):
    return next(part for part in parts if part.partId == part_id)


def test_standard_skeleton_and_skin_chains_match_v143():
    parts = build_side_parts(FrameInput(), "left")
    skeleton = _part(parts, "LF-SK")
    skin = _part(parts, "LF-SKIN")

    assert skeleton.flatWidth == 289.0
    assert [groove.segments[0].start.x for groove in skeleton.grooves] == [
        13.0,
        63.0,
        113.0,
        126.0,
        178.0,
        198.0,
        219.0,
        276.0,
    ]
    assert skin.flatWidth == 324.8
    assert [groove.segments[0].start.x for groove in skin.grooves] == [
        14.5,
        68.5,
        126.5,
        139.3,
        181.9,
        190.5,
        200.3,
        211.3,
        247.3,
        308.3,
    ]


def test_edge_fixings_and_hinges_follow_height():
    standard = build_side_parts(FrameInput(), "left")
    skeleton = _part(standard, "LF-SK")
    edge_holes = [hole for hole in skeleton.holes if hole.shapeId.startswith("edge-")]
    assert sorted({hole.center.y for hole in edge_holes}) == [15, 549, 1083, 1617, 2151, 2685]

    hinge_cuts = [hole for hole in skeleton.holes if hole.shapeId.startswith("hinge-body-")]
    assert [2700 - hole.center.y for hole in hinge_cuts] == [280, 680, 2420]

    custom_height = build_side_parts(FrameInput(doorHeight=3100, hingeCount=4), "left")
    custom_skeleton = _part(custom_height, "LF-SK")
    hinge_cuts = [hole for hole in custom_skeleton.holes if hole.shapeId.startswith("hinge-body-")]
    assert [3100 - hole.center.y for hole in hinge_cuts] == [280, 680, 1550, 2820]
    assert resolve_hinge_positions(2200, 3) == [280, 680, 1920]


def test_right_side_mirrors_actual_geometry_and_dimension_witnesses():
    left_parts = build_side_parts(FrameInput(), "left")
    right_parts = build_side_parts(FrameInput(), "right")
    left = _part(left_parts, "LF-SKIN")
    right = _part(right_parts, "RF-SKIN")
    width = left.flatWidth

    assert right.name == "右框外皮"
    assert right.process.mirrored is True
    assert right.holes[0].center.x == pytest.approx(width - left.holes[0].center.x)
    assert right.grooves[0].segments[0].start.x == pytest.approx(
        width - left.grooves[0].segments[0].start.x
    )
    assert right.dimensions[0].start.x == pytest.approx(width - left.dimensions[0].start.x)
    assert right.dimensions[0].end.x == pytest.approx(width - left.dimensions[0].end.x)


def test_skin_cut_outer_and_grooves_are_clipped_to_real_material():
    skin = _part(build_side_parts(FrameInput(), "left"), "LF-SKIN")
    assert [(point.x, point.y) for point in skin.cutOuter.points] == [
        (0, 0),
        (76, 0),
        (76, 47),
        (239.8, 47),
        (239.8, 0),
        (324.8, 0),
        (324.8, 2700),
        (239.8, 2700),
        (239.8, 2653),
        (76, 2653),
        (76, 2700),
        (0, 2700),
    ]

    for groove in skin.grooves:
        segment = groove.segments[0]
        if 76 < segment.start.x < 239.8:
            assert (segment.start.y, segment.end.y) == (47, 2653)
        else:
            assert (segment.start.y, segment.end.y) == (0, 2700)
