"""
绘图核心逻辑 - 从 door_26.py 原封不动提取
包含: DimensionCalculator, EzdxfDrawer, draw_door_in_frame, run_integrated_system
"""
import io
import math
import os
import tempfile
from typing import Any, Dict, Tuple, Optional, Callable, Union

import ezdxf
from ezdxf.disassemble import recursive_decompose

from config import CONFIG, TEMPLATE_PATH
from utils import parse_dim_str, parse_gap_str


# ===================== 模板缓存 =====================
# 启动时加载一次 template.dxf 到内存，避免每次请求重复磁盘 I/O
_template_text: Optional[str] = None
DIMENSION_SPACING_DELTA = 40
VIEW_TRIM_EDGE_GAP = 1200


def _load_template() -> None:
    """加载模板 DXF 到内存缓存（仅首次调用时读磁盘）"""
    global _template_text
    if _template_text is None and os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            _template_text = f.read()


def _get_cached_template() -> Optional[str]:
    """获取缓存的模板内容"""
    if _template_text is None:
        _load_template()
    return _template_text


HATCH_SAMPLE_LABELS = {
    "紫荆花": ("紫荆花",),
    "钱币款": ("钱币款", "钱币"),
    "流星雨": ("流星雨",),
    "四方纳福": ("四方纳福",),
    "竖条": ("竖条", "2039"),
    "斜实虚": ("斜实虚", "斜 实+虚"),
    "正实虚": ("正实虚", "正 实+虚"),
}

HATCH_FALLBACKS = {
    "紫荆花": {"pattern_name": "ZIJINGHUA", "scale": 0.75, "angle": 0, "color": 9, "solid_fill": 0, "hatch_style": 1, "pattern_type": 1},
    "钱币款": {"pattern_name": "QIANBI", "scale": 0.5, "angle": 0, "color": 9, "solid_fill": 0, "hatch_style": 1, "pattern_type": 1},
    "流星雨": {"pattern_name": "LIUXINGYU", "scale": 1.198, "angle": 0, "color": 9, "solid_fill": 0, "hatch_style": 1, "pattern_type": 1},
    "四方纳福": {"pattern_name": "EARTH", "scale": 7, "angle": 0, "color": 9, "solid_fill": 0, "hatch_style": 1, "pattern_type": 1},
    "竖条": {"pattern_name": "ANSI31", "scale": 15, "angle": 45, "color": 9, "solid_fill": 0, "hatch_style": 1, "pattern_type": 1},
    "斜实虚": {"pattern_name": "ANSI33", "scale": 6, "angle": 0, "color": 9, "solid_fill": 0, "hatch_style": 1, "pattern_type": 1},
    "正实虚": {"pattern_name": "ANSI33", "scale": 6, "angle": 315, "color": 9, "solid_fill": 0, "hatch_style": 1, "pattern_type": 1},
}


def _hatch_points(entity) -> list[tuple[float, float]]:
    points = []
    for path in entity.paths:
        if hasattr(path, "vertices"):
            points.extend((float(v[0]), float(v[1])) for v in path.vertices)
        elif hasattr(path, "edges"):
            for edge in path.edges:
                if hasattr(edge, "start"):
                    points.append((float(edge.start[0]), float(edge.start[1])))
                if hasattr(edge, "end"):
                    points.append((float(edge.end[0]), float(edge.end[1])))
                if hasattr(edge, "center"):
                    points.append((float(edge.center[0]), float(edge.center[1])))
    return points


def _hatch_center(entity) -> Optional[tuple[float, float]]:
    points = _hatch_points(entity)
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def _hatch_bounds(entity) -> Optional[tuple[float, float, float, float]]:
    points = _hatch_points(entity)
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _hatch_sample(entity) -> Dict[str, Any]:
    pattern_lines = []
    if entity.pattern is not None:
        for line in entity.pattern.lines:
            pattern_lines.append((
                float(line.angle),
                (float(line.base_point.x), float(line.base_point.y)),
                (float(line.offset.x), float(line.offset.y)),
                tuple(float(value) for value in line.dash_length_items),
            ))
    return {
        "pattern_name": getattr(entity.dxf, "pattern_name", "ANSI31"),
        "scale": float(getattr(entity.dxf, "pattern_scale", 1) or 1),
        "angle": float(getattr(entity.dxf, "pattern_angle", 0) or 0),
        "color": int(getattr(entity.dxf, "color", 9) or 9),
        "solid_fill": int(getattr(entity.dxf, "solid_fill", 0) or 0),
        "hatch_style": int(getattr(entity.dxf, "hatch_style", 1) or 1),
        "pattern_type": int(getattr(entity.dxf, "pattern_type", 1) or 1),
        "pattern_lines": pattern_lines,
    }


def _polygon_area(points: list[tuple[float, float]]) -> float:
    return abs(sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )) / 2


def _convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    unique = sorted(set((round(float(x), 6), round(float(y), 6)) for x, y in points))
    if len(unique) <= 2:
        return unique

    def cross(origin, first, second):
        return (
            (first[0] - origin[0]) * (second[1] - origin[1])
            - (first[1] - origin[1]) * (second[0] - origin[0])
        )

    lower = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _build_hatch_library(doc) -> Dict[str, Dict[str, Any]]:
    library = {key: dict(value) for key, value in HATCH_FALLBACKS.items()}
    modelspace = doc.modelspace()
    labels = []
    for entity in modelspace:
        if entity.dxftype() not in ("TEXT", "MTEXT"):
            continue
        try:
            text = entity.plain_text() if entity.dxftype() == "MTEXT" else entity.dxf.text
        except Exception:
            continue
        text = str(text).strip()
        if not text:
            continue
        insert = entity.dxf.insert
        labels.append((text, float(insert.x), float(insert.y)))

    hatches = []
    for entity in modelspace.query("HATCH"):
        bounds = _hatch_bounds(entity)
        if not bounds:
            continue
        x1, y1, x2, y2 = bounds
        hatches.append((entity, (x1 + x2) / 2, (y1 + y2) / 2, x1, y1, x2, y2))

    for canonical, aliases in HATCH_SAMPLE_LABELS.items():
        label = next((item for item in labels if any(alias in item[0] for alias in aliases)), None)
        if not label or not hatches:
            continue
        _text, x, y = label
        candidates = [
            item for item in hatches
            if item[3] - 120 <= x <= item[5] + 120 and item[4] >= y - 120
        ]
        pool = candidates or hatches
        nearest = min(pool, key=lambda item: (item[1] - x) ** 2 + (item[2] - y) ** 2)
        library[canonical] = _hatch_sample(nearest[0])
    return library


# ===================== 数据扣减计算 =====================
class DimensionCalculator:
    def __init__(self, params: Dict[str, Any]):
        self.p = params

    def calculate_from_light_size(self, light_w: int, light_h: int, is_back: bool = False) -> Tuple[int, int]:
        is_external = self.p.get('nk', '内开') == '外开'
        if is_back:
            if is_external:
                left = self.p.get('left_width_back', 0)
                right = self.p.get('right_width_back', 0)
                top = self.p.get('fw_top_back', 55)
                th = self.p.get('th_back', 55)
            else:
                left = self.p.get('left_width_front', 0)
                right = self.p.get('right_width_front', 0)
                top = self.p.get('fw_top_front', 55)
                th = self.p.get('th_front', 55)
        else:
            if not is_external:
                left = self.p.get('left_width_front', 0)
                right = self.p.get('right_width_front', 0)
                top = self.p.get('fw_top_front', 55)
                th = self.p.get('th_front', 55)
            else:
                left = self.p.get('left_width_front', 0)
                right = self.p.get('right_width_front', 0)
                top = self.p.get('fw_top_front', 55)
                th = self.p.get('th_front', 55)
        return int(max(300, light_w + left + right)), int(max(600, light_h + top + th))


