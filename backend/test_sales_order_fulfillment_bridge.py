"""Confirmed sales orders provision one idempotent fulfillment order."""

import os
import shutil
import sys
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import fulfillment_routes
import sales_order_routes
from auth import get_current_user
from fulfillment_database import FulfillmentDatabase
from sales_order_database import SalesOrderDatabase
from sales_order_fulfillment_service import SalesOrderFulfillmentService


class FakeTasks:
    def __init__(self):
        self.tasks = {
            "drawing-1": self._task("drawing-1", "单门", 1000, 2200),
            "drawing-2": self._task("drawing-2", "对开门", 1800, 2600),
        }

    @staticmethod
    def _task(task_id: str, door_type: str, width: int, height: int):
        return {
            "id": task_id,
            "status": "已通过",
            "customer": "测试客户",
            "project": "别墅项目",
            "door_type": door_type,
            "size": f"{width} x {height}",
            "params": {
                "dhdw": "测试客户",
                "gdmc": "别墅项目",
                "product_name": "不锈钢镀铜门",
                "door_type": door_type,
                "dw": width,
                "dh": height,
                "sel_kx": "左开",
                "sel_nk": "内开",
                "ys": "紫铜色",
            },
            "confirm_status": "未确认",
        }

    def get_task(self, task_id):
        task = self.tasks.get(task_id)
        return dict(task) if task else None

    def load_all_tasks(self):
        return [dict(task) for task in self.tasks.values()]

    def update_task(self, task_id, changes):
        self.tasks[task_id].update(changes)


class FakeQuotes:
    def find_groups_by_task(self, task_id):
        if task_id not in {"drawing-1", "drawing-2"}:
            return []
        task = 1 if task_id == "drawing-1" else 2
        width = 1000 if task == 1 else 1800
        height = 2200 if task == 1 else 2600
        return [{
            "quote_id": task,
            "quote_date": "2026-09-08",
            "updated_at": "2026-09-08T08:00:00Z",
            "customer_name": "测试客户",
            "project_name": "别墅项目",
            "group_index": 0,
            "group": {
                "groupName": f"第{task}樘",
                "taskId": task_id,
                "items": [{
                    "productName": "不锈钢镀铜门",
                    "width": width,
                    "height": height,
                    "unit": "套",
                    "quantity": 1,
                    "unitPrice": 2000 + task * 500,
                }],
            },
        }]


class FailingFulfillmentDatabase:
    def create_from_sales_order(self, sales_order, idempotency_key, user):
        raise RuntimeError("模拟履约数据库暂时不可用")


class SalesOrderFulfillmentBridgeTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="sales-order-bridge-")
        self.tasks = FakeTasks()
        self.quotes = FakeQuotes()
        self.sales_db = SalesOrderDatabase(os.path.join(self.temp_dir, "sales.db"))
        self.fulfillment_db = FulfillmentDatabase(
            os.path.join(self.temp_dir, "fulfillment.db"),
            os.path.join(self.temp_dir, "files"),
        )

        self.previous_sales_db = sales_order_routes.sales_order_db
        self.previous_tasks = sales_order_routes.task_repository
        self.previous_quotes = sales_order_routes.quote_db
        self.previous_provisioner = sales_order_routes.fulfillment_provisioner
        self.previous_fulfillment_db = fulfillment_routes.fulfillment_db
        self.previous_fulfillment_tasks = fulfillment_routes.task_repository
        self.previous_fulfillment_sales = fulfillment_routes.sales_order_repository

        sales_order_routes.configure_sales_order_database(self.sales_db)
        sales_order_routes.configure_task_repository(self.tasks)
        sales_order_routes.quote_db = self.quotes
        sales_order_routes.configure_fulfillment_provisioner(
            SalesOrderFulfillmentService(self.sales_db, self.fulfillment_db)
        )
        fulfillment_routes.fulfillment_db = self.fulfillment_db
        fulfillment_routes.configure_task_repository(self.tasks)
        fulfillment_routes.configure_sales_order_repository(self.sales_db)

        app = FastAPI()
        app.include_router(sales_order_routes.router)
        app.include_router(fulfillment_routes.router)
        app.dependency_overrides[get_current_user] = lambda: {"uid": "A", "name": "销售小A"}
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        sales_order_routes.configure_sales_order_database(self.previous_sales_db)
        sales_order_routes.configure_task_repository(self.previous_tasks)
        sales_order_routes.quote_db = self.previous_quotes
        sales_order_routes.configure_fulfillment_provisioner(self.previous_provisioner)
        fulfillment_routes.fulfillment_db = self.previous_fulfillment_db
        fulfillment_routes.configure_task_repository(self.previous_fulfillment_tasks)
        fulfillment_routes.configure_sales_order_repository(self.previous_fulfillment_sales)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def payload():
        return {
            "order_date": "2026-09-08",
            "customer_name": "测试客户",
            "project_name": "别墅项目",
            "delivery_address": "杭州",
            "salesperson": "销售小A",
            "delivery_date": "2026-10-01",
            "payment_template": "定金50%，发货前付清",
            "remark": "整单自动下达",
            "discount_amount": 0,
            "lines": [
                {"task_id": "drawing-1", "quantity": 2},
                {"task_id": "drawing-2", "quantity": 1},
            ],
            "payment_nodes": [{"name": "定金", "due_percent": 50}],
        }

    def create_and_confirm(self):
        response = self.client.post("/api/sales-orders", json=self.payload())
        self.assertEqual(response.status_code, 201, response.text)
        order = response.json()["order"]
        response = self.client.post(f"/api/sales-orders/{order['id']}/confirm")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["order"]

    def test_confirmation_creates_one_fulfillment_order_and_three_door_units(self):
        order = self.create_and_confirm()
        self.assertEqual(order["provisioning_status"], "ready")
        self.assertIsNotNone(order["fulfillment_order_id"])

        response = self.client.get("/api/fulfillment/orders")
        self.assertEqual(response.status_code, 200, response.text)
        rows = response.json()["orders"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sales_order_id"], order["id"])

        detail = self.client.get(f"/api/fulfillment/orders/{rows[0]['id']}").json()["order"]
        doors = detail["door_units"]
        self.assertEqual(len(doors), 3)
        self.assertEqual(len({door["production_no"] for door in doors}), 3)
        self.assertEqual(
            [(door["source_task_id"], door["source_quantity_index"]) for door in doors],
            [("drawing-1", 1), ("drawing-1", 2), ("drawing-2", 1)],
        )
        self.assertEqual(len({door["sales_order_line_id"] for door in doors}), 2)

    def test_retry_is_idempotent(self):
        order = self.create_and_confirm()
        response = self.client.post(f"/api/sales-orders/{order['id']}/retry-provisioning")
        self.assertEqual(response.status_code, 200, response.text)
        retried = response.json()["order"]
        self.assertEqual(retried["fulfillment_order_id"], order["fulfillment_order_id"])

        fulfillment = self.client.get(f"/api/fulfillment/orders/{retried['fulfillment_order_id']}").json()["order"]
        self.assertEqual(len(fulfillment["door_units"]), 3)

    def test_failed_provisioning_keeps_confirmed_order_and_can_retry(self):
        response = self.client.post("/api/sales-orders", json=self.payload())
        self.assertEqual(response.status_code, 201, response.text)
        order_id = response.json()["order"]["id"]

        sales_order_routes.configure_fulfillment_provisioner(
            SalesOrderFulfillmentService(self.sales_db, FailingFulfillmentDatabase())
        )
        response = self.client.post(f"/api/sales-orders/{order_id}/confirm")
        self.assertEqual(response.status_code, 200, response.text)
        failed = response.json()["order"]
        self.assertEqual(failed["status"], "confirmed")
        self.assertEqual(failed["provisioning_status"], "failed")
        self.assertIn("模拟履约数据库暂时不可用", failed["provisioning_error"])

        sales_order_routes.configure_fulfillment_provisioner(
            SalesOrderFulfillmentService(self.sales_db, self.fulfillment_db)
        )
        response = self.client.post(f"/api/sales-orders/{order_id}/retry-provisioning")
        self.assertEqual(response.status_code, 200, response.text)
        retried = response.json()["order"]
        self.assertEqual(retried["provisioning_status"], "ready")

        fulfillment = self.client.get(f"/api/fulfillment/orders/{retried['fulfillment_order_id']}").json()["order"]
        self.assertEqual(len(fulfillment["door_units"]), 3)


if __name__ == "__main__":
    unittest.main()
