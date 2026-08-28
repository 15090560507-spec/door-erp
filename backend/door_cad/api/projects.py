"""Saved door-frame cutting project endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from auth import get_current_user
from door_cad.repository import DoorCadProjectRepository, ProjectVersionError
from door_cad.services import calculate_frame_project

from .common import FrameProjectRequest, domain_error


router = APIRouter()
_repository = DoorCadProjectRepository()


def get_project_repository() -> DoorCadProjectRepository:
    return _repository


@router.get("/projects")
def list_projects(
    _current_user: dict = Depends(get_current_user),
    repository: DoorCadProjectRepository = Depends(get_project_repository),
) -> dict:
    try:
        return {"projects": repository.list_summaries()}
    except ProjectVersionError as exc:
        raise domain_error("PROJECT_VERSION_MISMATCH", str(exc), "projects", 409) from exc


@router.post("/projects", status_code=201)
def create_project(
    request: FrameProjectRequest,
    current_user: dict = Depends(get_current_user),
    repository: DoorCadProjectRepository = Depends(get_project_repository),
) -> dict:
    try:
        geometry = calculate_frame_project(request.inputs, request.project)
        return repository.create(request.inputs, geometry, current_user["uid"])
    except ProjectVersionError as exc:
        raise domain_error("PROJECT_VERSION_MISMATCH", str(exc), "project", 409) from exc
    except ValueError as exc:
        raise domain_error("PROJECT_SAVE_FAILED", str(exc), "project") from exc


@router.get("/projects/{project_id}")
def get_project(
    project_id: str,
    _current_user: dict = Depends(get_current_user),
    repository: DoorCadProjectRepository = Depends(get_project_repository),
) -> dict:
    try:
        return repository.get(project_id)
    except KeyError as exc:
        raise domain_error("PROJECT_NOT_FOUND", "下料项目不存在", "projectId", 404) from exc
    except ProjectVersionError as exc:
        raise domain_error("PROJECT_VERSION_MISMATCH", str(exc), "project", 409) from exc


@router.put("/projects/{project_id}")
def update_project(
    project_id: str,
    request: FrameProjectRequest,
    current_user: dict = Depends(get_current_user),
    repository: DoorCadProjectRepository = Depends(get_project_repository),
) -> dict:
    try:
        geometry = calculate_frame_project(request.inputs, request.project)
        return repository.update(project_id, request.inputs, geometry, current_user["uid"])
    except KeyError as exc:
        raise domain_error("PROJECT_NOT_FOUND", "下料项目不存在", "projectId", 404) from exc
    except ProjectVersionError as exc:
        raise domain_error("PROJECT_VERSION_MISMATCH", str(exc), "project", 409) from exc
    except ValueError as exc:
        raise domain_error("PROJECT_SAVE_FAILED", str(exc), "project") from exc
