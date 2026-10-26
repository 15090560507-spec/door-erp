import io
import unittest

import ezdxf

from drawing import run_integrated_system
from main import build_cad_params
from models import CADRequest


def draw(style, *, inset=20, spacing=20, **kwargs):
    params = dict(dw=1600, dh=2600, door_type='单门',
                  door_panel_style='H型布局', panel_b2_glass_style=style,
                  glass_line_inset=inset, glass_line_spacing=spacing,
                  fingerprint_lock='无', sel_hys='暗合页',
                  zmls='无', fmls='无', has_outer=False)
    params.update(kwargs)
    request = CADRequest(**params)
    message, result = run_integrated_system(*build_cad_params(request))
    if result is None:
        raise ValueError(message)
    return ezdxf.read(io.StringIO(result.getvalue()))


def panel_geometry(doc):
    geometry = []
    for entity in doc.modelspace():
        if entity.dxf.layer != 'A-DOOR-PANEL':
            continue
        if entity.dxftype() == 'LINE':
            points = tuple(sorted((tuple(round(v, 4) for v in tuple(entity.dxf.start)[:2]),
                                   tuple(round(v, 4) for v in tuple(entity.dxf.end)[:2]))))
            geometry.append(('LINE', points))
        elif entity.dxftype() == 'LWPOLYLINE':
            geometry.append(('LWPOLYLINE', tuple(tuple(round(v, 4) for v in point[:2])
                                                for point in entity.get_points())))
    return sorted(geometry)


class GlassPatternControlTests(unittest.TestCase):
    def test_vertical_has_no_glass_hatch_or_added_perimeter(self):
        doc = draw('竖条')
        baseline = draw('无线条')
        self.assertEqual(len(list(doc.modelspace().query('HATCH'))),
                         len(list(baseline.modelspace().query('HATCH'))))
        self.assertEqual(len([e for e in doc.modelspace().query('LWPOLYLINE')
                              if e.dxf.layer == 'A-DOOR-PANEL']),
                         len([e for e in baseline.modelspace().query('LWPOLYLINE')
                              if e.dxf.layer == 'A-DOOR-PANEL']))

    def test_vertical_ignores_glass_inset(self):
        self.assertEqual(panel_geometry(draw('竖条', inset=0)),
                         panel_geometry(draw('竖条', inset=60)))

    def test_zero_inset_is_not_replaced_by_twenty(self):
        self.assertNotEqual(panel_geometry(draw('单圈外围线', inset=0)),
                            panel_geometry(draw('单圈外围线', inset=20)))

    def test_every_internal_line_pattern_responds_to_spacing(self):
        for style in ('竖条', '双边框', '四角回纹', '双边框+花件', '六格线条', '八格线条'):
            with self.subTest(style=style):
                self.assertNotEqual(panel_geometry(draw(style, spacing=16)),
                                    panel_geometry(draw(style, spacing=20)))

    def test_out_of_range_values_are_not_silently_clamped(self):
        with self.assertRaisesRegex(ValueError, '外边距'):
            draw('单圈外围线', inset=1000)
        with self.assertRaisesRegex(ValueError, '线距'):
            draw('六格线条', spacing=1000)
        with self.assertRaisesRegex(ValueError, '线距'):
            draw('竖条', spacing=0)

    def test_grids_keep_divider_count_and_equal_centers(self):
        for style, rows in (('六格线条', 3), ('八格线条', 4)):
            centers = []
            for spacing in (16, 28):
                with self.subTest(style=style, spacing=spacing):
                    doc = draw(style, spacing=spacing)
                    hatch = next(e for e in doc.modelspace().query('HATCH')
                                 if e.dxf.layer == 'A-DOOR-HATCH')
                    vertices = list(hatch.paths[0].vertices)
                    left, right = min(p[0] for p in vertices), max(p[0] for p in vertices)
                    bottom, top = min(p[1] for p in vertices), max(p[1] for p in vertices)
                    vertical, horizontal = [], []
                    for entity in doc.modelspace().query('LINE'):
                        if entity.dxf.layer != 'A-DOOR-PANEL':
                            continue
                        a, b = entity.dxf.start, entity.dxf.end
                        if abs(a.x - b.x) < .001 and abs(a.y - bottom) < .001 and abs(b.y - top) < .001:
                            vertical.append(a.x)
                        if abs(a.y - b.y) < .001 and abs(a.x - left) < .001 and abs(b.x - right) < .001:
                            horizontal.append(a.y)
                    self.assertEqual(len(vertical), 2)
                    self.assertEqual(len(horizontal), 2 * (rows - 1))
                    vertical.sort()
                    horizontal.sort()
                    self.assertAlmostEqual(vertical[1] - vertical[0], spacing)
                    actual = [(horizontal[i] + horizontal[i + 1]) / 2
                              for i in range(0, len(horizontal), 2)]
                    for i in range(0, len(horizontal), 2):
                        self.assertAlmostEqual(horizontal[i + 1] - horizontal[i], spacing)
                    expected = [bottom + (top - bottom) * i / rows for i in range(1, rows)]
                    for a, b in zip(actual, expected):
                        self.assertAlmostEqual(a, b)
                    centers.append(((vertical[0] + vertical[1]) / 2, actual))
            self.assertEqual(centers[0], centers[1])

    def test_front_spacing_does_not_change_explicit_back_geometry(self):
        kwargs = dict(back_panel_same_as_front=False, back_door_panel_style='H型布局',
                      back_panel_b2_glass_style='八格线条', back_glass_line_spacing=24)
        def back_geometry(spacing):
            return [item for item in panel_geometry(draw('六格线条', spacing=spacing, **kwargs))
                    if all(1800 < point[0] < 6000 for point in item[1])]
        self.assertTrue(back_geometry(16))
        self.assertEqual(back_geometry(16), back_geometry(28))

    def test_child_spacing_changes_only_child_pattern(self):
        kwargs = dict(door_type='子母门', mother_door_width=900,
                      child_door_panel_style='H型布局', child_panel_b2_glass_style='六格线条')
        a = draw('无线条', child_glass_line_spacing=16, **kwargs)
        b = draw('无线条', child_glass_line_spacing=28, **kwargs)
        self.assertNotEqual(panel_geometry(a), panel_geometry(b))
        def mother_lines(doc):
            return [item for item in panel_geometry(doc)
                    if item[0] == 'LINE' and all(0 < point[0] < 1000 for point in item[1])]
        self.assertTrue(mother_lines(a))
        self.assertEqual(mother_lines(a), mother_lines(b))


if __name__ == '__main__':
    unittest.main()
