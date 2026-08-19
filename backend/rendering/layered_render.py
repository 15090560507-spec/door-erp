"""规则化分层效果图生成（CAD 管几何，AI 管材质）。

从已生成的 DXF 文本中提取门板、门框、门套/门头门柱与配件几何，
按 DXF 图层精确生成透明蒙版：
- 默认（无 AI）：使用默认平整材质（纯色）映射到蒙版；
- 传入 ai_config 时：调用效果渲染的模型接口（图像编辑）给整幅门体
  添加颜色/材质纹理，再把 AI 结果按 CAD 蒙版切回各部件图层。
CAD 只负责结构与位置，AI 不改变任何几何。

设计说明：
- 画布为门体内容区（正反面视图 + 尺寸标注）的外包矩形，保持 CAD 订货单比例。
- 输出像素尺寸由 ``target_long_edge`` 控制（默认 2600px 长边），``dpi`` 作为
  PSD 分辨率元数据写入（默认 300 DPI）。按 mm 1:1 直接 300 DPI 会把整张
  订货单放大到数十万像素，超出内存，因此采用“目标长边 + 分辨率元数据”方案。
- 配件通过“门板/门框/门套图层上的 INSERT 块”识别，独立成层。
- AI 不可用/失败时自动回退默认材质，不阻塞生成。
"""

from __future__ import annotations

import base64
import io
import math
import os
import urllib.request
from typing import Iterable, Optional

import cv2
import ezdxf
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from psd_tools.constants import Compression

from cad_preview import Primitive, _arc_sample_points, _bbox, _point

from .providers import RenderProviderRequest, get_provider
from .psd_writer import PsdNode, write_psd
from .storage import save_bytes

AI_MATERIAL_PROMPT = (
    "基于参考素材为铜门门体添加表面颜色与材质纹理。"
    "严格保持门体结构、比例、门板分格、拉手/锁具/合页位置与所有尺寸标注完全不变，"
    "只替换表面颜色、材质与轻微光影。输出平整的产品目录效果，无透视、无背景场景、无额外装饰。"
)


# ------------------------- 类别与图层映射 -------------------------

CATEGORY_BY_LAYER = {
    "A-DOOR-PANEL": "panel",
    "A-DOOR-FRAME": "frame",
    "A-DOOR-TRIM": "trim",
    "A-DOOR-HATCH": "panel",
    "A-DOOR-mark": "text",
    "YQ_DIM": "dim",
}

SKIP_LAYERS = {"A-DOOR-MASK", "A-DOOR-OCCLUSION", "A-HATCH-SAMPLE", "A-HATCH-SAMPLE-TEXT"}
ACCESSORY_LAYERS = {"A-DOOR-PANEL", "A-DOOR-FRAME", "A-DOOR-TRIM"}

PALETTE = {
    "panel": (196, 138, 61),       # 铜色
    "frame": (140, 90, 43),        # 深铜
    "trim": (108, 66, 31),         # 更深
    "accessory": (72, 72, 76),     # 金属灰
    "outline": (43, 43, 43),       # 轮廓深灰
    "text": (28, 28, 30),
    "dim": (40, 40, 40),
    "background": (255, 255, 255),
}

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font_path() -> Optional[str]:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def _load_font(size_px: int) -> ImageFont.ImageFont:
    path = _font_path()
    size_px = max(6, int(size_px))
    try:
        if path:
            return ImageFont.truetype(path, size_px)
    except Exception:
        pass
    return ImageFont.load_default()


# ------------------------- 图元采集 -------------------------

def _category_for(layer: str, kind: str) -> str:
    if layer in SKIP_LAYERS:
        return "skip"
    if layer in CATEGORY_BY_LAYER:
        return CATEGORY_BY_LAYER[layer]
    if kind in {"TEXT", "MTEXT"}:
        return "text"
    return "outline"


