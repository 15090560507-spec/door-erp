"""Personnel current-work aggregation contracts."""

import os
import shutil
import sys
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import operations_routes
import test_bom_generation
from auth import get_current_user
from fulfillment_database import FulfillmentDatabase, fulfillment_now
from test_bom_generation import create_door


class PersonnelWorkTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="door-personnel-work-")
        self.db = FulfillmentDatabase(
            os.path.join(self.temp_dir, "fulfillment.db"),
            os.path.join(self.temp_dir, "files"),
        )
        self.original_db = operations_routes.fulfillment_db
        operations_routes.fulfillment_db = self.db
        app = FastAPI()
        app.include_router(operations_routes.router)
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "A", "name": "销售小A", "role": "录入员",
        }
        self.client = TestClient(app)

    def tearDown(self):
        operations_routes.fulfillment_db = self.original_db
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_employee(self, employee_no: str, name: str, team: str) -> dict:
        response = self.client.post("/api/operations/employees", json={
            "employee_no": employee_no,
            "name": name,
            "team": team,
            "role_name": "生产",
            "capabilities": [],
            "work_center": team,
            "wage_type": "综合",
            "base_salary": 0,
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["employee"]

    def create_package(self, door_id: int) -> int:
        existing = self.db.fetch_one(
            "SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
            (door_id,),
        )
        if existing:
            return int(existing["id"])
        now = fulfillment_now()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO fulfillment_technical_packages(
                       door_unit_id, version, product_snapshot_json, created_by,
                       created_at, updated_at
                   ) VALUES (?, 1, '{}', 'A', ?, ?)""",
                (door_id, now, now),
            )
            return int(cursor.lastrowid)

    def add_work(self, package_id: int, door_id: int, employee: dict, name: str, status: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO fulfillment_work_packages(
                       technical_package_id, door_unit_id, name, executor_uid,
                       employee_id, quantity, unit, status, updated_at
                   ) VALUES (?, ?, ?, ?, ?, 1, '项', ?, ?)""",
                (package_id, door_id, name, employee["employee_no"], employee["id"], status, fulfillment_now()),
            )

    def test_groups_active_employees_and_returns_only_highest_priority_current_work(self):
        cutter = self.create_employee("E001", "张师傅", "下料组")
        idle = self.create_employee("E002", "李师傅", "下料组")
        assembler = self.create_employee("E003", "王师傅", "装配组")
        door_a = create_door(self.db, test_bom_generation.BomGenerationTest.base_params(), sales_order_id=91)
        door_b = create_door(self.db, test_bom_generation.BomGenerationTest.base_params(), sales_order_id=92)
        package_a = self.create_package(door_a)
        package_b = self.create_package(door_b)
        self.add_work(package_b, door_b, cutter, "门扇骨架·备料", "待排单")
        self.add_work(package_a, door_a, cutter, "门扇骨架·下料", "进行中")
        self.add_work(package_a, door_a, idle, "已结束工作", "已完成")
        self.add_work(package_b, door_b, assembler, "整门·拼装", "待质检")

        response = self.client.get("/api/operations/personnel-work")

        self.assertEqual(response.status_code, 200, response.text)
        departments = response.json()["departments"]
        self.assertEqual([item["name"] for item in departments], ["下料组", "装配组"])
        workers = {item["employee_no"]: item for group in departments for item in group["employees"]}
        self.assertEqual(workers["E001"]["status"], "工作中")
        self.assertEqual(workers["E001"]["current_work"]["operation_name"], "门扇骨架·下料")
        self.assertEqual(workers["E001"]["current_work"]["production_no"], self.db.fetch_one("SELECT production_no FROM fulfillment_door_units WHERE id=?", (door_a,))["production_no"])
        self.assertEqual(workers["E002"]["status"], "空闲")
        self.assertIsNone(workers["E002"]["current_work"])
        self.assertEqual(workers["E003"]["current_work"]["status"], "待质检")
        for worker in workers.values():
            self.assertNotIn("next_task", worker)
            self.assertNotIn("workload", worker)
            self.assertNotIn("payroll", worker)


if __name__ == "__main__":
    unittest.main()
