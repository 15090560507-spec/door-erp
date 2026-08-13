"""Authenticated APIs for factory-wide material and inventory management."""

from __future__ import annotations

import sqlite3
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user
from inventory_database import InventoryDatabase
from inventory_models import (
    AdjustmentCreate,
    IncomingInspectionCreate,
    LocationCreate,
    MaterialCreate,
    MaterialUpdate,
    PurchaseOrderCreate,
    PurchaseReceiptCreate,
    RequirementSupplement,
    WarehouseCreate,
)
from inventory_service import InventoryService
from purchasing_service import PurchasingService
from requirement_service import RequirementService


router = APIRouter(prefix="/api/inventory", tags=["inventory"])
inventory_db = InventoryDatabase()
inventory_service = InventoryService(inventory_db)
requirement_service = RequirementService(inventory_db)
purchasing_service = PurchasingService(inventory_db)


def configure_inventory_database(database: InventoryDatabase) -> None:
    global inventory_db, inventory_service, requirement_service, purchasing_service
    inventory_db = database
    inventory_service = InventoryService(database)
    requirement_service = RequirementService(database)
    purchasing_service = PurchasingService(database)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, sqlite3.IntegrityError):
        message = str(exc)
        if "inventory_materials.code" in message:
            message = "物料编码已经存在"
        elif "inventory_warehouses.code" in message:
            message = "仓库编码已经存在"
        elif "inventory_locations.warehouse_id, inventory_locations.code" in message:
            message = "该仓库中已经存在相同库位编码"
        elif "inventory_transactions.source_type" in message:
            message = "该来源单据行已经入账，不能重复提交"
        return HTTPException(status_code=409, detail=message)
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="库存操作失败，请查看服务端日志")


@router.get("/materials")
def list_materials(
    q: str = Query(""),
    category: str = Query(""),
    material_type: str = Query(""),
    include_inactive: bool = Query(False),
    current_user: Dict = Depends(get_current_user),
):
    return {
        "materials": inventory_service.list_materials(
            q=q,
            category=category,
            material_type=material_type,
            active_only=not include_inactive,
        )
    }


@router.post("/materials", status_code=201)
def create_material(req: MaterialCreate, current_user: Dict = Depends(get_current_user)):
    try:
        return {"material": inventory_service.create_material(**req.model_dump()), "message": "物料创建成功"}
    except Exception as exc:
        raise _error(exc) from exc


@router.put("/materials/{material_id}")
def update_material(material_id: int, req: MaterialUpdate, current_user: Dict = Depends(get_current_user)):
    try:
        return {
            "material": inventory_service.update_material(material_id, req.model_dump()),
            "message": "物料更新成功",
        }
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/warehouses")
def list_warehouses(current_user: Dict = Depends(get_current_user)):
    return {"warehouses": inventory_service.list_warehouses()}


@router.post("/warehouses", status_code=201)
def create_warehouse(req: WarehouseCreate, current_user: Dict = Depends(get_current_user)):
    try:
        warehouse = inventory_service.create_warehouse(**req.model_dump())
        return {"warehouse": warehouse, "message": "仓库创建成功"}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/warehouses/{warehouse_id}/locations", status_code=201)
def create_location(warehouse_id: int, req: LocationCreate, current_user: Dict = Depends(get_current_user)):
    try:
        location = inventory_service.create_location(warehouse_id, req.code, req.name, req.remark)
        return {"location": location, "message": "库位创建成功"}
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/balances")
def list_balances(
    q: str = Query(""),
    warehouse_id: Optional[int] = Query(None),
    low_stock_only: bool = Query(False),
    current_user: Dict = Depends(get_current_user),
):
    return {
        "balances": inventory_service.list_balances(
            q=q,
            warehouse_id=warehouse_id,
            low_stock_only=low_stock_only,
        )
    }


@router.get("/transactions")
def list_transactions(
    material_id: Optional[int] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    current_user: Dict = Depends(get_current_user),
):
    return {"transactions": inventory_service.list_transactions(material_id=material_id, limit=limit)}