def _to_primitive(entity, layer: str) -> Optional[Primitive]:
    kind = entity.dxftype()
    if kind == "LINE":
        return Primitive("line", layer, [_point(entity.dxf.start), _point(entity.dxf.end)], {})
    if kind == "LWPOLYLINE":
        try:
            has_bulge = any(abs(float(pt[4] or 0)) > 1e-9 for pt in entity.get_points("xyseb"))
            if has_bulge:
                path = ezdxf.path.make_path(entity)
                pts = [(float(p.x), float(p.y)) for p in path.flattening(distance=1.5, segments=16)]
                if len(pts) > 1 and pts[0] == pts[-1]:
                    pts.pop()
            else:
                pts = [_point(p) for p in entity.vertices_in_wcs()]
        except Exception:
            pts = [_point(p) for p in entity.vertices_in_wcs()]
        if len(pts) >= 2:
            return Primitive("polyline", layer, pts, {"closed": bool(entity.closed)})
        return None
    if kind == "POLYLINE":
        try:
            pts = [_point(v.dxf.location) for v in entity.vertices]
        except Exception:
            pts = []
        if len(pts) >= 2:
            return Primitive("polyline", layer, pts, {"closed": bool(entity.is_closed)})
        return None
    if kind == "ARC":
        center = _point(entity.dxf.center)
        radius = float(entity.dxf.radius)
        return Primitive(
            "arc", layer,
            _arc_sample_points(center, radius, float(entity.dxf.start_angle), float(entity.dxf.end_angle)),
            {"center": center, "radius": radius, "start_angle": float(entity.dxf.start_angle), "end_angle": float(entity.dxf.end_angle)},
        )
    if kind == "CIRCLE":
        center = _point(entity.ocs().to_wcs(entity.dxf.center))
        radius = float(entity.dxf.radius)
        return Primitive("circle", layer, [(center[0] - radius, center[1] - radius), (center[0] + radius, center[1] + radius)], {"center": center, "radius": radius})
    if kind in {"TEXT", "MTEXT"}:
        text = entity.plain_text() if kind == "MTEXT" else str(entity.dxf.text or "")
        insert = _point(entity.dxf.insert)
        height = float(getattr(entity.dxf, "char_height" if kind == "MTEXT" else "height", 24) or 24)
        rotation = float(getattr(entity.dxf, "rotation", 0) or 0)
        return Primitive("text", layer, [insert], {"text": text, "height": height, "rotation": rotation})
    if kind == "WIPEOUT":
        try:
            pts = [_point(p) for p in entity.boundary_path_wcs()]
        except Exception:
            pts = []
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts.pop()
        if len(pts) >= 3:
            return Primitive("wipeout", layer, pts, {})
        return None
    if kind == "HATCH":
        # 只取边界路径作为填充区域。
        try:
            for path in entity.paths:
                if hasattr(path, "vertices"):
                    pts = [(float(v[0]), float(v[1])) for v in path.vertices]
                    if len(pts) >= 3:
                        return Primitive("polyline", layer, pts, {"closed": True})
        except Exception:
            return None
        return None
    return None


def collect_primitives(doc) -> list[tuple[str, Primitive]]:
    """采集图元并按类别打标，返回 (category, Primitive) 列表。"""
    result: list[tuple[str, Primitive]] = []

    def walk(entity, depth: int, forced_category: Optional[str]):
        if depth > 4:
            return
        kind = entity.dxftype()
        layer = str(getattr(entity.dxf, "layer", "0") or "0")

        if kind == "INSERT":
            name = str(getattr(entity.dxf, "name", ""))
            is_accessory = layer in ACCESSORY_LAYERS
            child_cat = "accessory" if is_accessory else forced_category
            try:
                for ve in entity.virtual_entities():
                    walk(ve, depth + 1, child_cat)
            except Exception:
                if is_accessory:
                    result.append(("accessory", Primitive("insert", layer, [_point(entity.dxf.insert)], {"text": name})))
            return

        if kind == "DIMENSION":
            try:
                for ve in entity.virtual_entities():
                    walk(ve, depth + 1, forced_category)
            except Exception:
                pass
            return

        category = forced_category or _category_for(layer, kind)
        if category == "skip":
            return
        prim = _to_primitive(entity, layer)
        if prim is not None:
            result.append((category, prim))

    for entity in doc.modelspace().entities_in_redraw_order():
        walk(entity, 0, None)
    return result


