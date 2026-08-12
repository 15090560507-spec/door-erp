"""Minimal, retryable ERPNext bridge for Door ERP production releases."""

from __future__ import annotations

import io
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

from config import (
    ERPNEXT_API_KEY,
    ERPNEXT_API_SECRET,
    ERPNEXT_BASE_URL,
    ERPNEXT_COMPANY,
    ERPNEXT_CUSTOMER_GROUP,
    ERPNEXT_ENABLED,
    ERPNEXT_ITEM_GROUP,
    ERPNEXT_PUBLIC_URL,
    ERPNEXT_TERRITORY,
    ERPNEXT_TIMEOUT_SECONDS,
    ERPNEXT_VERIFY_TLS,
)
from production_database import ProductionDatabase, production_now


class ERPNextBridgeError(RuntimeError):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


def bridge_status() -> Dict[str, Any]:
    configured = bool(ERPNEXT_BASE_URL and ERPNEXT_API_KEY and ERPNEXT_API_SECRET)
    return {
        "enabled": ERPNEXT_ENABLED,
        "configured": configured,
        "public_url": ERPNEXT_PUBLIC_URL,
        "message": "ERPNext 已就绪" if ERPNEXT_ENABLED and configured else "ERPNext 尚未配置或未启用",
    }


def _safe_error(text: str) -> str:
    value = re.sub(r"(?i)(token|secret|api[_ -]?key)\s*[:=]\s*[^\s,;]+", r"\1=***", text or "")
    value = re.sub(r"(?i)Authorization\s*[:=]\s*[^\s,;]+", "Authorization=***", value)
    return value.replace("\n", " ").strip()[:800]


class ERPNextClient:
    def __init__(self) -> None:
        if not ERPNEXT_ENABLED:
            raise ERPNextBridgeError("ERPNext 集成未启用，请在服务器 .env 设置 ERPNEXT_ENABLED=true")
        if not ERPNEXT_BASE_URL or not ERPNEXT_API_KEY or not ERPNEXT_API_SECRET:
            raise ERPNextBridgeError("ERPNext 配置不完整，请检查 Base URL、API Key 和 API Secret")
        self.base_url = ERPNEXT_BASE_URL
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(ERPNEXT_TIMEOUT_SECONDS),
            headers={"Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}"},
            follow_redirects=False,
            verify=ERPNEXT_VERIFY_TLS,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "ERPNextClient":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ERPNextBridgeError("ERPNext 请求超时，请稍后重试") from exc
        except httpx.HTTPError as exc:
            raise ERPNextBridgeError(f"无法连接 ERPNext：{_safe_error(str(exc))}") from exc
        if response.status_code >= 400:
            try:
                body = response.json()
                detail = body.get("exception") or body.get("message") or body.get("_server_messages") or json.dumps(body, ensure_ascii=False)
            except ValueError:
                detail = response.text
            raise ERPNextBridgeError(f"ERPNext 返回 {response.status_code}：{_safe_error(str(detail))}", response.status_code)
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"text": response.text}

    def list_resource(self, doctype: str, filters: list[list[Any]], fields: list[str]) -> list[Dict[str, Any]]:
        payload = self.request(
            "GET",
            f"/api/resource/{quote(doctype, safe='')}",
            params={"filters": json.dumps(filters, ensure_ascii=False), "fields": json.dumps(fields), "limit_page_length": 1},
        )
        return list(payload.get("data") or [])

    def get_or_first(self, doctype: str, configured_name: str) -> str:
        if configured_name:
            return configured_name
        rows = self.list_resource(doctype, [], ["name"])
        if not rows or not rows[0].get("name"):
            raise ERPNextBridgeError(f"ERPNext 中未找到可用的“{doctype}”基础资料")
        return str(rows[0]["name"])

    def get_or_create_customer(self, customer_name: str) -> str:
        rows = self.list_resource("Customer", [["Customer", "customer_name", "=", customer_name]], ["name", "customer_name"])
        if rows:
            return str(rows[0]["name"])
        document = self.request("POST", "/api/resource/Customer", json={
            "customer_name": customer_name,
            "customer_type": "Company",
            "customer_group": self.get_or_first("Customer Group", ERPNEXT_CUSTOMER_GROUP),
            "territory": self.get_or_first("Territory", ERPNEXT_TERRITORY),
        }).get("data") or {}
        if not document.get("name"):
            raise ERPNextBridgeError("ERPNext 未返回新建客户编号")
        return str(document["name"])

    def get_or_create_item(self, item_code: str, item_name: str) -> str:
        rows = self.list_resource("Item", [["Item", "item_code", "=", item_code]], ["name", "item_code"])
        if rows:
            return str(rows[0]["name"])
        document = self.request("POST", "/api/resource/Item", json={
            "item_code": item_code,
            "item_name": item_name,
            "item_group": self.get_or_first("Item Group", ERPNEXT_ITEM_GROUP),
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "is_sales_item": 1,
            "is_purchase_item": 0,
            "description": f"Door ERP 冻结生产订单专用成品：{item_name}",
        }).get("data") or {}
        if not document.get("name"):
            raise ERPNextBridgeError("ERPNext 未返回新建成品物料编号")
        return str(document["name"])

    def get_or_create_sales_order(self, order_no: str, customer: str, item_code: str, due_date: str) -> str:
        rows = self.list_resource("Sales Order", [["Sales Order", "po_no", "=", order_no]], ["name", "po_no"])
        if rows:
            return str(rows[0]["name"])
        delivery_date = due_date or datetime.now().strftime("%Y-%m-%d")
        document = self.request("POST", "/api/resource/Sales Order", json={
            "customer": customer,
            "company": self.get_or_first("Company", ERPNEXT_COMPANY),
            "transaction_date": datetime.now().strftime("%Y-%m-%d"),
            "delivery_date": delivery_date,
            "po_no": order_no,
            "remarks": f"来源：Door ERP 冻结生产订单 {order_no}",
            "items": [{"item_code": item_code, "qty": 1, "uom": "Nos", "delivery_date": delivery_date}],
        }).get("data") or {}
        if not document.get("name"):
            raise ERPNextBridgeError("ERPNext 未返回新建销售订单编号")
        return str(document["name"])

    def upload_file(self, sales_order: str, filename: str, content: bytes, content_type: str) -> None:
        self.request(
            "POST",
            "/api/method/upload_file",
            data={"doctype": "Sales Order", "docname": sales_order, "is_private": "1"},
            files={"file": (filename, io.BytesIO(content), content_type)},
        )


