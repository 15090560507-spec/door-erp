"""Published BOM to inventory reservation and merged purchase demand tests."""

import os
import shutil
import sys
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import bom_routes
from auth import get_current_user
from fulfillment_database import FulfillmentDatabase
from inventory_service import InventoryService
from purchasing_service import PurchasingService
from test_bom_generation import create_door


class BomMaterialFlowTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="door-bom-material-flow-")
        self.db = FulfillmentDatabase(
            os.path.join(self.temp_dir, "fulfillment.db"),
            os.path.join(self.temp_dir, "files"),
        )
        self.user = {"uid": "A", "name": "销售小A", "role": "录入员"}
        self.original_db = bom_routes.fulfillment_db
        bom_routes.fulfillment_db = self.db
        app = FastAPI()
        app.include_router(bom_routes.router)
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)
        self.inventory = InventoryService(self.db.inventory_db)
        self.purchasing = PurchasingService(self.db.inventory_db)
        warehouse = next(row for row in self.inventory.list_warehouses() if row["code"] == "RAW")
        self.location = self.inventory.create_location(warehouse["id"], "BOM-01", "BOM测试区")
        self.warehouse = warehouse
        self.purchase_material = self.inventory.create_material(
            code="BOM-PLATE",
            name="BOM板材",
            category="板材",
            specification="定尺",
            unit="kg",
            material_type="原材料",
            default_warehouse_id=warehouse["id"],
            default_location_id=self.location["id"],
        )
        self.internal_material = self.inventory.create_material(
            code="BOM-INTERNAL",
            name="内部加工料",
            category="半成品",
            specification="自制",
            unit="kg",
            material_type="半成品",
            default_warehouse_id=warehouse["id"],
            default_location_id=self.location["id"],
        )
        self.inventory.post_transaction(
            material_id=self.purchase_material["id"],
            warehouse_id=warehouse["id"],
            location_id=self.location["id"],
            transaction_type="期初入库",
            quantity=2.25,
            unit="kg",
            source_type="test",
            source_id="bom-opening",
        )

    def tearDown(self):
        bom_routes.fulfillment_db = self.original_db
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def params():
        return {
            "product_name": "不锈钢镀铜门", "door_type": "单门",
            "dw": 1000, "dh": 2200, "fw_left_str": "55/75",
            "fw_right_str": "55/75", "fw_top_str": "85/100",
            "threshold_type": "高低槛", "th_str": "45/60",
            "sel_hys": "半钢暗合页", "hysl": "3个/扇",
        }

    def prepare_bom(self, sales_order_id: int, purchase_quantity: float, due_date: str) -> int:
        door_id = create_door(self.db, self.params(), sales_order_id=sales_order_id)
        package = self.db.latest_bom_package(door_id)
        with self.db.transaction() as connection:
            connection.execute("DELETE FROM fulfillment_components WHERE technical_package_id=?", (package["id"],))
            connection.execute(
                """INSERT INTO fulfillment_components(
                       technical_package_id, material_id, name, category, specification,
                       quantity, unit, acquisition_method, sequence_no, line_no, group_code,
                       theoretical_quantity, planned_quantity, source_type, match_status,
                       verification_status, operation_code
                   ) VALUES (?, ?, '采购板材', '板材', '定尺', ?, 'kg', '库存/采购',
                             1, 1, 'panel', ?, ?, 'manual', '已匹配', '已核验', 'PANEL'),
                            (?, ?, '内部加工料', '半成品', '自制', 1, 'kg', '内部加工',
                             2, 2, 'skeleton', 1, 1, 'manual', '已匹配', '已核验', 'SKELETON')""",
                (
                    package["id"], self.purchase_material["id"], purchase_quantity,
                    purchase_quantity, purchase_quantity,
                    package["id"], self.internal_material["id"],
                ),
            )
            connection.execute(
                "UPDATE fulfillment_door_units SET due_date=? WHERE id=?",
                (due_date, door_id),
            )
        return door_id

    def test_publish_is_idempotent_and_drives_traceable_shortage_and_merged_purchase(self):
        first_door = self.prepare_bom(31, 1.5, "2026-09-10")
        second_door = self.prepare_bom(32, 2.0, "2026-09-20")

        first_response = self.client.post(f"/api/bom/door-units/{first_door}/publish", json={})
        second_response = self.client.post(f"/api/bom/door-units/{second_door}/publish", json={})
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        duplicate = self.client.post(f"/api/bom/door-units/{first_door}/publish", json={})
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["idempotent"])
        self.assertEqual(
            self.db.fetch_one("SELECT COUNT(*) AS total FROM material_requirements")["total"],
            2,
        )

        first_requirement = self.db.requirement_service.get_requirement(
            self.db.fetch_one("SELECT id FROM material_requirements WHERE door_unit_id=?", (first_door,))["id"]
        )
        second_requirement = self.db.requirement_service.get_requirement(
            self.db.fetch_one("SELECT id FROM material_requirements WHERE door_unit_id=?", (second_door,))["id"]
        )
        first_purchase = next(row for row in first_requirement["items"] if row["material_id"] == self.purchase_material["id"])
        second_purchase = next(row for row in second_requirement["items"] if row["material_id"] == self.purchase_material["id"])
        self.assertEqual(first_purchase["reserved_quantity"], 1.5)
        self.assertEqual(second_purchase["reserved_quantity"], 0.75)
        self.assertEqual(second_purchase["shortage_quantity"], 1.25)
        self.assertEqual(second_purchase["door_unit_id"], second_door)
        self.assertEqual(second_purchase["component_id"], second_purchase["bom_item_id"])
        self.assertEqual(second_purchase["bom_version"], 1)

        shortages = self.purchasing.list_shortages()
        self.assertEqual(len(shortages), 1)
        self.assertEqual(shortages[0]["demand_quantity"], 1.25)
        self.assertEqual(shortages[0]["door_unit_id"], second_door)
        self.assertNotEqual(shortages[0]["material_id"], self.internal_material["id"])

        order = self.purchasing.create_order({
            "supplier": "板材供应商",
            "items": [{
                "material_id": self.purchase_material["id"],
                "quantity": 1.25,
                "unit": "kg",
                "unit_price": 10,
                "allocations": [{
                    "requirement_item_id": second_purchase["id"],
                    "quantity": 1.25,
                }],
            }],
        }, "buyer")
        allocation = order["items"][0]["allocations"][0]
        self.assertEqual(allocation["production_no"], second_requirement["production_no"])
        self.assertEqual(allocation["bom_item_id"], second_purchase["component_id"])


if __name__ == "__main__":
    unittest.main()
