import math
import os
import sys
import unittest


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from trim_geometry import calculate_quote_trim_metrics, calculate_trim_geometry


def base_params(**overrides):
    params = {
        "dw": 900,
        "dh": 2100,
        "door_type": "单门",
        "left_width_front": 55,
        "right_width_front": 85,
        "left_width_back": 85,
        "right_width_back": 55,
        "fw_top_front": 55,
        "fw_top_back": 75,
        "trim_front": 160,
        "trim_front_right": 160,
        "trim_front_top": 160,
        "trim_back": 140,
        "trim_back_top": 140,
        "overlap": 20,
        "overlap_front": 20,
        "overlap_back": 20,
        "overlap_front_lr": 20,
        "overlap_front_top": 20,
        "overlap_back_lr": 20,
        "overlap_back_top": 20,
        "qc": "无",
        "qc_height": 400,
        "qc_shape": "矩形气窗",
        "has_mm": False,
        "mm_height": 200,
    }
    params.update(overrides)
    return params


class TrimGeometryTests(unittest.TestCase):
    def test_rectangular_trim_is_outer_contour_minus_inner_contour(self):
        geometry = calculate_trim_geometry(base_params(trim_back=0), is_back=False)

        self.assertTrue(geometry.valid, geometry.error)
        self.assertAlmostEqual(geometry.outer_area_mm2, 1180 * 2240)
        self.assertAlmostEqual(geometry.inner_area_mm2, 860 * 2080)
        self.assertAlmostEqual(
            geometry.base_area_mm2,
            geometry.outer_area_mm2 - geometry.inner_area_mm2,
        )

    def test_lintel_is_counted_only_in_outer_trim_when_both_exist(self):
        outer, inner, target = calculate_quote_trim_metrics(base_params(has_mm=True))

        self.assertEqual(target, "outer")
        self.assertGreater(outer.included_lintel_area_mm2, 0)
        self.assertEqual(inner.included_lintel_area_mm2, 0)
        self.assertAlmostEqual(outer.quote_area_mm2, outer.base_area_mm2 + outer.lintel_area_mm2)

    def test_lintel_falls_back_to_inner_trim(self):
        outer, inner, target = calculate_quote_trim_metrics(
            base_params(trim_front=0, trim_front_right=0, trim_front_top=0, has_mm=True)
        )

        self.assertEqual(target, "inner")
        self.assertEqual(outer.quote_area_mm2, 0)
        self.assertGreater(inner.included_lintel_area_mm2, 0)

    def test_landscape_trim_uses_closed_outer_and_inner_contours(self):
        geometry = calculate_trim_geometry(
            base_params(
                trim_back=0,
                has_outer_landscape=True,
                outer_landscape_left_overlap=15,
                outer_landscape_right_overlap=25,
                outer_landscape_top_overlap=30,
                trim_front=180,
                trim_front_right=120,
                trim_front_top=240,
            ),
            is_back=False,
        )

        self.assertTrue(geometry.valid, geometry.error)
        self.assertEqual(len(geometry.component_contours), 3)
        self.assertAlmostEqual(
            geometry.base_area_mm2,
            geometry.outer_area_mm2 - geometry.inner_area_mm2,
        )

    def test_arch_trim_uses_sampled_real_curves(self):
        geometry = calculate_trim_geometry(
            base_params(
                trim_back=0,
                is_arch_door=True,
                arch_spring_height=1700,
            ),
            is_back=False,
        )

        self.assertTrue(geometry.valid, geometry.error)
        self.assertGreater(len(geometry.outer_contour), 50)
        self.assertTrue(math.isfinite(geometry.base_area_mm2))
        self.assertGreater(geometry.base_area_mm2, 0)

    def test_invalid_inner_contour_is_rejected(self):
        geometry = calculate_trim_geometry(
            base_params(trim_back=0, overlap_front_lr=500),
            is_back=False,
        )

        self.assertFalse(geometry.valid)
        self.assertIn("闭合", geometry.error)


if __name__ == "__main__":
    unittest.main()
