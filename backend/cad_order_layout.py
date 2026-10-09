"""Reflow order-sheet metadata around unmodified, full-size CAD drawings."""

import math
import unicodedata

from ezdxf import bbox
from ezdxf.math import Matrix44, Vec3


ORDER_LAYOUT_VERSION = 'content-aware-order-sheet-v1'
ORDER_NAMES = {'ORDER_FORM', 'ORDERFORM'}


def _text_width(text, height):
    # CAD text height describes cap height, not the full CJK glyph advance.
    return sum(1.7 if unicodedata.east_asian_width(char) in 'WF' else 1.0
               for char in text) * height


def _wrap(text, width, height):
    lines = []
    for paragraph in text.replace('\\P', '\n').split('\n'):
        line = ''
        used = 0.0
        for char in paragraph:
            advance = _text_width(char, height)
            if line and used + advance > width:
                lines.append(line)
                line, used = '', 0.0
            line += char
            used += advance
        lines.append(line)
    return lines


def _rectangle(entity):
    if entity.dxftype() != 'LWPOLYLINE' or not entity.closed or len(entity) != 4:
        return None
    points = list(entity.get_points())
    if any(abs(point[4]) > 1e-8 for point in points):
        return None
    xs = sorted({round(float(point[0]), 4) for point in points})
    ys = sorted({round(float(point[1]), 4) for point in points})
    if len(xs) != 2 or len(ys) != 2:
        return None
    return xs[0], ys[0], xs[1], ys[1]


def _template_grid(block):
    rectangles = [bounds for entity in block if (bounds := _rectangle(entity))]
    if not rectangles:
        raise ValueError('Order sheet has no rectangular outer frame')
    outer = max(rectangles, key=lambda rect: (rect[2] - rect[0]) * (rect[3] - rect[1]))
    x0, y0, x1, y1 = outer
    if abs(x0) > 0.01 or abs(y0) > 0.01:
        raise ValueError('Unsupported order-sheet origin')
    lines = list(block.query('LINE'))
    full_verticals = sorted({float(line.dxf.start.x) for line in lines
                             if abs(line.dxf.start.x - line.dxf.end.x) < 0.01
                             and abs(abs(line.dxf.start.y - line.dxf.end.y) - y1) < 0.1
                             and 0 < line.dxf.start.x < x1})
    if len(full_verticals) != 2:
        raise ValueError('Unsupported order-sheet table partitions')
    left, column = full_verticals
    horizontals = sorted({float(line.dxf.start.y) for line in lines
                          if abs(line.dxf.start.y - line.dxf.end.y) < 0.01
                          and abs(max(line.dxf.start.x, line.dxf.end.x) - left) < 0.1
                          and min(line.dxf.start.x, line.dxf.end.x) < left * 0.5})
    footer = next((y for y in horizontals if 0 < y < y1 * 0.1), None)
    header = next((y for y in horizontals if y > y1 * 0.7), None)
    if footer is None or header is None:
        raise ValueError('Unsupported order-sheet header/footer')
    logo_edges = [float(line.dxf.start.x) for line in lines
                  if abs(line.dxf.start.x - line.dxf.end.x) < 0.01
                  and abs(min(line.dxf.start.y, line.dxf.end.y) - header) < 0.1
                  and max(line.dxf.start.y, line.dxf.end.y) > y1 - 1
                  and 0 < line.dxf.start.x < left * 0.5]
    if not logo_edges:
        raise ValueError('Unsupported order-sheet logo partition')
    return x1, y1, left, column, header, footer, min(logo_edges), lines