# ------------------------- 几何工具 -------------------------

def _category_bbox(prims: list[Primitive]) -> Optional[tuple[float, float, float, float]]:
    points = [p for prim in prims for p in prim.points]
    if not points:
        return None
    return _bbox(points)


def _split_front_back(prims: list[Primitive], front_x: float, back_x: float) -> tuple[list[Primitive], list[Primitive]]:
    mid = (front_x + back_x) / 2
    front, back = [], []
    for prim in prims:
        if not prim.points:
            continue
        min_x, max_x, _min_y, _max_y = _bbox(prim.points)
        center_x = (min_x + max_x) / 2
        (front if center_x <= mid else back).append(prim)
    return front, back


def _find_view_titles(prims: list[Primitive]) -> tuple[tuple[float, float], tuple[float, float]]:
    """返回 ((front_x, front_y), (back_x, back_y)) 标题坐标。"""
    positions = {}
    for prim in prims:
        if prim.kind == "text" and str(prim.data.get("text", "")).strip() in {"正面", "背面"}:
            positions[str(prim.data["text"]).strip()] = prim.points[0]
    front = positions.get("正面")
    back = positions.get("背面")
    if front is None or back is None:
        raise ValueError("CAD 中未找到正面/背面视图标题，无法分层")
    return front, back


def _filter_to_door_views(
    prims: list[Primitive],
    front_pos: tuple[float, float],
    back_pos: tuple[float, float],
) -> list[Primitive]:
    """只保留正反面门体视图区域，丢弃订货单标题栏/图例等边缘内容。"""
    fx, fy = front_pos
    bx, by = back_pos
    gap = abs(bx - fx)
    half_width = max(2500.0, gap * 0.9)
    min_y = min(fy, by) - 3800.0
    max_y = max(fy, by) + 500.0
    kept: list[Primitive] = []
    for prim in prims:
        if not prim.points:
            continue
        min_x, max_x, min_yy, max_yy = _bbox(prim.points)
        cx = (min_x + max_x) / 2
        cy = (min_yy + max_yy) / 2
        if not (abs(cx - fx) <= half_width or abs(cx - bx) <= half_width):
            continue
        if cy < min_y or cy > max_y:
            continue
        kept.append(prim)
    return kept


# ------------------------- 栅格化 -------------------------

class _Canvas:
    def __init__(self, prims: list[tuple[str, Primitive]], target_long_edge: int, dpi: int):
        self.dpi = dpi
        content = [p for c, p in prims if c in {"panel", "frame", "trim", "accessory", "dim", "text"}]
        bbox = _category_bbox(content)
        if bbox is None:
            raise ValueError("CAD 中没有可渲染的门体几何")
        min_x, max_x, min_y, max_y = bbox
        width_mm = max(max_x - min_x, 1.0)
        height_mm = max(max_y - min_y, 1.0)
        pad_mm = max(width_mm, height_mm) * 0.02
        self.min_x = min_x - pad_mm
        self.min_y = min_y - pad_mm
        self.width_mm = width_mm + pad_mm * 2
        self.height_mm = height_mm + pad_mm * 2
        self.scale = target_long_edge / max(self.width_mm, self.height_mm)
        self.width = max(1, int(round(self.width_mm * self.scale)))
        self.height = max(1, int(round(self.height_mm * self.scale)))

    def px(self, x: float, y: float) -> tuple[int, int]:
        return int(round((x - self.min_x) * self.scale)), int(round((self.max_y() - y) * self.scale))

    def max_y(self) -> float:
        return self.min_y + self.height_mm


def _blank_rgba(w: int, h: int) -> np.ndarray:
    return np.zeros((h, w, 4), dtype=np.uint8)


