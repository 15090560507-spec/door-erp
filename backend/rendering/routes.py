import json
import logging
import os
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .database import render_db
from .cad_line_art import export_dxf_line_art
from .line_art import extract_uploaded_line_art, recrop_uploaded_line_art
from .models import LineArtCropUpdate, RenderAssetUpdate, RenderModelConfigCreate, RenderModelConfigUpdate
from .segmentation import confirm_image_segmentation, create_image_segmentation
from .storage import save_bytes
from .service import create_asset_from_upload, create_render_task_request, execute_component_regeneration, execute_precise_render_task, execute_render_task, file_response_path, generate_task_psd
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
    background_tasks: BackgroundTasks,
    lineArt: UploadFile = File(...),
    styleReference: UploadFile | None = File(None),
    tempAssets: list[UploadFile] | None = File(None),
    modelConfigId: str = Form(...),
    prompt: str = Form(...),
    size: str = Form("original"),
    count: int = Form(1),
    selectedAssetIds: str = Form("[]"),
    renderMode: str = Form("quick"),
    sourceType: str = Form("image"),
    sourceSide: str = Form("front"),
    sourceTaskId: str = Form(""),
    referenceBindings: str = Form("{}"),
    panelReferences: list[UploadFile] | None = File(None),
    trimReferences: list[UploadFile] | None = File(None),
    frameReferences: list[UploadFile] | None = File(None),
    glassReferences: list[UploadFile] | None = File(None),
    hardwareReferences: list[UploadFile] | None = File(None),
    segmentationId: str = Form(""),
    sourceDxf: UploadFile | None = File(None),
    current_user: dict = Depends(get_current_user),
):
    try:
        task, provider_request = await create_render_task_request(
            model_config_id=modelConfigId,
            prompt=prompt,
            size=size,
            count=count,
            selected_asset_ids=_parse_string_list(selectedAssetIds),
            line_art=lineArt,
            style_reference=styleReference,
            temp_assets=tempAssets or [],
            render_mode=renderMode,
            source_type=sourceType,
            source_side=sourceSide,
            source_task_id=sourceTaskId,
            reference_bindings=_parse_object(referenceBindings),
            reference_uploads={
                "panel": panelReferences or [],
                "trim": trimReferences or [],
                "frame": frameReferences or [],
                "glass": glassReferences or [],
                "hardware": hardwareReferences or [],
            },
            segmentation_id=segmentationId,
            source_dxf=sourceDxf,
        )
        executor = execute_precise_render_task if task.get("renderMode") == "precise" else execute_render_task
        background_tasks.add_task(executor, task["id"], provider_request)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Render task failed with unexpected error")
        raise HTTPException(status_code=500, detail={"message": f"效果渲染服务内部错误: {type(exc).__name__}: {exc}"}) from exc
    return {"task": task}


@render_router.get("/api/render/tasks")
def list_render_tasks(sourceTaskId: str = "", limit: int = 30, current_user: dict = Depends(get_current_user)):
    return {"tasks": render_db.list_tasks(limit=limit, source_task_id=sourceTaskId)}


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


@render_router.post("/api/render/tasks/{task_id}/components/{role}/regenerate")
def regenerate_render_component(
    task_id: str,
    role: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    task = render_db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="渲染任务不存在")
    if task.get("renderMode") != "precise" or task.get("status") != "completed":
        raise HTTPException(status_code=409, detail="只有已完成的精准分区任务可以单独重生成部件")
    if role not in {"panel", "trim", "frame", "glass", "hardware"}:
        raise HTTPException(status_code=400, detail="不支持的部件类型")
    render_db.update_task(task_id, {"status": "pending", "errorMessage": ""})
    background_tasks.add_task(execute_component_regeneration, task_id, role)
    return {"task": render_db.get_task(task_id)}


@render_router.post("/api/render/tasks/{task_id}/psd")
def create_task_psd(task_id: str, current_user: dict = Depends(get_current_user)):
    return {"task": generate_task_psd(task_id)}


