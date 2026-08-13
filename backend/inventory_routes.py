"""Authenticated APIs for factory-wide material and inventory management."""

from __future__ import annotations

import sqlite3
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user
from inventory_database import InventoryDatabase
from inventory_models import AdjustmentCreate, LocationCreate, MaterialCreate, MaterialUpdate, WarehouseCreate
from inventory_service import InventoryService


router = APIRouter(prefix="/api/inventory", tags=["inventory"])
inventory_db = InventoryDatabase()
inventory_service = InventoryService(inventory_db)


def configure_inventory_database(database: InventoryDatabase) -> None:
    global inventory_db, inventory_service
    inventory_db = database
    inventory_service = InventoryService(database)


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
