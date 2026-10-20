"""Keep order-sheet titles centered and leave nondefault brand cells blank."""

from ezdxf import bbox
from ezdxf.enums import TextEntityAlignment
from ezdxf.math import Vec3

from cad_order_layout import ORDER_NAMES, _template_grid, _text_width


DEFAULT_ORDER_TITLE = '浙江西州将军铜门订货单'


def normalize_order_title(value):
    return str(value or '').strip() or DEFAULT_ORDER_TITLE


def _regions(block):
    _, top, left, _, header, _, logo, lines = _template_grid(block)
    dividers = [line.dxf.start.y for line in lines
                if abs(line.dxf.start.y - line.dxf.end.y) < 0.01
                and header < line.dxf.start.y < top
                and min(line.dxf.start.x, line.dxf.end.x) <= logo + 0.1
                and max(line.dxf.start.x, line.dxf.end.x) >= left - 0.1]
    if not dividers:
        raise ValueError('无法识别订货单标题格，未修改品牌区')
    return (0, header, logo, top), (logo, max(dividers), left, top)


def _brand_content(block, region):
    x0, y0, x1, y1 = region
    graphics = {'SPLINE', 'CIRCLE', 'ARC', 'ELLIPSE', 'LINE', 'LWPOLYLINE',
                'POLYLINE', 'HATCH', 'SOLID', 'INSERT'}
    for entity in block:
        if entity.dxftype() in ('MTEXT', 'TEXT'):
            point = entity.dxf.insert
            if x0 < point.x < x1 and y0 < point.y < y1:
                yield entity
        elif entity.dxftype() in graphics:
            extent = bbox.extents([entity], fast=True)
            # Strict interior containment protects the original cell/grid edges.
            if (extent.has_data and x0 < extent.extmin.x and extent.extmax.x < x1
                    and y0 < extent.extmin.y and extent.extmax.y < y1):
                yield entity


def _centered_title(entity, title, center, width, height):
    replacement = entity.copy()
    replacement.dxf.text = title
    width_factor = abs(replacement.dxf.get('width', 1)) or 1
    replacement.dxf.height = min(replacement.dxf.height, height * 0.85 / 1.7,
                                 width * 0.92 / (_text_width(title, 1) * width_factor))
    replacement.set_placement(center, align=TextEntityAlignment.MIDDLE_CENTER)
    return replacement


def apply_order_sheet_branding(doc, title):
    title = normalize_order_title(title)
    jobs = []
    for insert in doc.modelspace().query('INSERT'):
        if insert.dxf.name.upper().replace(' ', '') not in ORDER_NAMES:
            continue
        if not insert.has_uniform_scaling or abs(insert.dxf.rotation) > 1e-8:
            raise ValueError('订货单品牌排版不支持非等比或旋转图框')
        block = doc.blocks[insert.dxf.name]
        brand, cell = _regions(block)
        x0, y0, x1, y1 = cell
        center = Vec3((x0 + x1) / 2, (y0 + y1) / 2, 0)
        replacements = []
        for definition in block.query('ATTDEF'):
            if definition.dxf.tag.upper() == 'TT':
                replacements.append((definition, _centered_title(definition, title, center, x1 - x0, y1 - y0)))
        scale = abs(insert.dxf.xscale)
        for attribute in insert.attribs:
            if attribute.dxf.tag.upper() == 'TT':
                replacements.append((attribute, _centered_title(attribute, title,
                    insert.matrix44().transform(center), (x1 - x0) * scale, (y1 - y0) * scale)))
        if not replacements:
            raise ValueError('订货单缺少 TT 标题属性，未修改品牌区')
        removals = list(_brand_content(block, brand)) if title != DEFAULT_ORDER_TITLE else []
        jobs.append((block, removals, replacements))

    for block, removals, replacements in jobs:
        for entity in removals:
            if entity.is_alive:
                block.delete_entity(entity)
        for original, replacement in replacements:
            original.dxf.update({key: value for key, value in replacement.dxf.all_existing_dxf_attribs().items()
                                 if key not in ('handle', 'owner')})
