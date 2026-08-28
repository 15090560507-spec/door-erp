import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from door_cad.models import FrameInput, ProjectMeta
from door_cad.services import calculate_frame_project, validate_project_geometry


def test_non_standard_dimensions_return_acknowledgeable_warning():
    geometry = calculate_frame_project(
        FrameInput(outerSideShort=56, outerSideLong=64),
        ProjectMeta(projectName="非标门框"),
    )

    assert geometry.validation.status == "WARNING"
    assert any(issue.code == "NON_STANDARD_SIDE_SIZE" for issue in geometry.validation.warnings)


def test_duplicate_part_id_is_blocking():
    geometry = calculate_frame_project(FrameInput(), ProjectMeta(projectName="校验测试"))
    bad_parts = geometry.parts[:-1] + [geometry.parts[0]]
    report = validate_project_geometry(geometry.model_copy(update={"parts": bad_parts}))

    assert report.status == "ERROR"
    assert any(issue.code == "DUPLICATE_PART_ID" for issue in report.errors)


def test_mirror_semantics_are_validated():
    geometry = calculate_frame_project(FrameInput(), ProjectMeta(projectName="镜像测试"))
    right = geometry.parts[2]
    broken = right.model_copy(update={"process": right.process.model_copy(update={"mirrored": False})})
    parts = geometry.parts.copy()
    parts[2] = broken
    report = validate_project_geometry(geometry.model_copy(update={"parts": parts}))

    assert report.status == "ERROR"
    assert any(issue.code == "MIRROR_SEMANTICS" for issue in report.errors)


def test_export_warning_acknowledgement_is_reported_separately():
    geometry = calculate_frame_project(FrameInput())
    assert geometry.validation.status == "WARNING"
    assert geometry.validation.errors == []
