"""Actual template geometry and independent controls for lock-edge disc panels."""

from dataclasses import dataclass
import math

import ezdxf
from ezdxf import bbox
from ezdxf.math import Vec2
from ezdxf.math.clipping import ConcaveClippingPolygon2d
from ezdxf.render.hatching import hatch_entity


DISC_STYLES = ('圆形', '圆形牡丹花', '四叶草牡丹花')


def disc_center_height(value, handle, handle_size, panel_bottom):
    if value is not None:
        height = float(value)
        if not math.isfinite(height) or height <= 0:
            raise ValueError('圆心高度必须是大于0的有限数值')
        return height
    if handle in ('铝雕圆形拉手', '铝雕滑盖圆环拉手', '铝雕圆形滑盖拉手'):
        return 1200.0
    ordinary = ('标配拉手', 'A1022', 'A635', '分体拉手', '背包拉手')
    if handle in ordinary:
        return float(panel_bottom) + 1000
    if handle_size and handle not in ('', '无', '凹槽拉手', '凹槽拉手+灯带'):
        return 1200.0
    return 1050.0


def disc_fill(style, value):
    return ('竖条' if style != '圆形' else '') if value is None else value


def _points(entity):
    path = ezdxf.path.make_path(entity)
    return [(float(p.x), float(p.y)) for p in path.flattening(distance=.2, segments=16)]


def _area(points):
    return abs(sum(x * points[(i + 1) % len(points)][1] - y * points[(i + 1) % len(points)][0]
                   for i, (x, y) in enumerate(points))) / 2


@dataclass
class DiscGeometry:
    block_name: str | None
    scale: float
    center: tuple[float, float]
    boundary: list[tuple[float, float]]


def disc_geometry(doc, style, radius, center_y, lock_x, direction, bounds):
    if style not in DISC_STYLES:
        raise ValueError('不支持的圆盘款式')
    if not all(math.isfinite(v) for v in (radius, center_y, lock_x)) or radius <= 0:
        raise ValueError('圆盘半径和圆心必须有效，半径必须大于0')
    scale = radius / 1000
    name = None
    if style == '圆形':
        local = [(direction * radius * math.cos(-math.pi / 2 + math.pi * i / 128),
                  radius * math.sin(-math.pi / 2 + math.pi * i / 128)) for i in range(129)]
        extent = (min(0, direction * radius), -radius, max(0, direction * radius), radius)
    else:
        name = ('YXMDH' if style == '圆形牡丹花' else 'SBMDH') + ('Y' if direction > 0 else 'Z')
        if name not in doc.blocks:
            raise ValueError(f'模板缺少圆盘花件块：{name}')
        block = doc.blocks[name]
        if not block.base_point.isclose((0, 0, 0)):
            raise ValueError(f'圆盘花件{name}基点不是原点，请检查模板')
        if style == '圆形牡丹花':
            arcs = list(block.query('ARC'))
            if not arcs:
                raise ValueError(f'无法识别{name}外围圆弧')
            local = _points(max(arcs, key=lambda e: e.dxf.radius))
        else:
            candidates = [_points(e) for e in block.query('LWPOLYLINE') if ezdxf.path.make_path(e).is_closed]
            if not candidates:
                raise ValueError(f'无法识别{name}闭合外轮廓')
            local = max(candidates, key=_area)
        local = [(x * scale, y * scale) for x, y in local]
        box = bbox.extents(block, fast=False)
        extent = (box.extmin.x * scale, box.extmin.y * scale, box.extmax.x * scale, box.extmax.y * scale)
    left, bottom, right, top = bounds
    x0, y0, x1, y1 = extent
    if (lock_x + x0 < left - 1e-5 or lock_x + x1 > right + 1e-5
            or center_y + y0 < bottom - 1e-5 or center_y + y1 > top + 1e-5):
        raise ValueError(f'{style}超出门板可用范围，请调整半径或圆心高度（半径{radius:g}mm，圆心{center_y:g}mm）')
    return DiscGeometry(name, scale, (lock_x, center_y), [(lock_x + x, center_y + y) for x, y in local])


def draw_disc_fill(drawer, bounds, boundary, sample):
    if not sample:
        raise ValueError('找不到圆盘外部填充样式')
    hatch = drawer.draw_hatch_rect(*bounds, sample)
    if hatch is None:
        return
    hatch.dxf.hatch_style = 0
    if hatch.dxf.solid_fill:
        hatch.paths.add_polyline_path(boundary, is_closed=True, flags=0)
        return
    clipper = ConcaveClippingPolygon2d([Vec2(p) for p in boundary])
    # Materialize the existing hatch engine's clipped lines for CAD, SVG and AI line art alike.
    try:
        for index, (start, end) in enumerate(hatch_entity(hatch, jiggle_origin=False)):
            if index >= 100000:
                raise ValueError('圆盘外部填充过密，请调整填充样式')
            if not start.isclose(end):
                start, end = Vec2(start), Vec2(end)
                delta = end - start
                denominator = delta.dot(delta)
                intervals = sorted(tuple(sorted(((a - start).dot(delta) / denominator,
                                                  (b - start).dot(delta) / denominator)))
                                   for a, b in clipper.clip_line(start, end))
                cursor = 0.0
                for low, high in intervals + [(1.0, 1.0)]:
                    low, high = max(0.0, low), min(1.0, high)
                    if low > cursor + 1e-8:
                        drawer.draw_line(start + delta * cursor, start + delta * low, 'A-DOOR-HATCH')
                    cursor = max(cursor, high)
    finally:
        drawer.ms.delete_entity(hatch)
