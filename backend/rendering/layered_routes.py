"""分层效果图 / PSD 生成 API（第一版：规则化，不依赖 AI）。"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from config import DATA_DIR

from .layered_render import render_layered_dxf
from .storage import RENDER_FILES_DIR, public_file_url

layered_router = APIRouter()
logger = logging.getLogger(__name__)

RECORDS_PATH = os.path.join(DATA_DIR, "layered_render_records.json")
_records_lock = threading.Lock()


def _shanghai_now() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        return datetime.now(timezone.utc)


class LayeredGenerateRequest(BaseModel):
    taskId: str
    dpi: int = 300
    targetLongEdge: int = 4000
    faces: str = Field("both", description="front / back / both")


# ------------------------- 记录存储（轻量 JSON，第一版够用） -------------------------

def _load_records() -> list[dict[str, Any]]:
    try:
        with open(RECORDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_records(records: list[dict[str, Any]]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with _records_lock:
        with open(RECORDS_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)


def _store_file(data: bytes, suffix: str, filename: str) -> dict[str, str]:
    folder = os.path.join(RENDER_FILES_DIR, "results")
    os.makedirs(folder, exist_ok=True)
    file_id = uuid.uuid4().hex
    saved_name = f"{file_id}{suffix}"
    path = os.path.join(folder, saved_name)
    with open(path, "wb") as handle:
        handle.write(data)
    return {
        "fileId": file_id,
        "filePath": path,
        "fileName": saved_name,
        "originalName": filename,
        "url": public_file_url(path),
    }


# ------------------------- 接口 -------------------------

@layered_router.post("/api/layered-render/generate")
def generate_layered(data: LayeredGenerateRequest, current_user: dict = Depends(get_current_user)):
    import main as main_module  # 延迟导入，避免循环依赖

    task = main_module.task_db.get_task(data.taskId)
    if not task:
        raise HTTPException(status_code=404, detail="图纸任务不存在")

    try:
        req = main_module.CADRequest(**(task.get("params") or {}))
        _key, dxf_bytes, _hit = main_module._cached_cad(req)
    except Exception as exc:
        logger.exception("Layered render: CAD regeneration failed")
        raise HTTPException(status_code=422, detail=f"图纸生成失败: {exc}") from exc

    try:
        result = render_layered_dxf(
            dxf_bytes.decode("utf-8"),
            dpi=data.dpi,
            target_long_edge=data.targetLongEdge,
        )
    except Exception as exc:
        logger.exception("Layered render failed")
        raise HTTPException(status_code=422, detail=f"分层效果图生成失败: {exc}") from exc

    customer = str((task.get("params") or {}).get("dhdw") or "未命名").strip() or "未命名"
    date_str = _shanghai_now().strftime("%Y%m%d")
    safe_customer = "".join(ch for ch in customer if ch not in '\\/:*?"<>|' and not ch.isspace()) or "未命名"

    files = {
        "psd": _store_file(result["psd_bytes"], ".psd", f"{safe_customer}-{date_str}-分层效果图.psd"),
        "complete": _store_file(result["complete_jpg"], ".jpg", f"{safe_customer}-{date_str}-完整订货单.jpg"),
        "front": _store_file(result["front_jpg"], ".jpg", f"{safe_customer}-{date_str}-正面效果图.jpg"),
        "back": _store_file(result["back_jpg"], ".jpg", f"{safe_customer}-{date_str}-反面效果图.jpg"),
    }

    record = {
        "id": uuid.uuid4().hex,
        "taskId": data.taskId,
        "customer": customer,
        "faces": data.faces,
        "dpi": data.dpi,
        "targetLongEdge": data.targetLongEdge,
        "canvasSize": list(result["canvas_size"]),
        "files": {key: {"url": value["url"], "originalName": value["originalName"]} for key, value in files.items()},
        "createdAt": _shanghai_now().isoformat(timespec="seconds"),
        "version": 1,
    }

    records = _load_records()
    records.insert(0, record)
    _save_records(records[:100])

    return {"record": record}


@layered_router.get("/api/layered-render/records")
def list_records(limit: int = 30, current_user: dict = Depends(get_current_user)):
    records = _load_records()
    return {"records": records[: max(1, min(limit, 100))]}


@layered_router.get("/api/layered-render/records/{record_id}")
def get_record(record_id: str, current_user: dict = Depends(get_current_user)):
    for record in _load_records():
        if record.get("id") == record_id:
            return {"record": record}
    raise HTTPException(status_code=404, detail="生成记录不存在")


@layered_router.delete("/api/layered-render/records/{record_id}")
def delete_record(record_id: str, current_user: dict = Depends(get_current_user)):
    records = _load_records()
    target = next((r for r in records if r.get("id") == record_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="生成记录不存在")
    # 删除磁盘文件
    for value in target.get("files", {}).values():
        try:
            url = value.get("url", "")
            marker = "/data/render/files/"
            if marker in url:
                rel = url.split(marker, 1)[1]
                os.remove(os.path.join(RENDER_FILES_DIR, rel))
        except Exception:
            pass
    _save_records([r for r in records if r.get("id") != record_id])
    return {"ok": True}