# ===================== ezdxf 绘图器 =====================
class EzdxfDrawer:
    def __init__(self, doc, ms, hinge_block_name, progress_callback=None):
        self.doc = doc
        self.ms = ms
        self.hinge_block_name = hinge_block_name
        self.progress_callback = progress_callback or (lambda x: None)
        self.doc.header["$DIMASSOC"] = 2
        self.doc.header["$FILLMODE"] = 1
        self.doc.header["$REGENMODE"] = 1
        if "HIDDEN" not in self.doc.linetypes:
            self.doc.linetypes.add("HIDDEN", pattern=[0.0, 8.0, -4.0], description="Hidden")
        if self.hinge_block_name not in self.doc.blocks:
            block = self.doc.blocks.new(name=self.hinge_block_name)
            block.add_lwpolyline([(-5, -40), (5, -40), (5, 40), (-5, 40)], close=True)

    def update_progress(self, msg):
        self.progress_callback(msg)

    def batch_add_layers(self, layers_dict):
        for name, color in layers_dict.items():
            if name not in self.doc.layers:
                self.doc.layers.add(name, color=color)

    def draw_poly(self, points, layer, closed=True):
        self.ms.add_lwpolyline(points, close=closed, dxfattribs={'layer': layer})

    def draw_bulged_poly(self, points, layer, closed=True):
        self.ms.add_lwpolyline(points, format='xyseb', close=closed, dxfattribs={'layer': layer})

    def draw_wipeout_rect(self, x1, y1, x2, y2, layer="A-DOOR-MASK"):
        self.draw_wipeout_polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], layer=layer)

    def draw_wipeout_polygon(self, points, layer="A-DOOR-MASK"):
        if len(points) < 3:
            return
        wipeout = self.ms.add_wipeout(points)
        wipeout.dxf.layer = layer

    def block_local_mask_points(self, block_name: str) -> Optional[list[tuple[float, float]]]:
        if block_name not in self.doc.blocks:
            return None

        all_points: list[tuple[float, float]] = []
        closed_candidates: list[list[tuple[float, float]]] = []
        for entity in recursive_decompose(self.doc.blocks[block_name]):
            if entity.dxftype() not in ("LINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE", "LWPOLYLINE", "POLYLINE"):
                continue
            try:
                path = ezdxf.path.make_path(entity)
                points = [(float(point.x), float(point.y)) for point in path.flattening(distance=2, segments=12)]
            except Exception:
                continue
            if len(points) > 1 and points[0] == points[-1]:
                points.pop()
            if not points:
                continue
            all_points.extend(points)
            if path.is_closed and len(points) >= 3 and _polygon_area(points) > 1:
                closed_candidates.append(points)

        if not all_points:
            return None

        min_x = min(point[0] for point in all_points)
        max_x = max(point[0] for point in all_points)
        min_y = min(point[1] for point in all_points)
        max_y = max(point[1] for point in all_points)
        for candidate in sorted(closed_candidates, key=_polygon_area, reverse=True):
            candidate_min_x = min(point[0] for point in candidate)
            candidate_max_x = max(point[0] for point in candidate)
            candidate_min_y = min(point[1] for point in candidate)
            candidate_max_y = max(point[1] for point in candidate)
            if (
                candidate_min_x <= min_x + 1
                and candidate_max_x >= max_x - 1
                and candidate_min_y <= min_y + 1
                and candidate_max_y >= max_y - 1
            ):
                return candidate

        hull = _convex_hull(all_points)
        return hull if len(hull) >= 3 else None

    def block_local_bbox(self, block_name: str) -> Optional[tuple[float, float, float, float]]:
        if block_name not in self.doc.blocks:
            return None
        xs: list[float] = []
        ys: list[float] = []

        def add_point(x: float, y: float):
            xs.append(float(x))
            ys.append(float(y))

        for entity in self.doc.blocks[block_name]:
            dxftype = entity.dxftype()
            try:
                if dxftype == "LINE":
                    add_point(entity.dxf.start.x, entity.dxf.start.y)
                    add_point(entity.dxf.end.x, entity.dxf.end.y)
                elif dxftype == "LWPOLYLINE":
                    for point in entity.get_points("xy"):
                        add_point(point[0], point[1])
                elif dxftype == "POLYLINE":
                    for vertex in entity.vertices:
                        add_point(vertex.dxf.location.x, vertex.dxf.location.y)
                elif dxftype in ("CIRCLE", "ARC"):
                    center = entity.dxf.center
                    radius = float(entity.dxf.radius)
                    add_point(center.x - radius, center.y - radius)
                    add_point(center.x + radius, center.y + radius)
                elif dxftype in ("TEXT", "MTEXT"):
                    insert = entity.dxf.insert
                    height = float(getattr(entity.dxf, "height", 100) or 100)
                    add_point(insert.x, insert.y)
                    add_point(insert.x + height * 4, insert.y + height)
                elif dxftype == "HATCH":
                    bounds = _hatch_bounds(entity)
                    if bounds:
                        x1, y1, x2, y2 = bounds
                        add_point(x1, y1)
                        add_point(x2, y2)
            except Exception:
                continue
        if not xs or not ys:
            return None
        return min(xs), min(ys), max(xs), max(ys)

    def draw_wipeout_for_block(
        self,
        block_name: str,
        insert_point,
        layer="A-DOOR-MASK",
        xscale=1,
        yscale=1,
        rotation=0,
    ) -> bool:
        local_points = self.block_local_mask_points(block_name)
        if not local_points:
            bbox = self.block_local_bbox(block_name)
            if not bbox:
                return False
            x1, y1, x2, y2 = bbox
            local_points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        if len(local_points) < 3:
            return False
        angle = math.radians(rotation)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        base_x, base_y = insert_point
        points = []
        for x, y in local_points:
            sx = x * xscale
            sy = y * yscale
            points.append((base_x + sx * cos_a - sy * sin_a, base_y + sx * sin_a + sy * cos_a))
        self.draw_wipeout_polygon(points, layer=layer)
        return True

    def draw_hatch_rect(self, x1, y1, x2, y2, sample, layer="A-DOOR-HATCH", mirror=False):
        if not sample or x2 - x1 <= 1 or y2 - y1 <= 1:
            return
        hatch = self.ms.add_hatch(dxfattribs={'layer': layer, 'color': sample.get('color', 9)})
        if sample.get('solid_fill'):
            hatch.set_solid_fill(color=sample.get('color', 9), style=sample.get('hatch_style', 1))
        else:
            angle = float(sample.get('angle', 0) or 0)
            if mirror:
                angle = (180 - angle) % 360
            hatch.set_pattern_fill(
                sample.get('pattern_name', 'ANSI31'),
                color=sample.get('color', 9),
                angle=angle,
                scale=sample.get('scale', 1),
                style=sample.get('hatch_style', 1),
                pattern_type=sample.get('pattern_type', 1),
            )
            pattern_lines = sample.get('pattern_lines') or []
            if pattern_lines:
                if mirror:
                    pattern_lines = [
                        (
                            (180 - line_angle) % 360,
                            (-base_point[0], base_point[1]),
                            (-offset[0], offset[1]),
                            dash_items,
                        )
                        for line_angle, base_point, offset, dash_items in pattern_lines
                    ]
                hatch.set_pattern_definition(pattern_lines)
        hatch.paths.add_polyline_path([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], is_closed=True)
        hatch.set_seed_points([((x1 + x2) / 2, (y1 + y2) / 2)])

    def draw_line(self, p1, p2, layer, linetype=None):
        attribs = {'layer': layer}
        if linetype:
            attribs['linetype'] = linetype
        self.ms.add_line(p1, p2, dxfattribs=attribs)

    def draw_arc(self, center, radius, start_angle, end_angle, layer):
        self.ms.add_arc(
            center=center,
            radius=radius,
            start_angle=start_angle,
            end_angle=end_angle,
            dxfattribs={'layer': layer},
        )

    def draw_dim(self, p1, p2, text_pos, rotation, layer, text_override=""):
        dimstyle = "23231" if "23231" in self.doc.dimstyles else "Standard"
        angle_deg = math.degrees(rotation)
        final_text = text_override if text_override else "<>"
        dim = self.ms.add_linear_dim(
            base=text_pos, p1=p1, p2=p2, angle=angle_deg,
            text=final_text, dimstyle=dimstyle, dxfattribs={'layer': layer}
        )
        dim.render()

    def draw_text(self, text_str, pos, height, layer):
        self.ms.add_text(text_str, dxfattribs={'layer': layer, 'height': height}).set_placement(pos)

    def insert_hinge_block(self, insert_point, layer="A-DOOR-FRAME"):
        self.ms.add_blockref(self.hinge_block_name, insert_point, dxfattribs={'layer': layer})

    def insert_custom_block(self, block_name, insert_point, layer="A-DOOR-PANEL", xscale=1, yscale=1, rotation=0):
        if block_name not in self.doc.blocks:
            block = self.doc.blocks.new(name=block_name)
            block.add_lwpolyline([(-15, -150), (15, -150), (15, 150), (-15, 150)], close=True)
        self.ms.add_blockref(block_name, insert_point, dxfattribs={
            'layer': layer,
            'xscale': xscale,
            'yscale': yscale,
            'rotation': rotation,
        })


