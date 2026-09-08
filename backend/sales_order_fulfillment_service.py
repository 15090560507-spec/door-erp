"""Idempotent bridge from confirmed sales orders to door-unit fulfillment."""

from __future__ import annotations

from typing import Any, Dict


class SalesOrderFulfillmentService:
    def __init__(self, sales_order_db: Any, fulfillment_db: Any):
        self.sales_order_db = sales_order_db
        self.fulfillment_db = fulfillment_db

    def provision(self, order_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
        order = self.sales_order_db.get(order_id)
        if not order:
            raise LookupError("订单不存在")
        if order.get("status") not in {"confirmed", "fulfilling"}:
            raise RuntimeError("只有已确认订单可以生成履约门樘")
        if order.get("provisioning_status") == "ready" and order.get("fulfillment_order_id"):
            return order

        operator = str(user.get("uid") or "")
        started = self.sales_order_db.mark_provisioning_started(order_id, operator)
        idempotency_key = str(started.get("provisioning_key") or f"sales-order:{order_id}")
        try:
            fulfillment_order = self.fulfillment_db.create_from_sales_order(started, idempotency_key, user)
            fulfillment_order_id = int(fulfillment_order.get("id") or 0)
            if fulfillment_order_id <= 0:
                raise RuntimeError("履约订单创建后未返回有效ID")
        except Exception as exc:
            self.sales_order_db.mark_provisioning_failed(order_id, str(exc), operator)
            raise RuntimeError(f"门樘和BOM草稿生成失败：{exc}") from exc
        return self.sales_order_db.mark_provisioned(order_id, fulfillment_order_id, operator)
