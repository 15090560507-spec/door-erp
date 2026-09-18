"""Sales-order draft, confirmation, occupancy, and snapshot tests."""

import os
import shutil
import sys
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import sales_order_routes
import fulfillment_routes
from auth import get_current_user
from fulfillment_database import FulfillmentDatabase
from sales_order_database import SalesOrderDatabase


class FakeTasks:
    def __init__(self):
        self.tasks = {
            "task-1": {
                "id": "task-1",
                "status": "已通过",
                "approved_at": "2026-09-05T09:00:00+08:00",
                "customer": "测试客户",
                "project": "别墅项目",
                "door_type": "单门",
                "size": "1000 x 2200",
                "params": {
                    "dhdw": "测试客户",
                    "gdmc": "别墅项目",
                    "product_name": "不锈钢镀铜门",
                    "door_type": "单门",
                    "dw": 1000,
                    "dh": 2200,
                    "sel_kx": "左开",
                    "sel_nk": "内开",
                    "ys": "紫铜色",
                },
                "quote_status": "未报价",
                "confirm_status": "未确认",
            },
            "task-2": {
                "id": "task-2",
                "status": "已通过",
                "customer": "另一客户",
                "project": "另一项目",
                "door_type": "对开门",
                "size": "1800 x 2600",
                "params": {"dw": 1800, "dh": 2600},
            },
            "task-pending": {
                "id": "task-pending",
                "status": "待终审",
                "customer": "测试客户",
                "project": "别墅项目",
                "door_type": "子母门",
                "params": {"dw": 1300, "dh": 2400},
            },
        }

    def get_task(self, task_id):
        task = self.tasks.get(task_id)
        return dict(task) if task else None

    def load_all_tasks(self):
        return [dict(task) for task in self.tasks.values()]

    def update_task(self, task_id, changes):
        self.tasks[task_id].update(changes)


class FakeQuotes:
    def __init__(self):
        self.enabled = False
        self.alternates = False
        self.unit_price = 1000

    def find_groups_by_task(self, task_id):
        if not self.enabled or task_id != "task-1":
            return []
        current = {
            "quote_id": 7,
            "quote_date": "2026-09-05",
            "updated_at": "2026-09-05T08:00:00Z",
            "customer_name": "测试客户",
            "project_name": "别墅项目",
            "group_index": 0,
            "group": {
                "groupName": "入户门",
                "taskId": "task-1",
                "items": [{
                    "productName": "不锈钢镀铜门",
                    "width": 1000,
                    "height": 2200,
                    "unit": "m2",
                    "unitPrice": self.unit_price,
                }],
            },
        }
        if not self.alternates:
            return [current]
        latest = dict(current)
        latest.update({"quote_id": 9, "quote_date": "2026-09-07", "updated_at": "2026-09-07T10:00:00Z"})
        latest["group"] = dict(current["group"])
        latest["group"]["items"] = [dict(current["group"]["items"][0], unitPrice=1200)]
        return [current, latest]


class SalesOrderApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="door-sales-orders-")
        self.tasks = FakeTasks()
        self.quotes = FakeQuotes()
        self.previous_db = sales_order_routes.sales_order_db
        self.previous_tasks = sales_order_routes.task_repository
        self.previous_quotes = sales_order_routes.quote_db
        self.previous_fulfillment_db = fulfillment_routes.fulfillment_db
        self.previous_fulfillment_tasks = fulfillment_routes.task_repository
        self.previous_fulfillment_sales = fulfillment_routes.sales_order_repository
        database = SalesOrderDatabase(os.path.join(self.temp_dir, "sales.db"))
        sales_order_routes.configure_sales_order_database(
            database
        )
        sales_order_routes.configure_task_repository(self.tasks)
        sales_order_routes.quote_db = self.quotes
        fulfillment_routes.fulfillment_db = FulfillmentDatabase(
            os.path.join(self.temp_dir, "fulfillment.db"),
            os.path.join(self.temp_dir, "files"),
        )
        fulfillment_routes.configure_task_repository(self.tasks)
        fulfillment_routes.configure_sales_order_repository(database)
        app = FastAPI()
        app.include_router(sales_order_routes.router)
        app.include_router(fulfillment_routes.router)
        app.dependency_overrides[get_current_user] = lambda: {"uid": "A", "name": "销售小A"}
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        sales_order_routes.configure_sales_order_database(self.previous_db)
        sales_order_routes.configure_task_repository(self.previous_tasks)
        sales_order_routes.quote_db = self.previous_quotes
        fulfillment_routes.fulfillment_db = self.previous_fulfillment_db
        fulfillment_routes.configure_task_repository(self.previous_fulfillment_tasks)
        fulfillment_routes.configure_sales_order_repository(self.previous_fulfillment_sales)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def payload(self):
        return {
            "order_date": "2026-09-05",
            "customer_name": "测试客户",
            "project_name": "别墅项目",
            "delivery_address": "杭州",
            "salesperson": "销售小A",
            "delivery_date": "2026-10-01",
            "payment_template": "定金50%，发货前付清",
            "remark": "",
            "discount_amount": 0,
            "lines": [{"task_id": "task-1", "quantity": 1}],
            "payment_nodes": [
                {"name": "定金", "due_amount": 1100},
                {"name": "发货款", "due_amount": 1100},
            ],
        }

    def test_draft_can_be_unquoted_but_confirmation_requires_quote(self):
        response = self.client.post("/api/sales-orders", json=self.payload())
        self.assertEqual(response.status_code, 201, response.text)
        order = response.json()["order"]
        self.assertEqual(order["status"], "draft")
        self.assertIsNone(order["lines"][0]["quote_id"])

        candidates = self.client.get("/api/sales-orders/candidates").json()["candidates"]
        self.assertNotIn("task-1", {item["task_id"] for item in candidates})

        response = self.client.post(f"/api/sales-orders/{order['id']}/confirm")
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("报价", response.json()["detail"]["message"])

    def test_candidates_only_return_approved_drawings_and_support_filters(self):
        response = self.client.get(
            "/api/sales-orders/candidates",
            params={
                "customer": "测试客户",
                "project": "别墅项目",
                "door_type": "单门",
                "width": 1000,
                "height": 2200,
                "quote_state": "未报价",
                "final_review_from": "2026-09-05",
                "final_review_to": "2026-09-05",
                "page": 1,
                "page_size": 20,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual([item["task_id"] for item in data["candidates"]], ["task-1"])
        self.assertEqual(data["page"], 1)
        self.assertNotIn("task-pending", {item["task_id"] for item in data["candidates"]})

    def test_latest_quote_is_default_and_alternates_are_preserved(self):
        self.quotes.enabled = True
        self.quotes.alternates = True
        response = self.client.get("/api/sales-orders/candidates")
        self.assertEqual(response.status_code, 200, response.text)
        candidate = next(item for item in response.json()["candidates"] if item["task_id"] == "task-1")
        self.assertEqual([choice["quote_id"] for choice in candidate["quotes"]], [9, 7])

        response = self.client.post("/api/sales-orders", json=self.payload())
        self.assertEqual(response.status_code, 201, response.text)
        line = response.json()["order"]["lines"][0]
        self.assertEqual(line["quote_id"], 9)
        self.assertEqual(line["unit_price"], 2640)

    def test_quote_item_rounding_matches_candidate_and_order_total(self):
        self.quotes.enabled = True
        self.quotes.unit_price = 1001
        candidate = next(
            item for item in self.client.get("/api/sales-orders/candidates").json()["candidates"]
            if item["task_id"] == "task-1"
        )
        self.assertEqual(candidate["quotes"][0]["amount"], 2202)

        payload = self.payload()
        payload["payment_nodes"] = [{"name": "全款", "due_amount": 2202}]
        response = self.client.post("/api/sales-orders", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        order = response.json()["order"]
        self.assertEqual(order["total_amount"], 2202)
        self.assertEqual(order["charge_lines"][0]["amount"], 2202)

    def test_manual_line_can_confirm_without_drawing_or_quote(self):
        payload = self.payload()
        payload["lines"] = [{
            "source_type": "manual",
            "product_name": "庭院门",
            "door_type": "平开门",
            "width": 3200,
            "height": 1800,
            "quantity": 2,
            "unit": "樘",
            "unit_price": 6800,
            "remark": "现场复尺后生产",
        }]
        payload["payment_nodes"] = [
            {"name": "定金", "due_amount": 6800},
            {"name": "发货款", "due_amount": 6800},
        ]
        response = self.client.post("/api/sales-orders", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        order = response.json()["order"]
        self.assertEqual(order["lines"][0]["source_type"], "manual")
        self.assertEqual(order["total_amount"], 13600)

        response = self.client.post(f"/api/sales-orders/{order['id']}/confirm")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["order"]["status"], "confirmed")

    def test_draft_line_technical_details_round_trip(self):
        technical_details = {
            "trim_type": "外包套",
            "main_door_style": "四方格",
            "lock_type": "指纹锁",
            "handle": "黑色长拉手",
            "hinge": "隐藏铰链",
            "material": "304不锈钢",
            "item_remark": "门扇内加防火板",
        }
        payload = self.payload()
        payload["lines"] = [{
            "source_type": "manual",
            "product_name": "庭院门",
            "door_type": "平开门",
            "width": 3200,
            "height": 1800,
            "quantity": 1,
            "unit": "樘",
            "unit_price": 6800,
            "remark": "",
            "technical_details": technical_details,
        }]
        payload["payment_nodes"] = [{"name": "全款", "due_amount": 6800}]

        response = self.client.post("/api/sales-orders", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        order = response.json()["order"]
        self.assertEqual(order["lines"][0]["technical_details"], technical_details)

        reloaded = self.client.get(f"/api/sales-orders/{order['id']}")
        self.assertEqual(reloaded.status_code, 200, reloaded.text)
        self.assertEqual(
            reloaded.json()["order"]["lines"][0]["technical_details"],
            technical_details,
        )

    def test_manual_line_validation_returns_line_and_field(self):
        payload = self.payload()
        payload["lines"] = [{
            "source_type": "manual",
            "product_name": "庭院门",
            "width": 0,
            "height": 1800,
            "quantity": 1,
            "unit_price": 6800,
        }]
        response = self.client.post("/api/sales-orders", json=payload)
        self.assertEqual(response.status_code, 422, response.text)
        detail = response.json()["detail"]
        self.assertEqual(detail["errors"][0]["line_no"], 1)
        self.assertEqual(detail["errors"][0]["field"], "width")

    def test_quote_snapshot_confirmation_and_cancel_release_task(self):
        self.quotes.enabled = True
        response = self.client.post("/api/sales-orders", json=self.payload())
        self.assertEqual(response.status_code, 201, response.text)
        order = response.json()["order"]
        self.assertEqual(order["total_amount"], 2200)
        self.assertEqual(order["lines"][0]["quote_id"], 7)
        self.assertTrue(order["lines"][0]["drawing_revision"])

        response = self.client.post(f"/api/sales-orders/{order['id']}/confirm")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["order"]["status"], "confirmed")
        self.assertEqual(self.tasks.tasks["task-1"]["confirm_status"], "已确认")

        response = self.client.post(f"/api/sales-orders/{order['id']}/cancel", json={"reason": "客户取消"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.tasks.tasks["task-1"]["confirm_status"], "未确认")
        candidates = self.client.get("/api/sales-orders/candidates").json()["candidates"]
        self.assertIn("task-1", {item["task_id"] for item in candidates})

    def test_rejects_mixed_customers(self):
        payload = self.payload()
        payload["lines"].append({"task_id": "task-2", "quantity": 1})
        response = self.client.post("/api/sales-orders", json=payload)
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("同一客户", response.json()["detail"])

    def test_confirmed_order_and_approved_drawing_enter_production_release(self):
        self.tasks.tasks["task-1"]["status"] = "已通过"
        self.quotes.enabled = True
        payload = self.payload()
        payload["lines"][0]["quantity"] = 2
        payload["payment_nodes"] = [
            {"name": "定金", "due_amount": 2200},
            {"name": "发货款", "due_amount": 2200},
        ]
        response = self.client.post("/api/sales-orders", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        order = response.json()["order"]

        pending = self.client.get("/api/fulfillment/pending-release").json()["tasks"]
        self.assertEqual(pending, [])

        response = self.client.post(f"/api/sales-orders/{order['id']}/confirm")
        self.assertEqual(response.status_code, 200, response.text)
        pending = self.client.get("/api/fulfillment/pending-release").json()["tasks"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["door_count"], 2)
        self.assertEqual(pending[0]["sales_order_no"], order["order_no"])

        response = self.client.post(
            "/api/fulfillment/orders/from-task/task-1",
            json={"door_count": 9, "due_date": "", "owner_uid": "leader-a", "sales_note": "正式下达"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["order"]["door_units"]), 2)
        refreshed = self.client.get(f"/api/sales-orders/{order['id']}").json()["order"]
        self.assertEqual(refreshed["status"], "fulfilling")
        response = self.client.post(f"/api/sales-orders/{order['id']}/cancel", json={"reason": "误操作"})
        self.assertEqual(response.status_code, 409, response.text)

    def test_source_change_requires_resave_before_confirmation(self):
        self.quotes.enabled = True
        response = self.client.post("/api/sales-orders", json=self.payload())
        order = response.json()["order"]
        self.tasks.tasks["task-1"]["status"] = "已通过"
        detail = self.client.get(f"/api/sales-orders/{order['id']}").json()["order"]
        self.assertFalse(detail["lines"][0]["source_changed"])
        self.tasks.tasks["task-1"]["params"]["dw"] = 1100

        detail = self.client.get(f"/api/sales-orders/{order['id']}").json()["order"]
        self.assertTrue(detail["lines"][0]["source_changed"])
        response = self.client.post(f"/api/sales-orders/{order['id']}/confirm")
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("图纸已变更", response.json()["detail"]["message"])

    def test_tm_numbering_charge_lines_and_amount_payment_validation(self):
        self.quotes.enabled = True
        first = self.client.post("/api/sales-orders", json=self.payload()).json()["order"]
        self.assertEqual(first["order_no"], "TM2600001")
        self.assertEqual(first["lines"][0]["line_code"], "TM2600001-01")
        self.assertEqual(len(first["charge_lines"]), 1)
        self.assertEqual(first["charge_lines"][0]["product_name"], "不锈钢镀铜门")
        self.assertEqual(first["charge_lines"][0]["door_line_no"], 1)

        payload = self.payload()
        payload["lines"] = [{
            "source_type": "manual",
            "product_name": "庭院门",
            "door_type": "平开门",
            "width": 3000,
            "height": 1800,
            "quantity": 1,
            "unit_price": 5000,
            "remark": "",
        }]
        payload["payment_nodes"] = [{"name": "定金", "due_amount": 5000}]
        second = self.client.post("/api/sales-orders", json=payload).json()["order"]
        self.assertEqual(second["order_no"], "TM2600002")

        invalid = self.payload()
        invalid["lines"] = [{
            "source_type": "manual",
            "product_name": "测试门",
            "width": 1000,
            "height": 2200,
            "quantity": 1,
            "unit_price": 2200,
            "remark": "",
        }]
        invalid["payment_nodes"] = [{"name": "定金", "due_amount": 1000}]
        order = self.client.post("/api/sales-orders", json=invalid).json()["order"]
        response = self.client.post(f"/api/sales-orders/{order['id']}/confirm")
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("必须等于订单总额", response.json()["detail"]["message"])

    def test_manual_order_supports_separate_door_and_trim_charge_lines(self):
        payload = self.payload()
        payload["lines"] = [{
            "source_type": "manual",
            "product_name": "不锈钢镀铜门",
            "door_type": "对开门",
            "width": 1800,
            "height": 2600,
            "quantity": 1,
            "unit_price": 0,
            "remark": "技术参数与价格项目分开维护",
        }]
        payload["charge_lines"] = [
            {
                "door_line_no": 1,
                "source_type": "manual",
                "item_type": "主门",
                "product_name": "不锈钢镀铜门",
                "specification": "1800 × 2600 mm",
                "quantity": 1,
                "unit": "樘",
                "unit_price": 5000,
            },
            {
                "door_line_no": 1,
                "source_type": "manual",
                "item_type": "门套",
                "product_name": "不锈钢镀铜门套",
                "specification": "外包套",
                "quantity": 2.5,
                "unit": "m2",
                "unit_price": 400,
            },
        ]
        payload["payment_nodes"] = [
            {"name": "定金", "due_amount": 2000},
            {"name": "发货款", "due_amount": 4000},
        ]

        response = self.client.post("/api/sales-orders", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        order = response.json()["order"]
        self.assertEqual(order["subtotal"], 6000)
        self.assertEqual(order["total_amount"], 6000)
        self.assertEqual(order["lines"][0]["amount"], 6000)
        self.assertEqual(order["lines"][0]["unit_price"], 6000)
        self.assertEqual(
            [(item["item_type"], item["amount"]) for item in order["charge_lines"]],
            [("主门", 5000), ("门套", 1000)],
        )

        response = self.client.post(f"/api/sales-orders/{order['id']}/confirm")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["order"]["status"], "confirmed")

    def test_numbering_resets_for_new_year(self):
        payload = self.payload()
        payload["lines"] = [{
            "source_type": "manual",
            "product_name": "庭院门",
            "width": 3000,
            "height": 1800,
            "quantity": 1,
            "unit_price": 5000,
            "remark": "",
        }]
        payload["payment_nodes"] = [{"name": "全款", "due_amount": 5000}]
        first = self.client.post("/api/sales-orders", json=payload).json()["order"]
        payload["order_date"] = "2027-01-02"
        second = self.client.post("/api/sales-orders", json=payload).json()["order"]
        self.assertEqual(first["order_no"], "TM2600001")
        self.assertEqual(second["order_no"], "TM2700001")


if __name__ == "__main__":
    unittest.main()
