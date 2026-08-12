"""End-to-end checks for requirements, reservations, purchasing and issuing."""

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


def main():
    global PASSED, FAILED
    temp_dir = tempfile.mkdtemp(prefix="door-production-material-test-")
    original_main_db = main_module.production_db
    original_router_db = production_routes.production_db
    test_db = ProductionDatabase(
        db_path=os.path.join(temp_dir, "production.db"),
        files_dir=os.path.join(temp_dir, "files"),
    )
    main_module.production_db = test_db
    production_routes.production_db = test_db
    uid = "prod_material_all"
    users = main_module.user_db.load_all_users()
    users.pop(uid, None)
    main_module.user_db.save(users)
    main_module.user_db.add_or_update_user(uid, "production123", "录入员", uid, permissions=[])

    try:
        client = TestClient(main_module.app)
        now = "2026-08-05T10:00:00+08:00"
        material_id = test_db.execute(
            """
            INSERT INTO production_materials(
                code, name, category, specification, unit, created_at, updated_at
            ) VALUES ('MAT-001', '不锈钢板', '板材', '1.0x1220x2440', '张', ?, ?)
            """,
            (now, now),
        )
        order = test_db.create_order(
            source_task_id="material-flow-task",
            source_revision="v1",
            customer="流程客户",
            project="流程项目",
            due_date="2026-08-30",
            sales_note="",
            include_quote=False,
            task_snapshot={"status": "已通过", "params": {}},
            quote_snapshot=None,
            dxf_bytes=b"0\nSECTION\n0\nEOF\n",
            created_by=uid,
        )

        response = client.put(
            f"/api/production/orders/{order['id']}/bom",
            json={"items": [{
                "material_id": material_id,
                "category": "板材",
                "name": "不锈钢板",
                "specification": "1.0x1220x2440",
                "quantity": 5,
                "unit": "张",
                "supply_type": "外购",
            }]},
            headers=headers(uid),
        )
        check("普通登录用户可保存 BOM", response.status_code == 200, response.text)

        test_db.execute(
            """
            INSERT INTO production_inventory_transactions(
                material_id, transaction_type, quantity, unit, operator_uid, created_at
            ) VALUES (?, '其他入库', 2, '张', ?, ?)
            """,
            (material_id, uid, now),
        )
        response = client.post(
            f"/api/production/orders/{order['id']}/bom/publish", headers=headers(uid)
        )
        check("BOM 发布成功", response.status_code == 200, response.text)

        response = client.get(
            f"/api/production/orders/{order['id']}/material-requirement", headers=headers(uid)
        )
        requirement = response.json().get("requirement") if response.status_code == 200 else None
        item = requirement["items"][0] if requirement else None
        check(
            "发布后自动预留现有库存并计算缺口",
            bool(item)
            and float(item["reserved_quantity"]) == 2
            and float(item["shortage_quantity"]) == 3
            and requirement["status"] == "部分备料",
            response.text,
        )

        response = client.post(
            "/api/production/material-requirements/purchase",
            json={
                "supplier": "测试供应商",
                "expected_date": "2026-08-10",
                "items": [{"requirement_item_id": item["id"]}],
            },
            headers=headers(uid),
        )
        purchase_id = response.json().get("purchase_id") if response.status_code == 200 else None
        check("缺料可一键转采购单", bool(purchase_id), response.text)

        purchases = client.get("/api/production/purchases", headers=headers(uid)).json()["purchases"]
        purchase_item = next(row for row in purchases if row["id"] == purchase_id)["items"][0]
        response = client.post(
            f"/api/production/purchases/{purchase_id}/receive",
            json={
                "items": [{
                    "item_id": purchase_item["id"],
                    "quantity": 3,
                    "warehouse_location": "A-01",
                }],
                "remark": "全部到货",
            },
            headers=headers(uid),
        )
        check("采购到货可入库", response.status_code == 200, response.text)

        requirement = client.get(
            f"/api/production/orders/{order['id']}/material-requirement", headers=headers(uid)
        ).json()["requirement"]
        item = requirement["items"][0]
        inventory = client.get("/api/production/inventory", headers=headers(uid)).json()["balances"][0]
        check(
            "到货后自动补齐预留且库存三数正确",
            requirement["status"] == "已备料"
            and float(item["reserved_quantity"]) == 5
            and float(inventory["on_hand"]) == 5
            and float(inventory["reserved"]) == 5
            and float(inventory["available"]) == 0,
            str({"requirement": requirement, "inventory": inventory}),
        )

        response = client.post(
            "/api/production/inventory/transactions",
            json={
                "material_id": material_id,
                "transaction_type": "报废",
                "quantity": 1,
                "unit": "张",
            },
            headers=headers(uid),
        )
        check("手工出库不能占用已预留库存", response.status_code == 400, response.text)

        response = client.post(
            "/api/production/inventory/transactions",
            json={
                "material_id": material_id,
                "order_id": order["id"],
                "transaction_type": "生产领料",
                "quantity": 1,
                "unit": "张",
            },
            headers=headers(uid),
        )
        check("生产领料不能绕过订单物料需求", response.status_code == 400, response.text)

        response = client.post(
            f"/api/production/orders/{order['id']}/materials/issue",
            json={"items": [{"requirement_item_id": item["id"], "quantity": 5}]},
            headers=headers(uid),
        )
        check(
            "生产领料扣减现存并释放预留",
            response.status_code == 200
            and response.json()["requirement"]["status"] == "已领料",
            response.text,
        )

        inventory = client.get("/api/production/inventory", headers=headers(uid)).json()["balances"][0]
        check(
            "领料后现存和预留均归零",
            float(inventory["on_hand"]) == 0 and float(inventory["reserved"]) == 0,
            str(inventory),
        )

        response = client.post(
            f"/api/production/orders/{order['id']}/materials/return",
            json={"items": [{"requirement_item_id": item["id"], "quantity": 1}]},
            headers=headers(uid),
        )
        check(
            "生产退料重新入库并优先回补本单预留",
            response.status_code == 200
            and float(response.json()["requirement"]["items"][0]["reserved_quantity"]) == 1,
            response.text,
        )
    finally:
        users = main_module.user_db.load_all_users()
        users.pop(uid, None)
        main_module.user_db.save(users)
        main_module.production_db = original_main_db
        production_routes.production_db = original_router_db
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\nResult: {PASSED} passed, {FAILED} failed")
    raise SystemExit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
