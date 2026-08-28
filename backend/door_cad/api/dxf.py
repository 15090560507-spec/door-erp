"""Combined DXF download endpoint."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict

from auth import get_current_user
from door_cad.exporters import build_combined_dxf, combined_dxf_filename
from door_cad.exporters.dxf_exporter import DxfAuditError
from door_cad.models import FrameInput, ProjectGeometry, ProjectMeta
from door_cad.repository import DoorCadProjectRepository
from door_cad.services import calculate_frame_project, requires_warning_acknowledgement

from .common import domain_error
from .projects import get_project_repository


router = APIRouter()


class DxfExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str | None = None
    inputs: FrameInput | None = None
    project: ProjectMeta | None = None
    acknowledgeWarnings: bool = False


def resolve_geometry(request: DxfExportRequest, repository: DoorCadProjectRepository) -> ProjectGeometry:
    if request.projectId:
        try:
            return ProjectGeometry.model_validate(repository.get(request.projectId)["geometry"])
        except KeyError as exc:
            raise domain_error("PROJECT_NOT_FOUND", "下料项目不存在", "projectId", 404) from exc
    if request.inputs is None:
        raise domain_error("INPUT_REQUIRED", "必须提交参数或已保存项目 ID", "inputs")
    return calculate_frame_project(request.inputs, request.project or ProjectMeta())


@router.post("/export-dxf")
def export_dxf(
    request: DxfExportRequest,
    _current_user: dict = Depends(get_current_user),
    repository: DoorCadProjectRepository = Depends(get_project_repository),
) -> Response:
    geometry = resolve_geometry(request, repository)
    if geometry.validation.errors:
        raise domain_error("GEOMETRY_INVALID", "几何校验未通过，不能导出 DXF", "validation")
    if requires_warning_acknowledgement(geometry.validation, request.acknowledgeWarnings):
        raise domain_error("WARNING_ACK_REQUIRED", "存在生产警告，请确认后再导出", "acknowledgeWarnings", 409)
    try:
        payload = build_combined_dxf(geometry)
    except DxfAuditError as exc:
        raise domain_error("DXF_AUDIT_FAILED", str(exc), "dxf", 500) from exc
    filename = combined_dxf_filename(geometry)
    return Response(
        content=payload,
        media_type="application/dxf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
