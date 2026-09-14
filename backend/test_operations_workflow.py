"""Route snapshot, workforce assignment, and monthly payroll contracts."""

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
from auth import get_current_user
from bom_generation_service import BomGenerationService
from fulfillment_database import FulfillmentDatabase, fulfillment_now
from test_bom_generation import BomGenerationTest, create_door
from work_package_service import WorkPackageService


class OperationsWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="door-operations-")
        self.db = FulfillmentDatabase(
            os.path.join(self.temp_dir, "fulfillment.db"),
            os.path.join(self.temp_dir, "files"),
        )
        self.original_db = operations_routes.fulfillment_db
        operations_routes.fulfillment_db = self.db
        self.user = {"uid": "A", "name": "销售小A", "role": "录入员"}
        app = FastAPI()
        app.include_router(operations_routes.router)
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        operations_routes.fulfillment_db = self.original_db
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_employee(self, employee_no="E001", base_salary=5000):
        response = self.client.post("/api/operations/employees", json={
            "employee_no": employee_no,
            "name": "测试员工",
            "team": "一组",
            "role_name": "拼装",
            "capabilities": ["ASSEMBLY"],
            "work_center": "总装区",
            "wage_type": "综合",
            "base_salary": base_salary,
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["employee"]

    def test_route_snapshot_is_not_changed_when_template_is_edited(self):
        door_id = create_door(self.db, BomGenerationTest.base_params(), sales_order_id=31)
        BomGenerationService(self.db).generate(door_id, self.user)
        package = self.db.fetch_one(
            "SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
            (door_id,),
        )
        now = fulfillment_now()
        with self.db.transaction() as conn:
            WorkPackageService().generate_for_package(conn, door_id=door_id, package_id=package["id"], now=now)
        before = self.db.fetch_one(
            "SELECT route_snapshot_json FROM fulfillment_work_packages WHERE technical_package_id=? AND operation_code='ASSEMBLY'",
            (package["id"],),
        )["route_snapshot_json"]

        template = self.client.get("/api/operations/route-templates").json()["templates"][0]
        template["name"] = "更新后的标准工艺"
        template["steps"][0]["name"] = "更新后的技术准备"
        response = self.client.put(f"/api/operations/route-templates/{template['id']}", json=template)
        self.assertEqual(response.status_code, 200, response.text)

        after = self.db.fetch_one(
            "SELECT route_snapshot_json FROM fulfillment_work_packages WHERE technical_package_id=? AND operation_code='ASSEMBLY'",
            (package["id"],),
        )["route_snapshot_json"]
        self.assertEqual(before, after)

    def test_assignment_and_payroll_lock_workflow(self):
        employee = self.create_employee()
        door_id = create_door(self.db, BomGenerationTest.base_params(), sales_order_id=32)
        response = self.client.put(f"/api/operations/door-units/{door_id}/assembly-assignment", json={
            "owner_id": employee["id"],
            "collaborator_ids": [],
            "work_center": "总装区",
            "planned_date": "2026-09-20",
            "note": "测试拼装分配",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["door_unit"]["assembly_owner"]["employee_no"], "E001")

        now = "2026-09-15T10:00:00"
        with self.db.transaction() as conn:
            package_id = conn.execute(
                "SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=? ORDER BY version DESC LIMIT 1",
                (door_id,),
            ).fetchone()["id"]
            cursor = conn.execute(
                """INSERT INTO fulfillment_work_packages(
                       technical_package_id, door_unit_id, name, category, route,
                       acquisition_method, executor_uid, quantity, actual_quantity, unit,
                       piece_rate, status, completed_at, updated_at
                   ) VALUES (?, ?, '总装配', '装配', '总装配', '内部加工', 'E001', 1, 1,
                             '樘', 120, '已完成', ?, ?)""",
                (package_id, door_id, now, now),
            )
            conn.execute(
                """INSERT INTO fulfillment_payroll_drafts(
                       door_unit_id, work_package_id, employee_uid, work_name,
                       quantity, piece_rate, amount, created_at
                   ) VALUES (?, ?, 'E001', '总装配', 1, 120, 120, ?)""",
                (door_id, cursor.lastrowid, now),
            )

        response = self.client.post("/api/operations/payroll/calculate", json={"month": "2026-09"})
        self.assertEqual(response.status_code, 200, response.text)
        period = response.json()["period"]
        self.assertEqual(period["entries"][0]["payable_amount"], 5120)
        entry_id = period["entries"][0]["id"]

        response = self.client.post("/api/operations/payroll/calculate", json={"month": "2026-09"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["period"]["entries"]), 1)
        response = self.client.get(f"/api/operations/payroll/{period['id']}")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["period"]["entries"][0]["payable_amount"], 5120)

        response = self.client.put(f"/api/operations/payroll/entries/{entry_id}", json={"allowance": 200})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["period"]["entries"][0]["payable_amount"], 5320)

        period_id = period["id"]
        for status in ("待审核", "已审批", "已锁定"):
            response = self.client.put(f"/api/operations/payroll/{period_id}/status", json={"status": status})
            self.assertEqual(response.status_code, 200, response.text)
        response = self.client.put(f"/api/operations/payroll/entries/{entry_id}", json={"allowance": 300})
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
