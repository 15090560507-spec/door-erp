from __future__ import annotations

import argparse
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import ezdxf
from ezdxf import bbox
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
from ezdxf.enums import TextEntityAlignment


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIRECTORY = ROOT / "docs" / "samples" / "parametric-section-proof"
PART_HEIGHT = 2100.0
HINGE_CENTERS = (250.0, 1050.0, 1850.0)


@dataclass(frozen=True)
class PartSpec:
    part_id: str
    label: str
    kind: str
    thickness: float
    formed_points: tuple[tuple[float, float], ...] = ()
    segments: tuple[float, ...] = ()
    face_width: float = 0.0
    hinge_slots: bool = False
    tube_size: tuple[float, float, float] | None = None

    @property
    def blank_width(self) -> float:
        return sum(self.segments)


PARTS = (
    PartSpec("TRIM-SKIN-01", "门套外皮", "sheet", 1.2, ((0, 0), (80, 0), (80, -25)), (80, 25), 80),
    PartSpec("TRIM-SKELETON-01", "门套折弯骨架", "sheet", 1.5, ((0, 0), (40, 0), (40, -30), (60, -30)), (40, 30, 20), 40),
    PartSpec("FRAME-SKIN-01", "门框外皮", "sheet", 1.5, ((0, 0), (50, 0), (50, -120), (75, -120)), (50, 120, 25), 50, True),
    PartSpec("FRAME-SKELETON-01", "门框折弯骨架", "sheet", 2.0, ((0, 0), (35, 0), (35, -50), (70, -50)), (35, 50, 35), 50, True),
    PartSpec("LEAF-SKIN-FRONT-01", "门扇正面外皮", "sheet", 1.0, ((0, 0), (20, 0), (20, -70), (40, -70)), (20, 70, 20), 70, True),
    PartSpec("LEAF-SKIN-BACK-01", "门扇反面外皮", "sheet", 1.0, ((0, 0), (-20, 0), (-20, -70), (-40, -70)), (20, 70, 20), 70, True),
    PartSpec("LEAF-TUBE-01", "门扇合页边方管骨架", "tube", 1.5, face_width=40, hinge_slots=True, tube_size=(40, 30, 1.5)),
)


LAYER_DEFINITIONS = {
    "REF-WALL": {"color": 8, "lineweight": 18},
    "SKIN": {"color": 5, "lineweight": 35},
    "SKELETON": {"color": 3, "lineweight": 35},
    "CUT": {"color": 1, "lineweight": 30},
    "BEND": {"color": 6, "linetype": "DASHED", "lineweight": 18},
    "WELD": {"color": 30, "lineweight": 35},
    "CENTER": {"color": 4, "linetype": "CENTER", "lineweight": 13},
    "DIM": {"color": 250, "lineweight": 13},
    "TEXT": {"color": 250, "lineweight": 18},
}


def _create_document() -> ezdxf.document.Drawing:
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    for name, attributes in LAYER_DEFINITIONS.items():
        if name not in doc.layers:
            doc.layers.add(name, **attributes)
    if "CN" not in doc.styles:
        style = doc.styles.add("CN", font="msyh.ttc")
        style.set_extended_font_data("Microsoft YaHei")
    return doc


def _line(msp, start: tuple[float, float], end: tuple[float, float], layer: str) -> None:
    msp.add_line(start, end, dxfattribs={"layer": layer})


def _poly(msp, points: Sequence[tuple[float, float]], layer: str, close: bool = False) -> None:
    msp.add_lwpolyline(points, close=close, dxfattribs={"layer": layer})


def _rect(msp, x: float, y: float, width: float, height: float, layer: str) -> None:
    _poly(msp, ((x, y), (x + width, y), (x + width, y + height), (x, y + height)), layer, close=True)