def _order_item_name(order: Dict[str, Any]) -> str:
    params = order.get("task_snapshot", {}).get("params", {}) if isinstance(order.get("task_snapshot"), dict) else {}
    parts = [str(params.get(key) or "").strip() for key in ("material", "product_name", "door_type", "zmks", "fmks")]
    return " ".join(part for part in parts if part) or order["order_no"]


def _snapshot_payload(order: Dict[str, Any]) -> bytes:
    payload = {
        "door_erp_order_no": order["order_no"],
        "source_task_id": order.get("source_task_id", ""),
        "source_revision": order.get("source_revision", ""),
        "customer": order.get("customer", ""),
        "project": order.get("project", ""),
        "due_date": order.get("due_date", ""),
        "sales_note": order.get("sales_note", ""),
        "task_snapshot": order.get("task_snapshot", {}),
        "quote_snapshot": order.get("quote_snapshot"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _public_sales_order_url(sales_order: str) -> str:
    if not ERPNEXT_PUBLIC_URL:
        return ""
    return f"{ERPNEXT_PUBLIC_URL}/app/sales-order/{quote(sales_order, safe='')}"


def sync_order_to_erpnext(database: ProductionDatabase, order_id: int) -> Dict[str, Any]:
    order = database.get_order(order_id)
    if not order:
        raise ERPNextBridgeError("生产订单不存在")
    idempotency_key = f"door-erp:{order['order_no']}:{order.get('source_revision', '')}"
    sync = database.ensure_erpnext_sync(order_id, idempotency_key)
    database.update_erpnext_sync(order_id, status="同步中", attempts=int(sync.get("attempts") or 0) + 1, last_error="")
    try:
        with ERPNextClient() as client:
            customer = client.get_or_create_customer(str(order["customer"]))
            item_code = f"DOOR-{order['order_no']}"
            item = client.get_or_create_item(item_code, _order_item_name(order))
            sales_order = client.get_or_create_sales_order(order["order_no"], customer, item, str(order.get("due_date") or ""))

            dxf_file = (Path(database.files_dir) / str(order["dxf_path"])).resolve()
            if dxf_file.is_file():
                client.upload_file(sales_order, f"{order['order_no']}_终审冻结图.dxf", dxf_file.read_bytes(), "application/dxf")
            client.upload_file(sales_order, f"{order['order_no']}_门参数.json", _snapshot_payload(order), "application/json")
            snapshot = order.get("task_snapshot") if isinstance(order.get("task_snapshot"), dict) else {}
            drawing_path = snapshot.get("drawing_img_b64") if isinstance(snapshot, dict) else ""
            if isinstance(drawing_path, str) and drawing_path:
                preview_file = (Path(database.files_dir) / drawing_path).resolve()
                if preview_file.is_file():
                    client.upload_file(sales_order, f"{order['order_no']}_图纸预览.png", preview_file.read_bytes(), "image/png")

        url = _public_sales_order_url(sales_order)
        database.update_erpnext_sync(
            order_id,
            status="已同步",
            erpnext_customer=customer,
            erpnext_item_code=item,
            erpnext_sales_order=sales_order,
            erpnext_url=url,
            last_error="",
            last_synced_at=production_now(),
        )
    except ERPNextBridgeError as exc:
        database.update_erpnext_sync(order_id, status="同步失败", last_error=str(exc))
    return database.get_erpnext_sync(order_id) or {}
