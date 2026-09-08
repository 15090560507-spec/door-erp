"""Automatic whole-door BOM generation tests."""

import os
import shutil
import sys
import tempfile
import unittest


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from bom_generation_service import BomGenerationService
from fulfillment_database import FulfillmentDatabase, fulfillment_now


def create_door(database: FulfillmentDatabase, params: dict, sales_order_id: int = 1) -> int:
    order = database.create_from_sales_order(
        {
            "id": sales_order_id,
            "order_no": f"SO{sales_order_id:04d}",
            "customer_name": "测试客户",
            "project_name": "整单BOM测试",
            "delivery_date": "2026-10-01",
            "remark": "",
            "lines": [{
                "id": sales_order_id * 10 + 1,
                "line_no": 1,
                "task_id": f"drawing-{sales_order_id}",
                "quantity": 1,
                "product_name": params.get("product_name", "不锈钢镀铜门"),
                "door_type": params.get("door_type", "单门"),
                "width": params.get("dw", 1000),
                "height": params.get("dh", 2200),
                "opening_direction": "左内开",
                "color": params.get("ys", "紫铜色"),
                "drawing_snapshot": {"params": params},
            }],
        },
        f"sales-order:{sales_order_id}",
        {"uid": "A", "name": "销售小A"},
    )
    return int(order["door_units"][0]["id"])


class BomGenerationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="door-bom-generation-")
        self.db = FulfillmentDatabase(
            os.path.join(self.temp_dir, "fulfillment.db"),
            os.path.join(self.temp_dir, "files"),
        )
        self.service = BomGenerationService(self.db)
        self.user = {"uid": "A", "name": "销售小A"}

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def base_params():
        return {
            "product_name": "不锈钢镀铜门",
            "door_type": "单门",
            "dw": 1000,
            "dh": 2200,
            "material": "304不锈钢",
            "ys": "紫铜色",
            "fw_left_str": "55/75",
            "fw_right_str": "55/75",
            "fw_top_str": "85/100",
            "threshold_type": "高低槛",
            "zmks": "大板布局",
            "fmks": "大板布局",
            "sel_hys": "半钢暗合页",
            "hysl": "3个/扇",
            "st_val": "标准锁体",
            "zmls": "凹槽拉手",
            "fmls": "凹槽拉手",
            "glass_spec": "10mm钢化玻璃",
            "sel_bz": "木箱",
            "panel_material_code": "MAT-PANEL-304",
        }

    def add_material(self, code: str, name: str, specification: str, unit: str = "扇") -> int:
        now = fulfillment_now()
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """INSERT INTO inventory_materials(
                       code, name, category, specification, unit, material_type,
                       created_at, updated_at
                   ) VALUES (?, ?, '门体', ?, ?, '原材料', ?, ?)""",
                (code, name, specification, unit, now, now),
            )
            return int(cursor.lastrowid)

    def test_generates_baseline_groups_and_matches_explicit_material_code(self):
        params = self.base_params()
        material_id = self.add_material("MAT-PANEL-304", "门扇面板", "304不锈钢 / 紫铜色")
        door_id = create_door(self.db, params)

        result = self.service.generate(door_id, self.user)

        self.assertIn(result["generation_status"], {"已生成", "待完善"})
        groups = {item["group_code"] for item in result["components"]}
        self.assertTrue({"frame", "panel", "hardware", "glass", "packaging"}.issubset(groups))
        panel = next(item for item in result["components"] if item["operation_code"] == "PANEL")
        self.assertEqual(panel["material_id"], material_id)
        self.assertEqual(panel["match_status"], "已匹配")
        self.assertEqual(panel["source_rule_version"], result["rule_version"])

    def test_missing_hardware_data_does_not_erase_valid_panel_and_frame_rows(self):
        params = self.base_params()
        params.pop("hysl")
        door_id = create_door(self.db, params, sales_order_id=2)

        result = self.service.generate(door_id, self.user)

        operation_codes = {item["operation_code"] for item in result["components"]}
        self.assertIn("PANEL", operation_codes)
        self.assertIn("FRAME_ASSEMBLY", operation_codes)
        self.assertTrue(any(item["field_path"] == "hysl" for item in result["warnings"]))
        self.assertGreater(result["blocking_warning_count"], 0)


if __name__ == "__main__":
    unittest.main()