# ===================== 门体绘制 =====================
def draw_door_in_frame(
    drawer: EzdxfDrawer, view_name: str, p: Dict, is_back: bool,
    use_light_size: bool = False, light_w: int = 0, light_h: int = 0
):
    drawer.update_progress(f"开始绘制{view_name}门体...")

    dw = p['dw']
    dh = p['dh']

    door_type = p.get('door_type', '单门')
    if is_back and door_type == "单门":
        left_width = p['right_width_front']
        right_width = p['left_width_front']
        fw_top = p['fw_top_front']
        th = p['th_front']
    else:
        left_width = p['left_width_back'] if is_back else p['left_width_front']
        right_width = p['right_width_back'] if is_back else p['right_width_front']
        fw_top = p['fw_top_back'] if is_back else p['fw_top_front']
        th = p['th_back'] if is_back else p['th_front']
    trim_w = p['trim_back'] if is_back else p['trim_front']
    trim_top_w = p.get('trim_back_top' if is_back else 'trim_front_top', trim_w)
    has_outer_portal = bool(p.get('has_outer_portal', False)) and not is_back
    overlap_key = 'overlap_back' if is_back else 'overlap_front'
    overlap = p.get(overlap_key, p.get('overlap', 20)) if trim_w > 0 else 0

    mother_door_width = p.get('mother_door_width', 600)
    mid_door_width = p.get('mid_door_width', 400)
    pillar_width_str = p.get('pillar_width_str', '55/85')
    has_pillar = p.get('has_pillar', False)
    door_open_dir = p.get('kx', '右开')
    nk_choice = p.get('nk', '内开')

    left_gap, right_gap = p.get('left_right_gap', (0, 0))
    top_gap, bottom_gap = p.get('top_bottom_gap', (0, 0))
    middle_gap = p.get('middle_gap', 0)

    # 面板基准：以开启侧门框为参照计算尺寸和位置，正反面绘制完全一致
    # 外开→正面框为基准, 内开→背面框为基准
    # 无缝侧门框更宽→面板与框自然重叠（物理正确）
    if is_back and door_type == "单门":
        ref_left = left_width
        ref_right = right_width
        ref_fw_top = fw_top
        ref_th = th
    elif nk_choice == "外开":
        ref_left = p['left_width_front']
        ref_right = p['right_width_front']
        ref_fw_top = p['fw_top_front']
        ref_th = p['th_front']
    else:
        ref_left = p['left_width_back']
        ref_right = p['right_width_back']
        ref_fw_top = p['fw_top_back']
        ref_th = p['th_back']
    panel_ref_fw_top = p['fw_top_front'] if nk_choice == "外开" else p['fw_top_back']
    panel_ref_th = p['th_front'] if nk_choice == "外开" else p['th_back']

    qc_choice = p.get('qc', '无')
    qc_height = p.get('qc_height', 400)
    qc_shape = p.get('qc_shape', '矩形气窗')
    is_integrated_door = bool(p.get('is_integrated_door', False))
    integrated_panel_height = float(p.get('integrated_panel_height', 300) or 0)
    integrated_press_top_rail = float(p.get('integrated_press_top_rail', 20) or 0)
    integrated_glass_bottom_rail = float(p.get('integrated_glass_bottom_rail', 20) or 0)
    integrated_glass_height = float(p.get('integrated_glass_height', 500) or 0)
    qc_h = qc_height if qc_choice in ["玻璃", "封闭"] else 0
    is_arch_qc = qc_h > 0 and qc_shape == "弧形气窗"
    is_arch_door = bool(p.get('is_arch_door', False)) and qc_h <= 0 and not is_integrated_door
    arch_spring_height = float(p.get('arch_spring_height', dh - 400) or dh - 400)
    arch_spring_height = max(1, min(arch_spring_height, dh - fw_top - 1))
    top_extra_h = integrated_panel_height + integrated_glass_height if is_integrated_door else qc_h
    total_h = dh + top_extra_h
    has_mm = p.get('has_mm', False)
    mm_height = p.get('mm_height', 200)
    hys_choice = p.get('hys', '葫芦头合页')
    hysl_str = p.get('hysl', '3个/扇')

    try:
        hys_count = int(''.join([c for c in hysl_str if c.isdigit()]))
    except Exception:
        hys_count = 3

    frame_center_x = 0.0
    frame_center_y = 0.0
    front_trim = p.get('trim_front', 0)
    front_total_width = dw + 2 * front_trim
    front_overlap = p.get('overlap_front', p.get('overlap', 20)) if front_trim > 0 else 0
    front_outer_right = dw - front_overlap + front_trim if front_trim > 0 else dw
    view_outer_left = overlap - trim_w if trim_w > 0 else 0
    front_offset_x = frame_center_x - front_total_width / 2

    if not is_back:
        offset_x = front_offset_x
    else:
        offset_x = front_offset_x + front_outer_right + VIEW_TRIM_EDGE_GAP - view_outer_left

    offset_y = frame_center_y

    def off(pt):
        return (pt[0] + offset_x, pt[1] + offset_y)

    def arch_geometry(left_x: float, right_x: float, spring_y: float, apex_y: float):
        span = right_x - left_x
        sagitta = apex_y - spring_y
        if span <= 0 or sagitta <= 0:
            return None
        half = span / 2
        radius = (half * half + sagitta * sagitta) / (2 * sagitta)
        center_x = left_x + half
        center_y = spring_y - (radius - sagitta)
        start_angle = math.degrees(math.atan2(spring_y - center_y, right_x - center_x))
        end_angle = math.degrees(math.atan2(spring_y - center_y, left_x - center_x))
        return {
            "center_x": center_x,
            "center_y": center_y,
            "radius": radius,
            "start_angle": start_angle,
            "end_angle": end_angle,
        }

    def arc_point(geom, angle_key: str, radius_delta: float = 0):
        angle = math.radians(geom[angle_key])
        radius = geom["radius"] + radius_delta
        return (
            geom["center_x"] + radius * math.cos(angle),
            geom["center_y"] + radius * math.sin(angle),
        )

    def draw_arch_geom(geom, layer: str, radius_delta: float = 0):
        if not geom:
            return
        radius = geom["radius"] + radius_delta
        if radius <= 0:
            return
        drawer.draw_arc(off((geom["center_x"], geom["center_y"])), radius, geom["start_angle"], geom["end_angle"], layer)

    def arc_top_point_at_x(geom, x: float, radius_delta: float = 0):
        radius = geom["radius"] + radius_delta
        if radius <= 0:
            return None
        dx = x - geom["center_x"]
        if abs(dx) > radius:
            return None
        y = geom["center_y"] + math.sqrt(max(0, radius * radius - dx * dx))
        return (x, y)

    def arc_angle_for_point(geom, pt):
        return math.degrees(math.atan2(pt[1] - geom["center_y"], pt[0] - geom["center_x"]))

    def arch_extended_points(geom, left_x: float, right_x: float, radius_delta: float = 0):
        if not geom:
            return None, None, None
        radius = geom["radius"] + radius_delta
        if radius <= 0:
            return None, None, None
        left_pt = arc_top_point_at_x(geom, left_x, radius_delta)
        right_pt = arc_top_point_at_x(geom, right_x, radius_delta)
        if left_pt and right_pt:
            return left_pt, right_pt, None
        left_base = arc_point(geom, "end_angle", radius_delta)
        right_base = arc_point(geom, "start_angle", radius_delta)
        spring_y = (left_base[1] + right_base[1]) / 2
        apex_y = geom["center_y"] + radius
        extended_geom = arch_geometry(left_x, right_x, spring_y, apex_y)
        if not extended_geom:
            return None, None, None
        return (left_x, spring_y), (right_x, spring_y), extended_geom

    def arch_extended_shape(geom, left_x: float, right_x: float, radius_delta: float = 0):
        left_pt, right_pt, extended_geom = arch_extended_points(geom, left_x, right_x, radius_delta)
        if not left_pt or not right_pt:
            return None, None, None, 0
        if extended_geom:
            return left_pt, right_pt, extended_geom, 0
        return left_pt, right_pt, geom, radius_delta

    def draw_arch_extended_to_x(geom, left_x: float, right_x: float, layer: str, radius_delta: float = 0):
        left_pt, right_pt, effective_geom, effective_delta = arch_extended_shape(geom, left_x, right_x, radius_delta)
        if not left_pt or not right_pt:
            return None, None
        if effective_geom is not geom or abs(effective_delta) < 0.01:
            draw_arch_geom(effective_geom, layer, effective_delta)
            return left_pt, right_pt
        radius = effective_geom["radius"] + effective_delta
        drawer.draw_arc(
            off((effective_geom["center_x"], effective_geom["center_y"])),
            radius,
            arc_angle_for_point(effective_geom, right_pt),
            arc_angle_for_point(effective_geom, left_pt),
            layer,
        )
        return left_pt, right_pt

    def arch_poly_points(geom, radius_delta: float = 0, segments: int = 32):
        if not geom:
            return []
        radius = geom["radius"] + radius_delta
        if radius <= 0:
            return []
        start = geom["end_angle"]
        end = geom["start_angle"]
        points = []
        for index in range(segments + 1):
            angle = math.radians(start + (end - start) * index / segments)
            points.append((
                geom["center_x"] + radius * math.cos(angle),
                geom["center_y"] + radius * math.sin(angle),
            ))
        return points

    def draw_arch_span(left_x: float, right_x: float, spring_y: float, apex_y: float, layer: str):
        draw_arch_geom(arch_geometry(left_x, right_x, spring_y, apex_y), layer)

    def frame_top_arch():
        if is_arch_qc:
            return arch_geometry(left_width, dw - right_width, total_h - qc_h, total_h - fw_top)
        if is_arch_door:
            return arch_geometry(left_width, dw - right_width, arch_spring_height, total_h - fw_top)
        return None

    def fmt_dim(value: float) -> str:
        return str(int(value)) if abs(value - int(value)) < 0.01 else f"{value:g}"

    integrated_layout = None
    if is_integrated_door:
        seal_overlap = integrated_press_top_rail
        press_bottom = max(th, dh - fw_top)
        seal_bottom = dh
        seal_top = seal_bottom + integrated_panel_height
        glass_bottom = seal_top
        glass_top = total_h
        glass_rail_top = min(glass_top, glass_bottom + fw_top)
        integrated_layout = {
            "glass_top": glass_top,
            "glass_bottom": glass_bottom,
            "glass_rail_top": glass_rail_top,
            "seal_top": seal_top,
            "seal_bottom": seal_bottom,
            "press_bottom": press_bottom,
            "seal_dim_bottom": seal_bottom - seal_overlap,
            "seal_dim_top": seal_top + seal_overlap,
            "seal_overlap": seal_overlap,
        }

    if integrated_layout:
        if is_back:
            drawer.draw_poly([off((0, 0)), off((left_width, 0)), off((left_width, dh)), off((0, dh))], 'A-DOOR-FRAME')
            drawer.draw_poly([off((dw - right_width, 0)), off((dw, 0)), off((dw, dh)), off((dw - right_width, dh))], 'A-DOOR-FRAME')
            drawer.draw_poly([off((0, integrated_layout["glass_bottom"])), off((left_width, integrated_layout["glass_bottom"])), off((left_width, total_h)), off((0, total_h))], 'A-DOOR-FRAME')
            drawer.draw_poly([off((dw - right_width, integrated_layout["glass_bottom"])), off((dw, integrated_layout["glass_bottom"])), off((dw, total_h)), off((dw - right_width, total_h))], 'A-DOOR-FRAME')
        else:
            drawer.draw_poly([off((0, 0)), off((left_width, 0)), off((left_width, total_h)), off((0, total_h))], 'A-DOOR-FRAME')
            drawer.draw_poly([off((dw - right_width, 0)), off((dw, 0)), off((dw, total_h)), off((dw - right_width, total_h))], 'A-DOOR-FRAME')
    elif is_arch_qc:
        inner_spring_y = total_h - qc_h
        inner_apex_y = total_h - fw_top
        arch_frame = arch_geometry(left_width, dw - right_width, inner_spring_y, inner_apex_y)
        if arch_frame:
            left_outer_top, right_outer_top, _effective_geom, _effective_delta = arch_extended_shape(arch_frame, 0, dw, fw_top)
            drawer.draw_poly([off((0, 0)), off((left_width, 0)), off((left_width, inner_spring_y)), off(left_outer_top), off((0, left_outer_top[1]))], 'A-DOOR-FRAME')
            drawer.draw_poly([off((dw - right_width, 0)), off((dw, 0)), off((dw, right_outer_top[1])), off(right_outer_top), off((dw - right_width, inner_spring_y))], 'A-DOOR-FRAME')
    elif is_arch_door:
        arch_frame = frame_top_arch()
        if arch_frame:
            left_outer_top, right_outer_top, _effective_geom, _effective_delta = arch_extended_shape(arch_frame, 0, dw, fw_top)
            drawer.draw_poly([off((0, 0)), off((left_width, 0)), off((left_width, arch_spring_height)), off(left_outer_top), off((0, left_outer_top[1]))], 'A-DOOR-FRAME')
            drawer.draw_poly([off((dw - right_width, 0)), off((dw, 0)), off((dw, right_outer_top[1])), off(right_outer_top), off((dw - right_width, arch_spring_height))], 'A-DOOR-FRAME')
    else:
        drawer.draw_poly([off((0, 0)), off((left_width, 0)), off((left_width, total_h)), off((0, total_h))], 'A-DOOR-FRAME')
        drawer.draw_poly([off((dw - right_width, 0)), off((dw, 0)), off((dw, total_h)), off((dw - right_width, total_h))], 'A-DOOR-FRAME')

    top_frame_bottom = total_h - fw_top

    if not is_arch_qc and not is_arch_door:
        drawer.draw_poly([off((left_width, top_frame_bottom)), off((dw - right_width, top_frame_bottom)), off((dw - right_width, total_h)), off((left_width, total_h))], 'A-DOOR-FRAME')
    elif is_arch_door:
        arch_frame = frame_top_arch()
        if arch_frame:
            draw_arch_geom(arch_frame, 'A-DOOR-FRAME')
            left_outer_top, right_outer_top = draw_arch_extended_to_x(arch_frame, 0, dw, 'A-DOOR-FRAME', fw_top)
            if left_outer_top and right_outer_top:
                drawer.draw_line(off(left_outer_top), off((left_width, arch_spring_height)), 'A-DOOR-FRAME')
                drawer.draw_line(off((dw - right_width, arch_spring_height)), off(right_outer_top), 'A-DOOR-FRAME')

    if qc_h > 0:
        mid_frame_top = total_h - qc_h
        mid_frame_bottom = mid_frame_top - fw_top
        if is_arch_qc:
            inner_spring_y = mid_frame_top
            inner_apex_y = total_h - fw_top
            arch_frame = arch_geometry(left_width, dw - right_width, inner_spring_y, inner_apex_y)
            if arch_frame:
                draw_arch_geom(arch_frame, 'A-DOOR-FRAME')
                arch_region = arch_poly_points(arch_frame)
                if arch_region:
                    drawer.draw_poly([off(point) for point in arch_region], 'A-DOOR-FRAME', closed=True)
                left_outer_top, right_outer_top = draw_arch_extended_to_x(arch_frame, 0, dw, 'A-DOOR-FRAME', fw_top)
                if left_outer_top and right_outer_top:
                    drawer.draw_line(off(left_outer_top), off((left_width, inner_spring_y)), 'A-DOOR-FRAME')
                    drawer.draw_line(off((dw - right_width, inner_spring_y)), off(right_outer_top), 'A-DOOR-FRAME')
        drawer.draw_poly([off((left_width, mid_frame_bottom)), off((dw - right_width, mid_frame_bottom)), off((dw - right_width, mid_frame_top)), off((left_width, mid_frame_top))], 'A-DOOR-FRAME')
        if th > 0:
            drawer.draw_poly([off((left_width, 0)), off((dw - right_width, 0)), off((dw - right_width, th)), off((left_width, th))], 'A-DOOR-FRAME')
    else:
        if th > 0:
            drawer.draw_poly([off((left_width, 0)), off((dw - right_width, 0)), off((dw - right_width, th)), off((left_width, th))], 'A-DOOR-FRAME')

    if trim_w > 0:
        W = trim_w
        WT = trim_top_w or trim_w
        O = overlap
        mm_offset = mm_height if has_mm else 0
        ix1, iy1 = O, 0
        ix2, iy2 = O, total_h - O + mm_offset
        ix3, iy3 = dw - O, total_h - O + mm_offset
        ix4, iy4 = dw - O, 0
        ox1, oy1 = O - W, 0
        ox2, oy2 = O - W, total_h - O + WT + mm_offset
        ox3, oy3 = dw - O + W, total_h - O + WT + mm_offset
        ox4, oy4 = dw - O + W, 0

        if has_outer_portal:
            # 外门头门柱不是连续包套：两侧门柱和上部门头分别为独立矩形。
            drawer.draw_poly([off((ox1, oy1)), off((ix1, iy1)), off((ix2, iy2)), off((ox1, iy2))], 'A-DOOR-TRIM')
            drawer.draw_poly([off((ix4, iy4)), off((ox4, oy4)), off((ox4, iy3)), off((ix3, iy3))], 'A-DOOR-TRIM')
            drawer.draw_poly([off((ox1, iy2)), off((ox2, oy2)), off((ox3, oy3)), off((ox4, iy3))], 'A-DOOR-TRIM')
        elif is_arch_qc or is_arch_door:
            frame_inner_arch = frame_top_arch()
            _frame_left, _frame_right, trim_base_arch, trim_base_delta = arch_extended_shape(frame_inner_arch, 0, dw, fw_top)
            if trim_base_arch:
                trim_left_inner, trim_right_inner = draw_arch_extended_to_x(trim_base_arch, ix1, ix4, 'A-DOOR-TRIM', trim_base_delta - O)
                trim_left_outer, trim_right_outer = draw_arch_extended_to_x(trim_base_arch, ox1, ox4, 'A-DOOR-TRIM', trim_base_delta - O + WT)
                drawer.draw_poly([off((ox1, oy1)), off((ox1, trim_left_outer[1])), off(trim_left_outer), off(trim_left_inner), off((ix1, iy1))], 'A-DOOR-TRIM')
                drawer.draw_poly([off((ix4, iy4)), off(trim_right_inner), off(trim_right_outer), off((ox4, trim_right_outer[1])), off((ox4, oy4))], 'A-DOOR-TRIM')
                drawer.draw_line(off(trim_left_outer), off(trim_left_inner), 'A-DOOR-TRIM')
                drawer.draw_line(off(trim_right_inner), off(trim_right_outer), 'A-DOOR-TRIM')
        else:
            drawer.draw_poly([off((ox1, oy1)), off((ox2, oy2)), off((ox3, oy3)), off((ox4, oy4)), off((ix4, iy4)), off((ix3, iy3)), off((ix2, iy2)), off((ix1, iy1))], 'A-DOOR-TRIM')
            drawer.draw_line(off((ix2, iy2)), off((ox2, oy2)), 'A-DOOR-TRIM')
            drawer.draw_line(off((ix3, iy3)), off((ox3, oy3)), 'A-DOOR-TRIM')

        if has_mm and mm_height > 0:
            mm_bottom = total_h - O
            mm_top = mm_bottom + mm_height
            mm_left = ix1
            mm_right = ix4
            drawer.draw_poly([off((mm_left, mm_top)), off((mm_right, mm_top)), off((mm_right, mm_bottom)), off((mm_left, mm_bottom))], 'A-DOOR-TRIM')

        # ===================== 包边款式偏移线 =====================
        trim_style = p.get('trim_style_outer', '') if not is_back else p.get('trim_style_inner', '')
        if trim_style and not has_outer_portal:
            # 包套上边高度 = total_h - O + W + mm_offset
            outer_top_y = total_h - O + WT + mm_offset
            inner_top_y = total_h - O + mm_offset
            style_trim_arch = None
            style_trim_delta = 0
            if is_arch_qc or is_arch_door:
                frame_inner_arch = frame_top_arch()
                _frame_left, _frame_right, style_trim_arch, style_trim_delta = arch_extended_shape(frame_inner_arch, 0, dw, fw_top)

            # 三边偏移多段线（左→上→右，底部对齐 y=0，不闭合）
            def draw_outer_offset(D):
                if (is_arch_qc or is_arch_door) and style_trim_arch:
                    radius_delta = style_trim_delta + W - O - D
                    left_x = O - W + D
                    right_x = dw - O + W - D
                    left_pt, right_pt, _effective_geom, _effective_delta = arch_extended_shape(style_trim_arch, left_x, right_x, radius_delta)
                    drawer.draw_line(off((left_pt[0], 0)), off(left_pt), 'A-DOOR-TRIM')
                    draw_arch_extended_to_x(style_trim_arch, left_x, right_x, 'A-DOOR-TRIM', radius_delta)
                    drawer.draw_line(off(right_pt), off((right_pt[0], 0)), 'A-DOOR-TRIM')
                    return
                left_x = O - W + D
                right_x = dw - O + W - D
                top_y = outer_top_y - D
                drawer.draw_poly(
                    [off((left_x, 0)), off((left_x, top_y)), off((right_x, top_y)), off((right_x, 0))],
                    'A-DOOR-TRIM', closed=False
                )

            def draw_inner_offset(D):
                if (is_arch_qc or is_arch_door) and style_trim_arch:
                    radius_delta = style_trim_delta - O + D
                    left_x = O - D
                    right_x = dw - O + D
                    left_pt, right_pt, _effective_geom, _effective_delta = arch_extended_shape(style_trim_arch, left_x, right_x, radius_delta)
                    drawer.draw_line(off((left_pt[0], 0)), off(left_pt), 'A-DOOR-TRIM')
                    draw_arch_extended_to_x(style_trim_arch, left_x, right_x, 'A-DOOR-TRIM', radius_delta)
                    drawer.draw_line(off(right_pt), off((right_pt[0], 0)), 'A-DOOR-TRIM')
                    return
                left_x = O - D
                right_x = dw - O + D
                top_y = inner_top_y + D
                drawer.draw_poly(
                    [off((left_x, 0)), off((left_x, top_y)), off((right_x, top_y)), off((right_x, 0))],
                    'A-DOOR-TRIM', closed=False
                )

            style = trim_style
            if style in ('斜包套', '阶梯包套'):
                draw_outer_offset(W / 2)
            elif style == '03款包套':
                draw_outer_offset(20)
                draw_outer_offset(40)
                draw_inner_offset(30)
            elif style in ('工字形包套', '02款包套'):
                draw_outer_offset(30)
                draw_inner_offset(30)
            elif style == '01款包套':
                half_w_plus_15 = W / 2 + 15
                draw_outer_offset(30)
                draw_outer_offset(half_w_plus_15)
                draw_inner_offset(30)
                draw_inner_offset(half_w_plus_15)

            # CAD块标注（块参考点在门套最左侧向左150mm，指引线从最左侧中心往左450mm）
            block_name_map = {
                '斜包套': 'XBT', '阶梯包套': 'JTBT',
                '工字形包套': 'GZXBT', '01款包套': '01BT', '02款包套': '02BT',
                '03款包套': '03BT', '平包套': 'PBT',
            }
            block_name = block_name_map.get(trim_style, 'XBT')
            trim_left_x = O - W  # 包套最左侧
            block_x = trim_left_x - 150  # 块在包套最左侧向左150mm
            block_y = total_h / 2 + 80
            leader_y = total_h / 2  # 包套最左侧中心点
            drawer.insert_custom_block(block_name, off((block_x, block_y)), layer='A-DOOR-TRIM')
            drawer.draw_line(off((trim_left_x, leader_y)), off((trim_left_x - 450, leader_y)), 'A-DOOR-TRIM')
    else:
        ox1, oy1, ox4, oy4, ox3, oy3 = 0, 0, dw, 0, dw, total_h
        ix1, iy1, ix4, iy4, ix3, iy3 = 0, 0, dw, 0, dw, total_h

    if qc_h > 0 and not is_arch_qc:
        qc_top = top_frame_bottom
        qc_bottom = mid_frame_top
        drawer.draw_poly([off((left_width, qc_bottom)), off((dw - right_width, qc_bottom)), off((dw - right_width, qc_top)), off((left_width, qc_top))], 'A-DOOR-FRAME')

    if is_integrated_door:
        drawer.draw_poly([off((left_width, integrated_layout["glass_bottom"])), off((dw - right_width, integrated_layout["glass_bottom"])), off((dw - right_width, integrated_layout["glass_rail_top"])), off((left_width, integrated_layout["glass_rail_top"]))], 'A-DOOR-FRAME')
        if not is_back:
            drawer.draw_poly([off((left_width, integrated_layout["seal_dim_bottom"])), off((dw - right_width, integrated_layout["seal_dim_bottom"])), off((dw - right_width, integrated_layout["seal_dim_top"])), off((left_width, integrated_layout["seal_dim_top"]))], 'A-DOOR-PANEL')
        drawer.draw_poly([off((left_width, integrated_layout["press_bottom"])), off((dw - right_width, integrated_layout["press_bottom"])), off((dw - right_width, integrated_layout["seal_bottom"])), off((left_width, integrated_layout["seal_bottom"]))], 'A-DOOR-FRAME')

    if integrated_layout:
        panel_y_top = integrated_layout["press_bottom"] - top_gap
    elif qc_h > 0:
        panel_y_top = total_h - qc_h - panel_ref_fw_top - top_gap
    elif is_arch_door:
        panel_y_top = arch_spring_height - top_gap
    else:
        panel_y_top = dh - panel_ref_fw_top - top_gap
    if p.get("has_dj"):
        panel_y_bot = max(0, p.get("dj_height", 0))
    else:
        panel_y_bot = panel_ref_th + bottom_gap
    pillar_y_bot = 0 if p.get("has_dj") else th
    pillar_y_top = mid_frame_bottom if qc_h > 0 else dh - fw_top

    pillar_width_front = 0
    pillar_width_back = 0
    current_pillar_width = 0
    layout_pillar_width = 0
    if door_type in ("两定两开", "四开门") and has_pillar and pillar_width_str:
        parts = parse_dim_str(pillar_width_str, 55, 85)
        pillar_small = min(parts[0], parts[1])
        pillar_big = max(parts[0], parts[1])
        if nk_choice == "内开":
            # 内开时外侧（正面）立柱用大值，内侧（背面）用小值。
            pillar_width_front = pillar_big
            pillar_width_back = pillar_small
        else:
            # 外开时内侧（背面）立柱用大值，外侧（正面）用小值。
            pillar_width_front = pillar_small
            pillar_width_back = pillar_big
        current_pillar_width = pillar_width_back if is_back else pillar_width_front
        # 门板排布始终以立柱小面为基准，保证小面与门板保持输入门缝。
        # 大面只在对应视图中变宽，从而形成压门框/压门板的效果。
        layout_pillar_width = pillar_small

    panel_positions = []
    pillar_inner_light_edges = None

    panel_arch_geom = None
    if is_arch_door:
        panel_arch_geom = arch_geometry(
            ref_left,
            dw - ref_right,
            arch_spring_height,
            dh - panel_ref_fw_top,
        )

    def draw_panel_body_rect(x1: float, x2: float):
        left, right = sorted((x1, x2))
        if right - left < 1:
            return
        if panel_arch_geom:
            radius_delta = -top_gap
            top_left = arc_top_point_at_x(panel_arch_geom, left, radius_delta)
            top_right = arc_top_point_at_x(panel_arch_geom, right, radius_delta)
            if top_left and top_right:
                start_angle = arc_angle_for_point(panel_arch_geom, top_right)
                end_angle = arc_angle_for_point(panel_arch_geom, top_left)
                included = (end_angle - start_angle) % 360
                if included > 180:
                    included = 360 - included
                bulge = math.tan(math.radians(included) / 4)
                drawer.draw_bulged_poly(
                    [
                        (*off((left, panel_y_bot)), 0, 0, 0),
                        (*off((right, panel_y_bot)), 0, 0, 0),
                        (*off(top_right), 0, 0, bulge),
                        (*off(top_left), 0, 0, 0),
                    ],
                    'A-DOOR-PANEL',
                    closed=True,
                )
                return
        drawer.draw_poly([
            off((left, panel_y_bot)),
            off((right, panel_y_bot)),
            off((right, panel_y_top)),
            off((left, panel_y_top)),
        ], 'A-DOOR-PANEL')

    if door_type == "单门":
        panel_x1 = ref_left + left_gap
        panel_x2 = dw - ref_right - right_gap
        draw_panel_body_rect(panel_x1, panel_x2)
        panel_positions.append((panel_x1, panel_x2))

    elif door_type == "对开门":
        total_door_width = dw - ref_left - ref_right - left_gap - right_gap
        single_panel_width = (total_door_width - middle_gap) / 2
        left_panel_x1 = ref_left + left_gap
        left_panel_x2 = left_panel_x1 + single_panel_width
        right_panel_x1 = left_panel_x2 + middle_gap
        right_panel_x2 = right_panel_x1 + single_panel_width

        draw_panel_body_rect(left_panel_x1, left_panel_x2)
        draw_panel_body_rect(right_panel_x1, right_panel_x2)
        panel_positions.extend([(left_panel_x1, left_panel_x2), (right_panel_x1, right_panel_x2)])

    elif door_type == "子母门":
        total_door_width = dw - ref_left - ref_right - left_gap - right_gap
        mother_width = max(500, min(mother_door_width, total_door_width - middle_gap - 100))
        son_width = total_door_width - mother_width - middle_gap

        is_mother_right = (is_back and door_open_dir == "左开") or (not is_back and door_open_dir == "右开")
        if is_mother_right:
            son_panel_x1 = ref_left + left_gap
            son_panel_x2 = son_panel_x1 + son_width
            mother_panel_x1 = son_panel_x2 + middle_gap
            mother_panel_x2 = mother_panel_x1 + mother_width
        else:
            mother_panel_x1 = ref_left + left_gap
            mother_panel_x2 = mother_panel_x1 + mother_width
            son_panel_x1 = mother_panel_x2 + middle_gap
            son_panel_x2 = son_panel_x1 + son_width

        draw_panel_body_rect(son_panel_x1, son_panel_x2)
        draw_panel_body_rect(mother_panel_x1, mother_panel_x2)
        panel_positions.extend([(son_panel_x1, son_panel_x2), (mother_panel_x1, mother_panel_x2)])

        if not is_back:
            mother_dim_y = panel_y_bot - 100 - DIMENSION_SPACING_DELTA
            drawer.draw_dim(off((mother_panel_x1, mother_dim_y)), off((mother_panel_x2, mother_dim_y)), off((mother_panel_x1 - 100, mother_dim_y - 50)), 0, 'YQ_DIM', "母门宽 <>")

    elif door_type == "四开门":
        total_door_width = dw - ref_left - ref_right - left_gap - right_gap
        if has_pillar and current_pillar_width > 0:
            internal_gap_count = 5
            mid_total_width = 2 * mid_door_width + middle_gap
            side_width = (total_door_width - 2 * layout_pillar_width - 2 * mid_door_width - internal_gap_count * middle_gap) / 2
            lx1 = ref_left + left_gap
            lx2 = lx1 + side_width
            lpx1 = lx2 + middle_gap
            lpx2 = lpx1 + layout_pillar_width
            lmx1 = lpx2 + middle_gap
            lmx2 = lmx1 + mid_door_width
            rmx1 = lmx2 + middle_gap
            rmx2 = rmx1 + mid_door_width
            rpx1 = rmx2 + middle_gap
            rpx2 = rpx1 + layout_pillar_width
            rx1 = rpx2 + middle_gap
            rx2 = rx1 + side_width
        else:
            mid_total_width = 2 * mid_door_width + middle_gap
            side_width = (total_door_width - mid_total_width) / 2
            lx1 = ref_left + left_gap
            lx2 = lx1 + side_width
            lpx1 = lpx2 = lx2
            lmx1 = lx2
            lmx2 = lmx1 + mid_door_width
            rmx1 = lmx2 + middle_gap
            rmx2 = rmx1 + mid_door_width
            rpx1 = rpx2 = rmx2
            rx1 = rmx2
            rx2 = rx1 + side_width

        lpx1_draw, lpx2_draw = lpx1, lpx2
        rpx1_draw, rpx2_draw = rpx1, rpx2
        if has_pillar and current_pillar_width > 0:
            left_pillar_center = (lpx1 + lpx2) / 2
            right_pillar_center = (rpx1 + rpx2) / 2
            lpx1_draw = left_pillar_center - current_pillar_width / 2
            lpx2_draw = left_pillar_center + current_pillar_width / 2
            rpx1_draw = right_pillar_center - current_pillar_width / 2
            rpx2_draw = right_pillar_center + current_pillar_width / 2

        draw_panel_body_rect(lx1, lx2)
        if has_pillar and current_pillar_width > 0:
            drawer.draw_poly([off((lpx1_draw, pillar_y_bot)), off((lpx2_draw, pillar_y_bot)), off((lpx2_draw, pillar_y_top)), off((lpx1_draw, pillar_y_top))], 'A-DOOR-FRAME')
        draw_panel_body_rect(lmx1, lmx2)
        draw_panel_body_rect(rmx1, rmx2)
        if has_pillar and current_pillar_width > 0:
            drawer.draw_poly([off((rpx1_draw, pillar_y_bot)), off((rpx2_draw, pillar_y_bot)), off((rpx2_draw, pillar_y_top)), off((rpx1_draw, pillar_y_top))], 'A-DOOR-FRAME')
        draw_panel_body_rect(rx1, rx2)

        panel_positions.extend([(lx1, lx2), (lmx1, lmx2), (rmx1, rmx2), (rx1, rx2)])
        if has_pillar and current_pillar_width > 0:
            pillar_inner_light_edges = (lpx2_draw, rpx1_draw)

        if not is_back:
            mid_dim_y = panel_y_bot - 150 - DIMENSION_SPACING_DELTA
            drawer.draw_dim(off((lmx1, mid_dim_y)), off((rmx2, mid_dim_y)), off((lmx1 + mid_total_width / 2, mid_dim_y - 50)), 0, 'YQ_DIM', "中门内空宽 <>")

    elif door_type == "两定两开":
        total_door_width = dw - ref_left - ref_right - left_gap - right_gap
        if has_pillar and current_pillar_width > 0:
            internal_gap_count = 5
            mid_total_width = 2 * mid_door_width + middle_gap
            side_width = (total_door_width - mid_total_width - 2 * layout_pillar_width - internal_gap_count * middle_gap) / 2
            lx1 = ref_left + left_gap
            lx2 = lx1 + side_width
            lpx1 = lx2 + middle_gap
            lpx2 = lpx1 + layout_pillar_width
            lmx1 = lpx2 + middle_gap
            lmx2 = lmx1 + mid_door_width
            rmx1 = lmx2 + middle_gap
            rmx2 = rmx1 + mid_door_width
            rpx1 = rmx2 + middle_gap
            rpx2 = rpx1 + layout_pillar_width
            rx1 = rpx2 + middle_gap
            rx2 = rx1 + side_width
        else:
            mid_total_width = 2 * mid_door_width + middle_gap
            side_width = (total_door_width - mid_total_width) / 2
            lx1 = ref_left + left_gap
            lx2 = lx1 + side_width
            lpx1 = lpx2 = lx2
            lmx1 = lx2
            lmx2 = lmx1 + mid_door_width
            rmx1 = lmx2 + middle_gap
            rmx2 = rmx1 + mid_door_width
            rpx1 = rpx2 = rmx2
            rx1 = rmx2
            rx2 = rx1 + side_width

        lpx1_draw, lpx2_draw = lpx1, lpx2
        rpx1_draw, rpx2_draw = rpx1, rpx2
        if has_pillar and current_pillar_width > 0:
            left_pillar_center = (lpx1 + lpx2) / 2
            right_pillar_center = (rpx1 + rpx2) / 2
            lpx1_draw = left_pillar_center - current_pillar_width / 2
            lpx2_draw = left_pillar_center + current_pillar_width / 2
            rpx1_draw = right_pillar_center - current_pillar_width / 2
            rpx2_draw = right_pillar_center + current_pillar_width / 2

        draw_panel_body_rect(lx1, lx2)
        if has_pillar and current_pillar_width > 0:
            drawer.draw_poly([off((lpx1_draw, pillar_y_bot)), off((lpx2_draw, pillar_y_bot)), off((lpx2_draw, pillar_y_top)), off((lpx1_draw, pillar_y_top))], 'A-DOOR-FRAME')
        draw_panel_body_rect(lmx1, lmx2)
        draw_panel_body_rect(rmx1, rmx2)
        if has_pillar and current_pillar_width > 0:
            drawer.draw_poly([off((rpx1_draw, pillar_y_bot)), off((rpx2_draw, pillar_y_bot)), off((rpx2_draw, pillar_y_top)), off((rpx1_draw, pillar_y_top))], 'A-DOOR-FRAME')
        draw_panel_body_rect(rx1, rx2)

        panel_positions.extend([(lx1, lx2), (lmx1, lmx2), (rmx1, rmx2), (rx1, rx2)])
        if has_pillar and current_pillar_width > 0:
            pillar_inner_light_edges = (lpx2_draw, rpx1_draw)
        if not is_back:
            mid_dim_y = panel_y_bot - 150 - DIMENSION_SPACING_DELTA
            drawer.draw_dim(off((lmx1, mid_dim_y)), off((rmx2, mid_dim_y)), off((lmx1 + mid_total_width / 2, mid_dim_y - 50)), 0, 'YQ_DIM', "中门内空宽 <>")

    # ===================== 尺寸标注 =====================
    rad90 = math.radians(90)

    if trim_w > 0:
        outer_left, outer_right, outer_bottom, outer_top = ox1, ox4, 0, oy3
    else:
        outer_left, outer_right, outer_bottom, outer_top = 0, dw, 0, dh

    dims_h = []
    if trim_w > 0:
        dims_h.append(("含包套总宽", outer_left, outer_right, -400, True, "含包套总宽 <>"))
        dims_h.append(("门套宽", ox1, ix1, -200, not has_outer_portal, None))
        dims_h.append(("门柱宽", ox1, ix1, -200, has_outer_portal, None))

    should_mark_light = p.get("mark_light_size", False) or use_light_size
    should_draw_light_view = (nk_choice == "内开" and not is_back) or (nk_choice == "外开" and is_back)
    if should_mark_light and should_draw_light_view:
        light_x1 = left_width
        light_x2 = dw - right_width
        if pillar_inner_light_edges:
            light_x1, light_x2 = pillar_inner_light_edges
        elif door_type in ("两定两开", "四开门") and len(panel_positions) >= 4:
            light_x1 = panel_positions[0][1]
            light_x2 = panel_positions[-1][0]
        light_text = f"见光宽 {light_w}" if use_light_size and light_w > 0 else "见光宽 <>"
        dims_h.append(("见光宽", light_x1, light_x2, -200, True, light_text))

    dims_h.append(("洞口宽", 0, dw, -300, True, None))

    dims_v = []
    if trim_w > 0:
        dims_v.append(("含包套总高", outer_bottom, outer_top, 400, True, "含包套总高 <>"))

    if has_mm and mm_height > 0 and trim_w > 0:
        dims_v.append(("门楣高度", total_h - O + mm_height, total_h - O, 300, True, f"{mm_height}"))

    if has_outer_portal and trim_top_w > 0:
        portal_header_bottom = total_h - overlap + (mm_height if has_mm else 0)
        portal_header_top = portal_header_bottom + trim_top_w
        dims_v.append(("门头高度", portal_header_bottom, portal_header_top, 200, True, None))

    if integrated_layout:
        seal_dim_bottom = integrated_layout["seal_bottom"] if is_back else integrated_layout["seal_dim_bottom"]
        seal_dim_top = integrated_layout["seal_top"] if is_back else integrated_layout["seal_dim_top"]
        seal_dim_text = fmt_dim(integrated_panel_height if is_back else integrated_panel_height + integrated_layout["seal_overlap"] * 2)
        dims_v.append(("上方玻璃", integrated_layout["glass_bottom"], integrated_layout["glass_top"], 200, True, fmt_dim(integrated_glass_height)))
        dims_v.append(("中间封板", seal_dim_bottom, seal_dim_top, 200, True, seal_dim_text))
        dims_v.append(("下方门", 0, dh, 200, True, fmt_dim(dh)))

    if qc_h > 0:
        mid_frame_top = total_h - qc_h
        dims_v.append(("气窗上部高度", mid_frame_top, total_h, 200, True, None))
        dims_v.append(("门高", 0, dh, 200, True, None))

    if is_arch_door:
        dims_v.append(("起弧高度", 0, arch_spring_height, 200, True, fmt_dim(arch_spring_height)))

    if should_mark_light and should_draw_light_view:
        light_text_h = f"见光高 {light_h}" if use_light_size and light_h > 0 else "见光高 <>"
        light_y1 = th
        light_y2 = mid_frame_bottom if qc_h > 0 else dh - fw_top
        dims_v.append(("见光高", light_y1, light_y2, 100, True, light_text_h))

    dims_v.append(("洞口高", 0, total_h, 300, True, None))

    horizontal_layers = {
        offset: (index + 1) * DIMENSION_SPACING_DELTA
        for index, offset in enumerate(sorted({y_offset for _, _, _, y_offset, condition, _ in dims_h if condition}, reverse=True))
    }
    vertical_layers = {
        offset: (index + 1) * DIMENSION_SPACING_DELTA
        for index, offset in enumerate(sorted({x_offset for _, _, _, x_offset, condition, _ in dims_v if condition}))
    }

    for name, x1, x2, y_offset, condition, text in dims_h:
        if condition:
            dim_y = y_offset - horizontal_layers[y_offset]
            drawer.draw_dim(off((x1, dim_y)), off((x2, dim_y)), off((x1 + (x2 - x1) / 2, dim_y - 50)), 0, 'YQ_DIM', text)

    for name, y1, y2, x_offset, condition, text in dims_v:
        if condition:
            dim_x = outer_right + x_offset + vertical_layers[x_offset]
            drawer.draw_dim(off((dim_x, y1)), off((dim_x, y2)), off((dim_x + 50, y1 + (y2 - y1) / 2)), rad90, 'YQ_DIM', text)

    title_top = integrated_layout["glass_top"] if integrated_layout else outer_top
    drawer.draw_text(f"{view_name}", off((dw / 2 - 60, title_top + 300)), 128, 'A-DOOR-mark')

    # ===================== 合页绘制 =====================
    hinge_ys = []
    if hys_count >= 1:
        hinge_ys.append(panel_y_bot + CONFIG.HINGE_CONFIG["first_offset"])
    if hys_count >= 2:
        hinge_ys.append(panel_y_top - CONFIG.HINGE_CONFIG["second_offset"])

    for i in range(2, hys_count):
        curr_y = hinge_ys[-1] - CONFIG.HINGE_CONFIG["subsequent_spacing"]
        if curr_y > panel_y_bot + CONFIG.HINGE_CONFIG["min_clearance"]:
            hinge_ys.append(curr_y)
        else:
            break

    hinge_x_list = []
    is_hinge_visible = (nk_choice == "外开" and not is_back) or (nk_choice == "内开" and is_back)
    # 暗合页/明合页暗装：不画合页块，保持立面干净
    if "暗" in hys_choice:
        is_hinge_visible = False

    if is_hinge_visible:
        if door_type == "单门":
            if (is_back and door_open_dir == "左开") or (not is_back and door_open_dir == "右开"):
                hinge_x_list.append(dw - right_width - 5)
            else:
                hinge_x_list.append(left_width + 5)
        elif door_type in ["对开门", "子母门"]:
            hinge_x_list.extend([left_width + 5, dw - right_width - 5])
        elif door_type == "四开门" and len(panel_positions) >= 4:
            hinge_x_list.extend([left_width + 5, panel_positions[0][1] + 5, panel_positions[2][1] + 5, dw - right_width - 5])
        elif door_type == "两定两开" and len(panel_positions) >= 4:
            if has_pillar:
                hinge_x_list.extend([panel_positions[1][0] - 5, panel_positions[2][1] + 5])
            else:
                hinge_x_list.extend([panel_positions[0][1] + 5, panel_positions[2][1] + 5])

    for hinge_x in hinge_x_list:
        for hinge_y in hinge_ys:
            drawer.insert_hinge_block(off((hinge_x, hinge_y)))

    # ===================== 门板样式线条绘制 =====================
    front_panel_style = p.get('door_panel_style') or "无造型"
    back_panel_style = p.get('back_door_panel_style') or "无造型"
    child_panel_style = p.get('child_door_panel_style') or ""
    panel_style_default = back_panel_style if is_back else front_panel_style
    hatch_library = _build_hatch_library(drawer.doc)

    front_fill_presets = {
        "紫荆花款": {"style": "两列式布局", "lock_offset_x": 150, "fills": ("紫荆花", "竖条", "")},
        "钱币款": {"style": "两列式布局", "lock_offset_x": 150, "fills": ("钱币款", "竖条", "")},
        "竖条款": {"style": "两列式布局", "lock_offset_x": 150, "fills": ("", "竖条", "")},
        "流星雨款": {"style": "两列式布局", "lock_offset_x": 150, "fills": ("流星雨", "斜实虚", "")},
        "四方纳福款": {"style": "两列式布局", "lock_offset_x": 150, "fills": ("四方纳福", "正实虚", "")},
    }
    legacy_preset_aliases = {
        "紫荆花": "紫荆花款",
        "钱币": "钱币款",
        "竖条": "竖条款",
        "流星雨": "流星雨款",
        "四方纳福": "四方纳福款",
    }

    def detect_panel_preset(text: str) -> Optional[Dict[str, Any]]:
        text = text or ""
        for key, preset in front_fill_presets.items():
            if key in text:
                return preset
        for key, preset_name in legacy_preset_aliases.items():
            if key in text:
                return front_fill_presets[preset_name]
        return None

    explicit_panel_preset = str(p.get("panel_preset", "") or "")
    front_preset = detect_panel_preset(explicit_panel_preset) or detect_panel_preset(str(p.get("zmks", "")))
    back_preset = detect_panel_preset(str(p.get("fmks", ""))) or front_preset
    force_panel_preset = bool(explicit_panel_preset)

    def panel_settings(group: str, style: str) -> Dict[str, float | str]:
        prefix = "" if group == "front" else f"{group}_panel_"
        return {
            "style": style,
            "lock_offset_x": float(p.get(f"{prefix}lock_offset_x", p.get("panel_lock_offset_x", 180)) or 0),
            "hinge_offset_y": float(p.get(f"{prefix}hinge_offset_y", p.get("panel_hinge_offset_y", 100)) or 0),
            "middle_offset_z": float(p.get(f"{prefix}middle_offset_z", p.get("panel_middle_offset_z", 180)) or 0),
            "plus_offset_a": float(p.get(f"{prefix}plus_offset_a", p.get("panel_plus_offset_a", 350)) or 0),
            "plus_offset_b": float(p.get(f"{prefix}plus_offset_b", p.get("panel_plus_offset_b", 100)) or 0),
            "three_col_a": float(p.get(f"{prefix}three_col_a", p.get("panel_three_col_a", 180)) or 0),
            "three_col_b": float(p.get(f"{prefix}three_col_b", p.get("panel_three_col_b", 0)) or 0),
            "three_col_c": float(p.get(f"{prefix}three_col_c", p.get("panel_three_col_c", 100)) or 0),
            "fill_a": str(p.get(f"{prefix}fill_a", p.get("panel_fill_a", "")) or ""),
            "fill_b": str(p.get(f"{prefix}fill_b", p.get("panel_fill_b", "")) or ""),
            "fill_c": str(p.get(f"{prefix}fill_c", p.get("panel_fill_c", "")) or ""),
            "disc_radius": float(p.get(f"{prefix}disc_radius", p.get("panel_disc_radius", 120)) or 0),
        }

    def panel_lock_edge(index: int, px1: float, px2: float) -> Optional[float]:
        if door_type == "单门":
            if (is_back and door_open_dir == "左开") or (not is_back and door_open_dir == "右开"):
                return px1
            return px2
        if door_type in ("对开门", "子母门"):
            return px2 if (px1 + px2) / 2 < dw / 2 else px1
        if door_type in ("四开门", "两定两开"):
            return px2 if index <= 1 else px1
        return None

    def draw_panel_line(x1: float, y1: float, x2: float, y2: float):
        drawer.draw_line(off((x1, y1)), off((x2, y2)), 'A-DOOR-PANEL')

    def draw_panel_rect(x1: float, x2: float):
        draw_panel_body_rect(x1, x2)

    def is_child_panel(index: int) -> bool:
        if door_type == "子母门":
            return index == 0
        if door_type in ("两定两开", "四开门"):
            return index in (0, 3)
        return False

    def panel_settings_for(index: int) -> Dict[str, float | str]:
        if is_child_panel(index):
            return panel_settings("child", child_panel_style)
        group = "back" if is_back else "front"
        preset = back_preset if is_back else front_preset
        return apply_panel_preset(panel_settings(group, panel_style_default), preset, group, force_panel_preset)

    def resolve_three_col_widths(panel_width: float, settings: Dict[str, float | str]):
        a = settings["three_col_a"] if settings["three_col_a"] > 0 else None
        b = settings["three_col_b"] if settings["three_col_b"] > 0 else None
        c = settings["three_col_c"] if settings["three_col_c"] > 0 else None
        if b and not a and not c:
            a = (panel_width - b) / 2
            c = panel_width - b - a
        elif a and not b and not c:
            b = panel_width - a
            c = 0
        if a and c:
            b = panel_width - a - c
        elif a and b:
            c = panel_width - a - b
        elif b and c:
            a = panel_width - b - c
        else:
            a = settings["three_col_a"] if settings["three_col_a"] > 0 else 180
            c = settings["three_col_c"] if settings["three_col_c"] > 0 else 100
            b = panel_width - a - c
        if not a or not b or not c or min(a, b, c) <= 1:
            return None
        if abs((a + b + c) - panel_width) > 1:
            return None
        return a, b, c

    def apply_panel_preset(
        settings: Dict[str, float | str],
        preset: Optional[Dict[str, Any]],
        view_group: str,
        force: bool = False,
    ) -> Dict[str, float | str]:
        if not preset:
            return settings
        next_settings = dict(settings)
        has_explicit_fill = any(str(next_settings.get(key, "")).strip() for key in ("fill_a", "fill_b", "fill_c"))
        if view_group == "back":
            if force or not has_explicit_fill:
                next_settings.update({
                    "style": "三列式布局",
                    "three_col_a": 0,
                    "three_col_b": 100,
                    "three_col_c": 0,
                    "fill_a": "",
                    "fill_b": "竖条",
                    "fill_c": "",
                })
        elif force or not has_explicit_fill:
            next_settings.update({
                "style": preset["style"],
                "lock_offset_x": preset["lock_offset_x"],
                "fill_a": preset["fills"][0],
                "fill_b": preset["fills"][1],
                "fill_c": preset["fills"][2],
            })
        return next_settings

    def draw_fill_rect(x1: float, x2: float, fill_name: str, mirror: bool = False):
        fill_name = (fill_name or "").strip()
        if not fill_name or fill_name == "无":
            return
        left, right = sorted((x1, x2))
        sample = hatch_library.get(fill_name)
        drawer.draw_hatch_rect(*off((left, panel_y_bot)), *off((right, panel_y_top)), sample, mirror=mirror)

    if panel_positions:
        for idx, (px1, px2) in enumerate(panel_positions):
            settings = panel_settings_for(idx)
            panel_style = str(settings["style"])
            if not panel_style or panel_style == "无造型":
                continue
            lock_edge = panel_lock_edge(idx, px1, px2)
            if lock_edge is None:
                continue

            direction = 1 if abs(lock_edge - px1) < 0.01 else -1
            hinge_edge = px2 if direction == 1 else px1

            if panel_style == "三列式布局":
                widths = resolve_three_col_widths(abs(px2 - px1), settings)
                if not widths:
                    continue
                a_width, _b_width, c_width = widths
                lock_line_x = lock_edge + direction * a_width
                hinge_line_x = hinge_edge - direction * c_width
                if px1 < lock_line_x < px2 and px1 < hinge_line_x < px2 and abs(lock_line_x - hinge_line_x) > 1:
                    draw_fill_rect(lock_edge, lock_line_x, str(settings.get("fill_a", "")))
                    draw_fill_rect(lock_line_x, hinge_line_x, str(settings.get("fill_b", "")))
                    draw_fill_rect(hinge_line_x, hinge_edge, str(settings.get("fill_c", "")))
                    draw_panel_rect(lock_edge, lock_line_x)
                    draw_panel_rect(lock_line_x, hinge_line_x)
                    draw_panel_rect(hinge_line_x, hinge_edge)
                continue

            if panel_style == "圆盘造型":
                radius = float(settings["disc_radius"])
                center_y = 1050
                if radius <= 0:
                    continue
                if not (panel_y_bot < center_y - radius and center_y + radius < panel_y_top):
                    continue
                if direction == 1 and lock_edge + radius > px2:
                    continue
                if direction == -1 and lock_edge - radius < px1:
                    continue
                if direction == 1:
                    drawer.draw_arc(off((lock_edge, center_y)), radius, 270, 90, 'A-DOOR-PANEL')
                else:
                    drawer.draw_arc(off((lock_edge, center_y)), radius, 90, 270, 'A-DOOR-PANEL')
                continue

            panel_lock_offset_x = float(settings["lock_offset_x"])
            if panel_lock_offset_x <= 0:
                continue
            lock_line_x = lock_edge + direction * panel_lock_offset_x
            if not (px1 < lock_line_x < px2):
                continue
            draw_panel_line(lock_line_x, panel_y_bot, lock_line_x, panel_y_top)

            if panel_style == "两列式布局":
                is_left_leaf = (px1 + px2) / 2 < dw / 2
                draw_fill_rect(lock_edge, lock_line_x, str(settings.get("fill_a", "")))
                draw_fill_rect(lock_line_x, hinge_edge, str(settings.get("fill_b", "")), mirror=is_left_leaf and str(settings.get("fill_b", "")) == "斜实虚")
                draw_panel_rect(lock_edge, lock_line_x)
                draw_panel_rect(lock_line_x, hinge_edge)
                continue

            if panel_style not in ("H型布局", "H+型布局"):
                continue

            hinge_line_x = hinge_edge - direction * float(settings["hinge_offset_y"])
            if not (px1 < hinge_line_x < px2):
                continue
            if abs(hinge_line_x - lock_line_x) < 1:
                continue
            draw_panel_line(hinge_line_x, panel_y_bot, hinge_line_x, panel_y_top)

            bx1, bx2 = sorted((lock_line_x, hinge_line_x))
            lower_line_y = panel_y_bot + float(settings["middle_offset_z"])
            upper_line_y = panel_y_top - float(settings["middle_offset_z"])
            y_lines = []
            if panel_y_bot < lower_line_y < panel_y_top:
                y_lines.append(lower_line_y)
            if panel_y_bot < upper_line_y < panel_y_top and abs(upper_line_y - lower_line_y) > 1:
                y_lines.append(upper_line_y)
            if panel_style == "H+型布局":
                plus_a_y = lower_line_y + float(settings["plus_offset_a"])
                plus_b_y = plus_a_y + float(settings["plus_offset_b"])
                for y in (plus_a_y, plus_b_y):
                    if panel_y_bot < y < panel_y_top and all(abs(y - exists) > 1 for exists in y_lines):
                        y_lines.append(y)
            for y in sorted(y_lines):
                draw_panel_line(bx1, y, bx2, y)

    def parse_handle_size(value: str) -> Optional[Tuple[float, float]]:
        if not value:
            return None
        normalized = value.lower().replace("×", "*").replace("x", "*")
        parts = [part.strip() for part in normalized.split("*") if part.strip()]
        if len(parts) != 2:
            return None
        try:
            a, b = float(parts[0]), float(parts[1])
        except ValueError:
            return None
        return min(a, b), max(a, b)

    def handle_targets(distance: float = 60, primary_only: bool = False):
        targets = []
        if not panel_positions:
            return targets

        def add(px1, px2, edge_side):
            if edge_side == "left":
                targets.append((px1 + distance, 1, "YBPLS"))
            else:
                targets.append((px2 - distance, -1, "ZBPLS"))

        if door_type == "单门":
            eff_dir = ("右开" if door_open_dir == "左开" else "左开") if is_back else door_open_dir
            add(*panel_positions[0], "right" if eff_dir == "左开" else "left")
        elif door_type == "对开门" and len(panel_positions) >= 2:
            if primary_only:
                idx = 1 if door_open_dir == "右开" else 0
                add(*panel_positions[idx], "left" if idx == 1 else "right")
            else:
                add(*panel_positions[0], "right")
                add(*panel_positions[1], "left")
        elif door_type == "子母门" and len(panel_positions) >= 2:
            mother_right = (is_back and door_open_dir == "左开") or (not is_back and door_open_dir == "右开")
            add(*panel_positions[1], "left" if mother_right else "right")
        elif door_type in ["四开门", "两定两开"] and len(panel_positions) >= 4:
            if primary_only:
                idx = 2 if door_open_dir == "右开" else 1
                add(*panel_positions[idx], "left" if idx == 2 else "right")
            else:
                add(*panel_positions[1], "right")
                add(*panel_positions[2], "left")
        return targets

    def sized_handle_targets(distance: float = 110):
        if door_type == "对开门" and len(panel_positions) >= 2:
            left_x1, left_x2 = panel_positions[0]
            right_x1, right_x2 = panel_positions[1]
            return [
                (left_x2 - distance, -1, "ZBPLS"),
                (right_x1 + distance, 1, "YBPLS"),
            ]
        if door_type in ("四开门", "两定两开") and len(panel_positions) >= 4:
            left_x1, left_x2 = panel_positions[1]
            right_x1, right_x2 = panel_positions[2]
            return [
                (left_x2 - distance, -1, "ZBPLS"),
                (right_x1 + distance, 1, "YBPLS"),
            ]
        return handle_targets(distance, primary_only=True)

    def backpack_handle_targets(distance: float = 60):
        if not is_back:
            return handle_targets(distance, primary_only=True)
        if not panel_positions:
            return []

        def add_target(index: int, edge_side: str):
            px1, px2 = panel_positions[max(0, min(index, len(panel_positions) - 1))]
            if edge_side == "left":
                return [(px1 + distance, 1, "YBPLS")]
            return [(px2 - distance, -1, "ZBPLS")]

        if door_type == "单门":
            return add_target(0, "left" if door_open_dir == "右开" else "right")

        if door_type == "对开门" and len(panel_positions) >= 2:
            return add_target(0, "right") if door_open_dir == "右开" else add_target(1, "left")

        if door_type == "子母门" and len(panel_positions) >= 2:
            return add_target(1, "right") if door_open_dir == "右开" else add_target(1, "left")

        if door_type in ("四开门", "两定两开") and len(panel_positions) >= 4:
            return add_target(1, "right") if door_open_dir == "右开" else add_target(2, "left")

        if door_open_dir == "右开":
            return add_target(0, "left")
        return add_target(0, "right")

    # ===================== 标配拉手/背包拉手/长拉手绘制 =====================
    current_handle = p.get('fmls') if is_back else p.get('zmls')
    handle_size = parse_handle_size(str(p.get("handle_size", "")))
    non_sized_handles = {"", "无", "标配拉手", "A1022", "A635", "分体拉手", "背包拉手"}
    current_sized_handle = bool(handle_size and str(current_handle).strip() not in non_sized_handles)

    def draw_mask(cx: float, cy: float, width: float, height: float):
        drawer.draw_wipeout_rect(
            *off((cx - width / 2, cy - height / 2)),
            *off((cx + width / 2, cy + height / 2)),
        )

    def draw_block_mask(block_name: str, cx: float, cy: float, xscale: float = 1, yscale: float = 1, fallback_width: float = 80, fallback_height: float = 220):
        if not drawer.draw_wipeout_for_block(block_name, off((cx, cy)), xscale=xscale, yscale=yscale):
            draw_mask(cx, cy, fallback_width, fallback_height)

    if current_handle in ("标配拉手", "A1022", "A635", "分体拉手") and not current_sized_handle:
        mask_targets = handle_targets(60)
        if current_handle == "分体拉手" and is_back and door_type == "对开门" and len(panel_positions) >= 2:
            if door_open_dir == "右开":
                left_x1, left_x2 = panel_positions[0]
                mask_targets = [(left_x2 - 60, -1, "ZBPLS")]
            else:
                right_x1, right_x2 = panel_positions[1]
                mask_targets = [(right_x1 + 60, 1, "YBPLS")]
        for hx, _toward_hinge, hblock in mask_targets:
            if current_handle == "A1022":
                block_name = ("Y1022" if hblock == "YBPLS" else "Z1022") if is_back else ("Z1022" if hblock == "YBPLS" else "Y1022")
            elif current_handle == "A635":
                block_name = "A635"
            elif current_handle == "分体拉手":
                block_name = "YFTLS" if hblock == "YBPLS" else "ZFTLS"
            else:
                block_name = hblock
            draw_block_mask(block_name, hx, panel_y_bot + 1000)

    if current_handle == "背包拉手" and not current_sized_handle:
        for hx, toward_hinge, _hblock in backpack_handle_targets(60):
            draw_block_mask("BBLS", hx, 1050, xscale=toward_hinge)

    if handle_size and current_sized_handle:
        handle_w, handle_h = handle_size
        for hx, _toward_hinge, _hblock in sized_handle_targets(110):
            draw_mask(hx, 1200, handle_w, handle_h)

    if not is_back and p.get("fingerprint_lock") in ("安志杰AF-12", "Q3指纹锁", "T5指纹锁"):
        for hx, toward_hinge, _hblock in handle_targets(60, primary_only=True):
            draw_block_mask("AZJ", hx, 1050, xscale=toward_hinge, fallback_width=80, fallback_height=180)

    if current_handle == "标配拉手" and not current_sized_handle:
        handle_y = panel_y_bot + 1000
        for hx, _toward_hinge, hblock in handle_targets(60):
            drawer.insert_custom_block(hblock, off((hx, handle_y)), layer="A-DOOR-PANEL")

    if current_handle == "A1022" and not current_sized_handle:
        handle_y = panel_y_bot + 1000
        for hx, _toward_hinge, hblock in handle_targets(60):
            if is_back:
                a1022_block = "Y1022" if hblock == "YBPLS" else "Z1022"
            else:
                a1022_block = "Z1022" if hblock == "YBPLS" else "Y1022"
            drawer.insert_custom_block(a1022_block, off((hx, handle_y)), layer="A-DOOR-PANEL")

    if current_handle == "A635" and not current_sized_handle:
        handle_y = panel_y_bot + 1000
        for hx, _toward_hinge, _hblock in handle_targets(60):
            drawer.insert_custom_block("A635", off((hx, handle_y)), layer="A-DOOR-PANEL")

    if current_handle == "分体拉手" and not current_sized_handle:
        handle_y = panel_y_bot + 1000
        targets = handle_targets(60)
        if is_back and door_type == "对开门" and len(panel_positions) >= 2:
            if door_open_dir == "右开":
                left_x1, left_x2 = panel_positions[0]
                targets = [(left_x2 - 60, -1, "ZBPLS")]
            else:
                right_x1, right_x2 = panel_positions[1]
                targets = [(right_x1 + 60, 1, "YBPLS")]
        for hx, _toward_hinge, hblock in targets:
            split_block = "YFTLS" if hblock == "YBPLS" else "ZFTLS"
            drawer.insert_custom_block(split_block, off((hx, handle_y)), layer="A-DOOR-PANEL")

    if current_handle == "背包拉手" and not current_sized_handle:
        for hx, toward_hinge, _hblock in backpack_handle_targets(60):
            drawer.insert_custom_block("BBLS", off((hx, 1050)), layer="A-DOOR-PANEL", xscale=toward_hinge)

    if handle_size and current_sized_handle:
        handle_w, handle_h = handle_size
        for hx, _toward_hinge, _hblock in sized_handle_targets(110):
            y_center = 1200
            drawer.draw_poly([
                off((hx - handle_w / 2, y_center - handle_h / 2)),
                off((hx + handle_w / 2, y_center - handle_h / 2)),
                off((hx + handle_w / 2, y_center + handle_h / 2)),
                off((hx - handle_w / 2, y_center + handle_h / 2)),
            ], "A-DOOR-PANEL")

    if not is_back and p.get("fingerprint_lock") in ("安志杰AF-12", "Q3指纹锁", "T5指纹锁"):
        for hx, toward_hinge, _hblock in handle_targets(60, primary_only=True):
            drawer.insert_custom_block("AZJ", off((hx, 1050)), layer="A-DOOR-PANEL", xscale=toward_hinge)

    drawer.update_progress(f"{view_name}绘制完成")


