import base64
import os
import urllib.request
from datetime import datetime
from typing import Iterable

from fastapi import HTTPException, UploadFile

from .database import render_db
from .providers import ProviderError, RenderProviderRequest, get_provider
from .storage import RENDER_FILES_DIR, public_file_url, save_bytes


async def save_upload_info(file: UploadFile, role: str, subdir: str = "temp", category: str = "", asset_id: str = "") -> dict:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"{role} 文件为空")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail=f"{role} 只支持图片")
    saved = save_bytes(content, file.filename or f"{role}.png", subdir)
    return {
        "id": saved["fileId"],
        "role": role,
        "category": category,
        "assetId": asset_id,
        "filePath": saved["filePath"],
        "thumbnailPath": saved["thumbnailPath"],
        "url": saved["url"],
        "thumbnailUrl": saved["thumbnailUrl"],
        "originalName": saved["originalName"],
        "mimeType": file.content_type or "image/png",
        "temporary": subdir != "library",
    }


async def create_asset_from_upload(file: UploadFile, name: str, category: str, tags: list[str], remark: str, favorite: bool) -> dict:
    file_info = await save_upload_info(file, "library_asset", "library", category)
    return render_db.create_asset({
        "name": name or file_info["originalName"],
        "category": category or "其他",
        "filePath": file_info["filePath"],
        "thumbnailPath": file_info["thumbnailPath"],
        "url": file_info["url"],
        "thumbnailUrl": file_info["thumbnailUrl"],
        "tags": tags,
        "remark": remark,
        "favorite": favorite,
        "originalName": file_info["originalName"],
    })


async def run_render_task(
    model_config_id: str,
    prompt: str,
    size: str,
    count: int,
    selected_asset_ids: list[str],
    line_art: UploadFile,
    style_reference: UploadFile | None,
    temp_assets: Iterable[UploadFile],
) -> dict:
    config = render_db.get_model_config(model_config_id, include_secret=True)
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    if not config.get("enabled"):
        raise HTTPException(status_code=400, detail="模型配置未启用")
    if not config.get("apiKey"):
        raise HTTPException(status_code=400, detail="模型配置缺少 API Key")
    line_info = await save_upload_info(line_art, "line_art", "temp")
    style_info = await save_upload_info(style_reference, "style_reference", "temp") if style_reference else None
    library_assets = []
    for asset_id in selected_asset_ids:
        asset = render_db.get_asset(asset_id)
        if asset:
            library_assets.append({
                **asset,
                "role": "asset",
                "assetId": asset["id"],
                "mimeType": _guess_mime(asset.get("filePath", "")),
                "originalName": asset.get("name", "asset"),
            })
    temp_infos = []
    for index, upload in enumerate(temp_assets or []):
        if upload and upload.filename:
            temp_infos.append(await save_upload_info(upload, "temp_asset", "temp", category=f"临时配件{index + 1}"))

    task = render_db.create_task({
        "modelConfigId": model_config_id,
        "prompt": prompt,
        "size": size or config.get("defaultSize", "original"),
        "count": _clamp_count(count),
        "selectedAssetIds": selected_asset_ids,
        "files": [line_info] + ([style_info] if style_info else []) + temp_infos,
    })
    render_db.update_task(task["id"], {"status": "running", "startedAt": datetime.now().isoformat()})
    provider_request = RenderProviderRequest(
        config=config,
        prompt=prompt,
        size=size or config.get("defaultSize", "original"),
        count=_clamp_count(count),
        line_art=line_info,
        style_reference=style_info,
        assets=library_assets,
        temp_assets=temp_infos,
    )
    try:
        response = get_provider(config.get("provider")).render(provider_request)
        images = _persist_results(task["id"], response.get("images", []))
        updated = render_db.update_task(task["id"], {
            "status": "completed",
            "images": images,
            "raw": response.get("raw"),
            "finishedAt": datetime.now().isoformat(),
        })
        return updated or task
    except ProviderError as exc:
        updated = render_db.update_task(task["id"], {
            "status": "failed",
            "errorType": exc.error_type,
            "errorMessage": exc.message,
            "upstreamRawError": exc.raw,
            "finishedAt": datetime.now().isoformat(),
        })
        raise HTTPException(status_code=exc.status_code, detail={"task": updated, "errorType": exc.error_type, "message": exc.message, "raw": exc.raw}) from exc


def _persist_results(task_id: str, images: list[dict]) -> list[dict]:
    results = []
    for index, image in enumerate(images):
        image_type = image.get("type")
        src = image.get("src", "")
        file_path = ""
        if image_type == "b64_json" and src:
            raw = src.split(",", 1)[1] if "," in src else src
            saved = save_bytes(base64.b64decode(raw), f"{task_id}_{index + 1}.png", "results")
            src = saved["url"]
            file_path = saved["filePath"]
            image_type = "file"
        elif image_type == "url" and src:
            saved = _try_save_remote_image(src, task_id, index)
            if saved:
                src = saved["url"]
                file_path = saved["filePath"]
                image_type = "file"
        results.append({"id": f"{task_id}-{index + 1}", "type": image_type or "url", "src": src, "filePath": file_path})
    return results


def file_response_path(path: str) -> str:
    full_path = os.path.abspath(os.path.join(RENDER_FILES_DIR, path))
    root = os.path.abspath(RENDER_FILES_DIR)
    if not full_path.startswith(root) or not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return full_path


def _try_save_remote_image(url: str, task_id: str, index: int) -> dict | None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "DoorERP-Render/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                return None
            data = response.read()
        ext = ".jpg" if "jpeg" in content_type or "jpg" in content_type else ".png"
        return save_bytes(data, f"{task_id}_{index + 1}{ext}", "results")
    except Exception:
        return None


def _guess_mime(path: str) -> str:
    ext = os.path.splitext(path or "")[1].lower()
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    return "image/png"


def _clamp_count(count: int) -> int:
    try:
        value = int(count)
    except Exception:
        value = 1
    return min(max(value, 1), 4)

