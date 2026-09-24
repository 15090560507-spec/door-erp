import base64
import copy
import logging
import os
import urllib.request
from typing import Iterable

import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image
from psd_tools.constants import Compression

from .database import render_db
from .database import utc_now_iso
from .image_geometry import encode_jpeg
from .layered_render import DxfGeometryValidationError
from .providers import ProviderError, RenderProviderRequest, get_provider
from .storage import RENDER_FILES_DIR, public_file_url, save_bytes

OUTPUT_IMAGE_COUNT = 1
logger = logging.getLogger(__name__)


def _resolve_render_size(render_mode: str, requested: str | None) -> str:
    value = str(requested or "").lower()
    if value in {"", "original", "auto"}:
        return "4k" if render_mode == "precise" else "2k"
    return value


def _effective_prompt(prompt: str, render_mode: str) -> str:
    mode_rule = "精准模式中部件位置和外轮廓必须严格服从已确认区域。" if render_mode == "precise" else "严格保持原门体比例、布局和部件位置。"
    policy = (
        "输出清晰、真实的门类产品效果图；"
        f"{mode_rule}"
        "最终图片不显示线稿、尺寸线、文字、标注箭头或辅助轮廓；"
        "玻璃和五金位于门扇表面上方，接缝仅表现为真实窄黑缝。"
    )
    return f"{prompt.strip()}\n{policy}" if prompt.strip() else policy


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

    resolved_size = _resolve_render_size("quick", size)
    effective_prompt = _effective_prompt(prompt, "quick")
    task = render_db.create_task({
        "modelConfigId": model_config_id,
        "modelConfigSnapshot": _config_snapshot(config),
        "prompt": effective_prompt,
        "size": resolved_size,
        "count": OUTPUT_IMAGE_COUNT,
        "selectedAssetIds": selected_asset_ids,
        "files": [line_info] + ([style_info] if style_info else []) + temp_infos,
    })
    render_db.update_task(task["id"], {"status": "running", "startedAt": utc_now_iso()})
    provider_request = RenderProviderRequest(
        config=config,
        prompt=effective_prompt,
        size=resolved_size,
        count=OUTPUT_IMAGE_COUNT,
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
            "raw": _success_raw_summary(response.get("raw")),
            "finishedAt": utc_now_iso(),
        })
        return updated or task
    except ProviderError as exc:
        updated = render_db.update_task(task["id"], {
            "status": "failed",
            "errorType": exc.error_type,
            "errorMessage": exc.message,
            "upstreamRawError": exc.raw,
            "finishedAt": utc_now_iso(),
        })
        raise HTTPException(status_code=exc.status_code, detail={"task": updated, "errorType": exc.error_type, "message": exc.message, "raw": exc.raw}) from exc


