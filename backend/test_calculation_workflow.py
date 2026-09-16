"""Calculation version workflow between confirmed BOM and production execution."""

import os
import shutil
import sys
import tempfile
import unittest


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from fulfillment_database import FulfillmentDatabase
from fulfillment_models import CalculationDraftUpdate, CalculationItemInput
from test_bom_generation import create_door


class CalculationWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="door-calculation-")
        self.db = FulfillmentDatabase(
            os.path.join(self.temp_dir, "fulfillment.db"),
            os.path.join(self.temp_dir, "files"),
        )
        self.user = {"uid": "A", "name": "销售小A"}
        self.door_id = create_door(self.db, {
            "product_name": "不锈钢镀铜门", "door_type": "单门",
            "dw": 1000, "dh": 2200,
        }, sales_order_id=901)
        package = self.db.latest_bom_package(self.door_id)
        with self.db.transaction() as connection:
            connection.execute("DELETE FROM fulfillment_components WHERE technical_package_id=?", (package["id"],))
            connection.execute(
                """INSERT INTO fulfillment_components(
                       technical_package_id, name, category, specification, quantity, unit,
                       acquisition_method, sequence_no, line_no, group_code,
                       theoretical_quantity, planned_quantity, source_type, match_status,
                       verification_status, operation_code, item_kind, procurement_mode
                   ) VALUES
                       (?, '门框外皮', '门框', '304/0.8mm', 1, '套', '内部加工', 1, 1,
                        'frame', 1, 1, 'manual', '无需物料', '已核验', 'FRAME_SKIN',
                        'manufactured_part', 'make'),
                       (?, '门扇骨架', '骨架', '40x20', 1, '套', '内部加工', 2, 2,
                        'skeleton', 1, 1, 'manual', '无需物料', '已核验', 'PANEL_SKELETON',
                        'manufactured_part', 'make')""",
                (package["id"], package["id"]),
            )
            connection.execute(
                "UPDATE fulfillment_technical_packages SET generation_status='已生成' WHERE id=?",
                (package["id"],),
            )
        self.db.publish_bom(self.door_id, "确认BOM", self.user)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_calculation_is_one_to_many_and_gates_preparation(self) -> None:
        door = self.db.get_door_unit(self.door_id)
        calculation = door["calculation"]
        self.assertEqual(calculation["status"], "未算料")
        self.assertEqual(len(calculation["items"]), 2)
        self.assertEqual(door["workflow"]["current_stage"], "preparation")
        self.assertTrue(any("算料" in item for item in door["workflow"]["stages"][0]["blockers"]))

        first, second = calculation["items"]
        payload = CalculationDraftUpdate(
            remark="门框拆左右件",
            items=[
                CalculationItemInput(**{key: value for key, value in first.items() if key in CalculationItemInput.model_fields}),
                CalculationItemInput(**{key: value for key, value in second.items() if key in CalculationItemInput.model_fields}),
                CalculationItemInput(
                    component_id=first["component_id"], part_name="门框外皮右件",
                    material_specification="304/0.8mm", finished_size="右框",
                    cut_length=2200, cut_width=120, quantity=1, unit="件",
                    actual_material_quantity=0.264,
                ),
            ],
        )
        saved = self.db.update_calculation(self.door_id, payload, self.user)
        self.assertEqual(saved["status"], "算料中")
        self.assertEqual(len(saved["items"]), 3)
        self.assertEqual(
            len([item for item in saved["items"] if item["component_id"] == first["component_id"]]),
            2,
        )

        submitted = self.db.submit_calculation(self.door_id, self.user)
        self.assertEqual(submitted["status"], "待确认")
        published = self.db.publish_calculation(self.door_id, self.user)
        self.assertEqual(published["status"], "已发布")
        self.assertEqual(self.db.get_door_unit(self.door_id)["workflow"]["current_stage"], "execution")

        with self.assertRaisesRegex(RuntimeError, "已发布冻结"):
            self.db.update_calculation(self.door_id, payload, self.user)


if __name__ == "__main__":
    unittest.main()
