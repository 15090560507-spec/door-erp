import copy
import io
import os
import unittest
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.lldxf.tagwriter import TagCollector
from ezdxf.math import Vec3

from cad_order_layout import _template_grid, _text_width
from cad_sheet_branding import DEFAULT_ORDER_TITLE, apply_order_sheet_branding, normalize_order_title
from config import TEMPLATE_PATH


def sheet(doc):
    return next(e for e in doc.modelspace().query('INSERT') if e.dxf.name == 'ORDER_FORM')


def title_bounds(block):
    _, top, left, _, header, _, logo, lines = _template_grid(block)
    bottom = max(line.dxf.start.y for line in lines
                 if abs(line.dxf.start.y - line.dxf.end.y) < 0.01
                 and header < line.dxf.start.y < top
                 and min(line.dxf.start.x, line.dxf.end.x) <= logo + 0.1
                 and max(line.dxf.start.x, line.dxf.end.x) >= left - 0.1)
    return logo, bottom, left, top


class SheetBrandingTests(unittest.TestCase):
    def test_default_brand_is_retained_and_title_is_centered(self):
        doc = ezdxf.readfile(TEMPLATE_PATH)
        block = doc.blocks['ORDER_FORM']
        original_graphics = [TagCollector.dxftags(e) for e in block if e.dxftype() in ('SPLINE', 'CIRCLE')]
        apply_order_sheet_branding(doc, DEFAULT_ORDER_TITLE)
        self.assertEqual(original_graphics, [TagCollector.dxftags(e) for e in block
                                           if e.dxftype() in ('SPLINE', 'CIRCLE')])
        self.assertIn('西州将军门业', [e.plain_text() for e in block.query('MTEXT')])
        self.assert_title(doc, DEFAULT_ORDER_TITLE)

    def test_nondefault_brand_cell_is_blank_without_removing_grid(self):
        for value in ('众鼎门业', '杭州兰庭新贵门业', '其他定制门业订货单'):
            with self.subTest(title=value):
                doc = ezdxf.readfile(TEMPLATE_PATH)
                block = doc.blocks['ORDER_FORM']
                _, top, _, _, header, _, logo, _ = _template_grid(block)
                def grid_tags():
                    result = []
                    for entity in block.query('LINE LWPOLYLINE'):
                        extent = bbox.extents([entity])
                        # The logo also contains a short LINE wholly inside its cell.
                        if not (0 < extent.extmin.x <= extent.extmax.x < logo
                                and header < extent.extmin.y <= extent.extmax.y < top):
                            result.append(TagCollector.dxftags(entity))
                    return result
                grid = grid_tags()
                protected = [TagCollector.dxftags(e) for e in doc.modelspace() if e is not sheet(doc)]
                apply_order_sheet_branding(doc, value)
                self.assertFalse(list(block.query('SPLINE CIRCLE')))
                self.assertNotIn('西州将军门业', [e.plain_text() for e in block.query('MTEXT')])
                self.assertEqual(grid, grid_tags())
                self.assertEqual(protected, [TagCollector.dxftags(e) for e in doc.modelspace() if e is not sheet(doc)])
                self.assert_title(doc, value)
                self.assertFalse(doc.audit().has_errors)

    def assert_title(self, doc, value):
        insert = sheet(doc)
        x0, y0, x1, y1 = title_bounds(doc.blocks['ORDER_FORM'])
        expected = insert.matrix44().transform(Vec3((x0 + x1) / 2, (y0 + y1) / 2, 0))
        title = insert.get_attrib('TT')
        self.assertEqual(title.dxf.text, value)
        self.assertEqual(title.dxf.halign, 1)
        self.assertEqual(title.dxf.valign, 2)
        self.assertTrue(title.dxf.align_point.isclose(expected))
        self.assertLessEqual(_text_width(value, title.dxf.height) * title.dxf.get('width', 1), (x1 - x0) * 0.94)
        self.assertGreater(title.dxf.height, 0)

    def test_long_title_shrinks_without_truncation(self):
        doc = ezdxf.readfile(TEMPLATE_PATH)
        height = sheet(doc).get_attrib('TT').dxf.height
        title = '定制生产单位' * 15 + '订货单'
        apply_order_sheet_branding(doc, title)
        self.assert_title(doc, title)
        self.assertLess(sheet(doc).get_attrib('TT').dxf.height, height)

    def test_title_normalization_and_template_isolation(self):
        self.assertEqual(normalize_order_title('  '), DEFAULT_ORDER_TITLE)
        self.assertEqual(normalize_order_title(None), DEFAULT_ORDER_TITLE)
        self.assertEqual(normalize_order_title(' 众鼎门业 '), '众鼎门业')
        custom = ezdxf.readfile(TEMPLATE_PATH)
        apply_order_sheet_branding(custom, '众鼎门业')
        default = ezdxf.readfile(TEMPLATE_PATH)
        apply_order_sheet_branding(default, ' ')
        self.assertTrue(list(default.blocks['ORDER_FORM'].query('SPLINE')))
        self.assert_title(default, DEFAULT_ORDER_TITLE)

    def test_unsupported_sheet_does_not_partially_delete_content(self):
        doc = ezdxf.new()
        block = doc.blocks.new('ORDER_FORM')
        block.add_circle((0, 0), 50)
        doc.modelspace().add_blockref('ORDER_FORM', (0, 0))
        before = [TagCollector.dxftags(e) for e in block]
        with self.assertRaises(ValueError):
            apply_order_sheet_branding(doc, '众鼎门业')
        self.assertEqual(before, [TagCollector.dxftags(e) for e in block])

    def test_simple_product_still_applies_title_and_blank_cell(self):
        from drawing import run_integrated_system
        from main import build_cad_params
        from models import CADRequest
        request = CADRequest(order_title='众鼎门业', product_name='牌匾', dw=1800, dh=600)
        info, checks, params = build_cad_params(request)
        message, stream = run_integrated_system(info, checks, copy.deepcopy(params))
        self.assertIsNotNone(stream, message)
        doc = ezdxf.read(io.StringIO(stream.getvalue()))
        self.assert_title(doc, '众鼎门业')
        self.assertFalse(list(doc.blocks['ORDER_FORM'].query('SPLINE CIRCLE')))
        self.assertFalse(doc.audit().has_errors)

    def test_generation_all_outputs_share_branding_and_preserve_door_geometry(self):
        from cad_download import editable_sheet_dxf
        from cad_preview import render_dxf_svg
        from drawing import run_integrated_system
        from main import build_cad_params
        from models import CADRequest
        from rendering.cad_sheet_jpg import render_dxf_sheet_jpg, _order_form_bbox, _plot
        from PIL import Image, ImageChops, ImageStat
        protected = None
        for index, value in enumerate((DEFAULT_ORDER_TITLE, '众鼎门业', '杭州兰庭新贵门业', '定制门业' * 6 + '订货单')):
            with self.subTest(title=value):
                request = CADRequest(order_title=value, dhdw='抬头验证', ys='测试色', mshd=80,
                                     dw=1400, dh=2470, sel_kx='右开', sel_nk='内开', st_val='连体锁')
                info, checks, params = build_cad_params(request)
                message, stream = run_integrated_system(info, checks, copy.deepcopy(params))
                self.assertIsNotNone(stream, message)
                self.assertNotIn('skipped', message)
                text = stream.getvalue()
                doc = ezdxf.read(io.StringIO(text))
                self.assert_title(doc, value)
                shapes = [TagCollector.dxftags(e) for e in doc.modelspace() if e.dxftype() != 'MTEXT'
                          and not (e.dxftype() == 'INSERT' and e.dxf.name == 'ORDER_FORM')]
                if protected is None:
                    protected = shapes
                else:
                    self.assertEqual(protected, shapes)
                self.assertEqual(bool(list(doc.blocks['ORDER_FORM'].query('SPLINE'))), value == DEFAULT_ORDER_TITLE)
                downloaded = editable_sheet_dxf(text.encode('utf-8'))
                parsed = ezdxf.read(io.StringIO(downloaded.decode('utf-8')))
                self.assertIn(value, [e.dxf.text for e in parsed.modelspace().query('TEXT')])
                self.assertFalse(parsed.audit().has_errors)
                if os.environ.get('CAD_BRANDING_ARTIFACT_DIR'):
                    folder = Path(os.environ['CAD_BRANDING_ARTIFACT_DIR'])
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / f'sheet-{index}.dxf').write_bytes(text.encode('utf-8'))
                    (folder / f'editable-{index}.dxf').write_bytes(downloaded)
                    (folder / f'preview-{index}.svg').write_text(render_dxf_svg(text), encoding='utf-8')
                    image = render_dxf_sheet_jpg(text, output_size=(1782, 1260))
                    (folder / f'sheet-{index}.jpg').write_bytes(image['content'])
                    editable_image = _plot(parsed, _order_form_bbox(doc), (1782, 1260))
                    (folder / f'editable-{index}.jpg').write_bytes(editable_image)
                    original = Image.open(io.BytesIO(image['content']))
                    editable = Image.open(io.BytesIO(editable_image))
                    difference = ImageChops.difference(original, editable)
                    # BURST can introduce subpixel checkbox rounding; the header must match exactly.
                    self.assertIsNone(difference.crop((0, 0, 1782, 210)).getbbox())
                    self.assertLess(max(ImageStat.Stat(difference).mean), 0.001)
                    self.assertLessEqual(max(high for _, high in difference.getextrema()), 2)


if __name__ == '__main__':
    unittest.main()
