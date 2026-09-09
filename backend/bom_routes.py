"""Authenticated whole-order BOM workbench endpoints."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user, require_uids
from bom_generation_service import BomGenerationService
from bom_models import (
    BomDraftUpdate,
    BomNewVersionRequest,
    BomPublishRequest,
    BomVerifyRequest,
)
from door_cad.services.fulfillment_adapter import adapt_fulfillment_frame
from fulfillment_routes import fulfillment_db
from fulfillment_models import ChangeCreate


router = APIRouter(
    prefix="/api/bom",
    tags=["whole-order-bom"],
    dependencies=[Depends(require_uids("A"))],
)


def bom_error(
    status_code: int,
    code: str,
    message: str,
    *,
    field: str = "",
    door_unit_id: int | None = None,
    bom_item_id: int | None = None,
    suggestion: str = "",
) -> HTTPException:
    return HTTPException(status_code=status_code, detail={
        "code": code,
        "field": field,
        "door_unit_id": door_unit_id,
        "bom_item_id": bom_item_id,
        "message": message,
        "suggestion": suggestion,
    })


def translate_error(exc: Exception, door_unit_id: int | None = None) -> HTTPException:
    if isinstance(exc, LookupError):
        return bom_error(404, "BOM_NOT_FOUND", str(exc), door_unit_id=door_unit_id)
    if isinstance(exc, RuntimeError):
        code = "BOM_VERSION_FROZEN" if "冻结" in str(exc) else "BOM_STATE_CONFLICT"
        return bom_error(409, code, str(exc), door_unit_id=door_unit_id)
    if isinstance(exc, (ValueError, sqlite3.IntegrityError)):
        return bom_error(422, "BOM_VALIDATION_FAILED", str(exc), door_unit_id=door_unit_id)
    return bom_error(500, "BOM_OPERATION_FAILED", f"BOM操作失败：{exc}", door_unit_id=door_unit_id)


def _detail(door_unit_id: int, version: int | None = None) -> Dict[str, Any]:
    detail = fulfillment_db.get_bom_detail(door_unit_id, version)
    try:
        frame = adapt_fulfillment_frame(fulfillment_db, door_unit_id)
        detail["frame_status"] = {
            "applicable": frame.applicable,
            "can_calculate": frame.can_calculate,
            "blocking": False,
            "deferred": bool(frame.errors),
            "technical_package_id": frame.technicalPackageId,
            "errors": [item.model_dump(mode="json") for item in frame.errors],
            "warnings": [item.model_dump(mode="json") for item in frame.warnings],
        }
    except LookupError:
        detail["frame_status"] = {
            "applicable": False, "can_calculate": False, "blocking": False,
            "deferred": True, "errors": [], "warnings": [],
        }
    return detail


@router.get("/workbench")
def workbench(
    q: str = Query(""),
    status: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    current_user: Dict = Depends(get_current_user),
):
    return fulfillment_db.list_bom_workbench(q.strip(), status.strip(), page, page_size)


@router.get("/door-units/{door_unit_id}")
def get_bom(door_unit_id: int, version: int | None = Query(None), current_user: Dict = Depends(get_current_user)):
    try:
        return {"bom": _detail(door_unit_id, version)}
    except Exception as exc:
        raise translate_error(exc, door_unit_id) from exc


@router.post("/door-units/{door_unit_id}/generate")
def generate_bom(door_unit_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        BomGenerationService(fulfillment_db).generate(door_unit_id, current_user)
        return {"bom": _detail(door_unit_id), "message": "整樘BOM已按当前规则生成"}
    except Exception as exc:
        raise translate_error(exc, door_unit_id) from exc


@router.put("/door-units/{door_unit_id}/draft")
def update_draft(door_unit_id: int, request: BomDraftUpdate, current_user: Dict = Depends(get_current_user)):
    try:
        fulfillment_db.update_bom_draft(door_unit_id, request, current_user)
        return {"bom": _detail(door_unit_id), "message": "BOM草稿已保存"}
    except Exception as exc:
        raise translate_error(exc, door_unit_id) from exc


@router.post("/door-units/{door_unit_id}/verify")
def verify_bom(door_unit_id: int, request: BomVerifyRequest, current_user: Dict = Depends(get_current_user)):
    try:
        package = fulfillment_db.latest_bom_package(door_unit_id)
        if package["status"] != "草稿":
            raise RuntimeError("BOM版本已确认冻结，不能继续核验")
        placeholders = ",".join("?" for _ in request.item_ids)
        rows = fulfillment_db.fetch_all(
            f"""SELECT * FROM fulfillment_components
                WHERE technical_package_id=? AND id IN ({placeholders})""",
            (package["id"], *request.item_ids),
        )
        found = {int(row["id"]): row for row in rows}
        for item_id in request.item_ids:
            row = found.get(item_id)
            if row is None:
                raise bom_error(
                    422, "BOM_ITEM_NOT_FOUND", "BOM行不存在或不属于当前版本",
                    door_unit_id=door_unit_id, bom_item_id=item_id,
                    suggestion="刷新BOM后重新选择",
                )
            if row["match_status"] != "已匹配" or row["material_id"] is None:
                raise bom_error(
                    422, "BOM_ITEM_NOT_MATCHED", "只有唯一匹配到物料档案的BOM行才能核验",
                    field="material_id", door_unit_id=door_unit_id, bom_item_id=item_id,
                    suggestion="先选择有效物料档案，再执行核验",
                )
            if float(row["planned_quantity"] or 0) <= 0:
                raise bom_error(
                    422, "BOM_QUANTITY_INVALID", "计划用量必须大于0",
                    field="planned_quantity", door_unit_id=door_unit_id, bom_item_id=item_id,
                    suggestion="填写准确计划用量",
                )
        fulfillment_db.verify_bom_items(door_unit_id, request.item_ids, current_user)
        return {"bom": _detail(door_unit_id), "message": f"已核验 {len(request.item_ids)} 项"}
    except HTTPException:
        raise
    except Exception as exc:
        raise translate_error(exc, door_unit_id) from exc


@router.post("/door-units/{door_unit_id}/publish")
def publish_bom(door_unit_id: int, request: BomPublishRequest, current_user: Dict = Depends(get_current_user)):
    try:
        package = fulfillment_db.latest_bom_package(door_unit_id)
        if package["status"] != "草稿":
            raise RuntimeError("BOM版本已确认冻结，不能重复发布")
        rows = fulfillment_db.fetch_all(
            "SELECT * FROM fulfillment_components WHERE technical_package_id=? ORDER BY line_no, id",
            (package["id"],),
        )
        blockers = []
        if not rows:
            blockers.append({"field": "items", "message": "BOM没有明细行"})
        for row in rows:
            if row["match_status"] not in {"已匹配", "无需物料"} or (
                row["match_status"] == "已匹配" and row["material_id"] is None
            ):
                blockers.append({"id": row["id"], "field": "material_id", "message": "物料尚未唯一匹配"})
            if float(row["planned_quantity"] or 0) <= 0:
                blockers.append({"id": row["id"], "field": "planned_quantity", "message": "计划用量必须大于0"})
            if row["verification_status"] != "已核验":
                blockers.append({"id": row["id"], "field": "verification_status", "message": "BOM行尚未核验"})
        if blockers:
            first = blockers[0]
            raise HTTPException(status_code=409, detail={
                "code": "BOM_PUBLISH_BLOCKED",
                "field": first.get("field", ""),
                "door_unit_id": door_unit_id,
                "bom_item_id": first.get("id"),
                "message": f"BOM还有 {len(blockers)} 项发布前问题",
                "suggestion": "按问题清单补齐物料、数量和核验状态后再发布",
                "blockers": blockers,
            })
        fulfillment_db.publish_bom(door_unit_id, request.remark, current_user)
        return {"bom": _detail(door_unit_id), "message": "BOM版本已发布并冻结"}
    except HTTPException:
        raise
    except Exception as exc:
        raise translate_error(exc, door_unit_id) from exc


@router.post("/door-units/{door_unit_id}/new-version")
def new_version(door_unit_id: int, request: BomNewVersionRequest, current_user: Dict = Depends(get_current_user)):
    try:
        fulfillment_db.create_change(
            door_unit_id,
            ChangeCreate(reason=request.reason, impact_note=request.impact_note),
            current_user,
        )
        return {"bom": _detail(door_unit_id), "message": "已创建新的BOM草稿版本"}
    except Exception as exc:
        raise translate_error(exc, door_unit_id) from exc


@router.get("/door-units/{door_unit_id}/diff/{from_version}/{to_version}")
def bom_diff(
    door_unit_id: int,
    from_version: int,
    to_version: int,
    current_user: Dict = Depends(get_current_user),
):
    try:
        return {"diff": fulfillment_db.diff_bom_versions(door_unit_id, from_version, to_version)}
    except Exception as exc:
        raise translate_error(exc, door_unit_id) from exc
