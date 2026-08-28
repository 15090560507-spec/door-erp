import json

import pytest

from door_cad.models import FrameInput, ProjectMeta
from door_cad.repository import DoorCadProjectRepository, ProjectVersionError
from door_cad.services import calculate_frame_project


def _geometry(project_name: str = "测试门框"):
    inputs = FrameInput()
    geometry = calculate_frame_project(
        inputs,
        ProjectMeta(orderNo="DD20260829001", projectName=project_name),
    )
    return inputs, geometry


def test_repository_create_list_get_and_update(tmp_path):
    repository = DoorCadProjectRepository(tmp_path / "projects.json", tmp_path / "backups")
    inputs, geometry = _geometry()

    created = repository.create(inputs, geometry, "admin")
    assert created["createdBy"] == "admin"
    assert created["createdAt"] == created["updatedAt"]
    assert created["geometry"]["validation"]["status"] == "PASSED"

    summaries = repository.list_summaries()
    assert summaries == [{
        "id": created["id"],
        "orderNo": "DD20260829001",
        "projectName": "测试门框",
        "taskId": None,
        "status": "PASSED",
        "updatedAt": created["updatedAt"],
        "updatedBy": "admin",
    }]
    assert repository.get(created["id"]) == created

    updated_inputs, updated_geometry = _geometry("修改后的项目")
    updated = repository.update(created["id"], updated_inputs, updated_geometry, "B")
    assert updated["id"] == created["id"]
    assert updated["createdAt"] == created["createdAt"]
    assert updated["createdBy"] == "admin"
    assert updated["updatedBy"] == "B"
    assert updated["geometry"]["project"]["projectName"] == "修改后的项目"


def test_repository_uses_atomic_replace_and_backup(tmp_path):
    repository = DoorCadProjectRepository(tmp_path / "projects.json", tmp_path / "backups")
    inputs, geometry = _geometry()
    created = repository.create(inputs, geometry, "admin")
    repository.update(created["id"], inputs, geometry, "admin")

    assert not list(tmp_path.glob("*.tmp"))
    assert list((tmp_path / "backups").glob("projects.json.*.bak"))


@pytest.mark.parametrize("field,value", [("schemaVersion", "0.9"), ("ruleVersion", "old-rule")])
def test_repository_rejects_stale_versions(tmp_path, field, value):
    path = tmp_path / "projects.json"
    document = {"schemaVersion": "1.0", "ruleVersion": "frame-new-v1.4.3", "projects": []}
    document[field] = value
    path.write_text(json.dumps(document), encoding="utf-8")

    repository = DoorCadProjectRepository(path, tmp_path / "backups")
    with pytest.raises(ProjectVersionError):
        repository.list_summaries()


def test_repository_rejects_mismatched_input_snapshot(tmp_path):
    repository = DoorCadProjectRepository(tmp_path / "projects.json", tmp_path / "backups")
    _, geometry = _geometry()
    with pytest.raises(ValueError, match="输入参数与几何快照"):
        repository.create(FrameInput(doorWidth=1900), geometry, "admin")
