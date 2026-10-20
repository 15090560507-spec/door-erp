import io
import time
import unittest
from unittest.mock import patch

import ezdxf
from ezdxf.lldxf.tagwriter import TagCollector

from cad_download import editable_sheet_dxf
from rendering.cad_sheet_jpg import _order_form_bbox


def encoded(doc):
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode('utf-8')


def decoded(content):
    return ezdxf.read(io.StringIO(content.decode('utf-8')))


def sample(name='ORDER_FORM'):
    doc = ezdxf.new('R2018', setup=True)
    doc.layers.new('SHEET', dxfattribs={'color': 5})
    block = doc.blocks.new(name)
    block.add_lwpolyline([(0, 0), (2000, 0), (2000, 3000), (0, 3000)], close=True,
                         dxfattribs={'color': 0})
    block.add_attdef('CUSTOMER', insert=(100, 200), height=70, text='Placeholder')
    block.add_attdef('HIDDEN', insert=(100, 300), height=70, text='Secret',
                     dxfattribs={'flags': 1})
    nested = doc.blocks.new('SHEET_TITLE')
    nested.add_text('订货单', height=80, dxfattribs={'color': 0})
    block.add_blockref('SHEET_TITLE', (200, 2700), dxfattribs={'color': 0})
    hardware = doc.blocks.new('HANDLE')
    hardware.add_circle((0, 0), 15)
    ms = doc.modelspace()
    insert = ms.add_blockref(name, (300, 400), dxfattribs={'layer': 'SHEET', 'color': 3})
    insert.add_auto_attribs({'CUSTOMER': '张三客户 √', 'HIDDEN': '不可见内容'})
    ms.add_blockref('HANDLE', (800, 1000))
    ms.add_linear_dim(base=(0, -100), p1=(0, 0), p2=(1000, 0)).render()
    return doc, insert


class EditableSheetDownloadTests(unittest.TestCase):
    def test_only_sheet_is_exploded_and_attribute_values_survive(self):
        doc, _ = sample()
        source = encoded(doc)
        original = decoded(source)
        handles = [entity.dxf.handle for entity in original.modelspace()
                   if entity.dxftype() == 'DIMENSION'
                   or (entity.dxftype() == 'INSERT' and entity.dxf.name == 'HANDLE')]
        protected = [TagCollector.dxftags(original.entitydb[handle]) for handle in handles]
        result = decoded(editable_sheet_dxf(source))
        self.assertEqual([entity.dxf.name for entity in result.modelspace().query('INSERT')], ['HANDLE'])
        text = [entity.dxf.text for entity in result.modelspace().query('TEXT')]
        self.assertIn('张三客户 √', text)
        self.assertIn('订货单', text)
        self.assertNotIn('Placeholder', text)
        self.assertNotIn('不可见内容', text)
        self.assertEqual(protected, [TagCollector.dxftags(result.entitydb[handle]) for handle in handles])
        self.assertFalse(result.audit().has_errors)
        self.assertIsNotNone(_order_form_bbox(original))

    def test_sheet_geometry_and_inherited_display_are_preserved(self):
        doc, _ = sample()
        result = decoded(editable_sheet_dxf(encoded(doc)))
        outline = next(iter(result.modelspace().query('LWPOLYLINE')))
        self.assertEqual(tuple(outline.get_points()[0][:2]), (300, 400))
        self.assertEqual(outline.dxf.layer, 'SHEET')
        self.assertEqual(outline.dxf.color, 3)
        title = next(entity for entity in result.modelspace().query('TEXT') if entity.dxf.text == '订货单')
        self.assertEqual(title.dxf.layer, 'SHEET')
        self.assertEqual(title.dxf.color, 3)
        self.assertEqual(title.dxf.insert, (500, 3100, 0))

    def test_byblock_transparency_inherits_without_making_the_sheet_invisible(self):
        doc, insert = sample()
        outline = next(iter(doc.blocks['ORDER_FORM'].query('LWPOLYLINE')))
        outline.dxf.transparency = 0x01000000
        result = decoded(editable_sheet_dxf(encoded(doc)))
        self.assertTrue(next(iter(result.modelspace().query('LWPOLYLINE'))).is_transparency_by_layer)
        insert.transparency = 0.3
        result = decoded(editable_sheet_dxf(encoded(doc)))
        self.assertEqual(next(iter(result.modelspace().query('LWPOLYLINE'))).dxf.transparency,
                         insert.dxf.transparency)

    def test_sheet_names_and_missing_sheet(self):
        for name in ('ORDERFORM', 'order_form', 'ORDER FORM'):
            with self.subTest(name=name):
                doc, _ = sample(name)
                result = decoded(editable_sheet_dxf(encoded(doc)))
                self.assertEqual([e.dxf.name for e in result.modelspace().query('INSERT')], ['HANDLE'])
        doc = ezdxf.new()
        doc.modelspace().add_line((0, 0), (10, 10))
        source = encoded(doc)
        self.assertEqual(editable_sheet_dxf(source), source)

    def test_multiline_attributes_remain_multiline(self):
        doc, insert = sample()
        attribute = insert.get_attrib('CUSTOMER')
        text = doc.modelspace().add_mtext('客户第一行\\P地址第二行',
                                        dxfattribs={'insert': attribute.dxf.insert, 'char_height': 70, 'width': 800})
        attribute.set_mtext(text)
        doc.modelspace().delete_entity(text)
        result = decoded(editable_sheet_dxf(encoded(doc)))
        self.assertIn('客户第一行\n地址第二行', [e.plain_text() for e in result.modelspace().query('MTEXT')])

    def test_recursive_sheet_or_skipped_entity_fails_instead_of_silent_loss(self):
        doc, _ = sample()
        doc.blocks['SHEET_TITLE'].add_blockref('ORDER_FORM', (0, 0))
        with self.assertRaisesRegex(ValueError, '循环|recursive'):
            editable_sheet_dxf(encoded(doc))
        doc, _ = sample()
        from ezdxf.entities import Insert
        def skipped(_insert, **kwargs):
            kwargs['skipped_entity_callback'](None, 'unsupported test entity')
            return iter(())
        with patch.object(Insert, 'virtual_entities', skipped):
            with self.assertRaisesRegex(ValueError, 'unsupported test entity'):
                editable_sheet_dxf(encoded(doc))

    def test_unsupported_transforms_and_clipped_sheets_fail_explicitly(self):
        doc, insert = sample()
        insert.dxf.xscale = 2
        with self.assertRaisesRegex(ValueError, '非等比'):
            editable_sheet_dxf(encoded(doc))
        doc, insert = sample()
        insert.new_extension_dict().add_dictionary('ACAD_FILTER')
        with self.assertRaisesRegex(ValueError, '裁剪'):
            editable_sheet_dxf(encoded(doc))
        doc, _ = sample()
        doc.blocks['ORDER_FORM'].block.dxf.flags |= 4
        with self.assertRaisesRegex(ValueError, '外部参照'):
            editable_sheet_dxf(encoded(doc))

    def test_uniform_rotation_scaling_and_array_are_preserved(self):
        doc, insert = sample()
        insert.set_scale(2)
        insert.dxf.rotation = 90
        insert.grid(size=(2, 1), spacing=(4000, 0))
        result = decoded(editable_sheet_dxf(encoded(doc)))
        outlines = list(result.modelspace().query('LWPOLYLINE'))
        self.assertEqual(len(outlines), 2)
        self.assertAlmostEqual(outlines[0].get_points()[1][0], 300)
        self.assertAlmostEqual(outlines[0].get_points()[1][1], 4400)
        self.assertFalse(result.audit().has_errors)