async def create_render_task_request(
    model_config_id: str,
    prompt: str,
    size: str,
    count: int,
    selected_asset_ids: list[str],
    line_art: UploadFile,
    style_reference: UploadFile | None,
    temp_assets: Iterable[UploadFile],
    render_mode: str = "quick",
    source_type: str = "image",
    source_side: str = "front",
    source_task_id: str = "",
    reference_bindings: dict | None = None,
    reference_uploads: dict[str, Iterable[UploadFile]] | None = None,
    segmentation_id: str = "",
    source_dxf: UploadFile | None = None,
) -> tuple[dict, RenderProviderRequest]:
    config = render_db.get_model_config(model_config_id, include_secret=True)
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    if not config.get("enabled"):
        raise HTTPException(status_code=400, detail="模型配置未启用")
    if not config.get("apiKey"):
        raise HTTPException(status_code=400, detail="模型配置缺少 API Key")

    line_info = await save_upload_info(line_art, "line_art", "temp")
    style_info = await save_upload_info(style_reference, "style_reference", "temp") if style_reference else None
    dxf_info = None
    if source_dxf:
        dxf_content = await source_dxf.read()
        if not dxf_content:
            raise HTTPException(status_code=400, detail="DXF 文件为空")
        if len(dxf_content) > 40 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="DXF 文件不能超过40MB")
        saved_dxf = save_bytes(dxf_content, source_dxf.filename or "source.dxf", "temp")
        dxf_info = {**saved_dxf, "role": "source_dxf", "mimeType": "application/dxf"}

    normalized_bindings = _normalize_reference_bindings(reference_bindings, selected_asset_ids)
    bound_asset_roles = {
        asset_id: role
        for role, binding in normalized_bindings.items()
        for asset_id in binding["assetIds"]
    }
    library_assets = []
    all_asset_ids = list(dict.fromkeys(selected_asset_ids + list(bound_asset_roles)))
    for asset_id in all_asset_ids:
        asset = render_db.get_asset(asset_id)
        if asset:
            target_role = bound_asset_roles.get(asset_id) or _role_for_category(asset.get("category", ""))
            library_assets.append({
                **asset,
                "role": "reference",
                "targetRole": target_role,
                "category": _role_label(target_role),
                "assetId": asset["id"],
                "mimeType": _guess_mime(asset.get("filePath", "")),
                "originalName": asset.get("name", "asset"),
            })

    temp_infos = []
    for index, upload in enumerate(temp_assets or []):
        if upload and upload.filename:
            temp_infos.append(await save_upload_info(upload, "temp_asset", "temp", category=f"临时配件{index + 1}"))

    bound_upload_infos: list[dict] = []
    for role, uploads in (reference_uploads or {}).items():
        if role not in normalized_bindings:
            continue
        for upload in uploads or []:
            if not upload or not upload.filename:
                continue
            info = await save_upload_info(upload, "component_reference", "temp", category=_role_label(role))
            info["targetRole"] = role
            bound_upload_infos.append(info)
            normalized_bindings[role]["files"].append(info)

    if style_info:
        style_info["targetRole"] = "panel"
        style_info["category"] = _role_label("panel")
        normalized_bindings["panel"]["files"].append(style_info)
    for info in temp_infos:
        info["targetRole"] = "hardware"
        normalized_bindings["hardware"]["files"].append(info)

    segmentation = render_db.get_segmentation(segmentation_id) if segmentation_id else {}
    if render_mode == "precise" and source_type == "image" and (not segmentation or not segmentation.get("confirmed")):
        raise HTTPException(status_code=409, detail="普通图片精准模式需要先识别并确认部件区域")

    normalized_mode = render_mode if render_mode in {"quick", "precise"} else "quick"
    resolved_size = _resolve_render_size(normalized_mode, size)
    effective_prompt = _effective_prompt(prompt, normalized_mode)
    task = render_db.create_task({
        "modelConfigId": model_config_id,
        "modelConfigSnapshot": _config_snapshot(config),
        "prompt": effective_prompt,
        "size": resolved_size,
        "count": OUTPUT_IMAGE_COUNT,
        "selectedAssetIds": selected_asset_ids,
        "files": [line_info] + ([dxf_info] if dxf_info else []) + ([style_info] if style_info else []) + temp_infos + bound_upload_infos,
        "renderMode": normalized_mode,
        "sourceType": source_type if source_type in {"task", "dxf", "image"} else "image",
        "sourceSide": source_side if source_side in {"front", "back"} else "front",
        "sourceTaskId": source_task_id,
        "referenceBindings": normalized_bindings,
        "segmentation": segmentation or {},
    })
    provider_request = RenderProviderRequest(
        config=config,
        prompt=effective_prompt,
        size=resolved_size,
        count=OUTPUT_IMAGE_COUNT,
        line_art=line_info,
        style_reference=style_info,
        assets=library_assets,
        temp_assets=bound_upload_infos + temp_infos,
    )
    return task, provider_request


def _normalize_reference_bindings(raw: dict | None, legacy_asset_ids: list[str]) -> dict:
    roles = ("panel", "trim", "frame", "glass", "hardware")
    bindings = {role: {"assetIds": [], "files": []} for role in roles}
    if isinstance(raw, dict):
        for role in roles:
            value = raw.get(role, {})
            ids = value.get("assetIds", []) if isinstance(value, dict) else value
            if isinstance(ids, list):
                bindings[role]["assetIds"] = list(dict.fromkeys(str(item) for item in ids if str(item)))
    assigned = {item for binding in bindings.values() for item in binding["assetIds"]}
    bindings["hardware"]["assetIds"].extend(item for item in legacy_asset_ids if item not in assigned)
    return bindings