def _fill_color(arr: np.ndarray, rgb: tuple[int, int, int]) -> np.ndarray:
    arr[..., 0] = rgb[0]
    arr[..., 1] = rgb[1]
    arr[..., 2] = rgb[2]
    arr[..., 3] = 255
    return arr


def _render_primitives(canvas: _Canvas, prims: list[Primitive], fill_rgb: Optional[tuple[int, int, int]], stroke_rgb: Optional[tuple[int, int, int]], stroke_width: int = 2) -> np.ndarray:
    """将图元栅格化为 RGBA numpy 数组（透明背景）。"""
    arr = _blank_rgba(canvas.width, canvas.height)

    def pt(xy: tuple[float, float]) -> tuple[int, int]:
        return canvas.px(xy[0], xy[1])

    for prim in prims:
        mapped = [pt(p) for p in prim.points]
        if prim.kind == "wipeout" and len(mapped) >= 3:
            if fill_rgb:
                cv2.fillPoly(arr, [np.array(mapped, dtype=np.int32)], (*fill_rgb, 255), lineType=cv2.LINE_AA)
            if stroke_rgb:
                cv2.polylines(arr, [np.array(mapped, dtype=np.int32)], True, (*stroke_rgb, 255), stroke_width, cv2.LINE_AA)
        elif prim.kind == "line" and len(mapped) == 2:
            if stroke_rgb:
                cv2.line(arr, mapped[0], mapped[1], (*stroke_rgb, 255), stroke_width, cv2.LINE_AA)
        elif prim.kind in {"polyline", "arc"} and len(mapped) >= 2:
            closed = bool(prim.data.get("closed", False))
            if fill_rgb and closed and len(mapped) >= 3:
                cv2.fillPoly(arr, [np.array(mapped, dtype=np.int32)], (*fill_rgb, 255), lineType=cv2.LINE_AA)
            if stroke_rgb:
                cv2.polylines(arr, [np.array(mapped, dtype=np.int32)], closed, (*stroke_rgb, 255), stroke_width, cv2.LINE_AA)
        elif prim.kind == "circle" and len(mapped) == 2:
            center = pt(prim.data["center"])
            radius = max(1, int(round(float(prim.data["radius"]) * canvas.scale)))
            if fill_rgb:
                cv2.circle(arr, center, radius, (*fill_rgb, 255), -1, cv2.LINE_AA)
            if stroke_rgb:
                cv2.circle(arr, center, radius, (*stroke_rgb, 255), stroke_width, cv2.LINE_AA)
    return arr


def _render_text(canvas: _Canvas, prims: list[Primitive], color: tuple[int, int, int]) -> np.ndarray:
    arr = _blank_rgba(canvas.width, canvas.height)
    pil = Image.fromarray(arr, "RGBA")
    draw = ImageDraw.Draw(pil)
    for prim in prims:
        if prim.kind != "text":
            continue
        text = str(prim.data.get("text", "")).strip()
        if not text:
            continue
        x, y = prim.points[0]
        px, py = canvas.px(x, y)
        height_px = max(6, float(prim.data.get("height", 24)) * canvas.scale)
        font = _load_font(height_px * 1.15)
        rotation = float(prim.data.get("rotation", 0) or 0)
        try:
            text_img = Image.new("RGBA", (int(height_px * len(text) * 1.6) + 8, int(height_px * 2.4) + 8), (0, 0, 0, 0))
            tdraw = ImageDraw.Draw(text_img)
            tdraw.text((4, 4), text, font=font, fill=(*color, 255))
            if rotation:
                text_img = text_img.rotate(-rotation, expand=True, resample=Image.BICUBIC)
            pil.alpha_composite(text_img, (px, py - text_img.height))
        except Exception:
            pass
    return np.array(pil, dtype=np.uint8)


# ------------------------- 合成与输出 -------------------------

