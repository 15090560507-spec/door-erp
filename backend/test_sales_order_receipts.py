"""Actual receipt allocation and shipment finance-gate tests."""

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


class SalesOrderReceiptTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="sales-receipts-")
        self.sales_db = SalesOrderDatabase(os.path.join(self.temp_dir, "sales.db"))
        self.fulfillment_db = FulfillmentDatabase(
            os.path.join(self.temp_dir, "fulfillment.db"),
            os.path.join(self.temp_dir, "files"),
        )
        self.previous_sales_db = sales_order_routes.sales_order_db
        self.previous_fulfillment_db = fulfillment_routes.fulfillment_db
        self.previous_fulfillment_sales = fulfillment_routes.sales_order_repository
        sales_order_routes.configure_sales_order_database(self.sales_db)
        fulfillment_routes.fulfillment_db = self.fulfillment_db
        fulfillment_routes.configure_sales_order_repository(self.sales_db)
        app = FastAPI()
        app.include_router(sales_order_routes.router)
        app.include_router(fulfillment_routes.router)
        app.dependency_overrides[get_current_user] = lambda: {"uid": "A", "name": "销售小A"}
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        sales_order_routes.configure_sales_order_database(self.previous_sales_db)
        fulfillment_routes.fulfillment_db = self.previous_fulfillment_db
        fulfillment_routes.configure_sales_order_repository(self.previous_fulfillment_sales)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_order(self, task_id: str, total: float):
        order = self.sales_db.create(
            {
                "order_date": "2026-09-14", "customer_name": "同一客户", "project_name": task_id,
                "delivery_date": "2026-10-01", "discount_amount": 0,
                "payment_nodes": [{"name": "定金", "due_amount": total / 2}, {"name": "发货款", "due_amount": total / 2}],
            },
            [{
                "task_id": task_id, "product_name": "不锈钢镀铜门", "door_type": "单门",
                "width": 1000, "height": 2200, "quantity": 1, "drawing_status": "已通过",
                "drawing_snapshot": {"params": {"dw": 1000, "dh": 2200}},
            }],
            [{"door_line_no": 1, "product_name": "不锈钢镀铜门", "quantity": 1, "unit": "樘", "unit_price": total}],
            "A",
        )
        return self.sales_db.confirm(order["id"], "A")

    def test_receipt_allocates_across_orders_and_reversal_restores_debt(self):
        first = self.create_order("drawing-1", 1000)
        second = self.create_order("drawing-2", 2000)
        response = self.client.post("/api/sales-orders/receipts", json={
            "receipt_date": "2026-09-14", "amount": 1800, "payment_method": "银行转账",
            "reference": "BANK-001", "remark": "同批定金",
            "allocations": [{"order_id": first["id"], "amount": 800}, {"order_id": second["id"], "amount": 1000}],
        })
        self.assertEqual(response.status_code, 201, response.text)
        receipt = response.json()["receipt"]
        self.assertEqual(len(receipt["allocations"]), 2)
        self.assertEqual(self.sales_db.payment_summary(first["id"])["unpaid_amount"], 200)
        self.assertEqual(self.sales_db.payment_summary(second["id"])["unpaid_amount"], 1000)

        detail = self.sales_db.get(first["id"])
        self.assertEqual(detail["payment_nodes"][0]["status"], "paid")
        self.assertEqual(detail["payment_nodes"][1]["status"], "partial")

        response = self.client.post(f"/api/sales-orders/receipts/{receipt['id']}/reverse", json={"reason": "银行退回"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.sales_db.payment_summary(first["id"])["paid_amount"], 0)
        self.assertEqual(self.sales_db.payment_summary(second["id"])["paid_amount"], 0)

    def test_sales_order_debt_blocks_shipping_and_authorization_keeps_debt(self):
        order = self.create_order("drawing-shipping", 3000)
        fulfillment = self.fulfillment_db.create_from_sales_order(order, "shipping-test", {"uid": "A", "name": "销售小A"})
        door_id = fulfillment["door_units"][0]["id"]
        with self.fulfillment_db.transaction() as connection:
            connection.execute("UPDATE fulfillment_door_units SET status='已入库待发货' WHERE id=?", (door_id,))

        response = self.client.post(f"/api/fulfillment/door-units/{door_id}/shipments", json={"required_payment": 0})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("未收款", response.json()["detail"])

        response = self.client.post(f"/api/fulfillment/door-units/{door_id}/shipments", json={
            "required_payment": 0, "carrier": "自送", "authorization_reason": "客户约定月末支付", "authorized_by": "销售小A",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("欠款", response.json()["message"])
        self.assertEqual(self.sales_db.payment_summary(order["id"])["unpaid_amount"], 3000)
        shipment = response.json()["door_unit"]["shipments"][0]
        self.assertEqual(shipment["authorized"], 1)
        self.assertEqual(shipment["required_payment"], 3000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