def _role_for_category(category: str) -> str:
    if category in {"门扇", "款式", "颜色", "纹理"}:
        return "panel"
    if category in {"包套", "门头"}:
        return "trim"
    if category == "门框":
        return "frame"
    if category == "玻璃":
        return "glass"
    return "hardware"


def _role_label(role: str) -> str:
    return {
        "panel": "门扇款式",
        "trim": "门套/门头门柱",
        "frame": "门框材质",
        "glass": "玻璃",
        "hardware": "五金配件",
    }.get(role, "其他")


def execute_render_task(task_id: str, provider_request: RenderProviderRequest) -> dict | None:
    render_db.update_task(task_id, {"status": "running", "startedAt": utc_now_iso()})
    try:
        response = get_provider(provider_request.config.get("provider")).render(provider_request)
        images = _persist_results(task_id, response.get("images", []))
        return render_db.update_task(task_id, {
            "status": "completed",
            "images": images,
            "raw": _success_raw_summary(response.get("raw")),
            "finishedAt": utc_now_iso(),
        })
    except ProviderError as exc:
        return render_db.update_task(task_id, {
            "status": "failed",
            "errorType": exc.error_type,
            "errorMessage": exc.message,
            "upstreamRawError": exc.raw,
            "finishedAt": utc_now_iso(),
        })
    except Exception as exc:
        logger.exception("Render background task failed")
        return render_db.update_task(task_id, {
            "status": "failed",
            "errorType": "internal_error",
            "errorMessage": f"效果渲染服务内部错误: {type(exc).__name__}: {exc}",
            "finishedAt": utc_now_iso(),
        })


def execute_precise_render_task(task_id: str, provider_request: RenderProviderRequest) -> dict | None:
    task = render_db.get_task(task_id)
    if not task:
        return None
    render_db.update_task(task_id, {"status": "running", "startedAt": utc_now_iso()})
    try:
        references: dict[str, list[dict]] = {role: [] for role in ("panel", "trim", "frame", "glass", "hardware")}
        for item in provider_request.assets + provider_request.temp_assets:
            role = str(item.get("targetRole") or "hardware")
            references.setdefault(role, []).append(item)
        side = task.get("sourceSide", "front")
        if task.get("sourceType") in {"task", "dxf"}:
            from .layered_render import render_layered_dxf
            if task.get("sourceType") == "task" and task.get("sourceTaskId"):
                import main as main_module
                drawing_task = main_module.task_db.get_task(task["sourceTaskId"])
                if not drawing_task:
                    raise ValueError("关联的图纸任务不存在")
                request = main_module.CADRequest(**(drawing_task.get("params") or {}))
                _cache_key, dxf_bytes, _cache_hit = main_module._cached_cad(request)
            else:
                dxf_info = next((item for item in task.get("files", []) if item.get("role") == "source_dxf"), None)
                if not dxf_info or not dxf_info.get("filePath"):
                    raise ValueError("上传的 DXF 文件不存在")
                with open(dxf_info["filePath"], "rb") as handle:
                    dxf_bytes = handle.read()
            result = render_layered_dxf(
                _decode_dxf(dxf_bytes),
                target_long_edge=_target_long_edge(task.get("size", "original")),
                ai_config=provider_request.config,
                reference_bindings=references,
                include_psd=False,
                selected_side=side,
            )
            final_bytes = result.get("selected_jpg")
            layer_pngs = result.get("selected_layer_pngs")
            if not final_bytes or not layer_pngs:
                raise ValueError(f"精准模式未生成有效的{side}单面图层")
            segmentation = {"source": "dxf", "confirmed": True, "confidence": 1.0}
        else:
            from .precise_render import render_precise_image

            segmentation = task.get("segmentation") or {}
            if not segmentation.get("confirmed"):
                raise ValueError("普通图片精准模式需要先完成区域识别与确认")
            line_info = next((item for item in task.get("files", []) if item.get("role") == "line_art"), None)
            if not line_info or not line_info.get("filePath"):
                raise ValueError("精准模式线稿文件不存在")
            result = render_precise_image(
                line_info["filePath"],
                segmentation.get("masks", {}),
                provider_request.config,
                references,
                target_long_edge=_target_long_edge(task.get("size", "4k")),
            )
            final_bytes = result["image_bytes"]
            layer_pngs = result["layer_pngs"]
        final_saved = save_bytes(final_bytes, f"{task_id}-{side}-precise.jpg", "results")
        final_image = {
            "id": f"{task_id}-1",
            "type": "file",
            "src": final_saved["url"],
            "filePath": final_saved["filePath"],
        }
        component_layers = {}
        for role, content in layer_pngs.items():
            saved = save_bytes(content, f"{task_id}-{role}.png", "results")
            component_layers[role] = {
                "currentVersion": 1,
                "versions": [{
                    "version": 1,
                    "url": saved["url"],
                    "filePath": saved["filePath"],
                    "originalName": saved["originalName"],
                }],
            }
        return render_db.update_task(task_id, {
            "status": "completed",
            "images": [final_image],
            "compositeImage": final_image,
            "componentLayers": component_layers,
            "segmentation": segmentation,
            "materialMode": result.get("material_mode", "flat"),
            "materialNote": result.get("material_note", ""),
            "geometryManifest": result.get("geometry_manifest"),
            "geometryValidation": result.get("geometry_validation"),
            "finishedAt": utc_now_iso(),
        })
    except DxfGeometryValidationError as exc:
        logger.warning("DXF geometry validation failed for render task %s", task_id)
        return render_db.update_task(task_id, {
            "status": "failed",
            "errorType": "dxf_geometry_validation",
            "errorMessage": f"DXF 结构检查未通过: {exc}",
            "geometryManifest": exc.geometry_manifest,
            "geometryValidation": exc.geometry_validation,
            "finishedAt": utc_now_iso(),
        })
    except Exception as exc:
        logger.exception("Precise render background task failed")
        return render_db.update_task(task_id, {
            "status": "failed",
            "errorType": "precise_render_error",
            "errorMessage": f"精准分区生成失败: {exc}",
            "finishedAt": utc_now_iso(),
        })