# ===================== 集成系统入口 =====================
def run_integrated_system(
    info: Dict, checks: Dict, draw_p: Dict,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Tuple[str, Optional[io.StringIO]]:
    if progress_callback is None:
        progress_callback = lambda x: None

    try:
        progress_callback("正在启动云端图纸引擎...")

        cached = _get_cached_template()
        if cached:
            doc = ezdxf.read(io.StringIO(cached))
        else:
            doc = ezdxf.new('R2010')
        doc.header["$DIMASSOC"] = 2

        ms = doc.modelspace()

        base_attrs = {
            "DHDW": info.get("DHDW", ""),
            "GDMC": info.get("GDMC", ""),
            "ZZCL": info.get("ZZCL", ""),
            "DHRQ": info.get("DHRQ", ""),
            "DDH": info.get("DDH", ""),
            "SL": info.get("SL", ""),
            "YS": info.get("YS", ""),
            "ZMLS": info.get("ZMLS", ""),
            "FMLS": info.get("FMLS", ""),
            "ST": info.get("ST", ""),
            "ZWS": info.get("ZWS", ""),
            "HYSL": info.get("HYSL", ""),
            "QH": info.get("QH", ""),
            "MSHD": info.get("MSHD", ""),
            "HHXD": info.get("HHXD", ""),
            "BZ": info.get("BZ", ""),
            "DOOR_TYPE": info.get("DOOR_TYPE", ""),
            "MOTHER_DOOR_WIDTH": info.get("MOTHER_DOOR_WIDTH", ""),
            "HYYS": info.get("HYYS", ""),
            "DXK": info.get("DXK", ""),
            "GXK": info.get("GXK", ""),
            "PXK": info.get("PXK", ""),
            "DJ": info.get("DJ", ""),
            "DJG": info.get("DJG", ""),
            "MX": info.get("MX", ""),
            "QC_HEIGHT": info.get("QC_HEIGHT", ""),
            "MM_HEIGHT": info.get("MM_HEIGHT", ""),
            "ZMKS": info.get("ZMKS", "按图"),
            "FMKS": info.get("FMKS", "按图"),
        }

        nk = checks.get("nk", "内开")
        kx = checks.get("kx", "右开")
        qc = checks.get("qc", "无")
        bz = checks.get("bz", "全包")
        threshold = checks.get("threshold", "高低槛")

        has_pillar = False
        if checks.get("lz", "无") == "有":
            has_pillar = True

        has_mm = False
        if checks.get("mm", "无") == "有":
            has_mm = True

        check_attrs = {
            "OUTER": checks.get("OUTER", ""),
            "INNER": checks.get("INNER", ""),
            "NK": "√" if nk == "内开" else "",
            "WK": "√" if nk == "外开" else "",
            "KX_RIGHT": "√" if kx == "右开" else "",
            "KX_LEFT": "√" if kx == "左开" else "",
            "LZ_YES": "√" if has_pillar else "",
            "LZ_NO": "" if has_pillar else "√",
            "MM_YES": "√" if has_mm else "",
            "MM_NO": "" if has_mm else "√",
            "QC_GLASS": "√" if qc == "玻璃" else "",
            "QC_SEAL": "√" if qc == "封闭" else "",
            "BZ_QB": "√" if bz == "全包" else "",
            "BZ_MX": "√" if bz == "木箱" else "",
            "GDK": "√" if threshold == "高低槛" else "",
            "PDK": "√" if threshold == "平底槛" else "",
            "DJ": "√" if threshold == "吊脚" else checks.get("DJ", ""),
        }

        all_attrs = {**base_attrs, **check_attrs}

        for insert in ms.query('INSERT'):
            to_replace = []
            for attrib in insert.attribs:
                tag = attrib.dxf.tag.strip().upper()
                if tag == "BZ":
                    ms.add_mtext(all_attrs["BZ"], dxfattribs={
                        'insert': attrib.dxf.insert,
                        'char_height': attrib.dxf.height,
                        'layer': attrib.dxf.layer,
                        'style': attrib.dxf.style
                    }).dxf.width = 6000
                    to_replace.append(attrib)
                elif tag in all_attrs:
                    attrib.dxf.text = str(all_attrs[tag])
                elif tag == "QC_TEXT":
                    if qc == "玻璃":
                        attrib.dxf.text = "玻璃"
                    elif qc == "封闭":
                        attrib.dxf.text = "封闭"
                    else:
                        attrib.dxf.text = "无"
                elif tag == "BZ_TYPE":
                    if bz == "全包":
                        attrib.dxf.text = "全包"
                    else:
                        attrib.dxf.text = "木箱"

            for old_attrib in to_replace:
                old_attrib.destroy()

        sel_hys = checks.get('hys', '葫芦头合页')
        hinge_name = CONFIG.HINGE_TYPES.get(sel_hys, "hlt")
        drawer = EzdxfDrawer(doc, ms, hinge_name, progress_callback)
        drawer.batch_add_layers({
            "A-DOOR-HATCH": 9,
            "A-DOOR-MASK": 7,
            "A-DOOR-FRAME": 4,
            "A-DOOR-PANEL": 2,
            "A-DOOR-TRIM": 1,
            "YQ_DIM": 3,
            "A-DOOR-mark": 7
        })

        draw_p.update({
            "door_type": info.get("DOOR_TYPE", "单门"),
            "mother_door_width": info.get("MOTHER_DOOR_WIDTH", 600),
            "mid_door_width": info.get("MID_DOOR_WIDTH", 400),
            "pillar_width_str": info.get("PILLAR_WIDTH_STR", "55/85"),
            "has_pillar": info.get("HAS_PILLAR", False),
            "qc_height": info.get("QC_HEIGHT", 400),
            "has_mm": info.get("HAS_MM", False),
            "mm_height": info.get("MM_HEIGHT", 200)
        })

        use_light = draw_p.get("use_light_size", False)
        lw = draw_p.get("light_w", 0)
        lh = draw_p.get("light_h", 0)

        draw_door_in_frame(drawer, "正面", draw_p, False, use_light, lw, lh)
        draw_door_in_frame(drawer, "背面", draw_p, True, use_light, lw, lh)

        buffer = io.StringIO()
        doc.write(buffer)
        buffer.seek(0)
        return "图纸生成成功！", buffer

    except Exception as e:
        import traceback
        return f"生成出错: {str(e)}\n{traceback.format_exc()}", None