def _text(
    msp,
    value: str,
    x: float,
    y: float,
    height: float = 38,
    layer: str = "TEXT",
    align: TextEntityAlignment = TextEntityAlignment.MIDDLE_CENTER,
    rotation: float = 0,
) -> None:
    entity = msp.add_text(
        value,
        dxfattribs={"layer": layer, "height": height, "style": "CN", "rotation": rotation},
    )
    entity.set_placement((x, y), align=align)


def _tick(msp, x: float, y: float, size: float = 12) -> None:
    _line(msp, (x - size, y - size), (x + size, y + size), "DIM")


def _dim_h(msp, x1: float, x2: float, y: float, offset: float, label: str) -> None:
    dim_y = y + offset
    _line(msp, (x1, y), (x1, dim_y), "DIM")
    _line(msp, (x2, y), (x2, dim_y), "DIM")
    _line(msp, (x1, dim_y), (x2, dim_y), "DIM")
    _tick(msp, x1, dim_y)
    _tick(msp, x2, dim_y)
    _text(msp, label, (x1 + x2) / 2, dim_y + (28 if offset >= 0 else -28), 25, "DIM")


def _dim_v(msp, x: float, y1: float, y2: float, offset: float, label: str) -> None:
    dim_x = x + offset
    _line(msp, (x, y1), (dim_x, y1), "DIM")
    _line(msp, (x, y2), (dim_x, y2), "DIM")
    _line(msp, (dim_x, y1), (dim_x, y2), "DIM")
    _tick(msp, dim_x, y1)
    _tick(msp, dim_x, y2)
    _text(msp, label, dim_x + (30 if offset >= 0 else -30), (y1 + y2) / 2, 25, "DIM", rotation=90)


def _draw_hinge_slots(msp, x: float, y: float, width: float, layer: str = "CUT") -> None:
    slot_width = min(30.0, max(width - 4.0, 8.0))
    slot_x = x + (width - slot_width) / 2
    for center in HINGE_CENTERS:
        _rect(msp, slot_x, y + center - 50, slot_width, 100, layer)
        _line(msp, (slot_x - 15, y + center), (slot_x + slot_width + 15, y + center), "CENTER")


def _draw_weld(msp, x: float, y: float, direction: int = 1) -> None:
    _poly(msp, ((x, y), (x + 18 * direction, y + 18), (x + 18 * direction, y - 18)), "WELD", close=True)


def _draw_header(msp) -> None:
    _rect(msp, -200, 0, 9000, 16200, "REF-WALL")
    _text(msp, "参数化生产剖面 CAD 概念验证", 4300, 15910, 95)
    _text(msp, "概念验证，非生产依据", 4300, 15780, 62, "CUT")
    _text(msp, "单位：mm  |  样例：单门合页边  |  版本：PROOF-V1", 4300, 15680, 34)