def execute_component_regeneration(task_id: str, role: str) -> dict | None:
    task = render_db.get_task(task_id)
    if not task:
        return None
    allowed = {"panel", "trim", "frame", "glass", "hardware"}
    if role not in allowed:
        return render_db.update_task(task_id, {"status": "failed", "errorMessage": "不支持的部件类型"})
    config = render_db.get_model_config(task.get("modelConfigId", ""), include_secret=True)
    if not config or not config.get("enabled") or not config.get("apiKey"):
        return render_db.update_task(task_id, {"status": "failed", "errorMessage": "当前渲染模型不可用"})
    render_db.update_task(task_id, {
        "status": "running",
        "errorType": "",
        "errorMessage": "",
        "upstreamRawError": "",
        "startedAt": utc_now_iso(),
    })
    try:
        references = _task_references(task)
        if not references.get(role):
            raise ValueError(f"{_role_label(role)}没有可用参考图")
        side = task.get("sourceSide", "front")
        single_binding = {name: (references.get(name, []) if name == role else []) for name in allowed}
        if task.get("sourceType") in {"task", "dxf"}:
            from .layered_render import render_layered_dxf
            if task.get("sourceType") == "task" and task.get("sourceTaskId"):
                import main as main_module
                drawing_task = main_module.task_db.get_task(task["sourceTaskId"])
                if not drawing_task:
                    raise ValueError("关联的图纸任务不存在")
                request = main_module.CADRequest(**(drawing_task.get("params") or {}))
                _cache_key, dxf_bytes, _cache_hit = main_module._cached_cad(request)
            else:
                dxf_info = next((item for item in task.get("files", []) if item.get("role") == "source_dxf"), None)
                if not dxf_info or not dxf_info.get("filePath"):
                    raise ValueError("上传的 DXF 文件不存在")
                with open(dxf_info["filePath"], "rb") as handle:
                    dxf_bytes = handle.read()
            result = render_layered_dxf(
                _decode_dxf(dxf_bytes),
                target_long_edge=_target_long_edge(task.get("size", "original")),
                ai_config=config,
                reference_bindings=single_binding,
                include_psd=False,
                selected_side=side,
            )
            layer_pngs = result.get("selected_layer_pngs") or {}
        else:
            from .precise_render import render_precise_image

            line_info = next((item for item in task.get("files", []) if item.get("role") == "line_art"), None)
            segmentation = task.get("segmentation") or {}
            if not line_info or not segmentation.get("confirmed"):
                raise ValueError("精准任务缺少已确认的线稿区域")
            result = render_precise_image(
                line_info["filePath"],
                segmentation.get("masks", {}),
                config,
                single_binding,
                target_long_edge=_target_long_edge(task.get("size", "4k")),
            )
            layer_pngs = result["layer_pngs"]

        content = layer_pngs.get(role)
        if not content:
            raise ValueError(f"{_role_label(role)}图层生成失败")
        layers = copy.deepcopy(task.get("componentLayers") or {})
        role_data = layers.setdefault(role, {"currentVersion": 0, "versions": []})
        next_version = max([int(item.get("version", 0)) for item in role_data.get("versions", [])] + [0]) + 1
        saved = save_bytes(content, f"{task_id}-{role}-v{next_version}.png", "results")
        role_data.setdefault("versions", []).append({
            "version": next_version,
            "url": saved["url"],
            "filePath": saved["filePath"],
            "originalName": saved["originalName"],
        })
        role_data["currentVersion"] = next_version
        final_image = _compose_component_layers(task_id, layers)
        return render_db.update_task(task_id, {
            "status": "completed",
            "errorType": "",
            "errorMessage": "",
            "upstreamRawError": "",
            "componentLayers": layers,
            "images": [final_image],
            "compositeImage": final_image,
            "psdStatus": "not_requested",
            "psdFile": None,
            "finishedAt": utc_now_iso(),
        })
    except Exception as exc:
        logger.exception("Component regeneration failed")
        return render_db.update_task(task_id, {
            "status": "completed",
            "errorType": "component_regeneration_error",
            "errorMessage": f"{_role_label(role)}重新生成失败: {exc}",
            "finishedAt": utc_now_iso(),
        })


