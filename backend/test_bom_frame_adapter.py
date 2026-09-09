"""Frozen drawing to v1.4.3 frame processing integration tests."""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from bom_generation_service import BomGenerationService
from door_cad.services.fulfillment_adapter import adapt_fulfillment_frame
from fulfillment_database import FulfillmentDatabase
from test_bom_generation import create_door


class BomFrameAdapterTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="door-frame-adapter-")
        self.db = FulfillmentDatabase(
            os.path.join(self.temp_dir, "fulfillment.db"),
            os.path.join(self.temp_dir, "files"),
        )
        self.params = {
            "product_name": "不锈钢镀铜门", "door_type": "单门", "frame_process": "新工艺",
            "dw": 1000, "dh": 2200, "material": "304不锈钢", "ys": "紫铜色",
            "fw_left_str": "55/75", "fw_right_str": "55/75", "fw_top_str": "85/100",
            "threshold_type": "高低槛", "th_str": "45/60",
            "sel_hys": "半钢暗合页", "hysl": "3个/扇", "sel_bz": "木箱",
        }
        self.user = {"uid": "A", "name": "销售小A"}

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_maps_supported_frozen_parameters_without_changing_v143_defaults(self):
        door_id = create_door(self.db, self.params)
        result = adapt_fulfillment_frame(self.db, door_id)

        self.assertTrue(result.can_calculate)
        self.assertEqual(result.inputs.doorWidth, 1000)
        self.assertEqual(result.inputs.doorHeight, 2200)
        self.assertEqual(result.inputs.outerSideShort, 55)
        self.assertEqual(result.inputs.outerSideLong, 75)
        self.assertEqual(result.inputs.topShort, 85)
        self.assertEqual(result.inputs.bottomShort, 45)
        self.assertEqual(result.inputs.skeletonThickness, 2)
        self.assertEqual(result.inputs.skinThickness, 0.8)

    def test_recalculate_calls_canonical_calculator_once_and_creates_eight_frame_rows(self):
        door_id = create_door(self.db, self.params, sales_order_id=2)
        service = BomGenerationService(self.db)
        service.generate(door_id, self.user)

        from door_cad.services import fulfillment_adapter

        with patch.object(
            fulfillment_adapter,
            "calculate_frame_project",
            wraps=fulfillment_adapter.calculate_frame_project,
        ) as calculator:
            result = service.recalculate_frame(door_id, self.user)

        self.assertEqual(calculator.call_count, 1)
        frame_rows = [row for row in result["components"] if row["source_type"] == "frame_geometry"]
        self.assertEqual(len(frame_rows), 8)
        self.assertEqual({row["operation_code"] for row in frame_rows}, {"FRAME_PART"})
        self.assertTrue(all(row["source_payload"]["geometry_ref"] for row in frame_rows))

    def test_unsupported_frame_rule_returns_specific_field_errors(self):
        params = dict(self.params, product_name="地弹簧门", sel_hys="地弹簧", hysl="2个/扇")
        door_id = create_door(self.db, params, sales_order_id=3)

        result = adapt_fulfillment_frame(self.db, door_id)

        self.assertFalse(result.can_calculate)
        fields = {issue.field for issue in result.errors}
        self.assertTrue({"product_name", "sel_hys", "hysl"}.issubset(fields))


if __name__ == "__main__":
    unittest.main()
