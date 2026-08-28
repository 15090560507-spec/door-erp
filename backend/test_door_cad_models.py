import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from door_cad.models import (
    AssemblyGeometry,
    ClosedPolyline,
    FrameInput,
    PartGeometry,
    PartProcessMeta,
    Point2D,
    Polyline,
    ProjectGeometry,
    ProjectMeta,
    ValidationReport,
)


def test_frame_input_preserves_confirmed_defaults():
    inputs = FrameInput()
    assert inputs.doorWidth == 1800
    assert inputs.doorHeight == 2700
    assert inputs.outerSideShort == 55
    assert inputs.outerSideLong == 62
    assert inputs.skeletonSideShort == 52
    assert inputs.skeletonSideLong == 59
    assert inputs.skeletonThickness == 2.0
    assert inputs.skinThickness == 0.8
    assert inputs.topShort == 55
    assert inputs.topLong == 75
    assert inputs.hingeCount == 3
    assert inputs.includeTop is True
    assert inputs.includeBottom is True


def test_linked_side_sizes_follow_outer_sizes():
    inputs = FrameInput(outerSideShort=60, outerSideLong=70)
    assert inputs.resolved_skeleton_sizes() == (57.0, 67.0)
    assert inputs.resolved_skin_sizes() == (60.0, 70.0)


def test_unlinked_side_sizes_preserve_explicit_values():
    inputs = FrameInput(
        linkedSideSizes=False,
        skeletonSideShort=51,
        skeletonSideLong=61,
        outerSideShort=56,
        outerSideLong=68,
    )
    assert inputs.resolved_skeleton_sizes() == (51.0, 61.0)
    assert inputs.resolved_skin_sizes() == (56.0, 68.0)


@pytest.mark.parametrize(
    "payload",
    [
        {"doorWidth": 0},
        {"doorHeight": -1},
        {"outerSideShort": 62, "outerSideLong": 55},
        {"skeletonThickness": 1, "skeletonGrooveDepth": 1},
        {"skinThickness": 0.3, "skinGrooveDepth": 0.3},
        {"hingeCount": 2},
        {"hingeCount": 5},
    ],
)
def test_frame_input_rejects_invalid_production_values(payload):
    with pytest.raises(ValidationError):
        FrameInput(**payload)


def test_top_and_bottom_parts_can_be_disabled_independently():
    inputs = FrameInput(includeTop=False, includeBottom=True)
    assert inputs.includeTop is False
    assert inputs.includeBottom is True


def test_project_geometry_round_trips_as_plain_json():
    boundary = ClosedPolyline(
        points=[
            Point2D(x=0, y=0),
            Point2D(x=100, y=0),
            Point2D(x=100, y=500),
            Point2D(x=0, y=500),
        ]
    )
    part = PartGeometry(
        partId="left-skeleton",
        name="左框骨架",
        position="left",
        materialType="skeleton",
        length=2700,
        thickness=2,
        flatWidth=300,
        cutOuter=boundary,
        foldSection=Polyline(points=[Point2D(x=0, y=0), Point2D(x=55, y=0)]),
        flatSection=Polyline(points=[Point2D(x=0, y=0), Point2D(x=300, y=0)]),
        process=PartProcessMeta(sourceRule="frame-new-v1.4.3"),
    )
    geometry = ProjectGeometry(
        project=ProjectMeta(orderNo="DD20260829001", projectName="模型测试"),
        inputs=FrameInput(),
        assembly=AssemblyGeometry(width=1800, height=2700),
        parts=[part],
        validation=ValidationReport(),
    )

    payload = geometry.model_dump_json()
    restored = ProjectGeometry.model_validate_json(payload)
    assert restored == geometry
    assert restored.schemaVersion == "1.0"
    assert restored.ruleVersion == "frame-new-v1.4.3"
    assert isinstance(restored.parts[0].cutOuter.points[0].x, float)


def test_geometry_rounds_only_when_serialized():
    point = Point2D(x=1.23456, y=9.87654)
    assert point.x == 1.23456
    assert point.model_dump() == {"x": 1.235, "y": 9.877}