def generate_task_psd(task_id: str) -> dict:
    task = render_db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="渲染任务不存在")
    if task.get("renderMode") != "precise" or task.get("status") != "completed":
        raise HTTPException(status_code=409, detail={"code": "PRECISE_RENDER_REQUIRED", "message": "快速 AI 结果需要先转为精准分区生成，才能生成可靠的分层 PSD"})
    layers = task.get("componentLayers") or {}
    first = _current_layer_image(layers, "panel") or _current_layer_image(layers, "frame") or _current_layer_image(layers, "trim")
    if first is None:
        raise HTTPException(status_code=422, detail="当前精准任务没有可用部件图层")
    width, height = first.size
    source_info = next((item for item in task.get("files", []) if item.get("role") == "line_art"), None)
    if source_info and source_info.get("filePath") and os.path.exists(source_info["filePath"]):
        source = Image.open(source_info["filePath"]).convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
    else:
        source = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    transparent = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    background = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    from .psd_writer import PsdNode, write_psd

    def layer_or_blank(role: str) -> Image.Image:
        image = _current_layer_image(layers, role)
        return image if image is not None else transparent.copy()

    nodes = [
        PsdNode("01_原始线稿", source, visible=False),
        PsdNode("02_门套与门头门柱", layer_or_blank("trim")),
        PsdNode("03_门框", layer_or_blank("frame")),
        PsdNode("04_门扇", layer_or_blank("panel")),
        PsdNode("05_玻璃", layer_or_blank("glass")),
        PsdNode("06_拉手与锁具", layer_or_blank("hardware")),
        PsdNode("07_其他五金", transparent.copy()),
        PsdNode("08_阴影与高光", layer_or_blank("lighting")),
        PsdNode("09_背景", background),
    ]
    render_db.update_task(task_id, {"psdStatus": "generating"})
    try:
        content = write_psd(nodes, (width, height), dpi=300, compression=Compression.ZIP)
        saved = save_bytes(content, f"{task_id}-分层效果图.psd", "results")
        psd_file = {"url": saved["url"], "filePath": saved["filePath"], "originalName": saved["originalName"]}
        return render_db.update_task(task_id, {"psdStatus": "completed", "psdFile": psd_file}) or task
    except Exception as exc:
        render_db.update_task(task_id, {"psdStatus": "failed", "errorMessage": f"PSD 生成失败: {exc}"})
        raise HTTPException(status_code=422, detail=f"PSD 生成失败: {exc}") from exc


