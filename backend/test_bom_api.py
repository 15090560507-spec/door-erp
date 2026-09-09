"""Whole-order BOM workbench API contract tests."""

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
from bom_generation_service import BomGenerationService
from fulfillment_database import FulfillmentDatabase, fulfillment_now
from test_bom_generation import create_door


class BomApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="door-bom-api-")
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

    def tearDown(self):
        bom_routes.fulfillment_db = self.original_db
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def params():
        return {
            "product_name": "不锈钢镀铜门",
            "door_type": "单门",
            "frame_process": "新工艺",
            "dw": 1000,
            "dh": 2200,
            "material": "304不锈钢",
            "ys": "紫铜色",
            "fw_left_str": "55/75",
            "fw_right_str": "55/75",
            "fw_top_str": "85/100",
            "threshold_type": "高低槛",
            "th_str": "45/60",
            "sel_hys": "半钢暗合页",
            "hysl": "3个/扇",
            "sel_bz": "木箱",
        }

    def create_generated_door(self, sales_order_id: int = 1) -> tuple[int, dict]:
        door_id = create_door(self.db, self.params(), sales_order_id=sales_order_id)
        result = BomGenerationService(self.db).generate(door_id, self.user)
        return door_id, result

    def add_material(self, code: str = "MAT-TEST", unit: str = "件") -> int:
        now = fulfillment_now()
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """INSERT INTO inventory_materials(
                       code, name, category, specification, unit, material_type,
                       created_at, updated_at
                   ) VALUES (?, '测试物料', '门体', '', ?, '原材料', ?, ?)""",
                (code, unit, now, now),
            )
            return int(cursor.lastrowid)

    def test_workbench_and_detail_expose_groups_versions_and_frame_state(self):
        door_id, _result = self.create_generated_door()

        response = self.client.get("/api/bom/workbench")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["total"], 1)
        self.assertGreaterEqual(payload["summary"]["missing_data"], 1)
        self.assertEqual(payload["items"][0]["door_unit_id"], door_id)

        response = self.client.get(f"/api/bom/door-units/{door_id}")
        self.assertEqual(response.status_code, 200)
        detail = response.json()["bom"]
        self.assertEqual(detail["version"], 1)
        self.assertTrue(any(group["code"] == "frame" for group in detail["groups"]))
        self.assertEqual(detail["version_history"][0]["version"], 1)
        self.assertTrue(detail["frame_status"]["can_calculate"])

    def test_draft_update_and_verify_only_allow_unambiguous_matched_rows(self):
        door_id, generated = self.create_generated_door(sales_order_id=2)
        panel = next(row for row in generated["components"] if row["operation_code"] == "PANEL")
        material_id = self.add_material()

        response = self.client.put(
            f"/api/bom/door-units/{door_id}/draft",
            json={"items": [{
                "id": panel["id"],
                "material_id": material_id,
                "planned_quantity": 2,
                "unit": "件",
                "remark": "人工核对板材",
            }]},
        )
        self.assertEqual(response.status_code, 200)
        updated = next(row for row in response.json()["bom"]["rows"] if row["id"] == panel["id"])
        self.assertEqual(updated["match_status"], "已匹配")
        self.assertEqual(updated["verification_status"], "待核验")

        response = self.client.post(
            f"/api/bom/door-units/{door_id}/verify",
            json={"item_ids": [panel["id"]]},
        )
        self.assertEqual(response.status_code, 200)
        verified = next(row for row in response.json()["bom"]["rows"] if row["id"] == panel["id"])
        self.assertEqual(verified["verification_status"], "已核验")

        unmatched = next(row for row in generated["components"] if row["id"] != panel["id"])
        response = self.client.post(
            f"/api/bom/door-units/{door_id}/verify",
            json={"item_ids": [unmatched["id"]]},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "BOM_ITEM_NOT_MATCHED")
        self.assertEqual(response.json()["detail"]["bom_item_id"], unmatched["id"])

    def test_publish_blocks_incomplete_rows_then_freezes_and_creates_new_version(self):
        door_id, _generated = self.create_generated_door(sales_order_id=3)

        response = self.client.post(f"/api/bom/door-units/{door_id}/publish", json={})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "BOM_PUBLISH_BLOCKED")

        BomGenerationService(self.db).recalculate_frame(door_id, self.user)
        material_id = self.add_material(code="MAT-ALL")
        with self.db.transaction() as connection:
            connection.execute(
                """UPDATE fulfillment_components
                   SET material_id=?, match_status='已匹配', verification_status='已核验',
                       planned_quantity=CASE WHEN planned_quantity<=0 THEN 1 ELSE planned_quantity END,
                       quantity=CASE WHEN quantity<=0 THEN 1 ELSE quantity END,
                       unit='件'
                   WHERE technical_package_id=(
                       SELECT id FROM fulfillment_technical_packages
                       WHERE door_unit_id=? ORDER BY version DESC LIMIT 1
                   )""",
                (material_id, door_id),
            )

        response = self.client.post(f"/api/bom/door-units/{door_id}/publish", json={"remark": "确认下料"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["bom"]["status"], "已确认")

        response = self.client.put(
            f"/api/bom/door-units/{door_id}/draft",
            json={"items": []},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "BOM_VERSION_FROZEN")

        response = self.client.post(
            f"/api/bom/door-units/{door_id}/new-version",
            json={"reason": "客户调整门板", "impact_note": "重新核对材料"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["bom"]["version"], 2)
        self.assertEqual(response.json()["bom"]["status"], "草稿")

        response = self.client.get(f"/api/bom/door-units/{door_id}/diff/1/2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["diff"]["from_version"], 1)
        self.assertEqual(response.json()["diff"]["to_version"], 2)


if __name__ == "__main__":
    unittest.main()
