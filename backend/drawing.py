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

from config import CONFIG, TEMPLATE_PATH
from utils import parse_dim_str, parse_gap_str


HATCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "hatches")
PANEL_FILL_PATTERNS = {
    "钱币": {"pattern": "qianbi", "file": "qianbi.pat", "scale": 1, "angle": 0, "type": "custom"},
    "qianbi": {"pattern": "qianbi", "file": "qianbi.pat", "scale": 1, "angle": 0, "type": "custom"},
    "万字纹": {"pattern": "wan", "file": "wan.pat", "scale": 0.5, "angle": 0, "type": "custom"},
    "wan": {"pattern": "wan", "file": "wan.pat", "scale": 0.5, "angle": 0, "type": "custom"},
    "鱼鳞纹": {"pattern": "yulin", "file": "yulin.pat", "scale": 0.8, "angle": 0, "type": "custom"},
    "yulin": {"pattern": "yulin", "file": "yulin.pat", "scale": 0.8, "angle": 0, "type": "custom"},
    "紫荆花": {"pattern": "zijinghua", "file": "zijinghua.pat", "scale": 0.8, "angle": 0, "type": "custom"},
    "zijinghua": {"pattern": "zijinghua", "file": "zijinghua.pat", "scale": 0.8, "angle": 0, "type": "custom"},
    "竖条": {"pattern": "shutiao", "file": "shutiao.pat", "scale": 0.4, "angle": 0, "type": "custom"},
    "shutiao": {"pattern": "shutiao", "file": "shutiao.pat", "scale": 0.4, "angle": 0, "type": "custom"},
    "实虚线": {"pattern": "ANSI33", "scale": 10, "angle": 0, "type": "builtin"},
    "ansi33": {"pattern": "ANSI33", "scale": 10, "angle": 0, "type": "builtin"},
    "四方纳福": {"pattern": "EARTH", "scale": 6, "angle": 0, "type": "builtin"},
    "earth": {"pattern": "EARTH", "scale": 6, "angle": 0, "type": "builtin"},
    "流星雨": {"pattern": "liuxingyu", "file": "liuxingyu.pat", "scale": 1, "angle": 0, "type": "custom"},
    "liuxingyu": {"pattern": "liuxingyu", "file": "liuxingyu.pat", "scale": 1, "angle": 0, "type": "custom"},
}


def _parse_pat_definition(file_name: str):
    path = os.path.join(HATCH_DIR, file_name)
    if not os.path.exists(path):
        return None
    definition = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("*") or line.startswith(";"):
                continue
            parts = [part.strip() for part in line.split(",")]
            if len(parts) < 5:
                continue
            try:
                angle = float(parts[0])
                base = (float(parts[1]), float(parts[2]))
                offset = (float(parts[3]), float(parts[4]))
                dashes = [float(part) for part in parts[5:] if part]
            except ValueError:
                continue
            definition.append([angle, base, offset, dashes])
    return definition or None

