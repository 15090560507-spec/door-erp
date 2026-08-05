"""Authenticated API routes for the production-fulfillment MVP."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response

from auth import PRODUCTION_PERMISSIONS, require_permissions
from production_database import ProductionDatabase, json_loads, production_now
from production_document_service import (
    ProductionDocument,
    build_inventory_document,
    build_order_document,
    build_purchase_document,
    build_shipment_document,
    render_print_html,
    render_xlsx,
)
from production_material_service import ProductionMaterialService
from production_models import (
    BomReplaceRequest,
    CuttingSheetUpdate,
    FinishedGoodInboundRequest,
    InventoryTransactionRequest,
    MaterialMovementRequest,
    MaterialRequest,
    OperationUpdateRequest,
    ProductionOrderActionRequest,
    PurchaseReceiveRequest,
    PurchaseRequest,
    PurchaseStatusRequest,
    QualityRequest,
    RequirementPurchaseRequest,
    ScheduleRequest,
    ShipmentRequest,
    ShipmentStatusRequest,
)


router = APIRouter(prefix="/api/production", tags=["production"])
production_db = ProductionDatabase()
task_repository: Any = None
read_production = require_permissions(*sorted(PRODUCTION_PERMISSIONS))


def _material_service() -> ProductionMaterialService:
    return ProductionMaterialService(production_db)


def configure_task_repository(repository: Any) -> None:
    global task_repository
    task_repository = repository


def production_source_revision(task: Dict[str, Any]) -> str:
    revision_payload = {
        "task_id": task.get("id"),
        "status": task.get("status"),
        "params": task.get("params") or {},
        "review_feedback": task.get("review_feedback", ""),
        "history": task.get("history", []),
    }
    serialized = json.dumps(
        revision_payload, ensure_ascii=False, sort_keys=True, default=str
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _review_summary(task: Dict[str, Any]) -> tuple[str, str]:
    history = task.get("history")
    if isinstance(history, list):
        for entry in reversed(history):
            if not isinstance(entry, dict):
                continue
            action = str(entry.get("action") or entry.get("status") or "")
            if "终审" in action or "通过" in action:
                return (
                    str(entry.get("time") or entry.get("created_at") or ""),
                    str(entry.get("user") or entry.get("operator") or ""),
                )
    return str(task.get("updated_at") or task.get("date") or ""), ""


def pending_release_tasks() -> List[Dict[str, Any]]:
    if task_repository is None:
        return []
    released = {
        (str(row["source_task_id"]), str(row["source_revision"]))
        for row in production_db.fetch_all(
            """
            SELECT source_task_id, source_revision
            FROM production_orders
            WHERE direct_release=1 AND status != '已作废'
            """
        )
    }
    rows: List[Dict[str, Any]] = []
    for task in task_repository.load_all_tasks():
        if task.get("status") != "已通过":
            continue
        revision = production_source_revision(task)
        if (str(task.get("id", "")), revision) in released:
            continue
        params = task.get("params") or {}
        approved_at, approved_by = _review_summary(task)
        rows.append({
            "task_id": str(task.get("id", "")),
            "source_revision": revision,
            "status": "待下达",
            "customer": str(params.get("dhdw") or task.get("customer") or ""),
            "project": str(params.get("gdmc") or task.get("project") or ""),
            "door_type": str(params.get("door_type") or ""),
            "width": params.get("dw"),
            "height": params.get("dh"),
            "opening": f"{params.get('sel_kx') or ''}{params.get('sel_nk') or ''}",
            "approved_at": approved_at,
            "approved_by": approved_by,
        })
    rows.sort(key=lambda row: row["approved_at"], reverse=True)
    return rows


def _order_or_404(order_id: int) -> Dict[str, Any]:
    order = production_db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="生产订单不存在")
    return order


def _event(order_id: int, action: str, detail: str, user: Dict[str, Any]) -> None:
    production_db.add_event(order_id, action, detail, user)


def _ensure_document_permission(current_user: Dict[str, Any], *allowed: str) -> None:
    permissions = set(current_user.get("permissions") or [])
    if not permissions.intersection({*allowed, "production.manager"}):
        raise HTTPException(status_code=403, detail="权限不足")


def _document_or_404(builder, *args) -> ProductionDocument:
    try:
        return builder(production_db, *args)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _xlsx_response(document: ProductionDocument, filename: str) -> Response:
    return Response(
        content=render_xlsx(document),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/dashboard")
def dashboard(current_user: Dict = Depends(read_production)):
    counts = production_db.dashboard()
    counts["待下达"] = len(pending_release_tasks())
    return {"counts": counts}


@router.get("/pending-release")
def list_pending_release(current_user: Dict = Depends(read_production)):
    return {"tasks": pending_release_tasks()}


@router.get("/orders")
def list_orders(
    stage: str = "",
    status: str = "",
    q: str = "",
    owner: str = "",
    shortage: str = "",
    due_from: str = "",
    due_to: str = "",
    current_user: Dict = Depends(read_production),
):
    return {"orders": production_db.list_orders(
        stage=stage,
        status=status,
        query=q,
        owner=owner,
        shortage=shortage,
        due_from=due_from,
        due_to=due_to,
    )}


@router.get("/orders/{order_id}")
def get_order(order_id: int, current_user: Dict = Depends(read_production)):
    order = _order_or_404(order_id)
    order["events"] = production_db.events(order_id)
    return {"order": order}


@router.get("/orders/{order_id}/timeline")
def get_order_timeline(order_id: int, current_user: Dict = Depends(read_production)):
    _order_or_404(order_id)
    return {"timeline": production_db.timeline(order_id)}


@router.get("/orders/{order_id}/approved-dxf")
def download_approved_dxf(order_id: int, current_user: Dict = Depends(read_production)):
    order = _order_or_404(order_id)
    root = Path(production_db.files_dir).resolve()
    dxf_path = (root / str(order["dxf_path"])).resolve()
    try:
        dxf_path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="生产图纸路径不安全") from exc
    if not dxf_path.is_file():
        raise HTTPException(status_code=404, detail="终审冻结 DXF 不存在")
    return FileResponse(
        path=dxf_path,
        media_type="application/dxf",
        filename=f"{order['order_no']}_终审冻结图.dxf",
    )


ORDER_DOCUMENT_PERMISSIONS = {
    "bom": ("production.technical",),
    "cutting": ("production.cutting", "production.technical"),
    "quality": ("production.quality",),
}


@router.get("/orders/{order_id}/documents/{document_type}.xlsx")
def export_order_document(
    order_id: int,
    document_type: str,
    current_user: Dict = Depends(read_production),
):
    permissions = ORDER_DOCUMENT_PERMISSIONS.get(document_type)
    if not permissions:
        raise HTTPException(status_code=404, detail="不支持的生产单据类型")
    _ensure_document_permission(current_user, *permissions)
    document = _document_or_404(build_order_document, order_id, document_type)
    return _xlsx_response(document, f"{document.title}_{document.document_no}.xlsx")


@router.get("/orders/{order_id}/documents/{document_type}/print")
def print_order_document(
    order_id: int,
    document_type: str,
    current_user: Dict = Depends(read_production),
):
    permissions = ORDER_DOCUMENT_PERMISSIONS.get(document_type)
    if not permissions:
        raise HTTPException(status_code=404, detail="不支持的生产单据类型")
    _ensure_document_permission(current_user, *permissions)
    document = _document_or_404(build_order_document, order_id, document_type)
    return HTMLResponse(render_print_html(document))


@router.post("/orders/{order_id}/copy")
def copy_order(
    order_id: int,
    req: ProductionOrderActionRequest,
    current_user: Dict = Depends(require_permissions("production.sales")),
):
    source = _order_or_404(order_id)
    dxf_path = Path(production_db.files_dir) / source["dxf_path"]
    if not dxf_path.exists():
        raise HTTPException(status_code=409, detail="原生产订单的 DXF 快照不存在")
    copied = production_db.create_order(
        source_task_id=source.get("source_task_id") or "",
        source_revision=f"copy:{source['order_no']}:{production_now()}",
        customer=source["customer"],
        project=source.get("project", ""),
        due_date=source.get("due_date", ""),
        sales_note=req.reason or source.get("sales_note", ""),
        include_quote=bool(source.get("include_quote")),
        task_snapshot=source.get("task_snapshot") or {},
        quote_snapshot=source.get("quote_snapshot"),
        dxf_bytes=dxf_path.read_bytes(),
        created_by=current_user["uid"],
        direct_release=False,
        source_order_id=order_id,
    )
    return {"order": copied, "message": "生产订单已复制"}


@router.post("/orders/{order_id}/withdraw")
def withdraw_order(
    order_id: int,
    req: ProductionOrderActionRequest,
    current_user: Dict = Depends(require_permissions("production.sales", "production.manager")),
):
    order = _order_or_404(order_id)
    if order.get("cutting_started"):
        raise HTTPException(status_code=409, detail="下料已经开始，不能直接撤回，请发起生产变更")
    updated = production_db.update_order(
        order_id, {"status": "已撤回", "withdrawn_at": production_now()}
    )
    _event(order_id, "撤回生产订单", req.reason, current_user)
    return {"order": updated, "message": "生产订单已撤回"}


def _change_order_status(
    order_id: int,
    action: str,
    req: ProductionOrderActionRequest,
    current_user: Dict,
):
    order = _order_or_404(order_id)
    mapping = {"pause": "已暂停", "resume": "进行中", "void": "已作废"}
    allowed_statuses = {
        "pause": {"进行中"},
        "resume": {"已暂停"},
        "void": {"进行中", "已暂停", "已撤回"},
    }
    if order["status"] not in allowed_statuses[action]:
        raise HTTPException(
            status_code=409,
            detail=f"当前状态“{order['status']}”不能执行该操作",
        )
    updated = production_db.update_order(order_id, {"status": mapping[action]})
    _event(order_id, mapping[action], req.reason, current_user)
    return {"order": updated}


@router.post("/orders/{order_id}/pause")
def pause_order(
    order_id: int,
    req: ProductionOrderActionRequest,
    current_user: Dict = Depends(require_permissions("production.manager")),
):
    return _change_order_status(order_id, "pause", req, current_user)


@router.post("/orders/{order_id}/resume")
def resume_order(
    order_id: int,
    req: ProductionOrderActionRequest,
    current_user: Dict = Depends(require_permissions("production.manager")),
):
    return _change_order_status(order_id, "resume", req, current_user)


@router.post("/orders/{order_id}/void")
def void_order(
    order_id: int,
    req: ProductionOrderActionRequest,
    current_user: Dict = Depends(require_permissions("production.manager")),
):
    return _change_order_status(order_id, "void", req, current_user)


# Materials
@router.get("/materials")
def list_materials(
    include_inactive: bool = False,
    current_user: Dict = Depends(read_production),
):
    sql = "SELECT * FROM production_materials"
    if not include_inactive:
        sql += " WHERE active = 1"
    sql += " ORDER BY id DESC"
    return {"materials": production_db.fetch_all(sql)}


@router.post("/materials")
def create_material(
    req: MaterialRequest,
    current_user: Dict = Depends(require_permissions("production.technical", "production.warehouse", "production.purchase")),
):
    now = production_now()
    try:
        material_id = production_db.execute(
            """
            INSERT INTO production_materials(
                code, name, category, material, specification, thickness, unit,
                supplier, warehouse_location, remark, active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.code.strip(), req.name.strip(), req.category, req.material, req.specification,
                req.thickness, req.unit, req.supplier, req.warehouse_location, req.remark,
                int(req.active), now, now,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="物料编码已存在") from exc
    return {"material": production_db.fetch_one("SELECT * FROM production_materials WHERE id = ?", (material_id,))}