def _draw_assembly(msp) -> None:
    x0, y0 = 150, 13350
    _rect(msp, x0, y0, 4100, 2050, "REF-WALL")
    _text(msp, "A. 总装水平剖面图", x0 + 2050, y0 + 1940, 55)

    wall_x, wall_y = x0 + 350, y0 + 350
    _rect(msp, wall_x, wall_y, 200, 1050, "REF-WALL")
    for hatch_y in range(int(wall_y + 50), int(wall_y + 1050), 90):
        _line(msp, (wall_x, hatch_y), (wall_x + 200, hatch_y + 70), "REF-WALL")
    _text(msp, "墙体 200", wall_x + 100, wall_y + 1130, 30)

    trim_origin = (wall_x - 80, wall_y + 1050)
    trim_points = ((trim_origin[0], trim_origin[1] + 25), (trim_origin[0], trim_origin[1]), (trim_origin[0] + 80, trim_origin[1]), (trim_origin[0] + 80, trim_origin[1] - 25))
    _poly(msp, trim_points, "SKIN")
    _rect(msp, wall_x - 45, wall_y + 995, 40, 30, "SKELETON")
    _text(msp, "门套外皮 + 折弯骨架", wall_x - 10, wall_y + 1240, 28)

    frame_x, frame_y = wall_x + 35, wall_y + 1090
    _poly(msp, ((frame_x, frame_y), (frame_x + 50, frame_y), (frame_x + 50, frame_y + 120), (frame_x + 75, frame_y + 120)), "SKIN")
    _rect(msp, frame_x + 8, frame_y + 18, 35, 50, "SKELETON")
    _text(msp, "门框外皮 + 折弯骨架", frame_x + 65, frame_y + 250, 28)

    leaf_x, leaf_y = frame_x + 54, frame_y + 124
    _line(msp, (leaf_x, leaf_y), (leaf_x, leaf_y + 480), "SKIN")
    _line(msp, (leaf_x + 70, leaf_y), (leaf_x + 70, leaf_y + 480), "SKIN")
    _line(msp, (leaf_x, leaf_y + 480), (leaf_x + 70, leaf_y + 480), "SKIN")
    _rect(msp, leaf_x + 20, leaf_y + 22, 40, 30, "SKELETON")
    _text(msp, "门扇双外皮 + 40x30x1.5 方管", leaf_x + 35, leaf_y + 580, 28)

    _line(msp, (frame_x + 40, frame_y + 118), (leaf_x + 45, leaf_y + 10), "CUT")
    _text(msp, "HINGE-01 联动开孔（剖面示意）", frame_x + 380, frame_y + 95, 28, "CUT", TextEntityAlignment.MIDDLE_LEFT)
    _dim_h(msp, wall_x, wall_x + 200, wall_y, -110, "墙厚 200")
    _dim_h(msp, leaf_x, leaf_x + 70, leaf_y + 480, 110, "门扇厚 70")
    _dim_h(msp, frame_x + 50, leaf_x, frame_y + 120, 85, "间隙 4")

    legend_x = x0 + 1900
    legend_y = y0 + 1380
    entries = (
        ("SKIN", "外皮"),
        ("SKELETON", "内骨架"),
        ("CUT", "切割 / 开孔"),
        ("BEND", "折弯线"),
        ("WELD", "焊接"),
        ("CENTER", "中心 / 对齐基准"),
    )
    for index, (layer, label) in enumerate(entries):
        yy = legend_y - index * 105
        _line(msp, (legend_x, yy), (legend_x + 180, yy), layer)
        _text(msp, label, legend_x + 230, yy, 26, align=TextEntityAlignment.MIDDLE_LEFT)


def _draw_parameter_table(msp) -> None:
    x, y = 4450, 13350
    _rect(msp, x, y, 4200, 2050, "REF-WALL")
    _text(msp, "B. 演示参数表", x + 2100, y + 1940, 55)
    rows = (
        "墙厚 / 成品高 / 门扇厚：200 / 2100 / 70",
        "门套外皮 / 折弯骨架：t1.2 / t1.5",
        "门框外皮 / 折弯骨架：t1.5 / t2.0",
        "门扇正反外皮：t1.0",
        "门扇合页边方管：40 x 30 x 1.5",
        "装配间隙：4",
        "HINGE-01 孔型：30 x 100",
        "孔中心高度：250 / 1050 / 1850",
        "定位基准：零件下端 + 合页边",
        "说明：全部尺寸仅为概念验证，尚未形成厂规",
    )
    for index, row in enumerate(rows):
        _text(msp, row, x + 180, y + 1740 - index * 155, 30, align=TextEntityAlignment.MIDDLE_LEFT, layer="CUT" if index == len(rows) - 1 else "TEXT")


