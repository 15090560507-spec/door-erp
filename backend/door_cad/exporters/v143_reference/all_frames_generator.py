from __future__ import annotations

from pathlib import Path
from typing import Any

import ezdxf

from .side_generator import add_cn_mtext, create_doc, draw_left_right_vertical_layout
from .top_bottom_generator import draw_top_bottom_layout


def generate_all_frames_dxf(
    output_path: str | Path,
    *,
    skeleton_params: dict[str, Any],
    outer_params: dict[str, Any],
    include_left: bool,
    include_right: bool,
    top_bottom_params: dict[str, Any],
    source_template: str | Path,
    door_width: float,
    door_height: float,
    document_title: str = "",
) -> dict[str, Any]:
    doc = create_doc()
    msp = doc.modelspace()

    has_sides = include_left or include_right
    has_top_bottom = top_bottom_params["include_top"] or top_bottom_params["include_bottom"]
    if not has_sides and not has_top_bottom:
        raise ValueError("至少选择一个门框零件。")

    lr = None
    if has_sides:
        lr = draw_left_right_vertical_layout(
            msp,
            skeleton_params,
            outer_params,
            include_left=include_left,
            include_right=include_right,
            origin_x=0,
            origin_y=0,
            show_title=True,
        )

    tb_origin_x = (lr["width"] + 260) if lr else 0
    tb = None
    if has_top_bottom:
        tb = draw_top_bottom_layout(
            msp,
            source_template=source_template,
            origin_x=tb_origin_x,
            origin_y=0,
            show_title=True,
            **top_bottom_params,
        )

    drawing_heights = []
    if lr:
        drawing_heights.append(lr["height"])
    if tb:
        drawing_heights.append(tb["drawing_height"])
    overall_y = max(drawing_heights) + 90
    enabled_groups = []
    if has_sides:
        enabled_groups.append("左右框")
    if has_top_bottom:
        enabled_groups.append("上下框")
    title = document_title.strip() or (
        f"全框总生产图｜门宽{door_width:.0f}｜门高{door_height:.0f}｜{'＋'.join(enabled_groups)}"
    )
    add_cn_mtext(
        msp,
        title,
        70,
        overall_y,
        height=20,
        width=1500,
        layer="L32_PART_ID",
    )
    add_cn_mtext(
        msp,
        "所有零件均按折弯截面、展开截面、展开平面自上而下排布。",
        70,
        overall_y - 38,
        height=7,
        width=1800,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output_path)
    auditor = ezdxf.readfile(output_path).audit()
    return {
        "output": str(output_path),
        "audit_errors": len(auditor.errors),
        "audit_fixes": len(auditor.fixes),
        "left_right": {
            "width": lr["width"],
            "height": lr["height"],
        } if lr else None,
        "top_bottom": tb,
        "tb_origin_x": tb_origin_x,
    }
