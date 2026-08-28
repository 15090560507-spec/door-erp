"""BOM workbook and canonical project JSON downloads."""

from __future__ import annotations

import json
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response

from auth import get_current_user
from door_cad.exporters.bom_excel import build_bom_workbook
from door_cad.repository import DoorCadProjectRepository
from door_cad.services import requires_warning_acknowledgement

from .common import domain_error
from .dxf import DxfExportRequest, resolve_geometry
from .projects import get_project_repository


router = APIRouter()


def _filename_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (value or "").strip())
    return cleaned.strip(" .") or fallback


def _download_name(request_geometry, suffix: str) -> str:
    order_no = _filename_part(request_geometry.project.orderNo, "无订单号")
    project_name = _filename_part(request_geometry.project.projectName, "未命名项目")
    return f"{order_no}-{project_name}-{suffix}"


def _validated_export_geometry(request: DxfExportRequest, repository: DoorCadProjectRepository):
    geometry = resolve_geometry(request, repository)
    if geometry.validation.errors:
        raise domain_error("GEOMETRY_INVALID", "几何校验未通过，不能导出", "validation")
    if requires_warning_acknowledgement(geometry.validation, request.acknowledgeWarnings):
        raise domain_error("WARNING_ACK_REQUIRED", "存在生产警告，请确认后再导出", "acknowledgeWarnings", 409)
    return geometry


@router.post("/export-bom")
def export_bom(
    request: DxfExportRequest,
    _current_user: dict = Depends(get_current_user),
    repository: DoorCadProjectRepository = Depends(get_project_repository),
) -> Response:
    geometry = _validated_export_geometry(request, repository)
    filename = _download_name(geometry, "门框BOM.xlsx")
    return Response(
        content=build_bom_workbook(geometry),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/export-json")
def export_project_json(
    request: DxfExportRequest,
    _current_user: dict = Depends(get_current_user),
    repository: DoorCadProjectRepository = Depends(get_project_repository),
) -> Response:
    geometry = _validated_export_geometry(request, repository)
    filename = _download_name(geometry, "门框下料项目.json")
    payload = json.dumps(geometry.model_dump(mode="json"), ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        content=payload,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
