"""Hierarchical BOM semantics for drawing-driven door parts."""

import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from bom_generation_service import BomGenerationService
from fulfillment_database import FulfillmentDatabase
from inventory_service import InventoryService
import test_bom_generation as bom_test_helpers


class HierarchicalBomTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="door-hierarchical-bom-")
        self.db = FulfillmentDatabase(
            os.path.join(self.temp_dir, "fulfillment.db"),
            os.path.join(self.temp_dir, "files"),
        )
        self.service = BomGenerationService(self.db)
        self.user = {"uid": "A", "name": "销售小A"}

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generated_door_has_frame_and_leaf_assembly_hierarchy(self) -> None:
        params = bom_test_helpers.BomGenerationTest.base_params()
        params.update({
            "skeleton_spec": "40x20镀锌骨架",
            "skeleton_quantity": 12,
            "skeleton_unit": "米",
        })
        door_id = bom_test_helpers.create_door(self.db, params)

        result = self.service.generate(door_id, self.user)
        by_code = {row["operation_code"]: row for row in result["components"]}

        expected = {
            "FRAME_ASSEMBLY",
            "FRAME_SKIN",
            "FRAME_SKELETON",
            "DOOR_ASSEMBLY",
            "PANEL_SKIN",
            "PANEL_SKELETON",
        }
        self.assertTrue(expected.issubset(by_code))
        self.assertEqual(by_code["FRAME_SKIN"]["parent_id"], by_code["FRAME_ASSEMBLY"]["id"])
        self.assertEqual(by_code["FRAME_SKELETON"]["parent_id"], by_code["FRAME_ASSEMBLY"]["id"])
        self.assertEqual(by_code["PANEL_SKIN"]["parent_id"], by_code["DOOR_ASSEMBLY"]["id"])
        self.assertEqual(by_code["PANEL_SKELETON"]["parent_id"], by_code["DOOR_ASSEMBLY"]["id"])

    def test_drawing_driven_rows_do_not_require_material_matching(self) -> None:
        params = bom_test_helpers.BomGenerationTest.base_params()
        door_id = bom_test_helpers.create_door(self.db, params, sales_order_id=2)

        result = self.service.generate(door_id, self.user)
        self_made = [
            row for row in result["components"]
            if row["item_kind"] in {"assembly", "manufactured_part"}
        ]

        self.assertGreaterEqual(len(self_made), 6)
        self.assertTrue(all(row["procurement_mode"] == "make" for row in self_made))
        self.assertTrue(all(row["material_id"] is None for row in self_made))
        self.assertTrue(all(row["match_status"] == "无需物料" for row in self_made))
        self.assertTrue(all(row["verification_status"] == "已核验" for row in self_made))

    def test_frame_trim_manufacturing_modes_generate_only_the_selected_structure(self) -> None:
        params = bom_test_helpers.BomGenerationTest.base_params()
        params["has_outer"] = True
        door_id = bom_test_helpers.create_door(self.db, params, sales_order_id=3)

        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE fulfillment_technical_packages SET frame_trim_mode='integrated_skeleton' WHERE door_unit_id=?",
                (door_id,),
            )
        result = self.service.generate(door_id, self.user)
        operation_codes = {row["operation_code"] for row in result["components"]}
        self.assertIn("FRAME_TRIM_ASSEMBLY", operation_codes)
        self.assertIn("FRAME_TRIM_SKELETON", operation_codes)
        self.assertIn("FRAME_SKIN", operation_codes)
        self.assertIn("TRIM_SKIN", operation_codes)
        self.assertNotIn("TRIM_SKELETON", operation_codes)

        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE fulfillment_technical_packages SET frame_trim_mode='fully_integrated' WHERE door_unit_id=?",
                (door_id,),
            )
        result = self.service.generate(door_id, self.user)
        operation_codes = {row["operation_code"] for row in result["components"]}
        self.assertIn("FRAME_TRIM_SKIN", operation_codes)
        self.assertIn("FRAME_TRIM_SKELETON", operation_codes)
        self.assertNotIn("FRAME_SKIN", operation_codes)
        self.assertNotIn("TRIM_SKIN", operation_codes)

    def test_custom_components_move_through_semi_finished_without_material_master(self) -> None:
        params = bom_test_helpers.BomGenerationTest.base_params()
        door_id = bom_test_helpers.create_door(self.db, params, sales_order_id=4)
        result = self.service.generate(door_id, self.user)
        parts = [row for row in result["components"] if row["item_kind"] == "manufactured_part"]

        for part in parts:
            self.db.component_inbound(
                door_id,
                SimpleNamespace(
                    component_id=part["id"], quantity=float(part["planned_quantity"]),
                    warehouse="半成品仓", location="本单暂存区", remark="测试入库",
                ),
                self.user,
            )

        door = self.db.get_door_unit(door_id)
        self.assertTrue(door["component_inventory"])
        self.assertTrue(all(row["available_quantity"] == row["planned_quantity"] for row in door["component_inventory"]))
        overview = InventoryService(self.db.inventory_db).warehouse_overview()
        self.assertEqual(len([row for row in overview["tracked_items"] if row["warehouse_type"] == "半成品"]), len(parts))

        _, changed = self.db.issue_assembly_components(door_id, "测试拼装领用", self.user)
        self.assertEqual(changed, len(parts))
        door = self.db.get_door_unit(door_id)
        self.assertTrue(all(row["available_quantity"] == 0 for row in door["component_inventory"]))


if __name__ == "__main__":
    unittest.main()