def _current_layer_image(layers: dict, role: str) -> Image.Image | None:
    role_data = layers.get(role) or {}
    version = role_data.get("currentVersion")
    current = next((item for item in role_data.get("versions", []) if item.get("version") == version), None)
    if not current or not current.get("filePath") or not os.path.exists(current["filePath"]):
        return None
    return Image.open(current["filePath"]).convert("RGBA")


def _task_references(task: dict) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {role: [] for role in ("panel", "trim", "frame", "glass", "hardware")}
    for role, binding in (task.get("referenceBindings") or {}).items():
        if role not in result or not isinstance(binding, dict):
            continue
        for asset_id in binding.get("assetIds", []):
            asset = render_db.get_asset(str(asset_id))
            if asset:
                result[role].append({
                    **asset,
                    "role": "reference",
                    "targetRole": role,
                    "category": _role_label(role),
                    "assetId": asset["id"],
                    "mimeType": _guess_mime(asset.get("filePath", "")),
                    "originalName": asset.get("name", "asset"),
                })
        for item in binding.get("files", []):
            if isinstance(item, dict) and item.get("filePath"):
                result[role].append(item)
    return result


def _compose_component_layers(task_id: str, layers: dict) -> dict:
    ordered = ("seam", "trim", "frame", "panel", "glass", "hardware", "lighting")
    images: list[tuple[str, Image.Image]] = []
    for role in ordered:
        role_data = layers.get(role) or {}
        version = role_data.get("currentVersion")
        current = next((item for item in role_data.get("versions", []) if item.get("version") == version), None)
        if current and current.get("filePath") and os.path.exists(current["filePath"]):
            images.append((role, Image.open(current["filePath"]).convert("RGBA")))
    if not images:
        raise ValueError("没有可合成的部件图层")
    width, height = images[0][1].size
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    for role, image in images:
        if image.size != (width, height):
            raise ValueError(f"{role} 图层尺寸 {image.width}x{image.height} 与共享画布 {width}x{height} 不一致")
        canvas.alpha_composite(image)
    output = encode_jpeg(np.array(canvas, dtype=np.uint8), quality=95)
    saved = save_bytes(output, f"{task_id}-composite.jpg", "results")
    return {"id": f"{task_id}-1", "type": "file", "src": saved["url"], "filePath": saved["filePath"]}


def _target_long_edge(size: str) -> int:
    value = str(size or "original").lower()
    if value == "4k":
        return 4096
    if value == "2k":
        return 2048
    if "x" in value:
        try:
            return max(int(part) for part in value.split("x", 1))
        except ValueError:
            pass
    return 1600


def _decode_dxf(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("gb18030", errors="ignore")


def _persist_results(task_id: str, images: list[dict]) -> list[dict]:
    results = []
    for index, image in enumerate((images or [])[:OUTPUT_IMAGE_COUNT]):
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
    try:
        inside_root = os.path.commonpath([root, full_path]) == root
    except ValueError:
        inside_root = False
    if not inside_root or not os.path.isfile(full_path):
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
    return OUTPUT_IMAGE_COUNT


def _config_snapshot(config: dict) -> dict:
    return {
        "name": config.get("name", ""),
        "provider": config.get("provider", ""),
        "baseUrl": config.get("baseUrl", ""),
        "model": config.get("model", ""),
        "endpoint": config.get("endpoint", ""),
        "apiType": config.get("apiType", ""),
    }


def _success_raw_summary(raw) -> dict:
    if isinstance(raw, dict):
        return {"omitted": True, "keys": list(raw.keys())[:20]}
    if isinstance(raw, list):
        return {"omitted": True, "items": len(raw)}
    return {"omitted": True}
