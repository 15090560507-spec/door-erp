"""Map frozen fulfillment parameters into the canonical v1.4.3 frame calculator."""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from door_cad.models import FrameInput, ProjectGeometry, ProjectMeta
from door_cad.services.frame_calculator import calculate_frame_project
from fulfillment_database import json_loads


UNSUPPORTED_FRAME_PRODUCTS = {"平移门", "地弹簧门", "天弹簧门", "铝艺栅栏", "雨棚", "牌匾", "其他"}


class FrameMappingIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    field: str
    message: str
    severity: Literal["error", "warning"]


class FrameInputAdaptation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    doorUnitId: int
    technicalPackageId: int
    version: int
    inputs: Optional[FrameInput] = None
    project: ProjectMeta
    errors: list[FrameMappingIssue] = Field(default_factory=list)
    warnings: list[FrameMappingIssue] = Field(default_factory=list)

    @property
    def can_calculate(self) -> bool:
        return self.inputs is not None and not self.errors


def _pair(value: Any) -> Optional[tuple[float, float]]:
    numbers = re.findall(r"\d+(?:\.\d+)?", str(value or ""))
    if len(numbers) < 2:
        return None
    short, long = float(numbers[0]), float(numbers[1])
    if short <= 0 or long <= short:
        return None
    return short, long


def _hinge_count(value: Any) -> Optional[int]:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else None


