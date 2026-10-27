"""Reference motifs share quotation credentials, not quotation extraction logic."""
import os
from typing import Dict
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from auth import ENTRY_ROLES, TASK_ROLES, require_roles
from config import DATA_DIR
from quote_routes import ai_config_db, _normalize_ai_model
from reference_pattern_models import PatternPreviewRequest, PatternTemplateCreate
from reference_pattern_geometry import pattern_contours
from reference_pattern_service import MAX_UPLOAD, ReferencePatternService


def shared_connection():
    config = ai_config_db.get()
    return {**config, "model": _normalize_ai_model(config.get("model") or "")}


service = ReferencePatternService(os.path.join(DATA_DIR, "reference_patterns.db"), shared_connection)
router = APIRouter(prefix="/api/reference-patterns", tags=["reference-patterns"])


def failure(exc):
    return HTTPException(status_code=404 if isinstance(exc, LookupError) else 409 if isinstance(exc, RuntimeError) else 400, detail=str(exc))


@router.get("/connection")
def connection(user: Dict = Depends(require_roles(*TASK_ROLES))):
    config = shared_connection()
    return {"model": config.get("model", ""), "configured": all(bool(config.get(key)) for key in ("baseUrl", "apiKey", "model"))}


@router.post("/jobs", status_code=202)
async def create_job(file: UploadFile = File(...), request_key: str = Form(..., min_length=1, max_length=100), user: Dict = Depends(require_roles(*ENTRY_ROLES))):
    raw = await file.read(MAX_UPLOAD + 1)
    try:
        return {"job": service.submit(user["uid"], raw, request_key)}
    except (ValueError, RuntimeError) as exc:
        raise failure(exc) from exc


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: Dict = Depends(require_roles(*TASK_ROLES))):
    try:
        return {"job": service.get_job(job_id)}
    except LookupError as exc:
        raise failure(exc) from exc


@router.get("/jobs/{job_id}/source")
def get_source(job_id: str, user: Dict = Depends(require_roles(*TASK_ROLES))):
    try:
        return Response(service.get_image(job_id), media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})
    except LookupError as exc:
        raise failure(exc) from exc


@router.post("/preview")
def preview(body: PatternPreviewRequest, user: Dict = Depends(require_roles(*TASK_ROLES))):
    try:
        return pattern_contours(body.placement, body.width, body.height)
    except ValueError as exc:
        raise failure(exc) from exc


@router.get("/templates")
def templates(user: Dict = Depends(require_roles(*TASK_ROLES))):
    return {"templates": service.list_templates(user["uid"])}


@router.post("/templates", status_code=201)
def save_template(body: PatternTemplateCreate, user: Dict = Depends(require_roles(*ENTRY_ROLES))):
    try:
        return {"template": service.save_template(user["uid"], body.name, body.snapshot)}
    except ValueError as exc:
        raise failure(exc) from exc
