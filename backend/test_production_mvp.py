"""Focused regression checks for the production-fulfillment MVP."""

import os
import shutil
import sys
import tempfile

from fastapi.testclient import TestClient

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import main as main_module
import production_routes
from auth import create_token
from production_database import ProductionDatabase


PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name} -- {detail}")


def headers(uid: str) -> dict:
    return {"Authorization": f"Bearer {create_token(uid)}"}


def cleanup_user(uid: str):
    users = main_module.user_db.load_all_users()
    if uid in users and uid != "admin":
        del users[uid]
        main_module.user_db.save(users)


def main():
    global PASSED, FAILED
    temp_dir = tempfile.mkdtemp(prefix="door-production-test-")
    original_main_db = main_module.production_db
    original_router_db = production_routes.production_db
    test_db = ProductionDatabase(
        db_path=os.path.join(temp_dir, "production.db"),
        files_dir=os.path.join(temp_dir, "files"),
    )
    main_module.production_db = test_db
    production_routes.production_db = test_db
    user_specs = {
        "prod_none": [],
        "prod_sales": ["production.sales"],
        "prod_tech": ["production.technical"],
        "prod_cut": ["production.cutting"],
        "prod_supply": ["production.purchase", "production.warehouse"],
    }
    for uid, permissions in user_specs.items():
        cleanup_user(uid)
        main_module.user_db.add_or_update_user(
            uid, "production123", "录入员", uid, permissions=permissions
        )

    try:
        order = test_db.create_order(
            source_task_id="approved-task-1",
            source_revision="revision-1",
            customer="测试客户",
            project="测试项目",
            due_date="2026-08-20",
            sales_note="测试生产订单",
            include_quote=False,
            task_snapshot={"status": "已通过", "params": {"door_type": "单门"}},
            quote_snapshot=None,
            dxf_bytes=b"0\nSECTION\n0\nEOF\n",
            created_by="prod_sales",
        )
        client = TestClient(main_module.app)

        response = client.get("/api/production/dashboard")
        check("未登录不能访问生产履约", response.status_code == 401, response.text)

        response = client.get("/api/production/dashboard", headers=headers("prod_none"))
        check("无生产权限用户返回 403", response.status_code == 403, response.text)

        response = client.get("/api/production/orders", headers=headers("prod_sales"))
        check(
            "销售可读取生产订单且快照未混入列表",
            response.status_code == 200
            and len(response.json().get("orders", [])) == 1
            and "task_snapshot" not in response.json()["orders"][0],
            response.text,
        )

        response = client.post(
            f"/api/production/orders/{order['id']}/copy",
            json={"reason": "生产第二樘同款门"},
            headers=headers("prod_sales"),
        )
        check(
            "销售复制生产订单会生成新单号",
            response.status_code == 200
            and response.json().get("order", {}).get("order_no") != order["order_no"],
            response.text,
        )

        bom_payload = {
            "items": [{
                "material_id": None,
                "category": "板材",
                "name": "门板不锈钢板",
                "specification": "1200x2400",
                "material": "304",
                "thickness": "1.0",
                "quantity": 2,
                "unit": "张",
                "supply_type": "自制",
                "remark": "",
            }]
        }
        response = client.put(
            f"/api/production/orders/{order['id']}/bom",
            json=bom_payload,
            headers=headers("prod_tech"),
        )
        check("技术可保存手工 BOM", response.status_code == 200, response.text)

        response = client.post(
            f"/api/production/orders/{order['id']}/bom/publish",
            headers=headers("prod_tech"),
        )
        check(
            "非空 BOM 可发布",
            response.status_code == 200 and response.json().get("status", {}).get("status") == "已发布",
            response.text,
        )

        response = client.post(
            f"/api/production/orders/{order['id']}/cutting-sheet",
            headers=headers("prod_tech"),
        )
        sheet = response.json().get("sheet") if response.status_code == 200 else None
        check(
            "已发布 BOM 可生成综合下料单且路由未被订单动作抢占",
            response.status_code == 200 and sheet and len(sheet.get("items", [])) == 1,
            response.text,
        )

        response = client.put(
            f"/api/production/orders/{order['id']}/cutting-sheet",
            json={
                "status": "下料中",
                "items": [{
                    "id": sheet["items"][0]["id"],
                    "actual_quantity": 1,
                    "cutter": "下料员",
                    "completed": False,
                    "remark": "",
                }],
            },
            headers=headers("prod_cut"),
        )
        check("下料员可启动下料", response.status_code == 200, response.text)

        response = client.post(
            f"/api/production/orders/{order['id']}/withdraw",
            json={"reason": "测试撤回"},
            headers=headers("prod_sales"),
        )
        check("下料开始后禁止直接撤回", response.status_code == 409, response.text)

        response = client.post(
            f"/api/production/orders/{order['id']}/resume",
            json={"reason": "非法恢复测试"},
            headers=headers("admin"),
        )
        check("未暂停订单不能直接恢复", response.status_code == 409, response.text)

        response = client.post(
            "/api/production/materials",
            json={"code": "TEST-001", "name": "测试板材", "unit": "张"},
            headers=headers("prod_tech"),
        )
        material_id = response.json().get("material", {}).get("id") if response.status_code == 200 else None
        check("技术可建立生产物料", response.status_code == 200 and material_id, response.text)

        response = client.post(
            "/api/production/purchases",
            json={
                "supplier": "测试供应商",
                "items": [{"material_id": material_id, "name": "测试板材", "quantity": 2, "unit": "张"}],
            },
            headers=headers("prod_supply"),
        )
        purchase_id = response.json().get("purchase_id") if response.status_code == 200 else None
        purchase = test_db.fetch_one(
            "SELECT id FROM production_purchase_items WHERE purchase_id=?", (purchase_id,)
        ) if purchase_id else None
        check("多权限用户可创建采购单", response.status_code == 200 and purchase, response.text)

        receive_payload = {
            "items": [{"item_id": purchase["id"], "quantity": 2, "warehouse_location": "A-01"}]
        }
        response = client.post(
            f"/api/production/purchases/{purchase_id}/receive",
            json=receive_payload,
            headers=headers("prod_supply"),
        )
        check("同一多权限用户可办理采购入库", response.status_code == 200, response.text)

        receive_payload["items"][0]["quantity"] = 1
        response = client.post(
            f"/api/production/purchases/{purchase_id}/receive",
            json=receive_payload,
            headers=headers("prod_supply"),
        )
        check("采购明细不能重复超量入库", response.status_code == 409, response.text)
    finally:
        main_module.production_db = original_main_db
        production_routes.production_db = original_router_db
        for uid in user_specs:
            cleanup_user(uid)
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\nPASS: {PASSED}")
    print(f"FAIL: {FAILED}")
    if FAILED:
        sys.exit(1)


if __name__ == "__main__":
    main()
