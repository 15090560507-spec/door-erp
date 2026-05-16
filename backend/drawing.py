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

    def insert_custom_block(self, block_name, insert_point, layer="A-DOOR-PANEL"):
        if block_name not in self.doc.blocks:
            block = self.doc.blocks.new(name=block_name)
            block.add_lwpolyline([(-15, -150), (15, -150), (15, 150), (-15, 150)], close=True)
        self.ms.add_blockref(block_name, insert_point, dxfattribs={'layer': layer})


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
    overlap = p['overlap'] if trim_w > 0 else 0
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
        trim_style = p.get('trim_style', '')
        if trim_style:
            # 包套上边高度 = dh - O + W + mm_offset
            outer_top_y = dh - O + W + mm_offset
            inner_top_y = dh - O + mm_offset

            # 三边偏移线（左、上、右，下方对齐 y=0）
            def draw_outer_offset(D):
                left_x = O - W + D
                right_x = dw - O + W - D
                top_y = outer_top_y - D
                drawer.draw_line(off((left_x, 0)), off((left_x, top_y)), 'A-DOOR-TRIM')
                drawer.draw_line(off((left_x, top_y)), off((right_x, top_y)), 'A-DOOR-TRIM')
                drawer.draw_line(off((right_x, 0)), off((right_x, top_y)), 'A-DOOR-TRIM')

            def draw_inner_offset(D):
                left_x = O - D
                right_x = dw - O + D
                top_y = inner_top_y + D
                drawer.draw_line(off((left_x, 0)), off((left_x, top_y)), 'A-DOOR-TRIM')
                drawer.draw_line(off((left_x, top_y)), off((right_x, top_y)), 'A-DOOR-TRIM')
                drawer.draw_line(off((right_x, 0)), off((right_x, top_y)), 'A-DOOR-TRIM')

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

            # CAD块标注（块名称放在标志线上方）
            block_name_map = {
                '斜包套': 'XBT', '阶梯包套': 'JTBT',
                '工字形包套': 'GZXBT', '01款包套': '01BT', '02款包套': '02BT',
            }
            block_name = block_name_map.get(trim_style, 'XBT')
            block_x = O - W - 150
            block_y = dh / 2 + 80
            leader_end_x = O - W + 20
            drawer.insert_custom_block(block_name, off((block_x, block_y)), layer='A-DOOR-TRIM')
            drawer.draw_line(off((block_x, block_y - 40)), off((leader_end_x, block_y - 40)), 'A-DOOR-TRIM')
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
            drawer.draw_dim(off((mother_panel_x1, panel_y_bot - 100)), off((mother_panel_x2, panel_y_bot - 100)), off((mother_panel_x1 - 100, panel_y_bot - 150)), 0, 'YQ_DIM', f"母门宽 {mother_width}")

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
            drawer.draw_dim(off((lmx1, panel_y_bot - 150)), off((rmx2, panel_y_bot - 150)), off((lmx1 + mid_total_width / 2, panel_y_bot - 200)), 0, 'YQ_DIM', f"中门宽度 {mid_total_width}mm")

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

    if use_light_size and light_w > 0 and ((nk_choice == "内开" and not is_back) or (nk_choice == "外开" and is_back)):
        dims_h.append(("见光宽", ref_left + left_gap, dw - ref_right - right_gap, -200, True, f"见光宽 {light_w}"))

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

    if use_light_size and light_h > 0 and ((nk_choice == "内开" and not is_back) or (nk_choice == "外开" and is_back)):
        dims_v.append(("见光高", panel_y_bot, panel_y_top, 100, True, f"见光高 {light_h}"))

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

    # ===================== 锁边偏移线绘制 =====================
    lock_side_offset = p.get('lock_side_offset', 150)

    if lock_side_offset > 0 and panel_positions:
        for idx, (px1, px2) in enumerate(panel_positions):
            lock_x = None

            if door_type == "单门":
                if (is_back and door_open_dir == "左开") or (not is_back and door_open_dir == "右开"):
                    lock_x = px1 + lock_side_offset
                else:
                    lock_x = px2 - lock_side_offset
            elif door_type == "对开门":
                if idx == 0:
                    lock_x = px2 - lock_side_offset
                else:
                    lock_x = px1 + lock_side_offset
            elif door_type == "子母门":
                if idx == 0:
                    lock_x = px2 - lock_side_offset
                else:
                    lock_x = px1 + lock_side_offset
            elif door_type in ("折叠四开门", "两定两开"):
                if idx <= 1:
                    lock_x = px2 - lock_side_offset
                else:
                    lock_x = px1 + lock_side_offset

            if lock_x is not None:
                drawer.draw_line(
                    off((lock_x, panel_y_bot)),
                    off((lock_x, panel_y_top)),
                    'A-DOOR-PANEL'
                )

    # ===================== 标配拉手绘制 =====================
    current_handle = p.get('fmls') if is_back else p.get('zmls')

    if current_handle == "标配拉手":
        handles_to_draw = []
        handle_y = panel_y_bot + 1000

        if door_type == "单门":
            if is_back:
                if door_open_dir == "左开":
                    eff_dir = "右开"
                else:
                    eff_dir = "左开"
            else:
                eff_dir = door_open_dir

            if eff_dir == "左开":
                handles_to_draw.append((panel_positions[0][1] - 60, "ZBPLS"))
            else:
                handles_to_draw.append((panel_positions[0][0] + 60, "YBPLS"))

        elif door_type == "对开门" and len(panel_positions) >= 2:
            handles_to_draw.extend([(panel_positions[0][1] - 60, "ZBPLS"), (panel_positions[1][0] + 60, "YBPLS")])
        elif door_type == "子母门" and len(panel_positions) >= 2:
            # 子门不画拉手，母门仅在中间缝侧设拉手（距边缘60mm）
            is_mother_right = (is_back and door_open_dir == "左开") or (not is_back and door_open_dir == "右开")
            if is_mother_right:
                # 母门在右，拉手在母门左边缘（靠中缝）
                handles_to_draw.append((panel_positions[1][0] + 60, "YBPLS"))
            else:
                # 母门在左，拉手在母门右边缘（靠中缝）
                handles_to_draw.append((panel_positions[0][1] - 60, "ZBPLS"))

        elif door_type in ["折叠四开门", "两定两开"] and len(panel_positions) >= 4:
            handles_to_draw.extend([(panel_positions[1][1] - 60, "ZBPLS"), (panel_positions[2][0] + 60, "YBPLS")])

        for hx, hblock in handles_to_draw:
            drawer.insert_custom_block(hblock, off((hx, handle_y)), layer="A-DOOR-PANEL")

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