def _draw_sheet_blank(msp, spec: PartSpec, x: float, y: float) -> None:
    width = spec.blank_width
    _rect(msp, x, y, width, PART_HEIGHT, "CUT")
    cumulative = 0.0
    for index, segment in enumerate(spec.segments[:-1], start=1):
        cumulative += segment
        _line(msp, (x + cumulative, y), (x + cumulative, y + PART_HEIGHT), "BEND")
        _text(msp, f"B{index}", x + cumulative, y + PART_HEIGHT + 38, 22, "BEND")
    if spec.hinge_slots:
        _draw_hinge_slots(msp, x, y, width)
    _dim_h(msp, x, x + width, y, -65, f"展开宽 {width:g}")
    _dim_v(msp, x + width, y, y + PART_HEIGHT, 70, "2100")
    segment_label = " + ".join(f"{value:g}" for value in spec.segments)
    _text(msp, f"分段 {segment_label}", x + width / 2, y - 130, 22)


def _draw_tube_blank(msp, spec: PartSpec, x: float, y: float, width: float) -> None:
    _rect(msp, x, y, width, PART_HEIGHT, "CUT")
    _draw_hinge_slots(msp, x, y, width)
    _dim_h(msp, x, x + width, y, -65, f"方管面宽 {width:g}")
    _dim_v(msp, x + width, y, y + PART_HEIGHT, 70, "下料长 2100")
    _text(msp, "方管下料图", x + width / 2, y + PART_HEIGHT + 55, 26)


def _draw_elevation(msp, spec: PartSpec, x: float, y: float, width: float) -> None:
    _rect(msp, x, y, width, PART_HEIGHT, "SKIN" if spec.kind == "sheet" else "SKELETON")
    if spec.hinge_slots:
        _draw_hinge_slots(msp, x, y, width)
    _dim_h(msp, x, x + width, y, -65, f"宽 {width:g}")
    _dim_v(msp, x + width, y, y + PART_HEIGHT, 70, "高 2100")
    _text(msp, "零件立面图", x + width / 2, y + PART_HEIGHT + 55, 26)


def _draw_part_card(msp, spec: PartSpec, x: float, y: float) -> None:
    card_width, card_height = 4200.0, 2500.0
    _rect(msp, x, y, card_width, card_height, "REF-WALL")
    _text(msp, f"{spec.part_id}  {spec.label}", x + 2100, y + 2405, 44)
    _text(msp, f"类型：{'板件' if spec.kind == 'sheet' else '方管'}  |  厚度：{spec.thickness:g} mm", x + 150, y + 2325, 25, align=TextEntityAlignment.MIDDLE_LEFT)

    formed_x, formed_y = x + 330, y + 2050
    _text(msp, "折弯成品截面图" if spec.kind == "sheet" else "方管成品截面图", x + 620, y + 2200, 27)
    if spec.kind == "sheet":
        shifted = tuple((formed_x + px * 2.3, formed_y + py * 2.3) for px, py in spec.formed_points)
        _poly(msp, shifted, "SKIN" if "SKIN" in spec.part_id else "SKELETON")
        for point in shifted[1:-1]:
            _draw_weld(msp, point[0], point[1])
        _text(msp, f"t={spec.thickness:g}", x + 620, y + 1810, 25)
    else:
        tube_width, tube_depth, tube_thickness = spec.tube_size or (40, 30, spec.thickness)
        scale = 4.0
        outer_w, outer_h = tube_width * scale, tube_depth * scale
        _rect(msp, formed_x, formed_y - outer_h, outer_w, outer_h, "SKELETON")
        _rect(msp, formed_x + tube_thickness * scale, formed_y - outer_h + tube_thickness * scale, outer_w - 2 * tube_thickness * scale, outer_h - 2 * tube_thickness * scale, "SKELETON")
        _text(msp, f"{tube_width:g}x{tube_depth:g}x{tube_thickness:g}", x + 620, y + 1810, 25)

    blank_x, blank_y = x + 1450, y + 120
    if spec.kind == "sheet":
        _text(msp, "板材展开图", blank_x + spec.blank_width / 2, y + 2280, 27)
        _draw_sheet_blank(msp, spec, blank_x, blank_y)
    else:
        _draw_tube_blank(msp, spec, blank_x, blank_y, spec.tube_size[0] if spec.tube_size else 40)

    elevation_x = x + 2950
    elevation_width = spec.face_width or (spec.tube_size[1] if spec.tube_size else 40)
    _draw_elevation(msp, spec, elevation_x, blank_y, elevation_width)

    if spec.hinge_slots:
        _text(msp, "HINGE-01：30x100，中心高 250 / 1050 / 1850", x + 2100, y + 45, 23, "CUT")


