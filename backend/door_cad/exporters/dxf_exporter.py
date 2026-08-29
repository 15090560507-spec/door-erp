"""One audited DXF containing every enabled door-frame part."""

from __future__ import annotations

import math
import os
import re
import tempfile
from pathlib import Path

import ezdxf

from door_cad.baseline import BASELINE_DIR
from door_cad.models import PartGeometry, Point2D, ProjectGeometry, Shape

from .v143_reference import generate_all_frames_dxf


LAYERS = {
    "L01_OUTER_CUT": 1,
    "L02_INNER_CUT": 3,
    "L03_GROOVE_INNER": 5,
    "L04_GROOVE_OUTER": 6,
    "L05_FOLD": 4,
    "L06_DIM": 2,
    "L07_NOTE": 7,
    "L08_SECTION": 8,
}


class DxfAuditError(RuntimeError):
    pass


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (value or "").strip())
    return cleaned.strip(" .") or "未命名"


def combined_dxf_filename(geometry: ProjectGeometry) -> str:
    order_no = _safe_filename(geometry.project.orderNo or "无订单号")
    project_name = _safe_filename(geometry.project.projectName or "未命名项目")
    return f"{order_no}-{project_name}-门框下料图.dxf"


def _xy(point: Point2D, offset: tuple[float, float]) -> tuple[float, float]:
    return point.x + offset[0], point.y + offset[1]


def _bounds(part: PartGeometry) -> tuple[float, float, float, float]:
    xs = [point.x for point in part.cutOuter.points]
    ys = [point.y for point in part.cutOuter.points]
    return min(xs), max(xs), min(ys), max(ys)


