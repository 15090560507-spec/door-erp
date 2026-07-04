import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .database import render_db
from .models import RenderAssetUpdate, RenderModelConfigCreate, RenderModelConfigUpdate
from .service import create_asset_from_upload, file_response_path, run_render_task
from auth import get_current_user


render_router = APIRouter()
logger = logging.getLogger(__name__)


@render_router.get("/api/render/health")
def render_health(current_user: dict = Depends(get_current_user)):
    return {"ok": True}


@render_router.get("/api/render/model-configs")
def list_model_configs(includeDisabled: bool = False, current_user: dict = Depends(get_current_user)):
    return {"configs": render_db.list_model_configs(include_disabled=includeDisabled)}


@render_router.post("/api/render/model-configs")
def create_model_config(data: RenderModelConfigCreate, current_user: dict = Depends(get_current_user)):
    return {"config": render_db.create_model_config(data.model_dump())}


@render_router.put("/api/render/model-configs/{config_id}")
def update_model_config(config_id: str, data: RenderModelConfigUpdate, current_user: dict = Depends(get_current_user)):
    updated = render_db.update_model_config(config_id, data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    return {"config": updated}


@render_router.delete("/api/render/model-configs/{config_id}")
def delete_model_config(config_id: str, current_user: dict = Depends(get_current_user)):
    updated = render_db.update_model_config(config_id, {"enabled": False})
    if not updated:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    return {"ok": True}


@render_router.get("/api/render/assets")
def list_assets(category: str = "", q: str = "", favorite: bool | None = None, limit: int = 60, offset: int = 0, current_user: dict = Depends(get_current_user)):
    return {"assets": render_db.list_assets(category=category, q=q, favorite=favorite, limit=limit, offset=offset)}


@render_router.post("/api/render/assets")
async def upload_asset(
    file: UploadFile = File(...),
    name: str = Form(""),
    category: str = Form("其他"),
    tags: str = Form("[]"),
    remark: str = Form(""),
    favorite: bool = Form(False),
    current_user: dict = Depends(get_current_user),
):
    return {"asset": await create_asset_from_upload(file, name, category, _parse_string_list(tags), remark, favorite)}


@render_router.post("/api/render/assets/batch")
async def upload_assets_batch(
    files: list[UploadFile] = File(...),
    category: str = Form("其他"),
    tags: str = Form("[]"),
    favorite: bool = Form(False),
    current_user: dict = Depends(get_current_user),
):
    created = []
    for file in files:
        created.append(await create_asset_from_upload(file, file.filename or "", category, _parse_string_list(tags), "", favorite))
    return {"assets": created}


@render_router.put("/api/render/assets/{asset_id}")
def update_asset(asset_id: str, data: RenderAssetUpdate, current_user: dict = Depends(get_current_user)):
    updated = render_db.update_asset(asset_id, data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="素材不存在")
    return {"asset": updated}


@render_router.delete("/api/render/assets/{asset_id}")
def delete_asset(asset_id: str, current_user: dict = Depends(get_current_user)):
    if not render_db.delete_asset(asset_id):
        raise HTTPException(status_code=404, detail="素材不存在")
    return {"ok": True}


@render_router.post("/api/render/tasks")
async def create_render_task(
    lineArt: UploadFile = File(...),
    styleReference: UploadFile | None = File(None),
    tempAssets: list[UploadFile] | None = File(None),
    modelConfigId: str = Form(...),
    prompt: str = Form(...),
    size: str = Form("original"),
    count: int = Form(1),
    selectedAssetIds: str = Form("[]"),
    current_user: dict = Depends(get_current_user),
):
    try:
        task = await run_render_task(
            model_config_id=modelConfigId,
            prompt=prompt,
            size=size,
            count=count,
            selected_asset_ids=_parse_string_list(selectedAssetIds),
            line_art=lineArt,
            style_reference=styleReference,
            temp_assets=tempAssets or [],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Render task failed with unexpected error")
        raise HTTPException(status_code=500, detail={"message": f"效果渲染服务内部错误: {type(exc).__name__}: {exc}"}) from exc
    return {"task": task}


@render_router.get("/api/render/tasks")
def list_render_tasks(limit: int = 30, current_user: dict = Depends(get_current_user)):
    return {"tasks": render_db.list_tasks(limit=limit)}


@render_router.get("/api/render/tasks/{task_id}")
def get_render_task(task_id: str, current_user: dict = Depends(get_current_user)):
    task = render_db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="渲染任务不存在")
    return {"task": task}


@render_router.delete("/api/render/tasks/{task_id}")
def delete_render_task(task_id: str, current_user: dict = Depends(get_current_user)):
    if not render_db.delete_task(task_id):
        raise HTTPException(status_code=404, detail="渲染任务不存在")
    return {"ok": True}


@render_router.get("/api/render/files/{path:path}")
def get_render_file(path: str, current_user: dict = Depends(get_current_user)):
    return FileResponse(file_response_path(path))


def _parse_string_list(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        parsed = [part.strip() for part in raw.split(",") if part.strip()]
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]