class EditableSheetRouteTests(unittest.TestCase):
    def setUp(self):
        import main
        from fastapi.testclient import TestClient
        from models import CADRequest
        self.main = main
        self.original_overrides = main.app.dependency_overrides.copy()
        main.app.dependency_overrides[main.get_current_user] = lambda: {'uid': 'A', 'role': '管理员'}
        self.client = TestClient(main.app)
        self.request = CADRequest(dhdw='拆框测试', ys='测试色', mshd=80,
                                  sel_kx='右开', sel_nk='内开', st_val='连体锁')
        self.source = encoded(sample()[0])
        self.key = 'editable-sheet-test'
        main._cad_cache.clear()
        main._cad_cache[self.key] = {'created': time.monotonic(), 'dxf': self.source}

    def tearDown(self):
        self.client.close()
        self.main.app.dependency_overrides = self.original_overrides
        self.main._cad_cache.clear()

    def test_download_cache_is_separate_and_versioned(self):
        main = self.main
        with patch.object(main, 'editable_sheet_dxf', wraps=editable_sheet_dxf) as convert:
            first, hit = main._cached_cad_download(self.key, self.source)
            second, second_hit = main._cached_cad_download(self.key, self.source)
            self.assertFalse(hit)
            self.assertTrue(second_hit)
            self.assertEqual(first, second)
            self.assertEqual(convert.call_count, 1)
            with patch.object(main, 'CAD_DOWNLOAD_VERSION', 'future-version'):
                _, future_hit = main._cached_cad_download(self.key, self.source)
                self.assertFalse(future_hit)
                self.assertEqual(convert.call_count, 2)
        self.assertEqual(main._cad_cache[self.key]['dxf'], self.source)
        self.assertIsNotNone(_order_form_bbox(decoded(self.source)))

    def test_route_download_does_not_replace_preview_or_print_source(self):
        main = self.main
        jpg = {'content': b'jpeg-test', 'usedOrderForm': True, 'width': 5940, 'height': 4200}
        with patch.object(main, '_cached_cad', return_value=(self.key, self.source, True)), \
                patch.object(main, '_cached_cad_svg', return_value=('<svg/>', True)) as svg, \
                patch.object(main, '_cached_cad_sheet_jpg', return_value=(jpg, True)) as plot:
            payload = self.request.model_dump()
            first = self.client.post('/api/generate_cad', json=payload)
            second = self.client.post('/api/generate_cad', json=payload)
            self.assertEqual(first.status_code, 200, first.text[:300])
            self.assertEqual(first.headers['X-CAD-Download-Cache'], 'MISS')
            self.assertEqual(second.headers['X-CAD-Download-Cache'], 'HIT')
            self.assertEqual(first.content, second.content)
            self.assertIsNone(_order_form_bbox(decoded(first.content)))
            self.assertEqual(self.client.post('/api/generate_cad_preview', json=payload).status_code, 200)
            self.assertEqual(self.client.post('/api/generate_cad_jpg', json=payload).status_code, 200)
            svg.assert_called_once_with(self.key, self.source)
            plot.assert_called_once_with(self.key, self.source)
        self.assertEqual(main._cad_cache[self.key]['dxf'], self.source)

    def test_failed_conversion_returns_error_not_partial_download(self):
        main = self.main
        with patch.object(main, '_cached_cad', return_value=(self.key, self.source, True)), \
                patch.object(main, 'editable_sheet_dxf', side_effect=ValueError('图框实体无法转换')):
            response = self.client.post('/api/generate_cad', json=self.request.model_dump())
        self.assertEqual(response.status_code, 400)
        self.assertIn('图框实体无法转换', response.json()['detail'])
        self.assertEqual(main._cad_cache[self.key]['dxf'], self.source)


if __name__ == '__main__':
    unittest.main()
