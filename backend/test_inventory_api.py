"""Authenticated API checks for shared inventory master data and adjustments."""

import os
import shutil
import sys
import tempfile

from fastapi.testclient import TestClient

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import inventory_routes
import main as main_module
from auth import create_token
from inventory_database import InventoryDatabase


def headers() -> dict:
    return {"Authorization": f"Bearer {create_token('admin')}"}


def main() -> None:
    temp_dir = tempfile.mkdtemp(prefix="door-inventory-api-")
    previous = inventory_routes.inventory_db
    inventory_routes.configure_inventory_database(InventoryDatabase(os.path.join(temp_dir, "inventory.db")))
    client = TestClient(main_module.app)
    passed = 0
    failed = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS {name}")
        else:
            failed += 1
            print(f"  FAIL {name} -- {detail}")

    try:
        response = client.get("/api/inventory/warehouses")
        check("未登录不能访问仓库", response.status_code == 401, response.text)

        response = client.get("/api/inventory/warehouses", headers=headers())
        warehouses = response.json().get("warehouses", [])
        raw = next((item for item in warehouses if item["code"] == "RAW"), None)
        check("登录后可查看五个公共仓库", response.status_code == 200 and len(warehouses) == 5, response.text)

        response = client.post(
            f"/api/inventory/warehouses/{raw['id']}/locations",
            headers=headers(),
            json={"code": "A-01", "name": "板材一区"},
        )
        location = response.json().get("location", {})
        check("可创建仓库库位", response.status_code == 201 and location.get("code") == "A-01", response.text)

        material_payload = {
            "code": "PLATE-08",
            "name": "0.8mm 铜板",
            "category": "板材",
            "specification": "0.8mm",
            "unit": "张",
            "material_type": "原材料",
            "default_warehouse_id": raw["id"],
            "default_location_id": location["id"],
            "minimum_stock": 2,
        }
        response = client.post("/api/inventory/materials", headers=headers(), json=material_payload)
        material = response.json().get("material", {})
        check("可创建物料档案", response.status_code == 201 and material.get("code") == "PLATE-08", response.text)

        supplier_payload = {
            "code": "SUP-001", "name": "测试板材供应商", "short_name": "测试供应商",
            "contact_name": "王师傅", "phone": "13800000000", "default_tax_rate": 13,
            "settlement_method": "月结", "payment_days": 30, "default_lead_days": 5,
            "supply_category": "板材", "remark": "",
        }
        response = client.post("/api/inventory/suppliers", headers=headers(), json=supplier_payload)
        supplier = response.json().get("supplier", {})
        check("可创建供应商档案", response.status_code == 201 and supplier.get("code") == "SUP-001", response.text)

        relation_payload = {
            "supplier_id": supplier.get("id"), "material_id": material.get("id"),
            "supplier_item_code": "TB-08", "supplier_item_name": "0.8铜板",
            "purchase_specification": "1220x2440", "purchase_unit": "张", "conversion_rate": 1,
            "tax_inclusive_price": 680, "tax_rate": 13, "minimum_order_quantity": 5,
            "lead_days": 3, "is_preferred": True, "remark": "常用",
        }
        response = client.post("/api/inventory/supplier-items", headers=headers(), json=relation_payload)
        relation = response.json().get("supplier_item", {})
        check("可建立供应商与商品供货关系", response.status_code == 201 and relation.get("is_preferred") == 1, response.text)

        response = client.get(f"/api/inventory/supplier-items?material_id={material.get('id')}", headers=headers())
        relations = response.json().get("supplier_items", [])
        check("商品可反查首选供应商和采购价", response.status_code == 200 and len(relations) == 1 and relations[0].get("tax_inclusive_price") == 680, response.text)

        response = client.post("/api/inventory/materials", headers=headers(), json=material_payload)
        check("重复物料编码返回409", response.status_code == 409, response.text)

        response = client.post(
            "/api/inventory/adjustments",
            headers=headers(),
            json={
                "remark": "期初盘点",
                "items": [{
                    "material_id": material["id"], "warehouse_id": raw["id"],
                    "location_id": location["id"], "quantity": 10, "unit": "张",
                }],
            },
        )
        adjustment = response.json().get("adjustment", {})
        check("盘点先形成草稿", response.status_code == 201 and adjustment.get("status") == "草稿", response.text)

        response = client.post(f"/api/inventory/adjustments/{adjustment['id']}/confirm", headers=headers())
        check("确认盘点后入账", response.status_code == 200 and response.json()["adjustment"]["status"] == "已确认", response.text)

        response = client.post(f"/api/inventory/adjustments/{adjustment['id']}/confirm", headers=headers())
        check("重复确认盘点返回409", response.status_code == 409, response.text)

        response = client.get("/api/inventory/balances?q=铜板", headers=headers())
        balances = response.json().get("balances", [])
        check("库存总览可查询余额", response.status_code == 200 and len(balances) == 1 and balances[0]["on_hand"] == 10, response.text)
    finally:
        inventory_routes.configure_inventory_database(previous)
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\nInventory API tests: {passed} PASS, {failed} FAIL")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