def _obround_points(shape: Shape, offset: tuple[float, float]) -> list[tuple[float, float]]:
    assert shape.center is not None and shape.width is not None and shape.height is not None
    cx, cy = _xy(shape.center, offset)
    width, height = shape.width, shape.height
    vertical = height >= width
    radius = min(width, height) / 2
    points: list[tuple[float, float]] = []
    if vertical:
        half_straight = max(0.0, (height - width) / 2)
        for index in range(9):
            angle = math.pi * index / 8
            points.append((cx + radius * math.cos(angle), cy + half_straight + radius * math.sin(angle)))
        for index in range(9):
            angle = math.pi + math.pi * index / 8
            points.append((cx + radius * math.cos(angle), cy - half_straight + radius * math.sin(angle)))
    else:
        half_straight = max(0.0, (width - height) / 2)
        for index in range(9):
            angle = -math.pi / 2 + math.pi * index / 8
            points.append((cx + half_straight + radius * math.cos(angle), cy + radius * math.sin(angle)))
        for index in range(9):
            angle = math.pi / 2 + math.pi * index / 8
            points.append((cx - half_straight + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def _draw_shape(modelspace, shape: Shape, offset: tuple[float, float]) -> None:
    attributes = {"layer": "L02_INNER_CUT"}
    if shape.kind == "circle" and shape.center and shape.diameter:
        modelspace.add_circle(_xy(shape.center, offset), shape.diameter / 2, dxfattribs=attributes)
    elif shape.kind == "rectangle" and shape.center and shape.width and shape.height:
        cx, cy = _xy(shape.center, offset)
        half_w, half_h = shape.width / 2, shape.height / 2
        modelspace.add_lwpolyline(
            [(cx - half_w, cy - half_h), (cx + half_w, cy - half_h), (cx + half_w, cy + half_h), (cx - half_w, cy + half_h)],
            close=True,
            dxfattribs=attributes,
        )
    elif shape.kind == "obround":
        modelspace.add_lwpolyline(_obround_points(shape, offset), close=True, dxfattribs=attributes)
    elif shape.points:
        modelspace.add_lwpolyline([_xy(point, offset) for point in shape.points], close=True, dxfattribs=attributes)


def _draw_dimensions(modelspace, part: PartGeometry, offset: tuple[float, float]) -> None:
    min_x, max_x, min_y, _ = _bounds(part)
    for index, dimension in enumerate(part.dimensions):
        p1, p2 = _xy(dimension.start, offset), _xy(dimension.end, offset)
        override = {"dimtxt": 22.0, "dimasz": 12.0, "dimexe": 8.0, "dimexo": 5.0}
        try:
            if dimension.orientation == "vertical":
                base = (offset[0] + max_x + 90 + index * 35, p1[1])
                dim = modelspace.add_linear_dim(base=base, p1=p1, p2=p2, angle=90, dimstyle="EZDXF", override=override)
            elif dimension.orientation == "horizontal":
                base = (p1[0], offset[1] + min_y - 90 - index * 35)
                dim = modelspace.add_linear_dim(base=base, p1=p1, p2=p2, angle=0, dimstyle="EZDXF", override=override)
            else:
                dim = modelspace.add_aligned_dim(p1=p1, p2=p2, distance=90 + index * 35, dimstyle="EZDXF", override=override)
            dim.dimension.dxf.layer = "L06_DIM"
            dim.render()
        except (ValueError, ezdxf.DXFError) as exc:
            raise DxfAuditError(f"零件 {part.partId} 标注 {dimension.dimensionId} 生成失败：{exc}") from exc


def _draw_part(modelspace, part: PartGeometry, origin: tuple[float, float]) -> None:
    plan_offset = (origin[0] + 760, origin[1])
    fold_offset = (origin[0], origin[1] + 140)
    flat_offset = (origin[0] + 380, origin[1] + 140)

    modelspace.add_text(part.partId, height=42, dxfattribs={"layer": "L07_NOTE"}).set_placement((origin[0], origin[1] - 150))
    modelspace.add_text("FOLDED", height=24, dxfattribs={"layer": "L07_NOTE"}).set_placement((fold_offset[0], fold_offset[1] - 65))
    modelspace.add_text("FLAT", height=24, dxfattribs={"layer": "L07_NOTE"}).set_placement((flat_offset[0], flat_offset[1] - 65))
    modelspace.add_text("CUT PLAN", height=24, dxfattribs={"layer": "L07_NOTE"}).set_placement((plan_offset[0], plan_offset[1] - 65))

    modelspace.add_lwpolyline([_xy(point, fold_offset) for point in part.foldSection.points], close=part.foldSection.closed, dxfattribs={"layer": "L08_SECTION"})
    modelspace.add_lwpolyline([_xy(point, flat_offset) for point in part.flatSection.points], close=part.flatSection.closed, dxfattribs={"layer": "L05_FOLD"})
    modelspace.add_lwpolyline([_xy(point, plan_offset) for point in part.cutOuter.points], close=True, dxfattribs={"layer": "L01_OUTER_CUT"})
    for shape in part.holes:
        _draw_shape(modelspace, shape, plan_offset)
    for groove in part.grooves:
        layer = "L03_GROOVE_INNER" if groove.face == "inner" else "L04_GROOVE_OUTER"
        for segment in groove.segments:
            modelspace.add_line(_xy(segment.start, plan_offset), _xy(segment.end, plan_offset), dxfattribs={"layer": layer})
    _draw_dimensions(modelspace, part, plan_offset)


def _make_document(geometry: ProjectGeometry):
    document = ezdxf.new("R2010", setup=True)
    document.header["$INSUNITS"] = 4
    for layer, color in LAYERS.items():
        if layer not in document.layers:
            document.layers.add(layer, color=color)
    modelspace = document.modelspace()

    max_width = max((_bounds(part)[1] - _bounds(part)[0] for part in geometry.parts), default=1000)
    max_height = max((_bounds(part)[3] - _bounds(part)[2] for part in geometry.parts), default=1000)
    column_width = max_width + 1600
    row_height = max_height + 650
    for index, part in enumerate(geometry.parts):
        column, row = index % 2, index // 2
        _draw_part(modelspace, part, (column * column_width, -row * row_height))

    title = f"{geometry.project.orderNo}  {geometry.project.projectName}  {geometry.ruleVersion}".strip()
    modelspace.add_text(title or geometry.ruleVersion, height=55, dxfattribs={"layer": "L07_NOTE"}).set_placement((0, 350))
    return document


def _renderer_parameters(geometry: ProjectGeometry) -> dict:
    inputs = geometry.inputs
    skeleton_short, skeleton_long = inputs.resolved_skeleton_sizes()
    outer_short, outer_long = inputs.resolved_skin_sizes()
    bottom_short, bottom_long = inputs.resolved_bottom_sizes()
    skeleton_hinge_center = inputs.hingeCenterSkeleton + (skeleton_short - 52.0)
    outer_hinge_center = inputs.hingeCenterSkin + (outer_short - 55.0)
    hinge_positions = inputs.hingePositions if inputs.hingeMode == "custom" else None
    project_label = "  ".join(
        value for value in (geometry.project.orderNo, geometry.project.projectName) if value
    )
    document_title = (
        f"{project_label}｜门框下料生产图｜门宽{inputs.doorWidth:.0f}｜门高{inputs.doorHeight:.0f}"
        if project_label
        else f"门框下料生产图｜门宽{inputs.doorWidth:.0f}｜门高{inputs.doorHeight:.0f}"
    )
    return {
        "skeleton_params": {
            "short_top": skeleton_short,
            "long_bottom": skeleton_long,
            "height": inputs.doorHeight,
            "thickness": inputs.skeletonThickness,
            "groove_depth": inputs.skeletonGrooveDepth,
            "groove_width": inputs.skeletonGrooveWidth,
            "hinge_style": inputs.hingeStyle,
            "hinge_count": inputs.hingeCount,
            "hinge_center_override": skeleton_hinge_center,
            "hinge_positions": hinge_positions,
        },
        "outer_params": {
            "short_top": outer_short,
            "long_bottom": outer_long,
            "height": inputs.doorHeight,
            "thickness": inputs.skinThickness,
            "groove_depth": inputs.skinGrooveDepth,
            "groove_width": inputs.skinGrooveWidth,
            "hinge_style": inputs.hingeStyle,
            "hinge_count": inputs.hingeCount,
            "hinge_center_override": outer_hinge_center,
            "hinge_positions": hinge_positions,
        },
        "include_left": inputs.includeLeft,
        "include_right": inputs.includeRight,
        "top_bottom_params": {
            "door_width": inputs.doorWidth,
            "side_small": outer_short,
            "side_large": outer_long,
            "top_outer_short": inputs.topShort,
            "top_outer_long": inputs.topLong,
            "bottom_outer_short": bottom_short,
            "bottom_outer_long": bottom_long,
            "include_top": inputs.includeTop,
            "include_bottom": inputs.includeBottom,
            "top_pin": inputs.topPin,
            "bottom_pin": inputs.bottomPin,
        },
        "source_template": BASELINE_DIR / "top_bottom_double_door_template.dxf",
        "door_width": inputs.doorWidth,
        "door_height": inputs.doorHeight,
        "document_title": document_title,
    }


def build_combined_dxf(geometry: ProjectGeometry) -> bytes:
    if geometry.validation.errors:
        raise DxfAuditError("几何校验未通过，不能导出 DXF")
    temporary_path = ""
    try:
        fd, temporary_path = tempfile.mkstemp(suffix=".dxf")
        os.close(fd)
        result = generate_all_frames_dxf(temporary_path, **_renderer_parameters(geometry))
        if result["audit_errors"]:
            raise DxfAuditError(f"DXF 审计失败：发现 {result['audit_errors']} 个错误")
        audited = ezdxf.readfile(temporary_path)
        auditor = audited.audit()
        if auditor.errors:
            messages = "; ".join(str(error) for error in auditor.errors[:5])
            raise DxfAuditError(f"DXF 审计失败：{messages}")
        return Path(temporary_path).read_bytes()
    except DxfAuditError:
        raise
    except Exception as exc:
        raise DxfAuditError(f"按 v1.4.3 标准生成 DXF 失败：{exc}") from exc
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)