def adapt_fulfillment_frame(database: Any, door_unit_id: int) -> FrameInputAdaptation:
    row = database.fetch_one(
        """SELECT d.id AS door_id, d.production_no, d.source_task_id,
                  o.order_no, o.sales_order_no, o.project, p.id AS package_id, p.version,
                  p.product_snapshot_json
           FROM fulfillment_door_units d
           JOIN fulfillment_orders o ON o.id=d.order_id
           JOIN fulfillment_technical_packages p ON p.door_unit_id=d.id
           WHERE d.id=? ORDER BY p.version DESC LIMIT 1""",
        (door_unit_id,),
    )
    if not row:
        raise LookupError("门樘生产单或技术包不存在")
    params = json_loads(row["product_snapshot_json"], {})
    project = ProjectMeta(
        orderNo=str(row["sales_order_no"] or row["order_no"] or row["production_no"] or ""),
        projectName=str(row["project"] or row["production_no"] or "门框下料"),
        taskId=str(row["source_task_id"] or "") or None,
    )
    errors: list[FrameMappingIssue] = []
    warnings: list[FrameMappingIssue] = []

    product_name = str(params.get("product_name") or "").strip()
    if product_name in UNSUPPORTED_FRAME_PRODUCTS:
        errors.append(FrameMappingIssue(
            code="FRAME_PRODUCT_UNSUPPORTED", field="product_name",
            message=f"{product_name}尚未配置 v1.4.3 门框加工规则", severity="error",
        ))
    process = str(params.get("frame_process") or "").strip()
    if process == "老工艺":
        errors.append(FrameMappingIssue(
            code="OLD_FRAME_PROCESS_UNSUPPORTED", field="frame_process",
            message="当前门框下料模块仅支持新工艺，老工艺需补充专用加工规则", severity="error",
        ))
    elif not process:
        warnings.append(FrameMappingIssue(
            code="FRAME_PROCESS_DEFAULTED", field="frame_process",
            message="图纸未记录门框工艺，暂按新工艺映射，生成前请核验", severity="warning",
        ))

    width = float(params.get("dw") or 0)
    height = float(params.get("dh") or 0)
    if width <= 0:
        errors.append(FrameMappingIssue(code="WIDTH_REQUIRED", field="dw", message="门洞宽度必须大于0", severity="error"))
    if height <= 0:
        errors.append(FrameMappingIssue(code="HEIGHT_REQUIRED", field="dh", message="门洞高度必须大于0", severity="error"))

    left = _pair(params.get("fw_left_str"))
    right = _pair(params.get("fw_right_str"))
    top = _pair(params.get("fw_top_str"))
    threshold_type = str(params.get("threshold_type") or "").strip()
    bottom = _pair(params.get("th_str"))
    for field, parsed, label in (
        ("fw_left_str", left, "左框小边/大边"),
        ("fw_right_str", right, "右框小边/大边"),
        ("fw_top_str", top, "上框小边/大边"),
    ):
        if parsed is None:
            errors.append(FrameMappingIssue(code="FRAME_SIZE_REQUIRED", field=field, message=f"{label}格式应为55/75", severity="error"))
    if left and right and left != right:
        errors.append(FrameMappingIssue(
            code="ASYMMETRIC_SIDE_FRAME_UNSUPPORTED", field="fw_right_str",
            message="左右框规格不一致，当前 v1.4.3 计算器不能共用同一侧框参数", severity="error",
        ))

    include_bottom = threshold_type not in {"吊脚", "无下框"}
    if include_bottom and bottom is None:
        errors.append(FrameMappingIssue(
            code="BOTTOM_FRAME_SIZE_REQUIRED", field="th_str",
            message="当前门槛需要填写下框小边/大边，例如45/60", severity="error",
        ))

    opening_mechanism = str(params.get("sel_hys") or params.get("hys") or "").strip()
    if opening_mechanism and "合页" not in opening_mechanism:
        errors.append(FrameMappingIssue(
            code="OPENING_MECHANISM_UNSUPPORTED", field="sel_hys",
            message=f"开启机构“{opening_mechanism}”需要专用门框孔位规则，不能套用合页模板", severity="error",
        ))
    hinge_count = _hinge_count(params.get("hysl") or params.get("pzsl"))
    if hinge_count is None:
        hinge_count = 3
        warnings.append(FrameMappingIssue(
            code="HINGE_COUNT_DEFAULTED", field="hysl",
            message="未识别到合页数量，暂按 v1.4.3 标准3个/扇，生成前请核验", severity="warning",
        ))
    elif hinge_count not in {3, 4}:
        errors.append(FrameMappingIssue(
            code="HINGE_COUNT_UNSUPPORTED", field="hysl",
            message=f"v1.4.3 门框孔位仅支持3或4个合页，当前为{hinge_count}个", severity="error",
        ))

    inputs: Optional[FrameInput] = None
    if not errors and left and top:
        resolved_bottom = bottom or top
        try:
            inputs = FrameInput(
                doorWidth=width,
                doorHeight=height,
                linkedSideSizes=True,
                outerSideShort=left[0],
                outerSideLong=left[1],
                hingeStyle=opening_mechanism or "可拆卸合页",
                hingeCount=hinge_count,
                includeBottom=include_bottom,
                sameTopBottom=resolved_bottom == top,
                topShort=top[0],
                topLong=top[1],
                bottomShort=resolved_bottom[0],
                bottomLong=resolved_bottom[1],
            )
        except ValueError as exc:
            errors.append(FrameMappingIssue(
                code="FRAME_INPUT_INVALID", field="frame", message=str(exc), severity="error",
            ))

    return FrameInputAdaptation(
        doorUnitId=door_unit_id,
        technicalPackageId=int(row["package_id"]),
        version=int(row["version"]),
        inputs=inputs,
        project=project,
        errors=errors,
        warnings=warnings,
    )


def calculate_fulfillment_frame(database: Any, door_unit_id: int) -> tuple[FrameInputAdaptation, ProjectGeometry]:
    adaptation = adapt_fulfillment_frame(database, door_unit_id)
    if not adaptation.can_calculate or adaptation.inputs is None:
        message = "；".join(issue.message for issue in adaptation.errors) or "门框参数尚未准备完成"
        raise ValueError(message)
    return adaptation, calculate_frame_project(adaptation.inputs, adaptation.project)
