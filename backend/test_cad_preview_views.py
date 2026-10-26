import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import ezdxf
from cad_preview import render_dxf_svg


class PreviewViewTests(unittest.TestCase):
    def test_groups_preserve_both_doors_and_dimensions_without_order_form(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        for x, label in ((0, "正面"), (3000, "背面")):
            msp.add_text(label, dxfattribs={"height": 60, "insert": (x + 500, 2300)})
            msp.add_lwpolyline([(x, 0), (x + 1000, 0), (x + 1000, 2100), (x, 2100)], close=True,
                               dxfattribs={"layer": "A-DOOR-FRAME"})
            msp.add_text("2100", dxfattribs={"height": 40, "insert": (x + 1150, 1000), "layer": "YQ_DIM"})
        msp.add_text("ORDER HEADER", dxfattribs={"insert": (500, 2500), "layer": "ORDER_FORM"})
        msp.add_text("UNRELATED NOTES", dxfattribs={"insert": (500, 5000)})
        # Nearby anchors used to pass the spatial filter despite very long text.
        msp.add_text("备注：本图纸仅供参考，生产尺寸按照标注", dxfattribs={"insert": (0, -250)})
        msp.add_text("锁体", dxfattribs={"insert": (4200, 1200)})
        block = doc.blocks.new('sheet-near-door')
        block.add_text('SHEET LABEL', dxfattribs={"insert": (0, 0)})
        block.add_line((0, 0), (100, 0))
        msp.add_blockref(block.name, (50, 100), dxfattribs={"layer": "ORDER_FORM"})
        dim = msp.add_linear_dim(base=(0, -100), p1=(0, 0), p2=(1000, 0),
                                 dxfattribs={"layer": "YQ_DIM"})
        dim.render()
        stream = io.StringIO()
        doc.write(stream)
        svg = render_dxf_svg(stream.getvalue(), doors_only=True)
        root = ET.fromstring(svg)
        groups = root.findall('{http://www.w3.org/2000/svg}g')
        self.assertEqual([g.get('data-cad-view') for g in groups], ['front', 'back'])
        for group in groups:
            self.assertIn('2100', ''.join(group.itertext()))
            self.assertEqual(len(group.findall('{http://www.w3.org/2000/svg}path')), 1)
        self.assertNotIn('ORDER HEADER', svg)
        self.assertNotIn('UNRELATED NOTES', svg)
        self.assertNotIn('本图纸', svg)
        self.assertNotIn('锁体', svg)
        self.assertNotIn('SHEET LABEL', svg)
        self.assertIn('1000', svg)
        self.assertNotIn('Preview is generated', svg)
        self.assertNotIn('data-cad-view', render_dxf_svg(stream.getvalue()))

    def test_simple_product_has_a_single_fallback_view(self):
        doc = ezdxf.new()
        doc.modelspace().add_line((0, 0), (400, 800))
        stream = io.StringIO()
        doc.write(stream)
        svg = render_dxf_svg(stream.getvalue(), doors_only=True)
        self.assertIn('data-cad-view="front"', svg)
        self.assertNotIn('data-cad-view="back"', svg)

    def test_preview_cache_separates_legacy_and_grouped_views(self):
        import main
        key = 'preview-view-unittest'
        main._cad_cache[key] = {"dxf": b"mock"}
        try:
            with patch.object(main, 'render_dxf_svg', side_effect=['legacy', 'grouped']) as render:
                self.assertEqual(main._cached_cad_svg(key, b'mock'), ('legacy', False))
                self.assertEqual(main._cached_cad_svg(key, b'mock', True), ('grouped', False))
                self.assertEqual(main._cached_cad_svg(key, b'mock', True), ('grouped', True))
                self.assertEqual(main._cached_cad_svg(key, b'mock'), ('legacy', True))
                self.assertEqual(render.call_count, 2)
        finally:
            main._cad_cache.pop(key, None)

    def test_preview_api_opts_into_grouped_views(self):
        import main
        from fastapi.testclient import TestClient
        from models import CADRequest
        previous = dict(main.app.dependency_overrides)
        main.app.dependency_overrides[main.get_current_user] = lambda: {"uid": "test-preview", "role": "管理员"}
        try:
            with patch.object(main, '_validate_task_params'), patch.object(main, '_cached_cad', return_value=('test-key', b'dxf', True)), \
                    patch.object(main, '_cached_cad_svg', return_value=('<svg/>', False)) as render, \
                    patch.object(main, '_cad_layout_headers', return_value={}):
                client = TestClient(main.app)
                response = client.post('/api/generate_cad_preview?doors_only=true', json=CADRequest().model_dump())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.text, '<svg/>')
                render.assert_called_once_with('test-key', b'dxf', doors_only=True)
        finally:
            main.app.dependency_overrides.clear()
            main.app.dependency_overrides.update(previous)

    def test_generated_dxf_has_nonempty_front_back_groups(self):
        from drawing import run_integrated_system
        from main import build_cad_params
        from models import CADRequest
        for door_type in ('单门', '对开门', '两定两开', 'wide-front'):
            with self.subTest(door_type=door_type):
                request = CADRequest(door_type='对开门' if door_type == 'wide-front' else door_type, dw=2440 if door_type == '两定两开' else 1400,
                                     dh=2520, has_outer=True, has_inner=True, zmls='A1022', fmls='背包拉手')
                if door_type == 'wide-front':
                    request = CADRequest(door_type='对开门', dw=2940, dh=2360, has_outer=False, has_inner=False,
                                         door_panel_style='H型布局', panel_b2_glass_style='单圈外围线',
                                         back_panel_same_as_front=True, zmls='自制长拉手', handle_size='50*1200')
                info, checks, params = build_cad_params(request)
                message, buffer = run_integrated_system(info, checks, params)
                self.assertIsNotNone(buffer, message)
                svg = render_dxf_svg(buffer.getvalue(), doors_only=True)
                root = ET.fromstring(svg)
                groups = root.findall('{http://www.w3.org/2000/svg}g')
                self.assertEqual([g.get('data-cad-view') for g in groups], ['front', 'back'])
                self.assertTrue(all(len(g) > 10 for g in groups))
                for group in groups:
                    texts = ''.join(group.itertext())
                    for unwanted in ('本图纸', '锁体', '指纹锁', '开启机构', '配置数量', '门扇厚度'):
                        self.assertNotIn(unwanted, texts)
                if os.environ.get('CAD_PREVIEW_TEST_ARTIFACTS'):
                    folder = Path(os.environ['CAD_PREVIEW_TEST_ARTIFACTS'])
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / f'{door_type}.svg').write_text(svg, encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
