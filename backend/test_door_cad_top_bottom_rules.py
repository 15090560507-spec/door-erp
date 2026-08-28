import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from door_cad.models import FrameInput
from door_cad.rules.top_bottom_template import TemplateRuleError
from door_cad.rules.top_frame import build_top_parts
from door_cad.rules.bottom_frame import build_bottom_parts


def test_top_and_bottom_use_four_independent_template_groups():
    inputs = FrameInput()
    top = build_top_parts(inputs)
    bottom = build_bottom_parts(inputs)

    assert [part.partId for part in top] == ["TF-SK", "TF-SKIN"]
    assert [part.partId for part in bottom] == ["BF-SK", "BF-SKIN"]
    assert all(part.cutOuter.closed for part in top + bottom)
    assert len({part.partId for part in top + bottom}) == 4
    assert all(part.process.sourceTemplate == "top_bottom_double_door_template.dxf" for part in top + bottom)


def test_top_bottom_lengths_and_sections_are_not_rotated_side_frames():
    inputs = FrameInput(doorWidth=1800, outerSideShort=55, outerSideLong=62)
    top = build_top_parts(inputs)
    top_skeleton, top_skin = top

    assert top_skeleton.length == 1690
    assert "短边 1676" in top_skeleton.process.notes
    assert top_skeleton.flatWidth == 289
    assert top_skin.flatWidth == 324.2
    assert [(point.x, point.y) for point in top_skeleton.foldSection.points] != [
        (0, 0),
        (0, 14),
        (52, 14),
        (52, -38),
        (39, -38),
        (39, -88),
        (59, -88),
        (59, -111),
        (0, -111),
        (0, -97),
    ]
    assert min(point.y for point in top_skeleton.cutOuter.points) < 0


def test_pin_holes_follow_top_and_bottom_switches():
    without_pins = FrameInput(topPin=False, bottomPin=False)
    assert not any(hole.shapeId == "pin" for part in build_top_parts(without_pins) for hole in part.holes)
    assert not any(hole.shapeId == "pin" for part in build_bottom_parts(without_pins) for hole in part.holes)

    with_pins = FrameInput(topPin=True, bottomPin=True)
    assert all(any(hole.shapeId == "pin" for hole in part.holes) for part in build_top_parts(with_pins))
    assert all(any(hole.shapeId == "pin" for hole in part.holes) for part in build_bottom_parts(with_pins))


def test_missing_template_returns_a_blocking_rule_error(tmp_path):
    missing = tmp_path / "missing-template.dxf"
    with pytest.raises(TemplateRuleError, match="上下框模板不存在"):
        build_top_parts(FrameInput(), template_path=missing)