# ===================== 模板缓存 =====================
# 启动时加载一次 template.dxf 到内存，避免每次请求重复磁盘 I/O
_template_text: Optional[str] = None


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

    def draw_line(self, p1, p2, layer):
        self.ms.add_line(p1, p2, dxfattribs={'layer': layer})

    def draw_hatch(self, points, pattern_key, layer="A-DOOR-PANEL-FILL"):
        config = PANEL_FILL_PATTERNS.get((pattern_key or "").strip())
        if not config:
            return None
        hatch = self.ms.add_hatch(color=256, dxfattribs={'layer': layer})
        pattern_name = config["pattern"]
        scale = float(config.get("scale", 1) or 1)
        angle = float(config.get("angle", 0) or 0)
        if pattern_name.upper() == "SOLID":
            hatch.set_solid_fill(color=256)
        elif config.get("type") == "custom":
            definition = _parse_pat_definition(config.get("file", ""))
            hatch.set_pattern_fill(
                pattern_name,
                color=256,
                angle=angle,
                scale=scale,
                pattern_type=2,
                definition=definition,
            )
        else:
            hatch.set_pattern_fill(pattern_name, color=256, angle=angle, scale=scale)
        hatch.paths.add_polyline_path(points, is_closed=True)
        return hatch

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

    left_width = p['left_width_back'] if is_back else p['left_width_front']
    right_width = p['right_width_back'] if is_back else p['right_width_front']
    fw_top = p['fw_top_back'] if is_back else p['fw_top_front']
    th = p['th_back'] if is_back else p['th_front']
    trim_w = p['trim_back'] if is_back else p['trim_front']
    overlap_key = 'overlap_back' if is_back else 'overlap_front'
    overlap = p.get(overlap_key, p.get('overlap', 20)) if trim_w > 0 else 0
    dw = p['dw']
    dh = p['dh']

    door_type = p.get('door_type', '单门')
    mother_door_width = p.get('mother_door_width', 600)
    mid_door_width = p.get('mid_door_width', 400)
    pillar_width_str = p.get('pillar_width_str', '55/70')
    has_pillar = p.get('has_pillar', False)
    door_open_dir = p.get('kx', '右开')
    nk_choice = p.get('nk', '内开')

    left_gap, right_gap = p.get('left_right_gap', (0, 0))
    top_gap, bottom_gap = p.get('top_bottom_gap', (0, 0))
    middle_gap = p.get('middle_gap', 0)

    # 面板基准：以开启侧门框为参照计算尺寸和位置，正反面绘制完全一致
    # 外开→正面框为基准, 内开→背面框为基准
    # 无缝侧门框更宽→面板与框自然重叠（物理正确）
    if nk_choice == "外开":
        ref_left = p['left_width_front']
        ref_right = p['right_width_front']
        ref_fw_top = p['fw_top_front']
        ref_th = p['th_front']
    else:
        ref_left = p['left_width_back']
        ref_right = p['right_width_back']
        ref_fw_top = p['fw_top_back']
        ref_th = p['th_back']

    qc_choice = p.get('qc', '无')
    qc_height = p.get('qc_height', 400)
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
    front_total_width = dw + 2 * p.get('trim_front', 0)

    if not is_back:
        offset_x = frame_center_x - front_total_width / 2
    else:
        offset_x = (frame_center_x - front_total_width / 2) + front_total_width + (dw + 2 * p.get('trim_back', 0)) + 300

    offset_y = frame_center_y

    def off(pt):
        return (pt[0] + offset_x, pt[1] + offset_y)

    drawer.draw_poly([off((0, 0)), off((left_width, 0)), off((left_width, dh)), off((0, dh))], 'A-DOOR-FRAME')
    drawer.draw_poly([off((dw - right_width, 0)), off((dw, 0)), off((dw, dh)), off((dw - right_width, dh))], 'A-DOOR-FRAME')

    qc_h = qc_height if qc_choice in ["玻璃", "封闭"] else 0
    top_frame_bottom = dh - fw_top

    drawer.draw_poly([off((left_width, top_frame_bottom)), off((dw - right_width, top_frame_bottom)), off((dw - right_width, dh)), off((left_width, dh))], 'A-DOOR-FRAME')

    if qc_h > 0:
        mid_frame_top = top_frame_bottom - qc_h
        mid_frame_bottom = mid_frame_top - fw_top
        drawer.draw_poly([off((left_width, mid_frame_bottom)), off((dw - right_width, mid_frame_bottom)), off((dw - right_width, mid_frame_top)), off((left_width, mid_frame_top))], 'A-DOOR-FRAME')
        if th > 0:
            drawer.draw_poly([off((left_width, 0)), off((dw - right_width, 0)), off((dw - right_width, th)), off((left_width, th))], 'A-DOOR-FRAME')
    else:
        if th > 0:
            drawer.draw_poly([off((left_width, 0)), off((dw - right_width, 0)), off((dw - right_width, th)), off((left_width, th))], 'A-DOOR-FRAME')

    if trim_w > 0:
        W = trim_w
        O = overlap
        mm_offset = mm_height if has_mm else 0
        ix1, iy1 = O, 0
        ix2, iy2 = O, dh - O + mm_offset
        ix3, iy3 = dw - O, dh - O + mm_offset
        ix4, iy4 = dw - O, 0
        ox1, oy1 = O - W, 0
        ox2, oy2 = O - W, dh - O + W + mm_offset
        ox3, oy3 = dw - O + W, dh - O + W + mm_offset
        ox4, oy4 = dw - O + W, 0

        drawer.draw_poly([off((ox1, oy1)), off((ox2, oy2)), off((ox3, oy3)), off((ox4, oy4)), off((ix4, iy4)), off((ix3, iy3)), off((ix2, iy2)), off((ix1, iy1))], 'A-DOOR-TRIM')
        drawer.draw_line(off((ix2, iy2)), off((ox2, oy2)), 'A-DOOR-TRIM')
        drawer.draw_line(off((ix3, iy3)), off((ox3, oy3)), 'A-DOOR-TRIM')

        if has_mm and mm_height > 0:
            mm_bottom = dh - O
            mm_top = mm_bottom + mm_height
            mm_left = ix1
            mm_right = ix4
            drawer.draw_poly([off((mm_left, mm_top)), off((mm_right, mm_top)), off((mm_right, mm_bottom)), off((mm_left, mm_bottom))], 'A-DOOR-TRIM')

        # ===================== 包边款式偏移线 =====================
        trim_style = p.get('trim_style_outer', '') if not is_back else p.get('trim_style_inner', '')
        if trim_style:
            # 包套上边高度 = dh - O + W + mm_offset
            outer_top_y = dh - O + W + mm_offset
            inner_top_y = dh - O + mm_offset

            # 三边偏移多段线（左→上→右，底部对齐 y=0，不闭合）
            def draw_outer_offset(D):
                left_x = O - W + D
                right_x = dw - O + W - D
                top_y = outer_top_y - D
                drawer.draw_poly(
                    [off((left_x, 0)), off((left_x, top_y)), off((right_x, top_y)), off((right_x, 0))],
                    'A-DOOR-TRIM', closed=False
                )

            def draw_inner_offset(D):
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
                '平包套': 'PBT',
            }
            block_name = block_name_map.get(trim_style, 'XBT')
            trim_left_x = O - W  # 包套最左侧
            block_x = trim_left_x - 150  # 块在包套最左侧向左150mm
            block_y = dh / 2 + 80
            leader_y = dh / 2  # 包套最左侧中心点
            drawer.insert_custom_block(block_name, off((block_x, block_y)), layer='A-DOOR-TRIM')
            drawer.draw_line(off((trim_left_x, leader_y)), off((trim_left_x - 450, leader_y)), 'A-DOOR-TRIM')
    else:
        ox1, oy1, ox4, oy4, ox3, oy3 = 0, 0, dw, 0, dw, dh
        ix1, iy1, ix4, iy4, ix3, iy3 = 0, 0, dw, 0, dw, dh

    if qc_h > 0:
        qc_top = top_frame_bottom
        qc_bottom = top_frame_bottom - qc_h
        drawer.draw_poly([off((left_width, qc_bottom)), off((dw - right_width, qc_bottom)), off((dw - right_width, qc_top)), off((left_width, qc_top))], 'A-DOOR-FRAME')

    if qc_h > 0:
        panel_y_top = top_frame_bottom - qc_h - ref_fw_top - top_gap
    else:
        panel_y_top = dh - ref_fw_top - top_gap
    if p.get("has_dj"):
        panel_y_bot = max(0, p.get("dj_height", 0))
    else:
        panel_y_bot = ref_th + bottom_gap

    pillar_width_front = 0
    pillar_width_back = 0
    if door_type == "两定两开" and has_pillar and pillar_width_str:
        parts = parse_dim_str(pillar_width_str, 55, 70)
        pillar_out = parts[0]
        pillar_in = parts[1]
        if nk_choice == "内开":
            pillar_width_front = pillar_in
            pillar_width_back = pillar_out
        else:
            pillar_width_front = pillar_out
            pillar_width_back = pillar_in

    panel_positions = []

    if door_type == "单门":
        panel_x1 = ref_left + left_gap
        panel_x2 = dw - ref_right - right_gap
        drawer.draw_poly([off((panel_x1, panel_y_bot)), off((panel_x2, panel_y_bot)), off((panel_x2, panel_y_top)), off((panel_x1, panel_y_top))], 'A-DOOR-PANEL')
        panel_positions.append((panel_x1, panel_x2))

    elif door_type == "对开门":
        total_door_width = dw - ref_left - ref_right - left_gap - right_gap
        single_panel_width = (total_door_width - middle_gap) / 2
        left_panel_x1 = ref_left + left_gap
        left_panel_x2 = left_panel_x1 + single_panel_width
        right_panel_x1 = left_panel_x2 + middle_gap
        right_panel_x2 = right_panel_x1 + single_panel_width

        drawer.draw_poly([off((left_panel_x1, panel_y_bot)), off((left_panel_x2, panel_y_bot)), off((left_panel_x2, panel_y_top)), off((left_panel_x1, panel_y_top))], 'A-DOOR-PANEL')
        drawer.draw_poly([off((right_panel_x1, panel_y_bot)), off((right_panel_x2, panel_y_bot)), off((right_panel_x2, panel_y_top)), off((right_panel_x1, panel_y_top))], 'A-DOOR-PANEL')
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

        drawer.draw_poly([off((son_panel_x1, panel_y_bot)), off((son_panel_x2, panel_y_bot)), off((son_panel_x2, panel_y_top)), off((son_panel_x1, panel_y_top))], 'A-DOOR-PANEL')
        drawer.draw_poly([off((mother_panel_x1, panel_y_bot)), off((mother_panel_x2, panel_y_bot)), off((mother_panel_x2, panel_y_top)), off((mother_panel_x1, panel_y_top))], 'A-DOOR-PANEL')
        panel_positions.extend([(son_panel_x1, son_panel_x2), (mother_panel_x1, mother_panel_x2)])

        if not is_back:
            drawer.draw_dim(off((mother_panel_x1, panel_y_bot - 100)), off((mother_panel_x2, panel_y_bot - 100)), off((mother_panel_x1 - 100, panel_y_bot - 150)), 0, 'YQ_DIM', "母门宽 <>")

    elif door_type == "折叠四开门":
        total_door_width = dw - ref_left - ref_right - left_gap - right_gap
        mid_total_width = 2 * mid_door_width + middle_gap
        side_width = (total_door_width - mid_total_width) / 2
        lx1 = ref_left + left_gap
        lx2 = lx1 + side_width
        lmx1 = lx2
        lmx2 = lmx1 + mid_door_width
        rmx1 = lmx2 + middle_gap
        rmx2 = rmx1 + mid_door_width
        rx1 = rmx2
        rx2 = rx1 + side_width

        drawer.draw_poly([off((lx1, panel_y_bot)), off((lx2, panel_y_bot)), off((lx2, panel_y_top)), off((lx1, panel_y_top))], 'A-DOOR-PANEL')
        drawer.draw_poly([off((lmx1, panel_y_bot)), off((lmx2, panel_y_bot)), off((lmx2, panel_y_top)), off((lmx1, panel_y_top))], 'A-DOOR-PANEL')
        drawer.draw_poly([off((rmx1, panel_y_bot)), off((rmx2, panel_y_bot)), off((rmx2, panel_y_top)), off((rmx1, panel_y_top))], 'A-DOOR-PANEL')
        drawer.draw_poly([off((rx1, panel_y_bot)), off((rx2, panel_y_bot)), off((rx2, panel_y_top)), off((rx1, panel_y_top))], 'A-DOOR-PANEL')

        panel_positions.extend([(lx1, lx2), (lmx1, lmx2), (rmx1, rmx2), (rx1, rx2)])

        if not is_back:
            drawer.draw_dim(off((lmx1, panel_y_bot - 150)), off((rmx2, panel_y_bot - 150)), off((lmx1 + mid_total_width / 2, panel_y_bot - 200)), 0, 'YQ_DIM', "中门宽度 <>")

    elif door_type == "两定两开":
        total_door_width = dw - ref_left - ref_right - left_gap - right_gap
        pillar_total = 2 * pillar_width_front if has_pillar else 0
        mid_total_width = 2 * mid_door_width + middle_gap
        side_width = (total_door_width - mid_total_width - pillar_total) / 2

        lx1 = ref_left + left_gap
        lx2 = lx1 + side_width
        lpx1 = lx2
        lpx2 = lpx1 + pillar_width_front if has_pillar else lpx1
        lmx1 = lpx2
        lmx2 = lmx1 + mid_door_width
        rmx1 = lmx2 + middle_gap
        rmx2 = rmx1 + mid_door_width
        rpx1 = rmx2
        rpx2 = rpx1 + pillar_width_front if has_pillar else rpx1
        rx1 = rpx2
        rx2 = rx1 + side_width

        drawer.draw_poly([off((lx1, panel_y_bot)), off((lx2, panel_y_bot)), off((lx2, panel_y_top)), off((lx1, panel_y_top))], 'A-DOOR-PANEL')
        if has_pillar:
            drawer.draw_poly([off((lpx1, panel_y_bot)), off((lpx2, panel_y_bot)), off((lpx2, panel_y_top)), off((lpx1, panel_y_top))], 'A-DOOR-FRAME')
        drawer.draw_poly([off((lmx1, panel_y_bot)), off((lmx2, panel_y_bot)), off((lmx2, panel_y_top)), off((lmx1, panel_y_top))], 'A-DOOR-PANEL')
        drawer.draw_poly([off((rmx1, panel_y_bot)), off((rmx2, panel_y_bot)), off((rmx2, panel_y_top)), off((rmx1, panel_y_top))], 'A-DOOR-PANEL')
        if has_pillar:
            drawer.draw_poly([off((rpx1, panel_y_bot)), off((rpx2, panel_y_bot)), off((rpx2, panel_y_top)), off((rpx1, panel_y_top))], 'A-DOOR-FRAME')
        drawer.draw_poly([off((rx1, panel_y_bot)), off((rx2, panel_y_bot)), off((rx2, panel_y_top)), off((rx1, panel_y_top))], 'A-DOOR-PANEL')

        panel_positions.extend([(lx1, lx2), (lmx1, lmx2), (rmx1, rmx2), (rx1, rx2)])

    # ===================== 尺寸标注 =====================
    rad90 = math.radians(90)

    if trim_w > 0:
        outer_left, outer_right, outer_bottom, outer_top = ox1, ox4, 0, oy3
    else:
        outer_left, outer_right, outer_bottom, outer_top = 0, dw, 0, dh

    dims_h = []
    if trim_w > 0:
        dims_h.append(("含包套总宽", outer_left, outer_right, -400, True, "含包套总宽 <>"))
        dims_h.append(("门套宽", ox1, ix1, -200, True, f" {trim_w}"))

    should_mark_light = p.get("mark_light_size", False) or use_light_size
    should_draw_light_view = (nk_choice == "内开" and not is_back) or (nk_choice == "外开" and is_back)
    if should_mark_light and should_draw_light_view:
        light_x1 = left_width
        light_x2 = dw - right_width
        if door_type in ("两定两开", "折叠四开门") and len(panel_positions) >= 4:
            light_x1 = panel_positions[0][1]
            light_x2 = panel_positions[-1][0]
        light_text = f"见光宽 {light_w}" if use_light_size and light_w > 0 else "见光宽 <>"
        dims_h.append(("见光宽", light_x1, light_x2, -200, True, light_text))

    dims_h.append(("洞口宽", 0, dw, -300, True, None))

    dims_v = []
    if trim_w > 0:
        dims_v.append(("含包套总高", outer_bottom, outer_top, 400, True, "含包套总高 <>"))

    if has_mm and mm_height > 0 and trim_w > 0:
        dims_v.append(("门楣高度", dh - O + mm_height, dh - O, 300, True, f"门楣高度 {mm_height}"))

    if qc_h > 0:
        mid_frame_top = top_frame_bottom - qc_h
        dims_v.append(("气窗上部高度", mid_frame_top, dh, 200, True, None))
        dims_v.append(("门板下部高度", 0, mid_frame_top, 200, True, None))

    if should_mark_light and should_draw_light_view:
        light_text_h = f"见光高 {light_h}" if use_light_size and light_h > 0 else "见光高 <>"
        light_y1 = th
        light_y2 = dh - fw_top
        dims_v.append(("见光高", light_y1, light_y2, 100, True, light_text_h))

    dims_v.append(("洞口高", 0, dh, 300, True, None))

    for name, x1, x2, y_offset, condition, text in dims_h:
        if condition:
            drawer.draw_dim(off((x1, y_offset)), off((x2, y_offset)), off((x1 + (x2 - x1) / 2, y_offset - 50)), 0, 'YQ_DIM', text)

    for name, y1, y2, x_offset, condition, text in dims_v:
        if condition:
            drawer.draw_dim(off((outer_right + x_offset, y1)), off((outer_right + x_offset, y2)), off((outer_right + x_offset + 50, y1 + (y2 - y1) / 2)), rad90, 'YQ_DIM', text)

    drawer.draw_text(f"{view_name}", off((dw / 2 - 60, outer_top + 300)), 80, 'A-DOOR-mark')

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
        elif door_type == "折叠四开门" and len(panel_positions) >= 4:
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
    panel_style = p.get('door_panel_style') or "无造型"
    panel_lock_offset_x = float(p.get('panel_lock_offset_x', 180) or 0)
    panel_hinge_offset_y = float(p.get('panel_hinge_offset_y', 100) or 0)
    panel_middle_offset_z = float(p.get('panel_middle_offset_z', 180) or 0)
    panel_plus_offset_a = float(p.get('panel_plus_offset_a', 350) or 0)
    panel_plus_offset_b = float(p.get('panel_plus_offset_b', 100) or 0)

    def panel_lock_edge(index: int, px1: float, px2: float) -> Optional[float]:
        if door_type == "单门":
            if (is_back and door_open_dir == "左开") or (not is_back and door_open_dir == "右开"):
                return px1
            return px2
        if door_type in ("对开门", "子母门"):
            return px2 if (px1 + px2) / 2 < dw / 2 else px1
        if door_type in ("折叠四开门", "两定两开"):
            return px2 if index <= 1 else px1
        return None

    def draw_panel_line(x1: float, y1: float, x2: float, y2: float):
        drawer.draw_line(off((x1, y1)), off((x2, y2)), 'A-DOOR-PANEL')

    def draw_panel_hatch(x1: float, x2: float, pattern_key: str):
        if not pattern_key or abs(x2 - x1) < 1:
            return
        left, right = sorted((x1, x2))
        drawer.draw_hatch([
            off((left, panel_y_bot)),
            off((right, panel_y_bot)),
            off((right, panel_y_top)),
            off((left, panel_y_top)),
        ], pattern_key)

    if panel_style != "无造型" and panel_positions and panel_lock_offset_x > 0:
        for idx, (px1, px2) in enumerate(panel_positions):
            lock_edge = panel_lock_edge(idx, px1, px2)
            if lock_edge is None:
                continue

            direction = 1 if abs(lock_edge - px1) < 0.01 else -1
            hinge_edge = px2 if direction == 1 else px1
            lock_line_x = lock_edge + direction * panel_lock_offset_x
            if not (px1 < lock_line_x < px2):
                continue
            draw_panel_line(lock_line_x, panel_y_bot, lock_line_x, panel_y_top)

            if panel_style == "两列式布局":
                lock_fill = p.get('panel_lock_fill_pattern', '')
                hinge_fill = p.get('panel_hinge_fill_pattern', '')
                draw_panel_hatch(lock_edge, lock_line_x, lock_fill)
                draw_panel_hatch(lock_line_x, hinge_edge, hinge_fill)

            if panel_style not in ("H型布局", "H+型布局"):
                continue

            hinge_line_x = hinge_edge - direction * panel_hinge_offset_y
            if not (px1 < hinge_line_x < px2):
                continue
            if abs(hinge_line_x - lock_line_x) < 1:
                continue
            draw_panel_line(hinge_line_x, panel_y_bot, hinge_line_x, panel_y_top)

            bx1, bx2 = sorted((lock_line_x, hinge_line_x))
            lower_line_y = panel_y_bot + panel_middle_offset_z
            upper_line_y = panel_y_top - panel_middle_offset_z
            y_lines = []
            if panel_y_bot < lower_line_y < panel_y_top:
                y_lines.append(lower_line_y)
            if panel_y_bot < upper_line_y < panel_y_top and abs(upper_line_y - lower_line_y) > 1:
                y_lines.append(upper_line_y)
            if panel_style == "H+型布局":
                plus_a_y = lower_line_y + panel_plus_offset_a
                plus_b_y = plus_a_y + panel_plus_offset_b
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
        elif door_type in ["折叠四开门", "两定两开"] and len(panel_positions) >= 4:
            if primary_only:
                idx = 2 if door_open_dir == "右开" else 1
                add(*panel_positions[idx], "left" if idx == 2 else "right")
            else:
                add(*panel_positions[1], "right")
                add(*panel_positions[2], "left")
        return targets

    # ===================== 标配拉手/背包拉手/长拉手绘制 =====================
    current_handle = p.get('fmls') if is_back else p.get('zmls')

    front_sized_handle = (not is_back) and bool(parse_handle_size(str(p.get("handle_size", ""))))

    if current_handle == "标配拉手" and not front_sized_handle:
        handle_y = panel_y_bot + 1000
        for hx, _toward_hinge, hblock in handle_targets(60):
            drawer.insert_custom_block(hblock, off((hx, handle_y)), layer="A-DOOR-PANEL")

    if current_handle == "A1022" and not front_sized_handle:
        handle_y = panel_y_bot + 1000
        for hx, _toward_hinge, hblock in handle_targets(60):
            a1022_block = "Z1022" if hblock == "YBPLS" else "Y1022"
            drawer.insert_custom_block(a1022_block, off((hx, handle_y)), layer="A-DOOR-PANEL")

    if current_handle == "背包拉手" and not front_sized_handle:
        for hx, toward_hinge, _hblock in handle_targets(60, primary_only=True):
            drawer.insert_custom_block("BBLS", off((hx, 1050)), layer="A-DOOR-PANEL", xscale=toward_hinge)

    handle_size = parse_handle_size(str(p.get("handle_size", "")))
    if handle_size and not is_back:
        handle_w, handle_h = handle_size
        for hx, _toward_hinge, _hblock in handle_targets(110, primary_only=True):
            y_center = 1200
            drawer.draw_poly([
                off((hx - handle_w / 2, y_center - handle_h / 2)),
                off((hx + handle_w / 2, y_center - handle_h / 2)),
                off((hx + handle_w / 2, y_center + handle_h / 2)),
                off((hx - handle_w / 2, y_center + handle_h / 2)),
            ], "A-DOOR-PANEL")

    if not is_back and p.get("fingerprint_lock") == "安志杰AF-12":
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
            "A-DOOR-FRAME": 4,
            "A-DOOR-PANEL": 2,
            "A-DOOR-PANEL-FILL": 8,
            "A-DOOR-TRIM": 1,
            "YQ_DIM": 3,
            "A-DOOR-mark": 7
        })

        draw_p.update({
            "door_type": info.get("DOOR_TYPE", "单门"),
            "mother_door_width": info.get("MOTHER_DOOR_WIDTH", 600),
            "mid_door_width": info.get("MID_DOOR_WIDTH", 400),
            "pillar_width_str": info.get("PILLAR_WIDTH_STR", "55/70"),
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