def adapt_order_sheet(doc, drawing_entities, notes):
    """Return a fallback warning, or None; never mutate drawing_entities."""
    if not drawing_entities:
        return None
    try:
        inserts = [entity for entity in doc.modelspace().query('INSERT')
                   if entity.dxf.name.upper().replace(' ', '') in ORDER_NAMES]
        if len(inserts) != 1:
            raise ValueError('A single ORDER_FORM insert is required for adaptive layout')
        insert = inserts[0]
        if (abs(insert.dxf.rotation) > 1e-8
                or any(abs(insert.dxf.get(key, 1) - 1) > 1e-8 for key in ('xscale', 'yscale', 'zscale'))):
            raise ValueError('Unsupported transformed order-sheet template')
        block = doc.blocks[insert.dxf.name]
        if not block.block.dxf.base_point.isclose(Vec3()):
            raise ValueError('Unsupported order-sheet base point')
        original = list(block)
        width, height, left, column, header, footer, logo, grid_lines = _template_grid(block)
        extent = bbox.extents(drawing_entities, fast=True)
        if not extent.has_data or not all(math.isfinite(value) for value in (*extent.extmin, *extent.extmax)):
            raise ValueError('Drawing bounds could not be resolved')
        draw_width, draw_height = extent.size.x, extent.size.y
        if draw_width <= 0 or draw_height <= 0:
            raise ValueError('Drawing bounds have no usable area')

        # The readability floor applies to metadata only, not door annotations.
        scale = max(0.35, min(1.5, draw_height / 6500))
        padding = max(90, min(260, draw_height * 0.035))
        left_width = max(draw_width + padding * 2, left * scale * 0.72)
        note_height = max(64, min(180, 152 * scale))
        note_width = left_width - padding * 2
        note_lines = [_wrap(note.plain_text(), note_width, note_height) for note in notes]
        note_space = sum(max(1, len(lines)) * note_height * 1.7 + padding * 0.5
                         for lines in note_lines if any(lines))
        legal = next((entity for entity in block.query('MTEXT')
                      if entity.dxf.insert.x < left and footer < entity.dxf.insert.y < height * 0.15), None)
        if legal is None:
            raise ValueError('Order-sheet legal remarks could not be located')
        legal_height = legal.dxf.char_height * scale
        legal_lines = _wrap(legal.plain_text(), left_width - padding, legal_height)
        footer_row = footer * scale
        footer_space = footer_row + len(legal_lines) * legal_height * 1.7 + padding
        header_space = (height - header) * scale
        body_space = draw_height + padding * 2 + note_space
        new_height = footer_space + body_space + header_space
        x_ratio = left_width / left
        body_ratio = (footer_space + body_space - footer_row) / (header - footer)

        def map_x(x):
            return x * x_ratio if x < left else left_width + (x - left) * scale

        def map_y(y):
            if y <= footer:
                return y * scale
            if y >= header:
                return new_height - (height - y) * scale
            return footer_row + (y - footer) * body_ratio

        def mapped(point):
            return Vec3(map_x(point.x), map_y(point.y), point.z)

        origin = Vec3(extent.extmin.x - padding,
                      extent.extmin.y - padding - footer_space, insert.dxf.insert.z)
        old_origin = insert.dxf.insert
        logo_scale = min(scale, x_ratio)
        logo_transform = Matrix44.chain(
            Matrix44.scale(logo_scale),
            Matrix44.translate((map_x(logo) - logo * logo_scale) / 2,
                               new_height - header_space - header * logo_scale, 0),
        )

        def fit_text(entity, old_point, tagged=False):
            kind = entity.dxftype()
            if kind == 'MTEXT':
                entity.dxf.char_height *= scale
                entity.dxf.width = max(entity.dxf.char_height * 2, min(
                    map_x(old_point.x + entity.dxf.width) - map_x(old_point.x),
                    map_x(width if old_point.x >= left else left) - map_x(old_point.x) - 20 * scale))
            else:
                entity.dxf.height *= scale
            if tagged or kind == 'MTEXT':
                # Attribute values must stay in their actual grid cell, not spill
                # across the table border when customers/styles have long names.
                boundaries = [width if old_point.x >= left else left]
                for line in grid_lines:
                    start, end = line.dxf.start, line.dxf.end
                    if (abs(start.x - end.x) < 0.01 and start.x > old_point.x
                            and min(start.y, end.y) <= old_point.y <= max(start.y, end.y)):
                        boundaries.append(float(start.x))
                available = max(20 * scale, map_x(min(boundaries)) - map_x(old_point.x) - 40 * scale)
                if kind == 'MTEXT':
                    entity.dxf.width = min(entity.dxf.width, available)
                    estimated = max((_text_width(line, entity.dxf.char_height)
                                     for line in entity.plain_text().splitlines()), default=0)
                    if estimated > available:
                        entity.dxf.char_height *= available / estimated
                else:
                    estimated = _text_width(entity.dxf.text, entity.dxf.height) * entity.dxf.get('width', 1)
                    if estimated > available:
                        entity.dxf.height *= available / estimated

        replacements = []
        for entity in original:
            replacement = entity.copy()
            kind = entity.dxftype()
            if entity is legal:
                replacement.text = '\\P'.join(legal_lines)
                replacement.dxf.insert = (padding / 2, footer_space - padding / 2, 0)
                replacement.dxf.char_height = legal_height
                replacement.dxf.width = left_width - padding
            elif kind in ('SPLINE', 'CIRCLE'):
                shape_bounds = bbox.extents([entity], fast=True)
                if not shape_bounds.has_data or shape_bounds.extmax.x > logo or shape_bounds.extmin.y < header:
                    raise ValueError('Unsupported graphic outside order-sheet logo')
                replacement.transform(logo_transform)
            elif kind == 'LINE':
                replacement.dxf.start = mapped(entity.dxf.start)
                replacement.dxf.end = mapped(entity.dxf.end)
            elif kind == 'LWPOLYLINE':
                points = list(entity.get_points())
                if _rectangle(entity) == (0.0, 0.0, round(width, 4), round(height, 4)):
                    replacement.set_points([(map_x(float(x)), map_y(float(y)), sw * scale, ew * scale, bulge)
                                            for x, y, sw, ew, bulge in points])
                else:
                    # Checkbox and threshold symbols keep their aspect ratio.
                    center = bbox.extents([entity], fast=True).center
                    replacement.transform(Matrix44.chain(Matrix44.scale(scale), Matrix44.translate(
                        map_x(center.x) - center.x * scale, map_y(center.y) - center.y * scale, 0)))
            elif kind in ('MTEXT', 'TEXT', 'ATTDEF'):
                point = entity.dxf.insert
                if kind == 'MTEXT' and point.x < logo and point.y >= header:
                    replacement.transform(logo_transform)
                else:
                    replacement.dxf.insert = mapped(point)
                    if kind in ('TEXT', 'ATTDEF') and entity.dxf.hasattr('align_point'):
                        replacement.dxf.align_point = mapped(entity.dxf.align_point)
                    fit_text(replacement, point, kind != 'MTEXT')
                    if kind == 'MTEXT' and entity.plain_text().strip() in (
                            '\u9ad8\u4f4e', '\u5e73\u5e95', '\u540a\u811a'):
                        # These labels straddle the original value-column line;
                        # treat them as value-cell labels rather than tiny cells.
                        available = 430 * scale
                        replacement.dxf.insert = (map_x(column) + 15 * scale, map_y(point.y), point.z)
                        replacement.dxf.width = available
                        replacement.dxf.char_height = min(entity.dxf.char_height * scale,
                            available / max(_text_width(entity.plain_text(), 1), 1))
            else:
                raise ValueError(f'Unsupported order-sheet entity: {kind}')
            replacements.append(replacement)

        attributes = []
        for attribute in insert.attribs:
            replacement = attribute.copy()
            point = attribute.dxf.insert - old_origin
            replacement.dxf.insert = mapped(point) + origin
            if attribute.dxf.hasattr('align_point'):
                replacement.dxf.align_point = mapped(attribute.dxf.align_point - old_origin) + origin
            fit_text(replacement, point, True)
            attributes.append(replacement)

        note_replacements = []
        note_top = footer_space + padding + draw_height + padding + note_space
        for note, lines in zip(notes, note_lines):
            replacement = note.copy()
            replacement.text = '\\P'.join(lines)
            replacement.dxf.insert = origin + Vec3(padding, note_top, 0)
            replacement.dxf.char_height = note_height
            replacement.dxf.width = note_width
            replacement.dxf.attachment_point = 1
            note_top -= max(1, len(lines)) * note_height * 1.7 + padding * 0.5
            note_replacements.append(replacement)

        # Commit only after the whole template can be laid out successfully.
        for entity in original:
            block.delete_entity(entity)
        for entity in replacements:
            block.add_entity(entity)
        for attribute, replacement in zip(insert.attribs, attributes):
            attribute.dxf.update({key: value for key, value in replacement.dxf.all_existing_dxf_attribs().items()
                                  if key not in ('handle', 'owner')})
        insert.dxf.insert = origin
        for note, replacement in zip(notes, note_replacements):
            note.text = replacement.text
            note.dxf.update({key: value for key, value in replacement.dxf.all_existing_dxf_attribs().items()
                             if key not in ('handle', 'owner')})
        return None
    except Exception as error:
        return f'Adaptive layout skipped: {error}'
