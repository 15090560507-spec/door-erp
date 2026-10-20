"""Reflow order-sheet metadata around unmodified, full-size CAD drawings."""

import math
import unicodedata

from ezdxf import bbox
from ezdxf.math import Matrix44, Vec3


ORDER_LAYOUT_VERSION = 'centered-branding-order-sheet-v4'
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


def _note_layout(texts, width, height):
    paragraphs = [_wrap(text, width, height) for text in texts]
    populated = [lines for lines in paragraphs if any(lines)]
    used = sum(len(lines) * height * 1.7 for lines in populated)
    used += max(0, len(populated) - 1) * height * 0.5
    widest = max((_text_width(line, height) for lines in paragraphs for line in lines), default=0)
    return paragraphs, used, widest


def _proportional_notes(texts, heights, width):
    """Wrap in template coordinates so sheet scaling cannot change font ratios."""
    paragraphs = []
    used = 0.0
    previous_height = None
    for text, height in zip(texts, heights):
        if not math.isfinite(height) or height <= 0:
            raise ValueError('Invalid manufacturing note height')
        lines, needed, widest = _note_layout([text], width, height)
        if widest > width:
            raise ValueError('Manufacturing note glyph exceeds the note region')
        paragraphs.append(lines[0])
        if text:
            if previous_height is not None:
                used += previous_height * 0.5
            used += needed
            previous_height = height
    return paragraphs, used


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

        legal = next((entity for entity in block.query('MTEXT')
                      if entity.dxf.insert.x < left and footer < entity.dxf.insert.y < height * 0.15), None)
        if legal is None:
            raise ValueError('Order-sheet legal remarks could not be located')
        padding_base = 180.0
        legal_lines = _wrap(legal.plain_text(), left - padding_base, legal.dxf.char_height)
        legal_top = footer + len(legal_lines) * legal.dxf.char_height * 1.7 + 60
        body_bottom = legal_top + padding_base
        texts = [note.plain_text() for note in notes]
        note_heights = [float(note.dxf.char_height) for note in notes]
        usable_width = left - padding_base * 2
        note_lines, note_used_base = _proportional_notes(texts, note_heights, usable_width)
        usable_height = header - body_bottom - padding_base * 2 - note_used_base
        if usable_width <= 0 or usable_height <= 0:
            raise ValueError('Manufacturing notes cannot fit at proportional height')

        # One scale for the entire grid: never independently resize its axes.
        scale = max(0.35, draw_width / usable_width, draw_height / usable_height)
        note_width = usable_width * scale
        note_space = (header - body_bottom - padding_base * 2) * scale - draw_height
        note_used = note_used_base * scale
        padding = padding_base * scale
        left_width = left * scale
        origin = Vec3(extent.center.x - left_width / 2,
                      extent.extmin.y - body_bottom * scale, insert.dxf.insert.z)
        old_origin = insert.dxf.insert
        transform = Matrix44.scale(scale)

        def fit_text(entity, old_point, tagged=False):
            kind = entity.dxftype()
            if kind in ('ATTDEF', 'ATTRIB') and entity.dxf.tag.upper() == 'TT':
                return  # The full title cell is fitted and centered after reflow.
            if kind == 'MTEXT':
                entity.dxf.width = min(entity.dxf.width,
                    ((width if old_point.x >= left else left) - old_point.x - 20) * scale)
            if tagged or kind == 'MTEXT':
                # Attribute values must stay in their actual grid cell, not spill
                # across the table border when customers/styles have long names.
                boundaries = [width if old_point.x >= left else left]
                for line in grid_lines:
                    start, end = line.dxf.start, line.dxf.end
                    if (abs(start.x - end.x) < 0.01 and start.x > old_point.x
                            and min(start.y, end.y) <= old_point.y <= max(start.y, end.y)):
                        boundaries.append(float(start.x))
                available = max(20 * scale, (min(boundaries) - old_point.x - 40) * scale)
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
                replacement.transform(transform)
                replacement.text = '\\P'.join(legal_lines)
                replacement.dxf.insert = (padding / 2, legal_top * scale, 0)
                replacement.dxf.width = left_width - padding
            elif kind in ('SPLINE', 'CIRCLE'):
                shape_bounds = bbox.extents([entity], fast=True)
                if not shape_bounds.has_data or shape_bounds.extmax.x > logo or shape_bounds.extmin.y < header:
                    raise ValueError('Unsupported graphic outside order-sheet logo')
                replacement.transform(transform)
            elif kind in ('LINE', 'LWPOLYLINE'):
                replacement.transform(transform)
            elif kind in ('MTEXT', 'TEXT', 'ATTDEF'):
                point = entity.dxf.insert
                replacement.transform(transform)
                if not (kind == 'MTEXT' and point.x < logo and point.y >= header):
                    fit_text(replacement, point, kind != 'MTEXT')
                    if kind == 'MTEXT' and entity.plain_text().strip() in (
                            '\u9ad8\u4f4e', '\u5e73\u5e95', '\u540a\u811a'):
                        # These labels straddle the original value-column line;
                        # treat them as value-cell labels rather than tiny cells.
                        available = 430 * scale
                        replacement.dxf.insert = ((column + 15) * scale, point.y * scale, point.z)
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
            replacement.transform(Matrix44.chain(Matrix44.translate(*(-old_origin)),
                                                  transform, Matrix44.translate(*origin)))
            fit_text(replacement, point, True)
            attributes.append(replacement)

        note_replacements = []
        note_top = origin.y + header * scale - padding - (note_space - note_used) / 2
        for note, lines, original_height in zip(notes, note_lines, note_heights):
            note_height = original_height * scale
            replacement = note.copy()
            replacement.text = '\\P'.join(lines)
            replacement.dxf.insert = (origin.x + padding, note_top, origin.z)
            replacement.dxf.char_height = note_height
            replacement.dxf.width = note_width
            replacement.dxf.attachment_point = 1
            if any(lines):
                note_top -= len(lines) * note_height * 1.7 + note_height * 0.5
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