def _composite(layers: list[np.ndarray]) -> np.ndarray:
    if not layers:
        raise ValueError("至少需要一层")
    base = _blank_rgba(layers[0].shape[1], layers[0].shape[0])
    for layer in layers:
        src_a = layer[..., 3:4].astype(np.float32) / 255.0
        dst_a = base[..., 3:4].astype(np.float32) / 255.0
        out_a = src_a + dst_a * (1.0 - src_a)
        out_rgb = layer[..., :3].astype(np.float32) * src_a + base[..., :3].astype(np.float32) * dst_a * (1.0 - src_a)
        base[..., :3] = np.where(out_a > 1e-6, (out_rgb / np.maximum(out_a, 1e-6)), 0).astype(np.uint8)
        base[..., 3] = (out_a[..., 0] * 255.0).astype(np.uint8)
    return base


def _to_pil(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(arr, "RGBA")


def _to_jpg(arr: np.ndarray, quality: int = 88) -> bytes:
    pil = Image.fromarray(arr[..., :3], "RGB")
    buf = io.BytesIO()
    pil.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def _crop(arr: np.ndarray, bbox: tuple[float, float, float, float], canvas: _Canvas) -> np.ndarray:
    min_x, max_x, min_y, max_y = bbox
    x1 = int(round((min_x - canvas.min_x) * canvas.scale))
    x2 = int(round((max_x - canvas.min_x) * canvas.scale))
    y_top = int(round((canvas.max_y() - max_y) * canvas.scale))
    y_bot = int(round((canvas.max_y() - min_y) * canvas.scale))
    x1 = max(0, min(canvas.width, x1))
    x2 = max(0, min(canvas.width, x2))
    y_top = max(0, min(canvas.height, y_top))
    y_bot = max(0, min(canvas.height, y_bot))
    if x2 <= x1 or y_bot <= y_top:
        return arr
    return arr[y_top:y_bot, x1:x2]


def _apply_ai_material(flat_rgb: np.ndarray, ai_config: dict, references: list[dict]) -> np.ndarray:
    """调用效果渲染模型接口给平整底图添加材质纹理，返回与底图等大的 RGB 数组。"""
    flat_pil = Image.fromarray(flat_rgb, "RGB")
    buffer = io.BytesIO()
    flat_pil.save(buffer, "PNG")
    saved = save_bytes(buffer.getvalue(), "layered-flat.png", "temp")

    request = RenderProviderRequest(
        config=ai_config,
        prompt=AI_MATERIAL_PROMPT,
        size="original",
        count=1,
        line_art={
            "filePath": saved["filePath"],
            "originalName": "layered-flat.png",
            "mimeType": "image/png",
        },
        style_reference=None,
        assets=references or [],
        temp_assets=[],
    )
    response = get_provider(ai_config.get("provider", "")).render(request)
    images = response.get("images") or []
    if not images:
        raise ValueError("模型返回中没有图片")
    image = images[0]
    src = str(image.get("src", ""))
    if image.get("type") == "b64_json":
        raw = src.split(",", 1)[1] if "," in src else src
        data = base64.b64decode(raw)
    elif image.get("type") == "url":
        req = urllib.request.Request(src, headers={"User-Agent": "DoorERP-Render/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    else:
        raise ValueError("无法识别的模型返回类型")
    result = Image.open(io.BytesIO(data)).convert("RGB")
    return np.array(result.resize((flat_rgb.shape[1], flat_rgb.shape[0]), Image.LANCZOS), dtype=np.uint8)


def render_layered_dxf(
    dxf_text: str,
    dpi: int = 300,
    target_long_edge: int = 2600,
    ai_config: Optional[dict] = None,
    references: Optional[list[dict]] = None,
) -> dict:
    """生成分层效果图，返回 PSD 与 JPG 字节流。

    :param ai_config: 效果渲染模型配置（含 apiKey 的完整配置）；为 None 时使用默认平整材质。
    :param references: 参考素材文件信息列表（素材库资产），供 AI 提取颜色/材质。
    """
    doc = ezdxf.read(io.StringIO(dxf_text))
    categorized = collect_primitives(doc)

    by_cat: dict[str, list[Primitive]] = {}
    for category, prim in categorized:
        by_cat.setdefault(category, []).append(prim)

    front_pos, back_pos = _find_view_titles(by_cat.get("text", []))
    front_x, _fy = front_pos
    back_x, _by = back_pos

    # 只保留门体视图区域，剔除订货单标题栏/图例
    for cat in list(by_cat.keys()):
        by_cat[cat] = _filter_to_door_views(by_cat[cat], front_pos, back_pos)

    def prims(cat: str) -> list[Primitive]:
        return by_cat.get(cat, [])

    canvas = _Canvas([(cat, p) for cat in by_cat for p in by_cat[cat]], target_long_edge, dpi)

    # 结构部件按正反面拆分
    front_cat: dict[str, list[Primitive]] = {}
    back_cat: dict[str, list[Primitive]] = {}
    for cat in ("panel", "frame", "trim", "accessory"):
        f, b = _split_front_back(prims(cat), front_x, back_x)
        front_cat[cat] = f
        back_cat[cat] = b

    def render_filled(cat: str, prim_list: list[Primitive]) -> np.ndarray:
        rgb = PALETTE[cat]
        arr = _render_primitives(canvas, prim_list, fill_rgb=rgb, stroke_rgb=None, stroke_width=2)
        # 加细描边，让蒙版边界更清晰
        stroke = _render_primitives(canvas, prim_list, fill_rgb=None, stroke_rgb=(40, 40, 40), stroke_width=max(1, int(canvas.scale * 0.4)))
        arr = _composite([arr, stroke])
        return arr

    def part_mask(prim_list: list[Primitive]) -> np.ndarray:
        """纯填充蒙版（只取 alpha 通道）。"""
        return _render_primitives(canvas, prim_list, fill_rgb=(255, 255, 255), stroke_rgb=None, stroke_width=1)

    # 轮廓层（所有线条/圆弧描边）
    outline_all = prims("outline") + prims("panel") + prims("frame") + prims("trim") + prims("accessory")
    outline_arr = _render_primitives(canvas, outline_all, fill_rgb=None, stroke_rgb=PALETTE["outline"], stroke_width=max(1, int(canvas.scale * 0.5)))

    text_arr = _render_text(canvas, prims("text"), PALETTE["text"])
    dim_arr = _render_primitives(canvas, prims("dim"), fill_rgb=None, stroke_rgb=PALETTE["dim"], stroke_width=max(1, int(canvas.scale * 0.3)))
    dim_arr = _composite([dim_arr, _render_text(canvas, prims("dim"), PALETTE["dim"])])

    white_bg = _blank_rgba(canvas.width, canvas.height)
    _fill_color(white_bg, PALETTE["background"])

    # ---------- 材质处理：AI 纹理 或 默认平整色 ----------
    material_mode = "flat"
    material_note = ""
    ai_rgb: Optional[np.ndarray] = None
    if ai_config:
        try:
            flat_complete = _composite([
                white_bg,
                _build_shadow(canvas, prims("panel") + prims("frame") + prims("trim")),
                render_filled("panel", prims("panel")),
                render_filled("frame", prims("frame")),
                render_filled("trim", prims("trim")),
                render_filled("accessory", prims("accessory")),
                outline_arr,
            ])
            ai_rgb = _apply_ai_material(flat_complete[..., :3], ai_config, references or [])
            material_mode = "ai"
        except Exception as exc:
            material_note = f"AI 材质处理失败，已回退默认材质：{exc}"
            ai_rgb = None

    def part_layer(cat: str, prim_list: list[Primitive]) -> np.ndarray:
        if ai_rgb is not None:
            alpha = part_mask(prim_list)[..., 3:4]
            return np.concatenate([ai_rgb, alpha], axis=2)
        return render_filled(cat, prim_list)

    def face_group(name: str, cats: dict[str, list[Primitive]]) -> PsdNode:
        children: list[PsdNode] = []
        shadow = _build_shadow(canvas, cats["panel"] + cats["frame"])
        children.append(PsdNode("阴影与高光", _to_pil(shadow)))
        children.append(PsdNode("门板", _to_pil(part_layer("panel", cats["panel"]))))
        children.append(PsdNode("门框", _to_pil(part_layer("frame", cats["frame"]))))
        children.append(PsdNode("门套或门头门柱", _to_pil(part_layer("trim", cats["trim"]))))
        children.append(PsdNode("配件", _to_pil(part_layer("accessory", cats["accessory"]))))
        return PsdNode(name, children=children)

    front_group = face_group("02_正面效果", front_cat)
    back_group = face_group("03_反面效果", back_cat)

    info_group = PsdNode("01_订货单信息", children=[
        PsdNode("尺寸标注", _to_pil(dim_arr)),
        PsdNode("表格与文字", _to_pil(text_arr)),
    ])

    # 原始 CAD 底图：白底 + 轮廓 + 文字，默认隐藏
    raw_cad = _composite([white_bg, outline_arr, text_arr, dim_arr])

    nodes = [
        info_group,
        front_group,
        back_group,
        PsdNode("04_CAD轮廓", _to_pil(outline_arr)),
        PsdNode("05_参考素材", children=[], visible=False),
        PsdNode("06_原始CAD底图", _to_pil(raw_cad), visible=False),
        PsdNode("07_白色背景", _to_pil(white_bg)),
    ]

    compression = Compression.ZIP if ai_rgb is not None else Compression.RLE
    psd_bytes = write_psd(nodes, (canvas.width, canvas.height), dpi=dpi, compression=compression)

    # 完整合成（白色背景 + 阴影 + 部件 + 轮廓 + 文字标注）
    complete = _composite([
        white_bg,
        _build_shadow(canvas, prims("panel") + prims("frame") + prims("trim")),
        part_layer("panel", prims("panel")),
        part_layer("frame", prims("frame")),
        part_layer("trim", prims("trim")),
        part_layer("accessory", prims("accessory")),
        outline_arr,
        text_arr,
        dim_arr,
    ])

    front_bbox = _category_bbox(front_cat["panel"] + front_cat["frame"] + front_cat["trim"] + front_cat["accessory"])
    back_bbox = _category_bbox(back_cat["panel"] + back_cat["frame"] + back_cat["trim"] + back_cat["accessory"])
    front_jpg = _to_jpg(_crop(complete, front_bbox, canvas) if front_bbox else complete)
    back_jpg = _to_jpg(_crop(complete, back_bbox, canvas) if back_bbox else complete)
    complete_jpg = _to_jpg(complete)

    return {
        "psd_bytes": psd_bytes,
        "complete_jpg": complete_jpg,
        "front_jpg": front_jpg,
        "back_jpg": back_jpg,
        "canvas_size": (canvas.width, canvas.height),
        "dpi": dpi,
        "scale": canvas.scale,
        "material_mode": material_mode,
        "material_note": material_note,
    }


def _build_shadow(canvas: _Canvas, prim_list: list[Primitive]) -> np.ndarray:
    if not prim_list:
        return _blank_rgba(canvas.width, canvas.height)
    mask = _render_primitives(canvas, prim_list, fill_rgb=(0, 0, 0), stroke_rgb=None, stroke_width=1)
    alpha = mask[..., 3].astype(np.float32)
    offset = max(2, int(round(canvas.scale * 1.5)))
    blur = max(2, int(round(canvas.scale * 1.5)))
    shadow = np.zeros_like(mask)
    shadow[..., 0] = 20
    shadow[..., 1] = 20
    shadow[..., 2] = 24
    shadow[..., 3] = (alpha * 0.55).astype(np.uint8)
    matrix = np.float32([[1, 0, 0], [0, 1, offset]])
    shadow = cv2.warpAffine(shadow, matrix, (canvas.width, canvas.height))
    shadow = cv2.GaussianBlur(shadow, (0, 0), blur)
    return shadow
