"""Plot the generated DXF order sheet to a fixed-size monochrome JPEG."""

from __future__ import annotations

import io
import os
import tempfile
from typing import Iterable, Optional

import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import (
    BackgroundPolicy,
    ColorPolicy,
    Configuration,
    LinePolicy,
    LineweightPolicy,
)

from cad_preview import Primitive, _bbox, _collect_entity


ORDER_FORM_NAMES = {"ORDERFORM", "ORDER_FORM"}
DEFAULT_OUTPUT_SIZE = (5940, 4200)
DEFAULT_DPI = 100
PLOT_CONFIG_VERSION = "autocad-monochrome-5940x4200-v1"
FONT_FILES = (
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
)
FONT_FAMILIES = ("SimSun", "Microsoft YaHei", "Noto Sans CJK SC", "Noto Sans CJK JP")


def render_dxf_sheet_jpg(
    dxf_text: str,
    output_size: tuple[int, int] = DEFAULT_OUTPUT_SIZE,
) -> dict:
    """Render the ORDER_FORM window with AutoCAD-like monochrome plot rules."""
    doc = ezdxf.read(io.StringIO(dxf_text))
    crop_bbox = _order_form_bbox(doc)
    if crop_bbox is None:
        raise ValueError("DXF 中未找到 ORDER_FORM 图框，无法按打印窗口导出 JPG")

    content = _plot(doc, crop_bbox, output_size)
    width, height = output_size
    return {
        "content": content,
        "width": width,
        "height": height,
        "usedOrderForm": True,
        "cadBBox": [float(value) for value in crop_bbox],
        "plotProfile": PLOT_CONFIG_VERSION,
    }


def _order_form_bbox(doc) -> Optional[tuple[float, float, float, float]]:
    candidates: list[tuple[float, float, float, float]] = []
    for entity in doc.modelspace().query("INSERT"):
        name = str(getattr(entity.dxf, "name", "") or "").upper().replace(" ", "")
        if name not in ORDER_FORM_NAMES:
            continue
        primitives: list[Primitive] = []
        _collect_entity(entity, primitives)
        geometry = [item for item in primitives if item.kind != "text" and item.points]
        bbox = _primitive_bbox(geometry)
        if bbox:
            candidates.append(bbox)
    if not candidates:
        return None
    return max(candidates, key=_bbox_area)


def _primitive_bbox(primitives: Iterable[Primitive]) -> Optional[tuple[float, float, float, float]]:
    points = [point for primitive in primitives for point in primitive.points]
    return _bbox(points) if points else None


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    min_x, max_x, min_y, max_y = bbox
    return max(max_x - min_x, 0) * max(max_y - min_y, 0)


def _fit_plot_window(
    bbox: tuple[float, float, float, float],
    output_size: tuple[int, int],
    margin_ratio: float = 0.006,
) -> tuple[float, float, float, float]:
    """Expand the CAD window to the page aspect ratio without stretching it."""
    min_x, max_x, min_y, max_y = bbox
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    width *= 1 + margin_ratio * 2
    height *= 1 + margin_ratio * 2
    page_ratio = output_size[0] / output_size[1]
    if width / height < page_ratio:
        width = height * page_ratio
    else:
        height = width / page_ratio
    return (
        center_x - width / 2,
        center_x + width / 2,
        center_y - height / 2,
        center_y + height / 2,
    )


def _plot(
    doc,
    crop_bbox: tuple[float, float, float, float],
    output_size: tuple[int, int],
) -> bytes:
    try:
        matplotlib_config = os.path.join(tempfile.gettempdir(), "door-erp-matplotlib")
        os.makedirs(matplotlib_config, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", matplotlib_config)
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
        from matplotlib import font_manager
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    except ImportError as exc:
        raise RuntimeError("CAD 打印后端未安装，请安装 matplotlib") from exc

    width_px, height_px = output_size
    figure = plt.figure(
        figsize=(width_px / DEFAULT_DPI, height_px / DEFAULT_DPI),
        dpi=DEFAULT_DPI,
        facecolor="white",
    )
    axes = figure.add_axes((0, 0, 1, 1), facecolor="white")
    axes.set_axis_off()
    axes.set_aspect("auto")

    _configure_cad_fonts(doc, font_manager)
    context = RenderContext(doc)
    backend = MatplotlibBackend(axes, adjust_figure=False)
    config = Configuration(
        color_policy=ColorPolicy.BLACK,
        background_policy=BackgroundPolicy.WHITE,
        line_policy=LinePolicy.ACCURATE,
        lineweight_policy=LineweightPolicy.ABSOLUTE,
        min_lineweight=0.1,
        max_flattening_distance=0.1,
    )
    try:
        Frontend(context, backend, config=config).draw_layout(doc.modelspace(), finalize=True)
        left, right, bottom, top = _fit_plot_window(crop_bbox, output_size)
        axes.set_xlim(left, right)
        axes.set_ylim(bottom, top)
        output = io.BytesIO()
        figure.savefig(
            output,
            format="jpeg",
            dpi=DEFAULT_DPI,
            facecolor="white",
            edgecolor="white",
            pil_kwargs={"quality": 96, "subsampling": 0, "optimize": True},
        )
        return output.getvalue()
    finally:
        plt.close(figure)


def _configure_cad_fonts(doc, font_manager) -> None:
    """Map Chinese CAD text to a CJK font available on Windows or Linux."""
    for path in FONT_FILES:
        if os.path.exists(path):
            try:
                font_manager.fontManager.addfont(path)
            except Exception:
                pass

    selected_family = ""
    for family in FONT_FAMILIES:
        try:
            font_manager.findfont(family, fallback_to_default=False)
            selected_family = family
            break
        except ValueError:
            continue
    if not selected_family:
        return

    for style in doc.styles:
        family, bold, italic = style.get_extended_font_data()
        if style.dxf.name == "Standard" or family in {"", "SimSun"}:
            style.dxf.font = ""
            style.set_extended_font_data(selected_family, bold=bold, italic=italic)
