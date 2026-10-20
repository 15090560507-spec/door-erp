"""Make only the order-sheet blocks editable in a private DXF download copy."""

import io

import ezdxf
from ezdxf.explode import attrib_to_text

from cad_order_layout import ORDER_NAMES


CAD_DOWNLOAD_VERSION = 'editable-order-sheet-v1'


def _inherit_display(entity, parent):
    if entity.dxf.layer == '0':
        entity.dxf.layer = parent.dxf.layer
    if entity.dxf.get('color', 256) == 0:
        entity.dxf.color = parent.dxf.get('color', 256)
        if not entity.dxf.hasattr('true_color') and parent.dxf.hasattr('true_color'):
            entity.dxf.true_color = parent.dxf.true_color
    for name, byblock, default in (('linetype', 'BYBLOCK', 'BYLAYER'), ('lineweight', -2, -1)):
        if entity.dxf.get(name, default) == byblock:
            entity.dxf.set(name, parent.dxf.get(name, default))
    if entity.is_transparency_by_block:
        if parent.dxf.hasattr('transparency'):
            entity.dxf.transparency = parent.dxf.transparency
        else:
            entity.dxf.discard('transparency')
    if parent.dxf.get('invisible', 0):
        entity.dxf.invisible = 1
    return entity


def _sheet_entities(insert, ancestors=()):
    name = insert.dxf.name
    if name.upper() in ancestors:
        raise ValueError(f'图框嵌套存在循环引用: {name}')
    if not insert.has_uniform_scaling:
        raise ValueError(f'图框含不支持的非等比块缩放: {name}')
    if insert.is_xref():
        raise ValueError(f'图框含不支持的外部参照: {name}')
    if insert.has_extension_dict and 'ACAD_FILTER' in insert.get_extension_dict():
        raise ValueError(f'图框含不支持的裁剪块: {name}')

    def fail(entity, reason):
        kind = entity.dxftype() if entity is not None else 'entity'
        raise ValueError(f'图框无法完整拆开 ({kind}): {reason}')

    if insert.mcount > 1:
        for single in insert.multi_insert():
            yield from _sheet_entities(single, ancestors)
        return
    for entity in insert.virtual_entities(skipped_entity_callback=fail, redraw_order=True):
        _inherit_display(entity, insert)
        if entity.dxftype() == 'INSERT':
            yield from _sheet_entities(entity, (*ancestors, name.upper()))
        else:
            yield entity
    for attribute in insert.attribs:
        if attribute.is_invisible:
            continue
        text = (attribute.virtual_mtext_entity() if attribute.has_embedded_mtext_entity
                else attrib_to_text(attribute.copy()))
        yield _inherit_display(text, insert)


def editable_sheet_dxf(dxf_bytes: bytes) -> bytes:
    doc = ezdxf.read(io.StringIO(dxf_bytes.decode('utf-8')))
    ms = doc.modelspace()
    sheets = [entity for entity in ms.query('INSERT')
              if entity.dxf.name.upper().replace(' ', '') in ORDER_NAMES]
    if not sheets:
        return dxf_bytes
    # Resolve everything first; skipped entities must never yield a partial file.
    replacements = [(insert, list(_sheet_entities(insert))) for insert in sheets]
    for insert, entities in replacements:
        for entity in entities:
            ms.add_entity(entity)
        ms.delete_entity(insert)
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode('utf-8')
