"""Authenticated whole-order BOM workbench endpoints."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user, require_uids
from bom_generation_service import BomGenerationService
from bom_readiness import automatic_verification_status, bom_blockers
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
    publish_blockers = []
    for row in detail["rows"]:
        row["blockers"] = bom_blockers(row)
        row["verification_status"] = automatic_verification_status(row)
        publish_blockers.extend(row["blockers"])
    if not detail["rows"]:
        publish_blockers.append({"field": "items", "message": "BOM没有明细行"})
    detail["publish_blockers"] = publish_blockers
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
        fulfillment_db.verify_bom_items(door_unit_id, request.item_ids, current_user)
        return {"bom": _detail(door_unit_id), "message": f"已重新检查 {len(request.item_ids)} 项"}
    except Exception as exc:
        raise translate_error(exc, door_unit_id) from exc


@router.post("/door-units/{door_unit_id}/publish")
def publish_bom(door_unit_id: int, request: BomPublishRequest, current_user: Dict = Depends(get_current_user)):
    try:
        package = fulfillment_db.latest_bom_package(door_unit_id)
        if package["status"] == "已确认":
            fulfillment_db.publish_bom(door_unit_id, request.remark, current_user)
            return {
                "bom": _detail(door_unit_id),
                "message": "该BOM版本已经发布，未重复生成物料需求",
                "idempotent": True,
            }
        if package["status"] != "草稿":
            raise RuntimeError("当前BOM状态不能发布")
        rows = fulfillment_db.fetch_all(
            "SELECT * FROM fulfillment_components WHERE technical_package_id=? ORDER BY line_no, id",
            (package["id"],),
        )
        blockers = [blocker for row in rows for blocker in bom_blockers(row)]
        if not rows:
            blockers.append({"field": "items", "message": "BOM没有明细行"})
        if blockers:
            first = blockers[0]
            raise HTTPException(status_code=409, detail={
                "code": "BOM_PUBLISH_BLOCKED",
                "field": first.get("field", ""),
                "door_unit_id": door_unit_id,
                "bom_item_id": first.get("id"),
                "message": f"BOM还有 {len(blockers)} 项发布前问题",
                "suggestion": "按问题清单补齐对应字段后再发布",
                "blockers": blockers,
            })
        fulfillment_db.publish_bom(door_unit_id, request.remark, current_user)
        return {"bom": _detail(door_unit_id), "message": "BOM版本已发布并冻结", "idempotent": False}
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