@router.post("/adjustments", status_code=201)
def create_adjustment(req: AdjustmentCreate, current_user: Dict = Depends(get_current_user)):
    try:
        document = inventory_service.create_adjustment(
            [item.model_dump() for item in req.items],
            req.remark,
            str(current_user.get("uid") or ""),
        )
        return {"adjustment": document, "message": "盘点调整草稿已保存"}
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/adjustments/{adjustment_id}")
def get_adjustment(adjustment_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        return {"adjustment": inventory_service.get_adjustment(adjustment_id)}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/adjustments/{adjustment_id}/confirm")
def confirm_adjustment(adjustment_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        document = inventory_service.confirm_adjustment(
            adjustment_id,
            str(current_user.get("uid") or ""),
        )
        return {"adjustment": document, "message": "盘点调整已确认并入账"}
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/requirements")
def list_requirements(
    q: str = Query(""),
    status: str = Query(""),
    current_user: Dict = Depends(get_current_user),
):
    return {"requirements": requirement_service.list_requirements(q=q, status=status)}


@router.get("/requirements/{requirement_id}")
def get_requirement(requirement_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        return {"requirement": requirement_service.get_requirement(requirement_id)}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/requirements/{requirement_id}/reallocate")
def reallocate_requirement(requirement_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        return {
            "requirement": requirement_service.reallocate_requirement(requirement_id),
            "message": "库存预留已按交期重新分配",
        }
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/requirement-items/{item_id}/supplement")
def supplement_requirement(item_id: int, req: RequirementSupplement, current_user: Dict = Depends(get_current_user)):
    try:
        return {
            "requirement": requirement_service.supplement_item(
                item_id,
                material_id=req.material_id,
                quantity=req.quantity,
                remark=req.remark,
            ),
            "message": "补料需求已建立",
        }
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/purchasing/shortages")
def list_purchase_shortages(q: str = Query(""), current_user: Dict = Depends(get_current_user)):
    try:
        return {"shortages": purchasing_service.list_shortages(q=q)}
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/purchasing/orders")
def list_purchase_orders(
    status: str = Query(""), q: str = Query(""), current_user: Dict = Depends(get_current_user)
):
    return {"orders": purchasing_service.list_orders(status=status, q=q)}


@router.post("/purchasing/orders", status_code=201)
def create_purchase_order(req: PurchaseOrderCreate, current_user: Dict = Depends(get_current_user)):
    try:
        order = purchasing_service.create_order(req.model_dump(), str(current_user.get("uid") or ""))
        return {"order": order, "message": "采购单草稿已创建"}
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/purchasing/orders/{order_id}")
def get_purchase_order(order_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        return {"order": purchasing_service.get_order(order_id)}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/purchasing/orders/{order_id}/confirm")
def confirm_purchase_order(order_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        order = purchasing_service.confirm_order(order_id, str(current_user.get("uid") or ""))
        return {"order": order, "message": "采购单已确认，需求缺口已进入采购覆盖"}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/purchasing/orders/{order_id}/cancel")
def cancel_purchase_order(order_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        return {"order": purchasing_service.cancel_order(order_id), "message": "采购单已取消，未到货数量已释放"}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/purchasing/orders/{order_id}/receipts", status_code=201)
def create_purchase_receipt(
    order_id: int, req: PurchaseReceiptCreate, current_user: Dict = Depends(get_current_user)
):
    try:
        receipt = purchasing_service.create_receipt(order_id, req.model_dump(), str(current_user.get("uid") or ""))
        return {"receipt": receipt, "message": "到货已登记，等待仓库来料检验"}
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/receipts")
def list_purchase_receipts(status: str = Query(""), current_user: Dict = Depends(get_current_user)):
    return {"receipts": purchasing_service.list_receipts(status=status)}


@router.get("/receipts/{receipt_id}")
def get_purchase_receipt(receipt_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        return {"receipt": purchasing_service.get_receipt(receipt_id)}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/receipt-items/{receipt_item_id}/inspect")
def inspect_purchase_receipt_item(
    receipt_item_id: int,
    req: IncomingInspectionCreate,
    current_user: Dict = Depends(get_current_user),
):
    try:
        receipt = purchasing_service.inspect_receipt_item(
            receipt_item_id,
            req.model_dump(),
            str(current_user.get("uid") or ""),
        )
        return {"receipt": receipt, "message": "来料检验已完成，接收数量已正式入库"}
    except Exception as exc:
        raise _error(exc) from exc
