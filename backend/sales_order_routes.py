"""Sales-order confirmation APIs joining drawing tasks and saved quotations."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user
from quote_routes import quote_db
from sales_order_database import SalesOrderDatabase
from sales_order_models import SalesOrderCancel, SalesOrderCreate, SalesOrderUpdate


router = APIRouter(prefix="/api/sales-orders", tags=["sales-orders"])
sales_order_db = SalesOrderDatabase()
task_repository = None
fulfillment_provisioner: Any = None


def configure_task_repository(repository) -> None:
    global task_repository
    task_repository = repository


def configure_sales_order_database(database: SalesOrderDatabase) -> None:
    global sales_order_db
    sales_order_db = database


def configure_fulfillment_provisioner(provisioner: Any) -> None:
    global fulfillment_provisioner
    fulfillment_provisioner = provisioner


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, sqlite3.IntegrityError):
        message = str(exc)
        if "sales_order_door_lines.sales_order_id, sales_order_door_lines.task_id" in message:
            message = "同一图纸不能在一张订单中重复添加"
        return HTTPException(status_code=409, detail=message)
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="订单操作失败，请查看服务端日志")


def _require_tasks():
    if task_repository is None:
        raise RuntimeError("图纸任务仓库尚未初始化")
    return task_repository


def _is_area_unit(unit: str) -> bool:
    normalized = str(unit or "").lower()
    return "m2" in normalized or "㎡" in normalized or "m²" in normalized


def _quote_item_quantity(item: Dict) -> float:
    explicit = float(item.get("quantity") or 0)
    if explicit > 0:
        return explicit
    if not _is_area_unit(item.get("unit", "")):
        return 1
    width = float(item.get("width") or 0)
    height = float(item.get("height") or 0)
    return width * height * 0.000001 if width > 0 and height > 0 else 0


def _quote_group_total(group: Dict) -> float:
    total = 0.0
    for item in group.get("items") or []:
        quantity = _quote_item_quantity(item)
        unit_price = float(item.get("unitPrice") or 0)
        total += round(quantity * unit_price) if quantity > 0 else 0
    return round(total, 2)


def _task_snapshot(task: Dict) -> Dict:
    return {
        "id": task.get("id"),
        "status": task.get("status", ""),
        "customer": task.get("customer", ""),
        "project": task.get("project", ""),
        "door_type": task.get("door_type", ""),
        "size": task.get("size", ""),
        "approved_at": task.get("approved_at"),
        "params": task.get("params") or {},
    }


def _drawing_revision(snapshot: Dict) -> str:
    revision_source = {
        "id": snapshot.get("id"),
        "customer": snapshot.get("customer"),
        "project": snapshot.get("project"),
        "door_type": snapshot.get("door_type"),
        "size": snapshot.get("size"),
        "params": snapshot.get("params") or {},
    }
    payload = json.dumps(revision_source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _quote_match(task_id: str, quote_id: Optional[int], group_index: Optional[int]) -> Optional[Dict]:
    matches = quote_db.find_groups_by_task(task_id)
    if quote_id is None:
        return matches[0] if matches else None
    for match in matches:
        if int(match.get("quote_id") or 0) != quote_id:
            continue
        if group_index is None or int(match.get("group_index") or 0) == group_index:
            return match
    raise ValueError("所选报价中找不到该图纸对应的门樘明细")


def _line_from_input(item, expected_customer: str) -> Dict:
    task = _require_tasks().get_task(item.task_id)
    if not task:
        raise LookupError(f"图纸任务不存在：{item.task_id}")
    customer = str(task.get("customer") or (task.get("params") or {}).get("dhdw") or "").strip()
    if expected_customer and customer != expected_customer:
        raise ValueError("一张订单只能包含同一客户的图纸")

    params = task.get("params") or {}
    quote_match = _quote_match(item.task_id, item.quote_id, item.quote_group_index)
    quote_snapshot: Dict = {}
    suggested_price = 0.0
    if quote_match:
        quote_snapshot = {
            "quote_id": quote_match["quote_id"],
            "quote_date": quote_match.get("quote_date", ""),
            "updated_at": quote_match.get("updated_at", ""),
            "group_index": quote_match["group_index"],
            "group": quote_match["group"],
        }
        suggested_price = _quote_group_total(quote_match["group"])
    unit_price = suggested_price if item.unit_price is None else float(item.unit_price)
    quantity = int(item.quantity)
    snapshot = _task_snapshot(task)
    opening = f"{params.get('sel_kx', '')}{params.get('sel_nk', '')}".strip()
    return {
        "task_id": item.task_id,
        "quote_id": quote_snapshot.get("quote_id"),
        "quote_group_index": quote_snapshot.get("group_index"),
        "product_name": str(params.get("product_name") or task.get("door_type") or ""),
        "door_type": str(task.get("door_type") or params.get("door_type") or ""),
        "width": float(params.get("dw") or 0),
        "height": float(params.get("dh") or 0),
        "opening_direction": opening,
        "color": str(params.get("ys") or ""),
        "quantity": quantity,
        "unit": "樘",
        "unit_price": unit_price,
        "amount": round(unit_price * quantity, 2),
        "drawing_status": str(task.get("status") or ""),
        "drawing_revision": _drawing_revision(snapshot),
        "drawing_snapshot": snapshot,
        "quote_snapshot": quote_snapshot,
        "remark": item.remark.strip(),
    }


def _prepare_order(req, exclude_order_id: Optional[int] = None) -> tuple[Dict, List[Dict]]:
    occupied = sales_order_db.active_task_ids(exclude_order_id=exclude_order_id)
    requested_ids = [line.task_id for line in req.lines]
    if len(set(requested_ids)) != len(requested_ids):
        raise ValueError("同一图纸不能在一张订单中重复添加")
    conflicts = occupied.intersection(requested_ids)
    if conflicts:
        raise RuntimeError(f"图纸 {next(iter(conflicts))} 已在其他有效订单中")

    first_task = _require_tasks().get_task(req.lines[0].task_id)
    if not first_task:
        raise LookupError(f"图纸任务不存在：{req.lines[0].task_id}")
    source_customer = str(first_task.get("customer") or (first_task.get("params") or {}).get("dhdw") or "").strip()
    customer = req.customer_name.strip() or source_customer
    if not customer:
        raise ValueError("客户名称不能为空")
    if source_customer and customer != source_customer:
        raise ValueError("订单客户必须与所选图纸客户一致")

    lines = [_line_from_input(item, customer) for item in req.lines]
    data = req.model_dump(exclude={"lines"})
    data["customer_name"] = customer
    return data, lines


def _candidate(task: Dict) -> Dict:
    task_id = str(task.get("id") or "")
    params = task.get("params") or {}
    matches = quote_db.find_groups_by_task(task_id)
    quotes = [{
        "quote_id": match["quote_id"],
        "quote_date": match.get("quote_date", ""),
        "updated_at": match.get("updated_at", ""),
        "group_index": match["group_index"],
        "group_name": match["group"].get("groupName", ""),
        "amount": _quote_group_total(match["group"]),
    } for match in matches]
    return {
        "task_id": task_id,
        "customer_name": str(task.get("customer") or params.get("dhdw") or ""),
        "project_name": str(task.get("project") or params.get("gdmc") or ""),
        "product_name": str(params.get("product_name") or task.get("door_type") or ""),
        "door_type": str(task.get("door_type") or params.get("door_type") or ""),
        "width": float(params.get("dw") or 0),
        "height": float(params.get("dh") or 0),
        "opening_direction": f"{params.get('sel_kx', '')}{params.get('sel_nk', '')}".strip(),
        "color": str(params.get("ys") or ""),
        "drawing_status": str(task.get("status") or ""),
        "quote_status": "已报价" if quotes else "未报价",
        "quotes": quotes,
    }


def _enrich_order(order: Dict) -> Dict:
    if not order:
        return order
    result = dict(order)
    enriched_lines: List[Dict] = []
    for stored_line in order.get("lines") or []:
        line = dict(stored_line)
        task = _require_tasks().get_task(str(line.get("task_id") or ""))
        if task:
            snapshot = _task_snapshot(task)
            line["current_drawing_status"] = str(task.get("status") or "")
            line["source_changed"] = _drawing_revision(snapshot) != str(line.get("drawing_revision") or "")
        else:
            line["current_drawing_status"] = "图纸已删除"
            line["source_changed"] = True
        line["quote_choices"] = _candidate(task)["quotes"] if task else []
        enriched_lines.append(line)
    result["lines"] = enriched_lines
    result["releasable_count"] = sum(
        int(line.get("quantity") or 0)
        for line in enriched_lines
        if line.get("current_drawing_status") == "已通过"
    )
    return result


@router.get("/candidates")
def list_candidates(
    q: str = Query(""),
    customer: str = Query(""),
    current_order_id: Optional[int] = Query(None),
    current_user: Dict = Depends(get_current_user),
):
    occupied = sales_order_db.active_task_ids(exclude_order_id=current_order_id)
    keyword = q.strip().lower()
    rows: List[Dict] = []
    for task in _require_tasks().load_all_tasks():
        if str(task.get("id") or "") in occupied:
            continue
        row = _candidate(task)
        if customer and row["customer_name"] != customer:
            continue
        haystack = " ".join(str(row.get(key) or "") for key in ("task_id", "customer_name", "project_name", "product_name", "door_type")).lower()
        if keyword and keyword not in haystack:
            continue
        rows.append(row)
    return {"candidates": rows[:300], "total": len(rows)}


@router.get("")
def list_orders(
    q: str = Query(""),
    status: str = Query(""),
    current_user: Dict = Depends(get_current_user),
):
    orders = []
    for summary in sales_order_db.list(q=q.strip(), status=status.strip()):
        detail = sales_order_db.get(int(summary["id"])) or summary
        live = _enrich_order(detail)
        summary["releasable_count"] = live.get("releasable_count", 0)
        orders.append(summary)
    return {"orders": orders, "total": len(orders)}


@router.get("/{order_id}")
def get_order(order_id: int, current_user: Dict = Depends(get_current_user)):
    order = sales_order_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"order": _enrich_order(order)}


@router.post("", status_code=201)
def create_order(req: SalesOrderCreate, current_user: Dict = Depends(get_current_user)):
    try:
        data, lines = _prepare_order(req)
        order = sales_order_db.create(data, lines, str(current_user.get("uid") or ""))
        return {"order": _enrich_order(order), "message": "订单草稿已保存"}
    except Exception as exc:
        raise _error(exc) from exc


@router.put("/{order_id}")
def update_order(order_id: int, req: SalesOrderUpdate, current_user: Dict = Depends(get_current_user)):
    try:
        data, lines = _prepare_order(req, exclude_order_id=order_id)
        order = sales_order_db.update_draft(order_id, data, lines, str(current_user.get("uid") or ""))
        return {"order": _enrich_order(order), "message": "订单草稿已更新"}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/{order_id}/confirm")
def confirm_order(order_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        order = sales_order_db.get(order_id)
        if not order:
            raise LookupError("订单不存在")
        order = _enrich_order(order)
        missing: List[str] = []
        if not str(order.get("delivery_date") or "").strip():
            missing.append("交期")
        for index, line in enumerate(order.get("lines") or [], start=1):
            if not line.get("quote_id"):
                missing.append(f"第{index}樘报价")
            if float(line.get("width") or 0) <= 0 or float(line.get("height") or 0) <= 0:
                missing.append(f"第{index}樘宽高")
            if int(line.get("quantity") or 0) <= 0:
                missing.append(f"第{index}樘数量")
            if line.get("source_changed"):
                missing.append(f"第{index}樘图纸已变更，请先保存草稿刷新快照")
        if float(order.get("total_amount") or 0) <= 0:
            missing.append("订单总金额")
        if missing:
            raise ValueError(f"正式确认前请补充或修正：{'、'.join(missing)}")
        confirmed = sales_order_db.confirm(order_id, str(current_user.get("uid") or ""))
        for line in confirmed.get("lines") or []:
            try:
                _require_tasks().update_task(str(line["task_id"]), {"confirm_status": "已确认"})
            except Exception:
                pass
        message = "订单已正式确认"
        if fulfillment_provisioner is not None:
            try:
                confirmed = fulfillment_provisioner.provision(order_id, current_user)
                message = "订单已正式确认，并已生成独立门樘和BOM草稿"
            except Exception as provision_error:
                confirmed = sales_order_db.get(order_id) or confirmed
                message = f"订单已确认，但门樘生成失败，可稍后重试：{provision_error}"
        else:
            message = "订单已正式确认，履约生成服务尚未连接"
        return {"order": _enrich_order(confirmed), "message": message}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/{order_id}/retry-provisioning")
def retry_provisioning(order_id: int, current_user: Dict = Depends(get_current_user)):
    if fulfillment_provisioner is None:
        raise HTTPException(status_code=503, detail="履约生成服务尚未连接")
    try:
        order = fulfillment_provisioner.provision(order_id, current_user)
        return {"order": _enrich_order(order), "message": "门樘和BOM草稿已生成"}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/{order_id}/cancel")
def cancel_order(order_id: int, req: SalesOrderCancel, current_user: Dict = Depends(get_current_user)):
    try:
        order = sales_order_db.cancel(order_id, req.reason.strip(), str(current_user.get("uid") or ""))
        for line in order.get("lines") or []:
            try:
                _require_tasks().update_task(str(line["task_id"]), {"confirm_status": "未确认"})
            except Exception:
                pass
        return {"order": _enrich_order(order), "message": "订单已取消，图纸可重新选择"}
    except Exception as exc:
        raise _error(exc) from exc
