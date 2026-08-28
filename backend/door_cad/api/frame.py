"""Frame calculation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from auth import get_current_user
from door_cad.models import ProjectGeometry
from door_cad.services import calculate_frame_project

from .common import FrameProjectRequest, domain_error


router = APIRouter()


@router.post("/calculate", response_model=ProjectGeometry)
def calculate_frame(
    request: FrameProjectRequest,
    _current_user: dict = Depends(get_current_user),
) -> ProjectGeometry:
    try:
        return calculate_frame_project(request.inputs, request.project)
    except ValueError as exc:
        raise domain_error("CALCULATION_FAILED", str(exc), "inputs") from exc
