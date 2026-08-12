"""Authenticated API routes for the door-unit fulfillment center."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user
from fulfillment_database import FulfillmentDatabase
from fulfillment_models import (
    ChangeCreate,
    ExceptionCreate,
    ExceptionResolve,
    FinishedInboundCreate,
    FulfillmentReleaseRequest,
    InspectionCreate,
    PaymentCreate,
    ShipmentCreate,
    ShipmentSign,
    SupplyAction,
    TechnicalPackageUpdate,
    WorkPackageAction,
)


router = APIRouter(prefix="/api/fulfillment", tags=["fulfillment"])
fulfillment_db = FulfillmentDatabase()
task_repository: Any = None
user_repository: Any = None


def configure_task_repository(repository: Any) -> None:
    global task_repository
    task_repository = repository


def configure_user_repository(repository: Any) -> None:
    global user_repository
    user_repository = repository


def source_revision(task: Dict[str, Any]) -> str:
    payload = {
        "task_id": task.get("id"),
        "status": task.get("status"),
        "params": task.get("params") or {},
        "review_feedback": task.get("review_feedback", ""),
        "history": task.get("history", []),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _review_summary(task: Dict[str, Any]) -> tuple[str, str]:
    for entry in reversed(task.get("history") or []):
        if not isinstance(entry, dict):
            continue
        action = str(entry.get("action") or entry.get("status") or "")
        if "终审" in action or "通过" in action:
            return str(entry.get("time") or entry.get("created_at") or ""), str(entry.get("user") or entry.get("operator") or "")
    return str(task.get("updated_at") or task.get("date") or ""), ""


def pending_release_tasks() -> List[Dict[str, Any]]:
    if task_repository is None:
        return []
    rows: List[Dict[str, Any]] = []
    for task in task_repository.load_all_tasks():
        if task.get("status") != "已通过":
            continue
        revision = source_revision(task)
        if fulfillment_db.source_is_released(str(task.get("id") or ""), revision):
            continue
        params = task.get("params") or {}
        approved_at, approved_by = _review_summary(task)
        rows.append({
            "task_id": str(task.get("id") or ""),
            "source_revision": revision,
            "status": "待下达",
            "customer": str(params.get("dhdw") or task.get("customer") or ""),
            "project": str(params.get("gdmc") or task.get("project") or ""),
            "product_name": str(params.get("product_name") or params.get("door_type") or ""),
            "door_type": str(params.get("door_type") or ""),
            "width": params.get("dw"),
            "height": params.get("dh"),
            "opening": f"{params.get('sel_kx') or ''}{params.get('sel_nk') or ''}",
            "approved_at": approved_at,
            "approved_by": approved_by,
        })
    rows.sort(key=lambda item: item["approved_at"], reverse=True)
    return rows


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, sqlite3.IntegrityError):
        return HTTPException(status_code=409, detail="该终审版本已经下达，请在原订单中增加或复制门樘")
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=f"生产履约操作失败：{exc}")


@router.get("/dashboard")
def dashboard(current_user: Dict = Depends(get_current_user)):
    data = fulfillment_db.dashboard()
    data["pending_release"] = len(pending_release_tasks())
    return data


@router.get("/people")
def people(current_user: Dict = Depends(get_current_user)):
    if user_repository is None:
        return {"people": []}
    users = user_repository.load_all_users()
    rows = [
        {"uid": str(uid), "name": str(info.get("name") or uid), "role": str(info.get("role") or "")}
        for uid, info in users.items()
    ]
    rows.sort(key=lambda item: (item["name"], item["uid"]))
    return {"people": rows}


@router.get("/pending-release")
def pending_release(current_user: Dict = Depends(get_current_user)):
    return {"tasks": pending_release_tasks()}


@router.post("/orders/from-task/{task_id}")
def release_order(task_id: str, req: FulfillmentReleaseRequest, current_user: Dict = Depends(get_current_user)):
    if task_repository is None:
        raise HTTPException(status_code=503, detail="图纸任务库尚未连接")
    task = task_repository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="图纸任务不存在")
    if task.get("status") != "已通过":
        raise HTTPException(status_code=409, detail="图纸尚未终审通过，不能下达生产")
    params = task.get("params") or {}
    required = {"product_name": "产品名称", "door_type": "门型"}
    missing = [label for key, label in required.items() if not str(params.get(key) or "").strip()]
    if missing:
        raise HTTPException(status_code=400, detail=f"下达生产前请补充：{'、'.join(missing)}")
    try:
        order = fulfillment_db.create_from_task(task, source_revision(task), req, current_user)
    except Exception as exc:
        raise _translate_error(exc) from exc
    return {"order": order, "message": f"客户订单 {order.get('order_no')} 已下达，生成 {len(order.get('door_units') or [])} 个门樘生产单"}


@router.get("/orders")
def list_orders(q: str = Query(""), status: str = Query(""), current_user: Dict = Depends(get_current_user)):
    return {"orders": fulfillment_db.list_orders(q.strip(), status.strip())}


@router.get("/orders/{order_id}")
def get_order(order_id: int, current_user: Dict = Depends(get_current_user)):
    order = fulfillment_db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="客户订单不存在")
    return {"order": order}


@router.get("/door-units/{door_id}")
def get_door_unit(door_id: int, current_user: Dict = Depends(get_current_user)):
    door = fulfillment_db.get_door_unit(door_id)
    if not door:
        raise HTTPException(status_code=404, detail="门樘生产单不存在")
    return {"door_unit": door}


@router.put("/door-units/{door_id}/technical-package")
def save_technical_package(door_id: int, req: TechnicalPackageUpdate, current_user: Dict = Depends(get_current_user)):
    try:
        return {"door_unit": fulfillment_db.save_technical_package(door_id, req, current_user), "message": "技术包草稿已保存"}
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post("/door-units/{door_id}/technical-package/confirm")
def confirm_technical_package(door_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        return {"door_unit": fulfillment_db.confirm_technical_package(door_id, current_user), "message": "技术包已冻结，工作包已释放"}
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.put("/work-packages/{work_id}")
def update_work_package(work_id: int, req: WorkPackageAction, current_user: Dict = Depends(get_current_user)):
    try:
        return {"door_unit": fulfillment_db.update_work_package(work_id, req, current_user), "message": "工作包已更新"}
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post("/door-units/{door_id}/exceptions")
def create_exception(door_id: int, req: ExceptionCreate, current_user: Dict = Depends(get_current_user)):
    try:
        return {"door_unit": fulfillment_db.create_exception(door_id, req, current_user), "message": "异常已登记"}
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post("/exceptions/{exception_id}/resolve")
def resolve_exception(exception_id: int, req: ExceptionResolve, current_user: Dict = Depends(get_current_user)):
    try:
        return {"door_unit": fulfillment_db.resolve_exception(exception_id, req.resolution, current_user), "message": "异常已解决"}
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post("/door-units/{door_id}/changes")
def create_change(door_id: int, req: ChangeCreate, current_user: Dict = Depends(get_current_user)):
    try:
        return {"door_unit": fulfillment_db.create_change(door_id, req, current_user), "message": "生产变更单已创建，新技术版本进入草稿"}
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.put("/supplies/{supply_id}")
def update_supply(supply_id: int, req: SupplyAction, current_user: Dict = Depends(get_current_user)):
    try:
        return {"door_unit": fulfillment_db.update_supply(supply_id, req, current_user), "message": "供应事项已更新"}
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post("/door-units/{door_id}/inspections")
def create_inspection(door_id: int, req: InspectionCreate, current_user: Dict = Depends(get_current_user)):
    try:
        return {"door_unit": fulfillment_db.create_inspection(door_id, req, current_user), "message": f"{req.inspection_type}已登记：{req.result}"}
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post("/door-units/{door_id}/finished-inbound")
def finished_inbound(door_id: int, req: FinishedInboundCreate, current_user: Dict = Depends(get_current_user)):
    try:
        return {"door_unit": fulfillment_db.finished_inbound(door_id, req, current_user), "message": "成品已入库"}
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post("/door-units/{door_id}/payments")
def record_payment(door_id: int, req: PaymentCreate, current_user: Dict = Depends(get_current_user)):
    try:
        return {"door_unit": fulfillment_db.record_payment(door_id, req, current_user), "message": "收款已登记"}
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post("/door-units/{door_id}/shipments")
def create_shipment(door_id: int, req: ShipmentCreate, current_user: Dict = Depends(get_current_user)):
    try:
        return {"door_unit": fulfillment_db.create_shipment(door_id, req, current_user), "message": "发货出库已登记"}
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post("/shipments/{shipment_id}/sign")
def sign_shipment(shipment_id: int, req: ShipmentSign, current_user: Dict = Depends(get_current_user)):
    try:
        return {"door_unit": fulfillment_db.sign_shipment(shipment_id, req, current_user), "message": "签收已登记，门樘履约完成"}
    except Exception as exc:
        raise _translate_error(exc) from exc
