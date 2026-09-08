"""Conservative baseline rules for a versioned whole-door BOM."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


CURRENT_BOM_RULE_VERSION = "door-bom-2026.09-v1"

GROUP_LABELS = {
    "frame": "门框与门槛",
    "panel": "门扇与面板",
    "skeleton": "骨架与型材",
    "trim": "门套/门头/门柱",
    "glass": "玻璃与线条",
    "hardware": "五金与开启机构",
    "ornament": "花件与外购装饰",
    "consumable": "辅料与耗材",
    "packaging": "包装",
    "subcontract": "外协加工",
}


@dataclass
class BomRuleWarning:
    field_path: str
    message: str
    code: str = "missing_data"
    severity: str = "warning"
    blocking: bool = True


@dataclass
class BomRuleItem:
    group_code: str
    name: str
    specification: str
    theoretical_quantity: float
    unit: str
    operation_code: str
    acquisition_method: str = "待确定"
    material_code: str = ""
    waste_rate: float = 0
    source_payload: Dict[str, Any] = field(default_factory=dict)
    data_status: str = "ready"
    requires_material: bool = True

    @property
    def category(self) -> str:
        return GROUP_LABELS[self.group_code]

    @property
    def planned_quantity(self) -> float:
        if self.theoretical_quantity <= 0:
            return 0
        value = self.theoretical_quantity * (1 + max(0, self.waste_rate) / 100)
        return float(math.ceil(value)) if self.unit in {"个", "件", "扇", "块", "套"} else round(value, 4)


def _text(params: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(params.get(key) or "").strip()
        if value:
            return value
    return ""


def _number(params: Dict[str, Any], key: str) -> float:
    try:
        return float(params.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _leaf_count(door_type: str) -> int:
    if any(name in door_type for name in ("四开", "两定两开")):
        return 4
    if any(name in door_type for name in ("对开", "子母")):
        return 2
    return 1


def _configured_quantity(value: str, leaf_count: int) -> Tuple[float, str]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(个|套)?\s*/\s*(扇|樘)", value)
    if not match:
        return 0, "件"
    base = float(match.group(1))
    unit = match.group(2) or "件"
    total = base * leaf_count if match.group(3) == "扇" else base
    return total, unit


def _missing(
    items: List[BomRuleItem],
    warnings: List[BomRuleWarning],
    *,
    group_code: str,
    name: str,
    operation_code: str,
    field_path: str,
    message: str,
) -> None:
    items.append(BomRuleItem(
        group_code=group_code,
        name=f"{name}（缺少资料）",
        specification="待确认",
        theoretical_quantity=0,
        unit="项",
        operation_code=operation_code,
        data_status="missing",
        requires_material=False,
        source_payload={"missing_field": field_path},
    ))
    warnings.append(BomRuleWarning(field_path=field_path, message=message))


def build_baseline_bom(params: Dict[str, Any]) -> Tuple[List[BomRuleItem], List[BomRuleWarning]]:
    """Generate only values supported by frozen order/drawing parameters."""
    items: List[BomRuleItem] = []
    warnings: List[BomRuleWarning] = []
    door_type = _text(params, "door_type")
    width = _number(params, "dw")
    height = _number(params, "dh")
    leaf_count = _leaf_count(door_type)
    required_date = _text(params, "required_date")

    frame_values = {
        "dw": width,
        "dh": height,
        "left": _text(params, "fw_left_str"),
        "right": _text(params, "fw_right_str"),
        "top": _text(params, "fw_top_str"),
        "threshold": _text(params, "threshold_type"),
    }
    if width > 0 and height > 0 and frame_values["left"] and frame_values["right"] and frame_values["top"]:
        items.append(BomRuleItem(
            group_code="frame", name="门框加工总成",
            specification=(
                f"洞口{width:g}×{height:g}; 左{frame_values['left']}; "
                f"右{frame_values['right']}; 上{frame_values['top']}; {frame_values['threshold'] or '门槛待确认'}"
            ),
            theoretical_quantity=1, unit="套", operation_code="FRAME_ASSEMBLY",
            acquisition_method="内部加工", material_code=_text(params, "frame_material_code"),
            source_payload=frame_values,
        ))
    else:
        _missing(
            items, warnings, group_code="frame", name="门框加工总成",
            operation_code="FRAME_ASSEMBLY", field_path="frame",
            message="门框宽高或左右上框规格不完整，暂不能形成准确门框下料项",
        )

    material = _text(params, "material", "zzcl")
    color = _text(params, "ys")
    if material and width > 0 and height > 0:
        items.append(BomRuleItem(
            group_code="panel", name="门扇面板",
            specification=" / ".join(value for value in (material, color) if value),
            theoretical_quantity=leaf_count, unit="扇", operation_code="PANEL",
            acquisition_method="内部加工", material_code=_text(params, "panel_material_code"),
            source_payload={
                "door_type": door_type, "door_width": width, "door_height": height,
                "front_style": _text(params, "zmks"), "back_style": _text(params, "fmks"),
                "material": material, "color": color,
            },
        ))
    else:
        _missing(
            items, warnings, group_code="panel", name="门扇面板", operation_code="PANEL",
            field_path="material", message="门板材质或门洞宽高缺失，无法形成门扇面板项",
        )

    skeleton_spec = _text(params, "skeleton_spec", "skeleton_material")
    skeleton_quantity = _number(params, "skeleton_quantity")
    if skeleton_spec and skeleton_quantity > 0:
        items.append(BomRuleItem(
            group_code="skeleton", name="门扇骨架/型材", specification=skeleton_spec,
            theoretical_quantity=skeleton_quantity, unit=_text(params, "skeleton_unit") or "米",
            operation_code="SKELETON", acquisition_method="内部加工",
            material_code=_text(params, "skeleton_material_code"),
            source_payload={"required_date": required_date},
        ))
    else:
        _missing(
            items, warnings, group_code="skeleton", name="门扇骨架/型材",
            operation_code="SKELETON", field_path="skeleton_spec",
            message="尚未配置骨架型材规格与用量，需要下料员补充",
        )

    trim_flags = {
        "outer": bool(params.get("has_outer")),
        "outer_portal": bool(params.get("has_outer_portal")),
        "outer_portal2": bool(params.get("has_outer_portal2")),
        "outer_landscape": bool(params.get("has_outer_landscape")),
        "inner": bool(params.get("has_inner")),
    }
    if any(trim_flags.values()):
        items.append(BomRuleItem(
            group_code="trim", name="门套/门头门柱配置",
            specification=", ".join(key for key, enabled in trim_flags.items() if enabled),
            theoretical_quantity=1, unit="套", operation_code="TRIM",
            acquisition_method="内部加工", material_code=_text(params, "trim_material_code"),
            source_payload=trim_flags,
        ))

    glass_spec = _text(params, "glass_spec")
    glass_requested = bool(glass_spec or _text(params, "qc_glass_style", "panel_b2_glass_style", "panel_b4_glass_style"))
    if glass_requested:
        glass_quantity = _number(params, "glass_quantity")
        if glass_spec and glass_quantity > 0:
            items.append(BomRuleItem(
                group_code="glass", name="玻璃", specification=glass_spec,
                theoretical_quantity=glass_quantity, unit=_text(params, "glass_unit") or "块",
                operation_code="GLASS", acquisition_method="库存/采购",
                material_code=_text(params, "glass_material_code"), source_payload={"glass_spec": glass_spec},
            ))
        else:
            _missing(
                items, warnings, group_code="glass", name="玻璃", operation_code="GLASS",
                field_path="glass_quantity" if glass_spec else "glass_spec",
                message="已选择玻璃配置，但玻璃规格或准确块数尚未确定",
            )

    hinge_name = _text(params, "sel_hys", "hys")
    hinge_config = _text(params, "hysl", "pzsl")
    if hinge_name:
        hinge_quantity, hinge_unit = _configured_quantity(hinge_config, leaf_count)
        if hinge_quantity > 0:
            items.append(BomRuleItem(
                group_code="hardware", name=hinge_name, specification=hinge_config,
                theoretical_quantity=hinge_quantity, unit=hinge_unit, operation_code="HINGE",
                acquisition_method="库存/采购", material_code=_text(params, "hinge_material_code"),
                source_payload={"leaf_count": leaf_count, "configuration": hinge_config},
            ))
        else:
            _missing(
                items, warnings, group_code="hardware", name=hinge_name, operation_code="HINGE",
                field_path="hysl", message="开启机构已选择，但配置数量无法识别，请补充每扇或每樘数量",
            )

    for field_path, name, operation in (
        ("st_val", _text(params, "st_val", "lock_type"), "LOCK_BODY"),
        ("fingerprint_lock", _text(params, "fingerprint_lock"), "FINGERPRINT_LOCK"),
        ("zmls", _text(params, "zmls"), "FRONT_HANDLE"),
        ("fmls", _text(params, "fmls"), "BACK_HANDLE"),
    ):
        if name:
            items.append(BomRuleItem(
                group_code="hardware", name=name, specification=field_path,
                theoretical_quantity=1, unit="套", operation_code=operation,
                acquisition_method="库存/采购", material_code=_text(params, f"{field_path}_material_code"),
                source_payload={"field": field_path, "value": name},
            ))

    pattern_text = " ".join(_text(params, key) for key in (
        "panel_b2_glass_style", "panel_b4_glass_style", "qc_glass_style",
        "back_panel_b2_glass_style", "back_panel_b4_glass_style",
    ))
    if "花" in pattern_text or "HJ" in pattern_text.upper():
        _missing(
            items, warnings, group_code="ornament", name="花件/花枝",
            operation_code="ORNAMENT", field_path="ornament_quantity",
            message="图纸包含花件或花枝，但型号与数量需要下料员核验",
        )

    consumables = params.get("consumables")
    if isinstance(consumables, list):
        for index, item in enumerate(consumables, start=1):
            if not isinstance(item, dict) or not str(item.get("name") or "").strip():
                continue
            quantity = float(item.get("quantity") or 0)
            if quantity <= 0:
                warnings.append(BomRuleWarning(
                    field_path=f"consumables.{index}.quantity",
                    message=f"辅料“{item.get('name')}”缺少准确用量",
                ))
            items.append(BomRuleItem(
                group_code="consumable", name=str(item.get("name")).strip(),
                specification=str(item.get("specification") or "待确认"),
                theoretical_quantity=max(0, quantity), unit=str(item.get("unit") or "件"),
                operation_code="CONSUMABLE", acquisition_method="库存/采购",
                material_code=str(item.get("material_code") or ""),
                data_status="ready" if quantity > 0 else "missing",
                source_payload=item,
            ))

    packaging = _text(params, "sel_bz")
    if packaging:
        items.append(BomRuleItem(
            group_code="packaging", name=packaging, specification="整樘包装",
            theoretical_quantity=1, unit="套", operation_code="PACKAGING",
            acquisition_method="内部加工", material_code=_text(params, "packaging_material_code"),
            source_payload={"sel_bz": packaging},
        ))

    subcontracting = params.get("subcontracting")
    if isinstance(subcontracting, list):
        for item in subcontracting:
            name = str(item.get("name") or "").strip() if isinstance(item, dict) else str(item).strip()
            if name:
                items.append(BomRuleItem(
                    group_code="subcontract", name=name, specification="外协工序",
                    theoretical_quantity=1, unit="项", operation_code="SUBCONTRACT",
                    acquisition_method="外协", requires_material=False,
                    source_payload=item if isinstance(item, dict) else {"name": name},
                ))

    return items, warnings
