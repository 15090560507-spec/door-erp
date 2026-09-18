"""Shared readiness rules for BOM draft rows."""

from __future__ import annotations

from typing import Any, Mapping


SELF_MADE_KINDS = {"assembly", "manufactured_part"}


def is_self_made(row: Mapping[str, Any]) -> bool:
    return row.get("procurement_mode") == "make" or row.get("item_kind") in SELF_MADE_KINDS


def bom_blockers(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    row_id = row.get("id")
    for field, label in (
        ("name", "部件名称"),
        ("category", "分类"),
        ("unit", "单位"),
        ("acquisition_method", "取得方式"),
    ):
        if not str(row.get(field) or "").strip():
            blockers.append({"id": row_id, "field": field, "message": f"请填写{label}"})

    try:
        planned_quantity = float(row.get("planned_quantity") or 0)
    except (TypeError, ValueError):
        planned_quantity = 0
    if planned_quantity <= 0:
        blockers.append({"id": row_id, "field": "planned_quantity", "message": "计划用量必须大于0"})

    if not is_self_made(row) and not row.get("material_id"):
        blockers.append({"id": row_id, "field": "material_id", "message": "请选择物料档案"})
    return blockers


def automatic_verification_status(row: Mapping[str, Any]) -> str:
    return "已核验" if not bom_blockers(row) else "待核验"
