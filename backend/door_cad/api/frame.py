"""Frame calculation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from auth import get_current_user
from door_cad.models import ProjectGeometry
from door_cad.services import calculate_frame_project
from door_cad.services.fulfillment_adapter import adapt_fulfillment_frame

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


@router.get("/from-door-unit/{door_unit_id}")
def frame_from_door_unit(
    door_unit_id: int,
    _current_user: dict = Depends(get_current_user),
) -> dict:
    from fulfillment_routes import fulfillment_db

    try:
        adaptation = adapt_fulfillment_frame(fulfillment_db, door_unit_id)
    except LookupError as exc:
        raise domain_error("DOOR_UNIT_NOT_FOUND", str(exc), "doorUnitId", 404) from exc
    return adaptation.model_dump(mode="json")
