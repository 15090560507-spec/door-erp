import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from door_cad.models import FrameInput, ProjectMeta
from door_cad.services import calculate_frame_project


def test_standard_order_calculates_eight_parts_once():
    geometry = calculate_frame_project(FrameInput(), ProjectMeta(projectName="标准门框"))

    assert [part.partId for part in geometry.parts] == [
        "LF-SK", "LF-SKIN", "RF-SK", "RF-SKIN",
        "TF-SK", "TF-SKIN", "BF-SK", "BF-SKIN",
    ]
    assert geometry.validation.status == "PASSED"
    assert geometry.assembly.width == 1800
    assert geometry.assembly.height == 2700
    assert len(geometry.assembly.placements) == 8


def test_part_switches_control_parts_and_assembly_placements():
    geometry = calculate_frame_project(
        FrameInput(includeRight=False, includeBottom=False),
        ProjectMeta(projectName="部分门框"),
    )

    assert [part.partId for part in geometry.parts] == ["LF-SK", "LF-SKIN", "TF-SK", "TF-SKIN"]
    assert [placement.partId for placement in geometry.assembly.placements] == [
        "LF-SK", "LF-SKIN", "TF-SK", "TF-SKIN",
    ]


def test_empty_project_name_is_a_warning_not_a_calculation_error():
    geometry = calculate_frame_project(FrameInput())

    assert geometry.validation.status == "WARNING"
    assert not geometry.validation.errors
    assert any(issue.code == "PROJECT_NAME_MISSING" for issue in geometry.validation.warnings)