def _draw_notes(msp) -> None:
    x, y = 4400, 2400
    _rect(msp, x, y, 4250, 2500, "REF-WALL")
    _text(msp, "C. 图纸阅读与后续确认", x + 2125, y + 2390, 48)
    notes = (
        "1. 外皮与内骨架分别编号、分别出图。",
        "2. 折弯骨架输出板材展开；方管骨架输出方管下料。",
        "3. 红色孔槽属于加工特征，不是参考图中的普通线条。",
        "4. HINGE-01 同时关联门框和门扇，要求孔组同轴。",
        "5. 水平剖面表达穿透层；立面表达孔位高度。",
        "6. 折弯线 B1/B2 只表达顺序，未计算折弯补偿。",
        "7. 焊缝符号仅示意，焊接标准与公差尚未定义。",
        "8. 下一版应由厂内实物和正式工艺尺寸校正。",
    )
    for index, note in enumerate(notes):
        _text(msp, note, x + 170, y + 2140 - index * 205, 30, align=TextEntityAlignment.MIDDLE_LEFT)
    _text(msp, "禁止直接用于下料或生产", x + 2125, y + 300, 52, "CUT")


def _configure_fonts(doc, font_manager) -> None:
    font_paths = (
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    )
    for path in font_paths:
        if os.path.exists(path):
            try:
                font_manager.fontManager.addfont(path)
            except Exception:
                pass
    for style in doc.styles:
        if style.dxf.name in {"Standard", "CN"}:
            style.dxf.font = ""
            style.set_extended_font_data("Microsoft YaHei")


def _render_png(dxf_path: Path, png_path: Path) -> None:
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "door-erp-section-proof-mpl"))
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager, pyplot as plt
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    doc = ezdxf.readfile(dxf_path)
    _configure_fonts(doc, font_manager)
    extents = bbox.extents(doc.modelspace(), fast=True)
    min_x, min_y, _ = extents.extmin
    max_x, max_y, _ = extents.extmax
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    margin = 180.0

    figure = plt.figure(figsize=(16, 28), dpi=180, facecolor="white")
    axes = figure.add_axes((0.01, 0.01, 0.98, 0.98), facecolor="white")
    axes.set_axis_off()
    axes.set_aspect("equal", adjustable="box")
    context = RenderContext(doc)
    backend = MatplotlibBackend(axes, adjust_figure=False)
    config = Configuration(color_policy=ColorPolicy.COLOR, background_policy=BackgroundPolicy.WHITE)
    Frontend(context, backend, config=config).draw_layout(doc.modelspace(), finalize=True)
    axes.set_xlim(min_x - margin, max_x + margin)
    axes.set_ylim(min_y - margin, max_y + margin)
    figure.savefig(png_path, format="png", dpi=180, facecolor="white", edgecolor="white")
    plt.close(figure)


def _fit_bounds(
    bounds: tuple[float, float, float, float],
    output_size: tuple[int, int],
    margin_ratio: float = 0.02,
) -> tuple[float, float, float, float]:
    min_x, min_y, max_x, max_y = bounds
    width = max(max_x - min_x, 1.0) * (1 + margin_ratio * 2)
    height = max(max_y - min_y, 1.0) * (1 + margin_ratio * 2)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    target_ratio = output_size[0] / output_size[1]
    if width / height < target_ratio:
        width = height * target_ratio
    else:
        height = width / target_ratio
    return center_x - width / 2, center_y - height / 2, center_x + width / 2, center_y + height / 2


