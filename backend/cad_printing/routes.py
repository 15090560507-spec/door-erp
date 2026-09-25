from __future__ import annotations

import hmac
import os
import uuid
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from auth import get_current_user
from config import DATA_DIR
from .database import CadPrintDatabase
from .models import (
    CadPrintCreateRequest,
    WorkerDeviceRequest,
    WorkerHeartbeatRequest,
    WorkerStatusRequest,
)
from . import storage


cad_print_router = APIRouter()
_cad_generator: Callable[[dict], tuple[str, bytes]] | None = None
cad_print_db = CadPrintDatabase(
    Path(DATA_DIR) / "cad_print" / "jobs.json",
    Path(DATA_DIR) / "cad_print" / "nodes.json",
    lease_seconds=int(os.environ.get("CAD_PRINT_LEASE_SECONDS", "300")),
    offline_seconds=int(os.environ.get("CAD_PRINT_NODE_OFFLINE_SECONDS", "45")),
)


def configure_cad_generator(generator: Callable[[dict], tuple[str, bytes]]) -> None:
    global _cad_generator
    _cad_generator = generator


def configure_cad_print_database(database: CadPrintDatabase) -> None:
    global cad_print_db
    cad_print_db = database


def _worker_token(x_cad_print_token: str = Header(default="")) -> None:
    expected = os.environ.get("CAD_PRINT_DEVICE_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="CAD 打印节点令牌尚未配置")
    if not x_cad_print_token or not hmac.compare_digest(x_cad_print_token, expected):
        raise HTTPException(status_code=401, detail="CAD 打印节点令牌无效")


def _public_job(item: dict) -> dict:
    result = dict(item)
    result.pop("dxfPath", None)
    result.pop("resultPath", None)
    result.pop("fingerprint", None)
    return result


def _required_job(job_id: str) -> dict:
    item = cad_print_db.get_job(job_id)
    if not item:
        raise HTTPException(status_code=404, detail="CAD 打印任务不存在")
    return item


@cad_print_router.post("/api/cad-print/jobs")
def create_cad_print_job(
    request: CadPrintCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    if _cad_generator is None:
        raise HTTPException(status_code=503, detail="CAD 打印服务尚未初始化")
    try:
        fingerprint, dxf_bytes = _cad_generator(request.params)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"DXF 生成失败：{exc}") from exc

    completed = cad_print_db.find_completed(fingerprint)
    if completed:
        return {"job": _public_job(completed), "reused": True}

    job_id = uuid.uuid4().hex[:16]
    source_path = storage.save_dxf(job_id, dxf_bytes)
    item = cad_print_db.create_job(
        source_task_id=request.sourceTaskId,
        fingerprint=fingerprint,
        dxf_path=str(source_path),
        created_by=str(current_user.get("uid", "")),
        job_id=job_id,
    )
    return {"job": _public_job(item), "reused": False}


@cad_print_router.get("/api/cad-print/jobs")
def list_cad_print_jobs(
    sourceTaskId: str = "",
    limit: int = 30,
    current_user: dict = Depends(get_current_user),
):
    return {"jobs": [_public_job(item) for item in cad_print_db.list_jobs(sourceTaskId, limit)]}


@cad_print_router.get("/api/cad-print/jobs/{job_id}")
def get_cad_print_job(job_id: str, current_user: dict = Depends(get_current_user)):
    return {"job": _public_job(_required_job(job_id))}


@cad_print_router.get("/api/cad-print/jobs/{job_id}/result")
def download_cad_print_result(job_id: str, current_user: dict = Depends(get_current_user)):
    item = _required_job(job_id)
    if item.get("status") != "completed" or not item.get("resultPath"):
        raise HTTPException(status_code=409, detail="CAD 原生 JPG 尚未生成")
    path = Path(item["resultPath"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="CAD 原生 JPG 文件不存在")
    return FileResponse(path, media_type="image/jpeg", filename=f"{job_id}-AutoCAD.jpg")


@cad_print_router.get("/api/cad-print/node-status")
def get_cad_print_node_status(current_user: dict = Depends(get_current_user)):
    device_id = os.environ.get("CAD_PRINT_DEVICE_ID", "win-main").strip() or "win-main"
    return {"node": cad_print_db.node_status(device_id)}


@cad_print_router.post("/api/cad-print/worker/heartbeat", dependencies=[Depends(_worker_token)])
def worker_heartbeat(request: WorkerHeartbeatRequest):
    node = cad_print_db.heartbeat(request.deviceId, request.model_dump())
    return {"node": {**node, "online": True}}


@cad_print_router.post("/api/cad-print/worker/claim", dependencies=[Depends(_worker_token)])
def worker_claim(request: WorkerDeviceRequest):
    item = cad_print_db.claim_next(request.deviceId)
    if not item:
        return {"job": None}
    job = _public_job(item)
    job["dxfUrl"] = f"/api/cad-print/worker/jobs/{item['id']}/dxf"
    return {"job": job}


@cad_print_router.get(
    "/api/cad-print/worker/jobs/{job_id}/dxf",
    dependencies=[Depends(_worker_token)],
)
def worker_download_dxf(job_id: str):
    item = _required_job(job_id)
    path = Path(item.get("dxfPath", ""))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="待打印 DXF 文件不存在")
    return FileResponse(path, media_type="application/dxf", filename=f"{job_id}.dxf")


@cad_print_router.post(
    "/api/cad-print/worker/jobs/{job_id}/status",
    dependencies=[Depends(_worker_token)],
)
def worker_update_status(job_id: str, request: WorkerStatusRequest):
    item = cad_print_db.update_worker_status(
        job_id,
        request.deviceId,
        request.status,
        request.errorStage,
        request.errorMessage,
        request.logTail,
    )
    if not item:
        raise HTTPException(status_code=409, detail="打印任务不属于当前节点或已失效")
    return {"job": _public_job(item)}


@cad_print_router.post(
    "/api/cad-print/worker/jobs/{job_id}/result",
    dependencies=[Depends(_worker_token)],
)
async def worker_upload_result(
    job_id: str,
    deviceId: str = Form(...),
    file: UploadFile = File(...),
):
    item = _required_job(job_id)
    if item.get("deviceId") != deviceId:
        raise HTTPException(status_code=409, detail="打印任务不属于当前节点")
    content = await file.read()
    try:
        path, width, height = storage.save_result(job_id, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    item = cad_print_db.complete_job(
        job_id,
        deviceId,
        result_path=str(path),
        width=width,
        height=height,
        result_url=f"/api/cad-print/jobs/{job_id}/result",
    )
    if not item:
        raise HTTPException(status_code=409, detail="打印任务状态已失效")
    return {"job": _public_job(item)}
