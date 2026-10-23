import io
import math
import unittest
import os
from pathlib import Path

import ezdxf

from config import TEMPLATE_PATH
from disc_panel import disc_geometry, disc_center_height, disc_fill


class DiscPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = ezdxf.readfile(TEMPLATE_PATH)

    def test_actual_blocks_scale_and_lock_anchor(self):
        for style, stem in [('圆形牡丹花', 'YXMDH'), ('四叶草牡丹花', 'SBMDH')]:
            for direction, suffix in [(-1, 'Z'), (1, 'Y')]:
                with self.subTest(style=style, direction=direction):
                    geometry = disc_geometry(self.doc, style, 700, 1250, 0, direction, (-1100, 100, 1100, 2600))
                    self.assertEqual(geometry.block_name, stem + suffix)
                    self.assertEqual(geometry.scale, .7)
                    self.assertEqual(geometry.center, (0, 1250))
                    self.assertTrue(all(x * direction >= -1e-6 for x, _ in geometry.boundary))
                    self.assertGreater(len(geometry.boundary), 8)
                    full = disc_geometry(self.doc, style, 1000, 1250, 0, direction, (-1100, 100, 1100, 2600))
                    self.assertEqual(full.scale, 1)

    def test_auto_and_manual_height(self):
        self.assertEqual(disc_center_height(None, '标配拉手', '', 80), 1080)
        self.assertEqual(disc_center_height(None, '背包拉手', '', 75), 1075)
        self.assertEqual(disc_center_height(None, '铝雕圆形拉手', '150*300', 80), 1200)
        self.assertEqual(disc_center_height(None, '铝雕拉手', '40*800', 80), 1200)
        self.assertEqual(disc_center_height(1300, '标配拉手', '', 80), 1300)
        self.assertEqual(disc_center_height(None, '无', '', 80), 1050)

    def test_circle_and_validation(self):
        geometry = disc_geometry(self.doc, '圆形', 200, 1200, 0, 1, (0, 50, 800, 2400))
        self.assertIsNone(geometry.block_name)
        self.assertAlmostEqual(max(x for x, _ in geometry.boundary), 200, delta=.2)
        for radius, center in [(0, 1200), (900, 1200), (200, 80), (math.nan, 1200)]:
            with self.subTest(radius=radius), self.assertRaises(ValueError):
                disc_geometry(self.doc, '圆形', radius, center, 0, 1, (0, 50, 800, 2400))
        with self.assertRaisesRegex(ValueError, '缺少'):
            disc_geometry(ezdxf.new(), '圆形牡丹花', 700, 1200, 0, 1, (0, 50, 900, 2400))

    def test_fill_defaults_and_explicit_empty(self):
        self.assertEqual(disc_fill('圆形牡丹花', None), '竖条')
        self.assertEqual(disc_fill('四叶草牡丹花', ''), '')
        self.assertEqual(disc_fill('圆形', None), '')
        self.assertEqual(disc_fill('圆形', '正实虚'), '正实虚')

    def test_generated_front_back_and_outer_fill(self):
        from models import CADRequest
        from main import build_cad_params
        from drawing import run_integrated_system
        for style, stem in [('圆形牡丹花', 'YXMDH'), ('四叶草牡丹花', 'SBMDH')]:
            with self.subTest(style=style):
                request = CADRequest(dw=2000, dh=2600, door_type='对开门', door_panel_style='圆盘造型',
                    panel_disc_style=style, panel_disc_radius=700, panel_disc_center_height=1200,
                    back_panel_same_as_front=True, zmls='无', fmls='无')
                info, checks, params = build_cad_params(request)
                self.assertEqual(params['panel_disc_style'], style)
                message, stream = run_integrated_system(info, checks, params)
                self.assertIsNotNone(stream, message)
                doc = ezdxf.read(io.StringIO(stream.getvalue()))
                blocks = [e for e in doc.modelspace().query('INSERT')
                          if e.dxf.name.startswith(stem) and e.dxf.layer == 'A-DOOR-PANEL']
                self.assertEqual(len(blocks), 4)
                self.assertTrue(all(abs(e.dxf.xscale - .7) < 1e-9 for e in blocks))
                self.assertTrue(all(abs(e.dxf.yscale - .7) < 1e-9 and abs(e.dxf.zscale - .7) < 1e-9 for e in blocks))
                self.assertTrue(all(abs(e.dxf.insert.y - 1200) < 1e-7 for e in blocks))
                lines = [e for e in doc.modelspace().query('LINE') if e.dxf.layer == 'A-DOOR-HATCH']
                self.assertGreater(len(lines), 10)
                from ezdxf.math import Vec2, is_point_in_polygon_2d
                for block in blocks:
                    direction = 1 if block.dxf.name.endswith('Y') else -1
                    geometry = disc_geometry(doc, style, 700, block.dxf.insert.y, block.dxf.insert.x,
                        direction, (block.dxf.insert.x - 1100, 0, block.dxf.insert.x + 1100, 2600))
                    polygon = [Vec2(p) for p in geometry.boundary]
                    for line in lines:
                        for fraction in (.01, .25, .5, .75, .99):
                            point = line.dxf.start.lerp(line.dxf.end, fraction)
                            self.assertNotEqual(is_point_in_polygon_2d(Vec2(point), polygon), 1,
                                                f'Fill enters {block.dxf.name} at {block.dxf.insert}: {point}; line={line.dxf.start}->{line.dxf.end}')
                self.assertFalse(doc.audit().has_errors)
                if os.environ.get('DISC_ARTIFACT_DIR'):
                    from cad_preview import render_dxf_svg
                    from rendering.cad_sheet_jpg import render_dxf_sheet_jpg
                    folder = Path(os.environ['DISC_ARTIFACT_DIR'])
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / f'{stem}.dxf').write_text(stream.getvalue(), encoding='utf-8')
                    (folder / f'{stem}.svg').write_text(render_dxf_svg(stream.getvalue()), encoding='utf-8')
                    (folder / f'{stem}.jpg').write_bytes(render_dxf_sheet_jpg(stream.getvalue(), output_size=(1782,1260))['content'])

    def test_child_and_back_independent_parameters(self):
        from models import CADRequest
        from main import build_cad_params
        from drawing import run_integrated_system
        request = CADRequest(dw=2200, dh=2600, door_type='子母门', mother_door_width=900,
            child_door_panel_style='圆盘造型', child_panel_disc_style='四叶草牡丹花',
            child_panel_disc_radius=250, child_panel_disc_center_height=1350,
            child_panel_disc_outer_fill='', child_back_same_as_front=False,
            child_back_door_panel_style='圆盘造型', child_back_panel_disc_style='圆形牡丹花',
            child_back_panel_disc_radius=300, child_back_panel_disc_center_height=1400,
            child_back_panel_disc_outer_fill='')
        info, checks, params = build_cad_params(request)
        message, stream = run_integrated_system(info, checks, params)
        self.assertIsNotNone(stream, message)
        doc = ezdxf.read(io.StringIO(stream.getvalue()))
        blocks = [e for e in doc.modelspace().query('INSERT') if e.dxf.layer == 'A-DOOR-PANEL'
                  and e.dxf.name in ('SBMDHZ', 'SBMDHY', 'YXMDHZ', 'YXMDHY')]
        self.assertEqual(len(blocks), 2)
        self.assertEqual(sorted(round(e.dxf.xscale, 2) for e in blocks), [.25, .3])
        self.assertEqual(sorted(e.dxf.insert.y for e in blocks), [1350, 1400])

    def test_real_circle_tracks_handle_and_manual_override(self):
        from models import CADRequest
        from main import build_cad_params
        from drawing import run_integrated_system
        for explicit in (None, 1350):
            request = CADRequest(door_panel_style='圆盘造型', panel_disc_radius=200,
                panel_disc_center_height=explicit, zmls='铝雕圆形拉手', handle_size='150*300')
            info, checks, params = build_cad_params(request)
            message, stream = run_integrated_system(info, checks, params)
            self.assertIsNotNone(stream, message)
            doc = ezdxf.read(io.StringIO(stream.getvalue()))
            discs = [e for e in doc.modelspace().query('ARC')
                     if e.dxf.layer == 'A-DOOR-PANEL' and abs(e.dxf.radius - 200) < 1e-6]
            self.assertEqual(len(discs), 1)
            self.assertEqual(discs[0].dxf.center.y, explicit or 1200)


if __name__ == '__main__':
    unittest.main()