@render_router.post("/api/render/line-art/extractions")
async def extract_line_art(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传图片为空")
    if len(data) > 40 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="图片不能超过40MB")
    try:
        return {"extraction": extract_uploaded_line_art(data, file.filename or "order-sheet.png")}
    except Exception as exc:
        logger.exception("Line-art extraction failed")
        raise HTTPException(status_code=422, detail=f"线稿提取失败: {exc}") from exc


@render_router.put("/api/render/line-art/extractions/{extraction_id}")
def update_line_art_crop(extraction_id: str, data: LineArtCropUpdate, current_user: dict = Depends(get_current_user)):
    try:
        item = recrop_uploaded_line_art(
            extraction_id,
            data.front.model_dump(),
            data.back.model_dump(),
            data.rotation,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="线稿提取记录不存在") from exc
    except Exception as exc:
        logger.exception("Line-art recrop failed")
        raise HTTPException(status_code=422, detail=f"线稿裁剪失败: {exc}") from exc
    return {"extraction": item}


@render_router.post("/api/render/segmentations")
async def create_segmentation(lineArt: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    if not (lineArt.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="区域识别只支持图片线稿")
    content = await lineArt.read()
    if not content:
        raise HTTPException(status_code=400, detail="线稿图片为空")
    try:
        return {"segmentation": create_image_segmentation(content, lineArt.filename or "line-art.png")}
    except Exception as exc:
        logger.exception("Image segmentation failed")
        raise HTTPException(status_code=422, detail=f"部件区域识别失败: {exc}") from exc


@render_router.post("/api/render/line-art/dxf")
async def extract_dxf_upload(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="DXF 文件为空")
    if len(content) > 40 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="DXF 文件不能超过40MB")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("gb18030", errors="ignore")
    try:
        views = export_dxf_line_art(text)
        source = save_bytes(content, file.filename or "source.dxf", "temp")
        return {"extraction": {
            "id": source["fileId"],
            "sourceType": "dxf",
            "sourceUrl": "",
            "front": views["front"],
            "back": views["back"],
            "reviewRequired": False,
            "warnings": [],
        }}
    except Exception as exc:
        logger.exception("DXF line-art extraction failed")
        raise HTTPException(status_code=422, detail=f"DXF 线稿提取失败: {exc}") from exc


@render_router.put("/api/render/segmentations/{segmentation_id}")
async def update_segmentation(
    segmentation_id: str,
    panelMask: UploadFile | None = File(None),
    trimMask: UploadFile | None = File(None),
    frameMask: UploadFile | None = File(None),
    glassMask: UploadFile | None = File(None),
    hardwareMask: UploadFile | None = File(None),
    current_user: dict = Depends(get_current_user),
):
    uploads = {}
    for role, upload in {
        "panel": panelMask,
        "trim": trimMask,
        "frame": frameMask,
        "glass": glassMask,
        "hardware": hardwareMask,
    }.items():
        if upload:
            uploads[role] = await upload.read()
    try:
        return {"segmentation": confirm_image_segmentation(segmentation_id, uploads)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="区域识别记录不存在") from exc
    except Exception as exc:
        logger.exception("Image segmentation update failed")
        raise HTTPException(status_code=422, detail=f"部件区域保存失败: {exc}") from exc


@render_router.get("/api/render/files/{path:path}")
def get_render_file(
    path: str,
    download: str = "",
    name: str = "",
    current_user: dict = Depends(get_current_user),
):
    """返回渲染文件；download=1 时按附件下载（带原始文件名）。"""
    response = FileResponse(file_response_path(path))
    if download:
        safe_name = "".join(ch for ch in (name or os.path.basename(path)) if ch not in '\\/:*?"<>|').strip() or "download"
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(safe_name)}"
    return response


def _parse_string_list(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        parsed = [part.strip() for part in raw.split(",") if part.strip()]
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _parse_object(raw: str) -> dict:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