@router.put("/materials/{material_id}")
def update_material(
    material_id: int,
    req: MaterialRequest,
    current_user: Dict = Depends(require_permissions("production.technical", "production.warehouse", "production.purchase")),
):
    if not production_db.fetch_one("SELECT id FROM production_materials WHERE id = ?", (material_id,)):
        raise HTTPException(status_code=404, detail="生产物料不存在")
    try:
        production_db.execute(
            """
            UPDATE production_materials SET
                code=?, name=?, category=?, material=?, specification=?, thickness=?, unit=?,
                supplier=?, warehouse_location=?, remark=?, active=?, updated_at=?
            WHERE id=?
            """,
            (
                req.code.strip(), req.name.strip(), req.category, req.material, req.specification,
                req.thickness, req.unit, req.supplier, req.warehouse_location, req.remark,
                int(req.active), production_now(), material_id,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="物料编码已存在") from exc
    return {"material": production_db.fetch_one("SELECT * FROM production_materials WHERE id = ?", (material_id,))}


@router.delete("/materials/{material_id}")
def disable_material(
    material_id: int,
    current_user: Dict = Depends(require_permissions("production.technical", "production.warehouse")),
):
    production_db.execute(
        "UPDATE production_materials SET active=0, updated_at=? WHERE id=?", (production_now(), material_id)
    )
    return {"success": True}


# BOM
@router.get("/orders/{order_id}/bom")
def get_bom(order_id: int, current_user: Dict = Depends(read_production)):
    _order_or_404(order_id)
    status = production_db.fetch_one("SELECT * FROM production_bom_status WHERE order_id=?", (order_id,))
    items = production_db.fetch_all(
        "SELECT * FROM production_bom_items WHERE order_id=? ORDER BY id", (order_id,)
    )
    return {"status": status or {"status": "草稿"}, "items": items}


@router.put("/orders/{order_id}/bom")
def replace_bom(
    order_id: int,
    req: BomReplaceRequest,
    current_user: Dict = Depends(require_permissions("production.technical")),
):
    _order_or_404(order_id)
    state = production_db.fetch_one("SELECT status FROM production_bom_status WHERE order_id=?", (order_id,))
    if state and state["status"] == "已发布":
        raise HTTPException(status_code=409, detail="BOM 已发布，首版不能直接覆盖，请先由负责人撤回")
    now = production_now()
    with production_db.transaction() as conn:
        conn.execute("DELETE FROM production_bom_items WHERE order_id=?", (order_id,))
        conn.executemany(
            """
            INSERT INTO production_bom_items(
                order_id, material_id, category, name, specification, material, thickness,
                quantity, unit, supply_type, remark, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    order_id, item.material_id, item.category, item.name.strip(), item.specification,
                    item.material, item.thickness, item.quantity, item.unit, item.supply_type,
                    item.remark, now, now,
                )
                for item in req.items if item.name.strip()
            ],
        )
        conn.execute("UPDATE production_bom_status SET updated_at=? WHERE order_id=?", (now, order_id))
    _event(order_id, "保存BOM草稿", f"{len(req.items)} 项", current_user)
    return get_bom(order_id, current_user)


@router.post("/orders/{order_id}/bom/publish")
def publish_bom(
    order_id: int,
    current_user: Dict = Depends(require_permissions("production.technical")),
):
    _order_or_404(order_id)
    count = production_db.fetch_one(
        "SELECT COUNT(*) AS count FROM production_bom_items WHERE order_id=?", (order_id,)
    )
    if not count or int(count["count"]) == 0:
        raise HTTPException(status_code=409, detail="BOM 为空，不能发布")
    now = production_now()
    with production_db.transaction() as conn:
        conn.execute(
            "UPDATE production_bom_status SET status='已发布', published_by=?, published_at=?, updated_at=? WHERE order_id=?",
            (current_user["uid"], now, now, order_id),
        )
        conn.execute(
            "UPDATE production_orders SET stage='备料', updated_at=? WHERE id=?", (now, order_id)
        )
        _material_service().create_requirement_for_order(conn, order_id)
    _event(order_id, "发布BOM", "", current_user)
    return get_bom(order_id, current_user)


# Purchases and inventory
@router.get("/material-requirements")
def list_material_requirements(current_user: Dict = Depends(read_production)):
    return {"requirements": _material_service().list_requirements()}


@router.get("/orders/{order_id}/material-requirement")
def get_material_requirement(order_id: int, current_user: Dict = Depends(read_production)):
    _order_or_404(order_id)
    return {"requirement": _material_service().get_requirement_for_order(order_id)}


@router.post("/material-requirements/purchase")
def purchase_requirement_shortages(
    req: RequirementPurchaseRequest,
    current_user: Dict = Depends(require_permissions("production.purchase")),
):
    if not req.items:
        raise HTTPException(status_code=400, detail="请至少选择一条缺料明细")
    now = production_now()
    prefix = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("CG%Y%m%d")
    service = _material_service()
    with production_db.transaction() as conn:
        purchase_no = production_db._next_number(
            conn, "production_purchase_orders", "purchase_no", prefix
        )
        cursor = conn.execute(
            """
            INSERT INTO production_purchase_orders(
                purchase_no, supplier, status, expected_date, remark, created_by, created_at, updated_at
            ) VALUES (?, ?, '草稿', ?, ?, ?, ?, ?)
            """,
            (purchase_no, req.supplier, req.expected_date, req.remark, current_user["uid"], now, now),
        )
        purchase_id = int(cursor.lastrowid)
        affected_requirements: set[int] = set()
        affected_orders: set[int] = set()
        for requested in req.items:
            item = conn.execute(
                """
                SELECT i.*, r.order_id
                FROM production_material_requirement_items i
                JOIN production_material_requirements r ON r.id=i.requirement_id
                WHERE i.id=?
                """,
                (requested.requirement_item_id,),
            ).fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="物料需求明细不存在")
            if not item["material_id"]:
                raise HTTPException(
                    status_code=409,
                    detail=f"{item['name']} 尚未关联物料资料，请先处理 BOM",
                )
            shortage = service._shortage(item)
            quantity = float(requested.quantity) if requested.quantity is not None else shortage
            if shortage <= 1e-9:
                raise HTTPException(status_code=409, detail=f"{item['name']} 当前没有待采购缺口")
            if quantity > shortage + 1e-9:
                raise HTTPException(
                    status_code=409,
                    detail=f"{item['name']} 本次最多可转采购 {shortage:g}{item['unit']}",
                )
            conn.execute(
                """
                INSERT INTO production_purchase_items(
                    purchase_id, order_id, material_id, requirement_item_id, name,
                    specification, quantity, unit, unit_price, remark
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    purchase_id, item["order_id"], item["material_id"], item["id"],
                    item["name"], item["specification"], quantity, item["unit"], req.remark,
                ),
            )
            conn.execute(
                """
                UPDATE production_material_requirement_items
                SET purchased_quantity=purchased_quantity+?, updated_at=? WHERE id=?
                """,
                (quantity, now, item["id"]),
            )
            affected_requirements.add(int(item["requirement_id"]))
            affected_orders.add(int(item["order_id"]))
        for requirement_id in affected_requirements:
            service._refresh_requirement(conn, requirement_id)
    for order_id in affected_orders:
        _event(order_id, "缺料转采购", purchase_no, current_user)
    return {"purchase_id": purchase_id, "purchase_no": purchase_no}


@router.post("/orders/{order_id}/materials/issue")
def issue_order_materials(
    order_id: int,
    req: MaterialMovementRequest,
    current_user: Dict = Depends(require_permissions("production.warehouse")),
):
    _order_or_404(order_id)
    try:
        _material_service().issue(
            order_id, [item.model_dump() for item in req.items], current_user["uid"], req.remark
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _event(order_id, "生产领料", req.remark, current_user)
    return {"requirement": _material_service().get_requirement_for_order(order_id)}


@router.post("/orders/{order_id}/materials/return")
def return_order_materials(
    order_id: int,
    req: MaterialMovementRequest,
    current_user: Dict = Depends(require_permissions("production.warehouse")),
):
    _order_or_404(order_id)
    try:
        _material_service().return_materials(
            order_id, [item.model_dump() for item in req.items], current_user["uid"], req.remark
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _event(order_id, "生产退料", req.remark, current_user)
    return {"requirement": _material_service().get_requirement_for_order(order_id)}


@router.get("/purchases")
def list_purchases(current_user: Dict = Depends(read_production)):
    purchases = production_db.fetch_all("SELECT * FROM production_purchase_orders ORDER BY id DESC")
    for purchase in purchases:
        purchase["items"] = production_db.fetch_all(
            "SELECT * FROM production_purchase_items WHERE purchase_id=? ORDER BY id", (purchase["id"],)
        )
    return {"purchases": purchases}


@router.get("/purchases/{purchase_id}/export.xlsx")
def export_purchase_document(
    purchase_id: int,
    current_user: Dict = Depends(read_production),
):
    _ensure_document_permission(current_user, "production.purchase")
    document = _document_or_404(build_purchase_document, purchase_id)
    return _xlsx_response(document, f"采购单_{document.document_no}.xlsx")


@router.get("/purchases/{purchase_id}/print")
def print_purchase_document(
    purchase_id: int,
    current_user: Dict = Depends(read_production),
):
    _ensure_document_permission(current_user, "production.purchase")
    return HTMLResponse(render_print_html(
        _document_or_404(build_purchase_document, purchase_id)
    ))


@router.post("/purchases")
def create_purchase(
    req: PurchaseRequest,
    current_user: Dict = Depends(require_permissions("production.purchase")),
):
    if not req.items:
        raise HTTPException(status_code=400, detail="采购单至少需要一条明细")
    now = production_now()
    prefix = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("CG%Y%m%d")
    with production_db.transaction() as conn:
        purchase_no = production_db._next_number(conn, "production_purchase_orders", "purchase_no", prefix)
        cursor = conn.execute(
            """
            INSERT INTO production_purchase_orders(purchase_no, supplier, expected_date, remark, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (purchase_no, req.supplier, req.expected_date, req.remark, current_user["uid"], now, now),
        )
        purchase_id = int(cursor.lastrowid)
        conn.executemany(
            """
            INSERT INTO production_purchase_items(
                purchase_id, order_id, material_id, requirement_item_id, name,
                specification, quantity, unit, unit_price, remark
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    purchase_id, item.order_id, item.material_id, item.requirement_item_id,
                    item.name, item.specification,
                    item.quantity, item.unit, item.unit_price, item.remark,
                )
                for item in req.items
            ],
        )
    for order_id in {item.order_id for item in req.items if item.order_id}:
        _event(int(order_id), "创建采购单", purchase_no, current_user)
    return {"purchase_id": purchase_id, "purchase_no": purchase_no}


@router.put("/purchases/{purchase_id}/status")
def update_purchase_status(
    purchase_id: int,
    req: PurchaseStatusRequest,
    current_user: Dict = Depends(require_permissions("production.purchase")),
):
    allowed = {"草稿", "已下单", "部分到货", "已完成"}
    if req.status not in allowed:
        raise HTTPException(status_code=400, detail="采购状态不正确")
    production_db.execute(
        "UPDATE production_purchase_orders SET status=?, updated_at=? WHERE id=?",
        (req.status, production_now(), purchase_id),
    )
    purchase = production_db.fetch_one(
        "SELECT purchase_no FROM production_purchase_orders WHERE id=?", (purchase_id,)
    )
    order_rows = production_db.fetch_all(
        "SELECT DISTINCT order_id FROM production_purchase_items WHERE purchase_id=? AND order_id IS NOT NULL",
        (purchase_id,),
    )
    for row in order_rows:
        _event(int(row["order_id"]), f"采购单{req.status}", purchase["purchase_no"] if purchase else "", current_user)
    return {"success": True}


@router.post("/purchases/{purchase_id}/receive")
def receive_purchase(
    purchase_id: int,
    req: PurchaseReceiveRequest,
    current_user: Dict = Depends(require_permissions("production.warehouse")),
):
    purchase = production_db.fetch_one("SELECT * FROM production_purchase_orders WHERE id=?", (purchase_id,))
    if not purchase:
        raise HTTPException(status_code=404, detail="采购单不存在")
    now = production_now()
    service = _material_service()
    with production_db.transaction() as conn:
        affected_order_ids = set()
        affected_requirement_ids = set()
        for received in req.items:
            item = conn.execute(
                "SELECT * FROM production_purchase_items WHERE id=? AND purchase_id=?",
                (received.item_id, purchase_id),
            ).fetchone()
            if not item:
                raise HTTPException(status_code=404, detail=f"采购明细 {received.item_id} 不存在")
            new_received = float(item["received_quantity"]) + received.quantity
            if new_received > float(item["quantity"]) + 1e-9:
                remaining = max(0, float(item["quantity"]) - float(item["received_quantity"]))
                raise HTTPException(
                    status_code=409,
                    detail=f"采购明细 {received.item_id} 本次最多可入库 {remaining:g}{item['unit']}",
                )
            if item["order_id"]:
                affected_order_ids.add(int(item["order_id"]))
            conn.execute(
                "UPDATE production_purchase_items SET received_quantity=? WHERE id=?",
                (new_received, received.item_id),
            )
            if item["requirement_item_id"]:
                conn.execute(
                    """
                    UPDATE production_material_requirement_items
                    SET received_quantity=received_quantity+?, updated_at=? WHERE id=?
                    """,
                    (received.quantity, now, item["requirement_item_id"]),
                )
                requirement_row = conn.execute(
                    "SELECT requirement_id FROM production_material_requirement_items WHERE id=?",
                    (item["requirement_item_id"],),
                ).fetchone()
                if requirement_row:
                    affected_requirement_ids.add(int(requirement_row["requirement_id"]))
            conn.execute(
                """
                INSERT INTO production_inventory_transactions(
                    material_id, order_id, purchase_id, transaction_type, quantity, unit,
                    warehouse_location, remark, operator_uid, created_at
                ) VALUES (?, ?, ?, '采购入库', ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["material_id"], item["order_id"], purchase_id, received.quantity,
                    item["unit"], received.warehouse_location, req.remark, current_user["uid"], now,
                ),
            )
        incomplete = conn.execute(
            "SELECT COUNT(*) AS count FROM production_purchase_items WHERE purchase_id=? AND received_quantity < quantity",
            (purchase_id,),
        ).fetchone()["count"]
        status = "部分到货" if incomplete else "已完成"
        conn.execute(
            "UPDATE production_purchase_orders SET status=?, updated_at=? WHERE id=?", (status, now, purchase_id)
        )
        service.allocate_open_requirements(conn, affected_order_ids)
        for requirement_id in affected_requirement_ids:
            service._refresh_requirement(conn, requirement_id)
    for order_id in affected_order_ids:
        _event(order_id, "采购到货入库", purchase["purchase_no"], current_user)
    return {"success": True, "status": status}


@router.get("/inventory")
def inventory(current_user: Dict = Depends(read_production)):
    balances = _material_service().inventory_balances()
    for balance in balances:
        balance["quantity"] = balance["on_hand"]
    transactions = production_db.fetch_all(
        "SELECT * FROM production_inventory_transactions ORDER BY id DESC LIMIT 200"
    )
    return {"balances": balances, "transactions": transactions}


@router.get("/inventory/export.xlsx")
def export_inventory_document(current_user: Dict = Depends(read_production)):
    _ensure_document_permission(current_user, "production.warehouse")
    document = build_inventory_document(production_db)
    return _xlsx_response(document, f"库存流水_{document.document_no}.xlsx")


@router.get("/inventory/print")
def print_inventory_document(current_user: Dict = Depends(read_production)):
    _ensure_document_permission(current_user, "production.warehouse")
    return HTMLResponse(render_print_html(build_inventory_document(production_db)))


@router.post("/inventory/transactions")
def create_inventory_transaction(
    req: InventoryTransactionRequest,
    current_user: Dict = Depends(require_permissions("production.warehouse")),
):
    if req.quantity == 0:
        raise HTTPException(status_code=400, detail="库存数量不能为 0")
    if req.transaction_type in {"生产领料", "生产退料"}:
        raise HTTPException(
            status_code=400,
            detail="生产领料和退料必须在对应生产订单的物料需求中操作",
        )
    quantity = req.quantity
    if req.transaction_type in {"生产领料", "报废", "成品出库"}:
        quantity = -abs(quantity)
    elif req.transaction_type in {"采购入库", "其他入库", "生产退料"}:
        quantity = abs(quantity)
    with production_db.transaction() as conn:
        if quantity < 0 and req.material_id:
            balance = conn.execute(
                """
                SELECT
                    COALESCE((SELECT SUM(quantity) FROM production_inventory_transactions
                              WHERE material_id=?), 0) AS on_hand,
                    COALESCE((SELECT SUM(quantity) FROM production_inventory_reservations
                              WHERE material_id=? AND status='有效'), 0) AS reserved
                """,
                (req.material_id, req.material_id),
            ).fetchone()
            available = float(balance["on_hand"] or 0) - float(balance["reserved"] or 0)
            if abs(quantity) > available + 1e-6:
                raise HTTPException(
                    status_code=400,
                    detail=f"可用库存不足，当前可用 {max(0, available):g}{req.unit}",
                )
        cursor = conn.execute(
            """
            INSERT INTO production_inventory_transactions(
                material_id, order_id, transaction_type, quantity, unit, warehouse_location,
                remark, operator_uid, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.material_id, req.order_id, req.transaction_type, quantity, req.unit,
                req.warehouse_location, req.remark, current_user["uid"], production_now(),
            ),
        )
        tx_id = int(cursor.lastrowid)
        if quantity > 0 and req.material_id:
            _material_service().allocate_open_requirements(conn, [req.order_id] if req.order_id else [])
    if req.order_id:
        _event(
            req.order_id,
            req.transaction_type,
            f"{quantity:g}{req.unit} {req.warehouse_location}".strip(),
            current_user,
        )
    return {"transaction_id": tx_id}


# Cutting and schedule
@router.get("/orders/{order_id}/cutting-sheet")
def get_cutting_sheet(order_id: int, current_user: Dict = Depends(read_production)):
    _order_or_404(order_id)
    sheet = production_db.fetch_one("SELECT * FROM production_cutting_sheets WHERE order_id=?", (order_id,))
    if sheet:
        sheet["items"] = production_db.fetch_all(
            "SELECT * FROM production_cutting_items WHERE sheet_id=? ORDER BY id", (sheet["id"],)
        )
    return {"sheet": sheet}


@router.post("/orders/{order_id}/cutting-sheet")
def create_cutting_sheet(
    order_id: int,
    current_user: Dict = Depends(require_permissions("production.cutting", "production.technical")),
):
    _order_or_404(order_id)
    existing = production_db.fetch_one("SELECT id FROM production_cutting_sheets WHERE order_id=?", (order_id,))
    if existing:
        raise HTTPException(status_code=409, detail="综合下料单已经存在")
    bom_status = production_db.fetch_one("SELECT status FROM production_bom_status WHERE order_id=?", (order_id,))
    if not bom_status or bom_status["status"] != "已发布":
        raise HTTPException(status_code=409, detail="BOM 未发布，不能生成综合下料单")
    requirement = _material_service().get_requirement_for_order(order_id)
    if not requirement:
        raise HTTPException(status_code=409, detail="物料需求尚未生成，请重新发布 BOM")
    if requirement["status"] not in {"已备料", "已领料"}:
        raise HTTPException(
            status_code=409,
            detail=f"当前物料状态为“{requirement['status']}”，备料完成后才能生成综合下料单",
        )
    bom_items = production_db.fetch_all(
        "SELECT * FROM production_bom_items WHERE order_id=? ORDER BY id", (order_id,)
    )
    now = production_now()
    with production_db.transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO production_cutting_sheets(order_id, created_by, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (order_id, current_user["uid"], now, now),
        )
        sheet_id = int(cursor.lastrowid)
        conn.executemany(
            """
            INSERT INTO production_cutting_items(sheet_id, bom_item_id, name, specification, quantity, unit)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (sheet_id, item["id"], item["name"], item["specification"], item["quantity"], item["unit"])
                for item in bom_items
            ],
        )
    _event(order_id, "生成综合下料单", "", current_user)
    return get_cutting_sheet(order_id, current_user)


@router.put("/orders/{order_id}/cutting-sheet")
def update_cutting_sheet(
    order_id: int,
    req: CuttingSheetUpdate,
    current_user: Dict = Depends(require_permissions("production.cutting")),
):
    sheet = production_db.fetch_one("SELECT * FROM production_cutting_sheets WHERE order_id=?", (order_id,))
    if not sheet:
        raise HTTPException(status_code=404, detail="综合下料单不存在")
    now = production_now()
    with production_db.transaction() as conn:
        for item in req.items:
            conn.execute(
                """
                UPDATE production_cutting_items
                SET actual_quantity=?, cutter=?, completed=?, remark=?
                WHERE id=? AND sheet_id=?
                """,
                (item.actual_quantity, item.cutter, int(item.completed), item.remark, item.id, sheet["id"]),
            )
        status = req.status or sheet["status"]
        conn.execute(
            "UPDATE production_cutting_sheets SET status=?, updated_at=? WHERE id=?", (status, now, sheet["id"])
        )
        if status in {"下料中", "已完成"}:
            conn.execute(
                "UPDATE production_orders SET cutting_started=1, stage=?, updated_at=? WHERE id=?",
                ("生产" if status == "已完成" else "下料", now, order_id),
            )
    _event(order_id, "更新综合下料单", req.status or "更新明细", current_user)
    return get_cutting_sheet(order_id, current_user)


@router.get("/orders/{order_id}/schedule")
def get_schedule(order_id: int, current_user: Dict = Depends(read_production)):
    _order_or_404(order_id)
    return {"schedule": production_db.fetch_one("SELECT * FROM production_schedules WHERE order_id=?", (order_id,))}


@router.put("/orders/{order_id}/schedule")
def save_schedule(
    order_id: int,
    req: ScheduleRequest,
    current_user: Dict = Depends(require_permissions("production.schedule")),
):
    _order_or_404(order_id)
    requirement = _material_service().get_requirement_for_order(order_id)
    if not requirement:
        raise HTTPException(status_code=409, detail="BOM 尚未发布，不能排单")
    if requirement["status"] not in {"已备料", "已领料"} and not req.allow_shortage:
        raise HTTPException(
            status_code=409,
            detail=f"当前物料状态为“{requirement['status']}”；确认允许缺料排单后才能保存",
        )
    now = production_now()
    with production_db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO production_schedules(
                order_id, planned_start, planned_end, producer, shortage_status, owner, updated_by, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(order_id) DO UPDATE SET
                planned_start=excluded.planned_start, planned_end=excluded.planned_end,
                producer=excluded.producer, shortage_status=excluded.shortage_status,
                owner=excluded.owner, updated_by=excluded.updated_by, updated_at=excluded.updated_at
            """,
            (
                order_id, req.planned_start, req.planned_end, req.producer,
                "不缺料" if requirement["status"] in {"已备料", "已领料"} else requirement["status"],
                req.owner, current_user["uid"], now,
            ),
        )
        conn.execute(
            "UPDATE production_orders SET shortage_status=?, updated_at=? WHERE id=?",
            (
                "不缺料" if requirement["status"] in {"已备料", "已领料"} else requirement["status"],
                now,
                order_id,
            ),
        )
    _event(order_id, "保存排单", f"{req.planned_start} - {req.planned_end}", current_user)
    return get_schedule(order_id, current_user)


# Operations, quality, finished goods, shipments
@router.get("/orders/{order_id}/operations")
def get_operations(order_id: int, current_user: Dict = Depends(read_production)):
    _order_or_404(order_id)
    return {"operations": production_db.fetch_all(
        "SELECT * FROM production_operations WHERE order_id=? ORDER BY sequence_no", (order_id,)
    )}


@router.put("/orders/{order_id}/operations/{operation_id}")
def update_operation(
    order_id: int,
    operation_id: int,
    req: OperationUpdateRequest,
    current_user: Dict = Depends(require_permissions("production.worker", "production.manager")),
):
    _order_or_404(order_id)
    if req.status not in {"待开始", "进行中", "已完成", "不适用"}:
        raise HTTPException(status_code=400, detail="工序状态不正确")
    operation = production_db.fetch_one(
        "SELECT * FROM production_operations WHERE id=? AND order_id=?", (operation_id, order_id)
    )
    if not operation:
        raise HTTPException(status_code=404, detail="生产工序不存在")
    now = production_now()
    started_at = operation.get("started_at")
    completed_at = operation.get("completed_at")
    if req.status == "进行中" and not started_at:
        started_at = now
    if req.status in {"已完成", "不适用"}:
        completed_at = now
    production_db.execute(
        """
        UPDATE production_operations
        SET status=?, operator_name=?, started_at=?, completed_at=?, remark=?
        WHERE id=? AND order_id=?
        """,
        (req.status, req.operator_name, started_at, completed_at, req.remark, operation_id, order_id),
    )
    remaining = production_db.fetch_one(
        "SELECT COUNT(*) AS count FROM production_operations WHERE order_id=? AND status NOT IN ('已完成','不适用')",
        (order_id,),
    )
    production_db.update_order(order_id, {"stage": "质检" if remaining and remaining["count"] == 0 else "生产"})
    _event(order_id, f"工序：{operation['name']}", req.status, current_user)
    return get_operations(order_id, current_user)


@router.get("/orders/{order_id}/quality")
def get_quality(order_id: int, current_user: Dict = Depends(read_production)):
    _order_or_404(order_id)
    rows = production_db.fetch_all(
        "SELECT * FROM production_quality_inspections WHERE order_id=? ORDER BY id DESC", (order_id,)
    )
    for row in rows:
        row["photos"] = json_loads(row.pop("photos_json", None), [])
    return {"inspections": rows}


@router.post("/orders/{order_id}/quality")
def create_quality(
    order_id: int,
    req: QualityRequest,
    current_user: Dict = Depends(require_permissions("production.quality")),
):
    _order_or_404(order_id)
    if req.result not in {"合格", "不合格"}:
        raise HTTPException(status_code=400, detail="质检结果不正确")
    if req.result == "合格":
        remaining = production_db.fetch_one(
            "SELECT COUNT(*) AS count FROM production_operations WHERE order_id=? AND status NOT IN ('已完成','不适用')",
            (order_id,),
        )
        if remaining and remaining["count"]:
            raise HTTPException(status_code=409, detail="仍有生产工序未完成，不能判定成品合格")
    production_db.execute(
        """
        INSERT INTO production_quality_inspections(
            order_id, result, inspector, return_operation, photos_json, remark, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (order_id, req.result, req.inspector, req.return_operation, json.dumps(req.photos, ensure_ascii=False), req.remark, production_now()),
    )
    if req.result == "合格":
        production_db.update_order(order_id, {"stage": "入库"})
    else:
        production_db.update_order(order_id, {"stage": "生产"})
        if req.return_operation:
            production_db.execute(
                """
                UPDATE production_operations SET status='待开始', completed_at=NULL
                WHERE order_id=? AND name=?
                """,
                (order_id, req.return_operation),
            )
    _event(order_id, "成品质检", req.result, current_user)
    return get_quality(order_id, current_user)


@router.get("/finished-goods")
def list_finished_goods(current_user: Dict = Depends(read_production)):
    return {"finished_goods": production_db.fetch_all(
        """
        SELECT f.*, o.order_no, o.customer, o.project
        FROM production_finished_goods f JOIN production_orders o ON o.id=f.order_id
        ORDER BY f.id DESC
        """
    )}


@router.post("/orders/{order_id}/finished-goods/inbound")
def inbound_finished_good(
    order_id: int,
    req: FinishedGoodInboundRequest,
    current_user: Dict = Depends(require_permissions("production.warehouse")),
):
    _order_or_404(order_id)
    if production_db.fetch_one("SELECT id FROM production_finished_goods WHERE order_id=?", (order_id,)):
        raise HTTPException(status_code=409, detail="该生产订单已经办理成品入库")
    quality = production_db.fetch_one(
        "SELECT result FROM production_quality_inspections WHERE order_id=? ORDER BY id DESC LIMIT 1", (order_id,)
    )
    if not quality or quality["result"] != "合格":
        raise HTTPException(status_code=409, detail="成品质检未合格，不能入库")
    now = production_now()
    prefix = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("CP%Y%m%d")
    with production_db.transaction() as conn:
        finished_no = production_db._next_number(conn, "production_finished_goods", "finished_no", prefix)
        cursor = conn.execute(
            """
            INSERT INTO production_finished_goods(finished_no, order_id, warehouse_location, inbound_by, inbound_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (finished_no, order_id, req.warehouse_location, current_user["uid"], now),
        )
        finished_id = int(cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO production_inventory_transactions(
                order_id, finished_good_id, transaction_type, quantity, unit,
                warehouse_location, operator_uid, created_at
            ) VALUES (?, ?, '成品入库', 1, '樘', ?, ?, ?)
            """,
            (order_id, finished_id, req.warehouse_location, current_user["uid"], now),
        )
        conn.execute(
            "UPDATE production_orders SET stage='发货', updated_at=? WHERE id=?", (now, order_id)
        )
    _event(order_id, "成品入库", finished_no, current_user)
    return {"finished_good": production_db.fetch_one("SELECT * FROM production_finished_goods WHERE id=?", (finished_id,))}


@router.get("/shipments")
def list_shipments(current_user: Dict = Depends(read_production)):
    shipments = production_db.fetch_all("SELECT * FROM production_shipments ORDER BY id DESC")
    for shipment in shipments:
        shipment["photos"] = json_loads(shipment.pop("photos_json", None), [])
        shipment["items"] = production_db.fetch_all(
            """
            SELECT si.*, o.order_no, o.customer, o.project, f.finished_no
            FROM production_shipment_items si
            JOIN production_orders o ON o.id=si.order_id
            JOIN production_finished_goods f ON f.id=si.finished_good_id
            WHERE si.shipment_id=?
            """,
            (shipment["id"],),
        )
    return {"shipments": shipments}


@router.get("/shipments/{shipment_id}/export.xlsx")
def export_shipment_document(
    shipment_id: int,
    current_user: Dict = Depends(read_production),
):
    _ensure_document_permission(current_user, "production.shipping")
    document = _document_or_404(build_shipment_document, shipment_id)
    return _xlsx_response(document, f"发货单_{document.document_no}.xlsx")


@router.get("/shipments/{shipment_id}/print")
def print_shipment_document(
    shipment_id: int,
    current_user: Dict = Depends(read_production),
):
    _ensure_document_permission(current_user, "production.shipping")
    return HTMLResponse(render_print_html(
        _document_or_404(build_shipment_document, shipment_id)
    ))


@router.post("/shipments")
def create_shipment(
    req: ShipmentRequest,
    current_user: Dict = Depends(require_permissions("production.shipping")),
):
    order_ids = list(dict.fromkeys(req.order_ids))
    if not order_ids:
        raise HTTPException(status_code=400, detail="发货单至少需要一张生产订单")
    placeholders = ",".join("?" for _ in order_ids)
    goods = production_db.fetch_all(
        f"SELECT * FROM production_finished_goods WHERE order_id IN ({placeholders}) AND status='已入库'",
        order_ids,
    )
    if len(goods) != len(order_ids):
        raise HTTPException(status_code=409, detail="所选生产订单中存在未入库或已出库成品")
    now = production_now()
    prefix = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("FH%Y%m%d")
    try:
        with production_db.transaction() as conn:
            shipment_no = production_db._next_number(conn, "production_shipments", "shipment_no", prefix)
            cursor = conn.execute(
                """
                INSERT INTO production_shipments(
                    shipment_no, customer, project, address, contact, phone, logistics,
                    tracking_no, photos_json, remark, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    shipment_no, req.customer, req.project, req.address, req.contact, req.phone,
                    req.logistics, req.tracking_no, json.dumps(req.photos, ensure_ascii=False),
                    req.remark, current_user["uid"], now, now,
                ),
            )
            shipment_id = int(cursor.lastrowid)
            conn.executemany(
                "INSERT INTO production_shipment_items(shipment_id, order_id, finished_good_id) VALUES (?, ?, ?)",
                [(shipment_id, good["order_id"], good["id"]) for good in goods],
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="所选成品已经加入其他发货单") from exc
    for order_id in order_ids:
        _event(order_id, "创建发货单", shipment_no, current_user)
    return {"shipment_id": shipment_id, "shipment_no": shipment_no}


@router.put("/shipments/{shipment_id}/status")
def update_shipment_status(
    shipment_id: int,
    req: ShipmentStatusRequest,
    current_user: Dict = Depends(require_permissions("production.shipping")),
):
    allowed = {"待发货", "已出库", "运输中", "已签收", "已完成"}
    if req.status not in allowed:
        raise HTTPException(status_code=400, detail="发货状态不正确")
    shipment = production_db.fetch_one("SELECT * FROM production_shipments WHERE id=?", (shipment_id,))
    if not shipment:
        raise HTTPException(status_code=404, detail="发货单不存在")
    if req.status == shipment["status"]:
        return {"success": True}
    allowed_transitions = {
        "待发货": {"已出库"},
        "已出库": {"运输中", "已签收", "已完成"},
        "运输中": {"已签收", "已完成"},
        "已签收": {"已完成"},
        "已完成": set(),
    }
    if req.status not in allowed_transitions.get(shipment["status"], set()):
        raise HTTPException(
            status_code=409,
            detail=f"发货状态不能从“{shipment['status']}”变更为“{req.status}”",
        )
    now = production_now()
    with production_db.transaction() as conn:
        conn.execute(
            "UPDATE production_shipments SET status=?, tracking_no=?, remark=?, updated_at=? WHERE id=?",
            (req.status, req.tracking_no or shipment["tracking_no"], req.remark or shipment["remark"], now, shipment_id),
        )
        if req.status == "已出库":
            items = conn.execute(
                "SELECT * FROM production_shipment_items WHERE shipment_id=?", (shipment_id,)
            ).fetchall()
            for item in items:
                conn.execute(
                    "UPDATE production_finished_goods SET status='已出库', outbound_at=? WHERE id=?",
                    (now, item["finished_good_id"]),
                )
                conn.execute(
                    """
                    INSERT INTO production_inventory_transactions(
                        order_id, finished_good_id, transaction_type, quantity, unit,
                        operator_uid, created_at
                    ) VALUES (?, ?, '成品出库', -1, '樘', ?, ?)
                    """,
                    (item["order_id"], item["finished_good_id"], current_user["uid"], now),
                )
        if req.status in {"已签收", "已完成"}:
            conn.execute(
                """
                UPDATE production_orders SET stage='完成', status='已完成', updated_at=?
                WHERE id IN (SELECT order_id FROM production_shipment_items WHERE shipment_id=?)
                """,
                (now, shipment_id),
            )
    order_rows = production_db.fetch_all(
        "SELECT order_id FROM production_shipment_items WHERE shipment_id=?", (shipment_id,)
    )
    for row in order_rows:
        _event(int(row["order_id"]), f"发货单{req.status}", shipment["shipment_no"], current_user)
    return {"success": True}