def _render_region(
    doc: ezdxf.document.Drawing,
    png_path: Path,
    bounds: tuple[float, float, float, float],
    output_size: tuple[int, int],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager, pyplot as plt
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    _configure_fonts(doc, font_manager)
    width_px, height_px = output_size
    figure = plt.figure(figsize=(width_px / 180, height_px / 180), dpi=180, facecolor="white")
    axes = figure.add_axes((0.01, 0.01, 0.98, 0.98), facecolor="white")
    axes.set_axis_off()
    axes.set_aspect("equal", adjustable="box")
    context = RenderContext(doc)
    backend = MatplotlibBackend(axes, adjust_figure=False)
    config = Configuration(color_policy=ColorPolicy.COLOR, background_policy=BackgroundPolicy.WHITE)
    Frontend(context, backend, config=config).draw_layout(doc.modelspace(), finalize=True)
    min_x, min_y, max_x, max_y = _fit_bounds(bounds, output_size)
    axes.set_xlim(min_x, max_x)
    axes.set_ylim(min_y, max_y)
    figure.savefig(png_path, format="png", dpi=180, facecolor="white", edgecolor="white")
    plt.close(figure)


def _render_detail_previews(dxf_path: Path, output_directory: Path) -> None:
    doc = ezdxf.readfile(dxf_path)
    _render_region(
        doc,
        output_directory / "parametric-section-assembly.png",
        (-100, 13200, 8800, 16150),
        (4200, 1400),
    )
    _render_region(
        doc,
        output_directory / "parametric-section-parts-upper.png",
        (-100, 7600, 8800, 13100),
        (3600, 2200),
    )
    _render_region(
        doc,
        output_directory / "parametric-section-parts-lower.png",
        (-100, 2200, 8800, 8000),
        (3600, 2350),
    )


def _write_readme(output_directory: Path) -> None:
    readme = """# 参数化生产剖面 CAD 概念验证

本目录包含第一版概念验证图：

- `parametric-section-proof.dxf`：毫米制 CAD 图纸。
- `parametric-section-proof.png`：从该 DXF 重新读取后生成的预览。
- `parametric-section-assembly.png`：总装剖面和演示参数放大图。
- `parametric-section-parts-upper.png`：门套、门框零件放大图。
- `parametric-section-parts-lower.png`：门扇外皮、方管和说明放大图。

图中展示总装水平剖面、板件折弯成品截面、板材展开、方管下料、零件立面和 `HINGE-01` 联动开孔。

所有尺寸均为演示假设，图纸明确标注“概念验证，非生产依据”。折弯补偿、折弯半径、K 因子、焊接标准、公差和真实孔型尚未使用厂规，不得直接下料。
"""
    (output_directory / "README.md").write_text(readme, encoding="utf-8")


def generate_section_proof(output_directory: Path = DEFAULT_OUTPUT_DIRECTORY) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    dxf_path = output_directory / "parametric-section-proof.dxf"
    png_path = output_directory / "parametric-section-proof.png"

    doc = _create_document()
    msp = doc.modelspace()
    _draw_header(msp)
    _draw_assembly(msp)
    _draw_parameter_table(msp)

    positions = (
        (0, 10500),
        (4400, 10500),
        (0, 7800),
        (4400, 7800),
        (0, 5100),
        (4400, 5100),
        (0, 2400),
    )
    for spec, position in zip(PARTS, positions):
        _draw_part_card(msp, spec, *position)
    _draw_notes(msp)

    doc.saveas(dxf_path)
    audit = ezdxf.readfile(dxf_path).audit()
    if audit.errors:
        raise RuntimeError(f"DXF audit failed with {len(audit.errors)} errors")
    _render_png(dxf_path, png_path)
    _render_detail_previews(dxf_path, output_directory)
    _write_readme(output_directory)
    return dxf_path, png_path


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the parametric section CAD proof drawing.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    args = parser.parse_args(list(argv) if argv is not None else None)
    dxf_path, png_path = generate_section_proof(args.output)
    print(dxf_path)
    print(png_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
