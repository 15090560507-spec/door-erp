"""Regression checks for the expanded production workbench."""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import main as main_module
import production_routes
from auth import create_token
from database import TaskDatabaseManager
from production_database import ProductionDatabase


PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name} -- {detail}")


def headers(uid: str) -> dict:
    return {"Authorization": f"Bearer {create_token(uid)}"}


def cleanup_user(uid: str) -> None:
    users = main_module.user_db.load_all_users()
    if uid in users and uid != "admin":
        del users[uid]
        main_module.user_db.save(users)


def approved_task() -> dict:
    return {
        "id": "approved-workbench-1",
        "status": "已通过",
        "date": "2026-08-05",
        "review_feedback": "终审通过",
        "history": [{"action": "终审通过", "user": "总工D", "time": "2026-08-05T09:30:00+08:00"}],
        "params": {
            "dhdw": "测试订货单位",
            "gdmc": "测试项目",
            "door_type": "单门",
            "dw": 1200,
            "dh": 2400,
            "sel_kx": "右开",
            "sel_nk": "内开",
            "zzcl": "1.0mm铜",
            "zmks": "紫荆花款",
            "fmks": "竖条款",
        },
    }


def main() -> None:
    global PASSED, FAILED
    temp_dir = tempfile.mkdtemp(prefix="door-production-workbench-")
    task_file = os.path.join(temp_dir, "tasks.json")
    with open(task_file, "w", encoding="utf-8") as stream:
        json.dump([approved_task()], stream, ensure_ascii=False)

    test_task_db = TaskDatabaseManager(
        file_path=task_file,
        backup_dir=os.path.join(temp_dir, "task-backups"),
    )
    test_production_db = ProductionDatabase(
        db_path=os.path.join(temp_dir, "production.db"),
        files_dir=os.path.join(temp_dir, "production-files"),
    )
    original_main_db = main_module.production_db
    original_main_tasks = main_module.task_db
    original_router_db = production_routes.production_db
    original_router_tasks = getattr(production_routes, "task_repository", None)

    user_specs = {
        "prod_workbench_none": [],
        "prod_workbench_reader": ["production.worker"],
        "prod_workbench_sales": ["production.sales"],
        "prod_workbench_tech": ["production.technical"],
        "prod_workbench_purchase": ["production.purchase"],
        "prod_workbench_warehouse": ["production.warehouse"],
        "prod_workbench_quality": ["production.quality"],
        "prod_workbench_shipping": ["production.shipping"],
    }
    for uid, permissions in user_specs.items():
        cleanup_user(uid)
        main_module.user_db.add_or_update_user(
            uid, "production123", "录入员", uid, permissions=permissions
        )

    try:
        main_module.production_db = test_production_db
        main_module.task_db = test_task_db
        production_routes.production_db = test_production_db
        production_routes.task_repository = test_task_db
        client = TestClient(main_module.app)

        response = client.get(
            "/api/production/pending-release",
            headers=headers("prod_workbench_reader"),
        )
        rows = response.json().get("tasks", []) if response.status_code == 200 else []
        check(
            "终审通过且未下达的任务显示为待下达",
            response.status_code == 200
            and len(rows) == 1
            and rows[0].get("task_id") == "approved-workbench-1"
            and rows[0].get("status") == "待下达",
            response.text,
        )

        response = client.get(
            "/api/production/pending-release",
            headers=headers("prod_workbench_none"),
        )
        check("所有登录用户可查看待下达任务", response.status_code == 200, response.text)

        if rows:
            test_production_db.create_order(
                source_task_id=rows[0]["task_id"],
                source_revision=rows[0]["source_revision"],
                customer="测试订货单位",
                project="测试项目",
                due_date="",
                sales_note="",
                include_quote=False,
                task_snapshot=approved_task(),
                quote_snapshot=None,
                dxf_bytes=b"0\nSECTION\n0\nEOF\n",
                created_by="prod_workbench_sales",
            )

        response = client.get(
            "/api/production/pending-release",
            headers=headers("prod_workbench_reader"),
        )
        check(
            "相同终审版本下达后不再出现在待下达列表",
            response.status_code == 200 and response.json().get("tasks") == [],
            response.text,
        )

        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        seeded_orders = []
        for index, due_date in enumerate(
            [today - timedelta(days=1), today + timedelta(days=1), today + timedelta(days=10)]
        ):
            seeded_orders.append(test_production_db.create_order(
                source_task_id=f"dashboard-{index}",
                source_revision=f"dashboard-revision-{index}",
                customer=f"看板客户{index}",
                project="看板项目",
                due_date=due_date.isoformat(),
                sales_note="",
                include_quote=False,
                task_snapshot=approved_task(),
                quote_snapshot=None,
                dxf_bytes=b"0\nSECTION\n0\nEOF\n",
                created_by="prod_workbench_sales",
                direct_release=False,
            ))
        now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
        test_production_db.execute(
            """
            INSERT INTO production_schedules(
                order_id, planned_start, planned_end, producer, shortage_status,
                owner, updated_by, updated_at
            ) VALUES (?, '', '', '生产甲', '缺料', '王师傅', 'prod_workbench_sales', ?)
            """,
            (seeded_orders[1]["id"], now),
        )
        test_production_db.update_order(seeded_orders[1]["id"], {"shortage_status": "缺料"})

        response = client.get(
            "/api/production/dashboard",
            headers=headers("prod_workbench_reader"),
        )
        counts = response.json().get("counts", {}) if response.status_code == 200 else {}
        check(
            "生产总览包含待下达和交期预警",
            response.status_code == 200
            and counts.get("待下达") == 0
            and counts.get("已逾期", 0) >= 1
            and counts.get("即将到期", 0) >= 1
            and counts.get("今日下达", 0) >= 3,
            response.text,
        )

        response = client.get(
            "/api/production/orders",
            params={
                "owner": "王师傅",
                "shortage": "缺料",
                "due_from": today.isoformat(),
                "due_to": (today + timedelta(days=3)).isoformat(),
            },
            headers=headers("prod_workbench_reader"),
        )
        filtered = response.json().get("orders", []) if response.status_code == 200 else []
        check(
            "生产订单支持负责人缺料和交期组合筛选",
            response.status_code == 200
            and len(filtered) == 1
            and filtered[0].get("id") == seeded_orders[1]["id"]
            and filtered[0].get("owner") == "王师傅",
            response.text,
        )

        timeline_order = seeded_orders[1]
        response = client.get(
            f"/api/production/orders/{timeline_order['id']}/timeline",
            headers=headers("prod_workbench_reader"),
        )
        timeline = response.json().get("timeline", []) if response.status_code == 200 else []
        check(
            "生产订单时间轴返回标准化操作记录",
            response.status_code == 200
            and len(timeline) >= 1
            and timeline[0].get("title") in {"下达生产订单", "复制生产订单"},
            response.text,
        )

        response = client.get(
            f"/api/production/orders/{timeline_order['id']}/approved-dxf",
            headers=headers("prod_workbench_reader"),
        )
        check(
            "登录生产用户可下载冻结DXF",
            response.status_code == 200
            and response.content.startswith(b"0\nSECTION")
            and "attachment" in response.headers.get("content-disposition", ""),
            response.text,
        )

        response = client.get(
            f"/api/production/orders/{timeline_order['id']}/approved-dxf"
        )
        check("未登录不能下载冻结DXF", response.status_code == 401, response.text)

        order_id = timeline_order["id"]
        with test_production_db.transaction() as conn:
            material_id = conn.execute(
                """
                INSERT INTO production_materials(
                    code, name, category, specification, unit, created_at, updated_at
                ) VALUES ('WB-001', '测试板材', '板材', '1200x2400', '张', ?, ?)
                """,
                (now, now),
            ).lastrowid
            bom_item_id = conn.execute(
                """
                INSERT INTO production_bom_items(
                    order_id, material_id, category, name, specification, material,
                    thickness, quantity, unit, supply_type, remark, created_at, updated_at
                ) VALUES (?, ?, '板材', '测试板材', '1200x2400', '铜', '1.0', 2, '张', '外购', '', ?, ?)
                """,
                (order_id, material_id, now, now),
            ).lastrowid
            conn.execute(
                "UPDATE production_bom_status SET status='已发布', published_at=?, updated_at=? WHERE order_id=?",
                (now, now, order_id),
            )
            sheet_id = conn.execute(
                """
                INSERT INTO production_cutting_sheets(order_id, status, created_by, created_at, updated_at)
                VALUES (?, '已下发', 'prod_workbench_tech', ?, ?)
                """,
                (order_id, now, now),
            ).lastrowid
            conn.execute(
                """
                INSERT INTO production_cutting_items(
                    sheet_id, bom_item_id, name, specification, quantity, actual_quantity, unit, cutter
                ) VALUES (?, ?, '测试板材', '1200x2400', 2, 2, '张', '下料甲')
                """,
                (sheet_id, bom_item_id),
            )
            conn.execute(
                """
                INSERT INTO production_quality_inspections(
                    order_id, result, inspector, photos_json, remark, created_at
                ) VALUES (?, '合格', '质检甲', '[]', '尺寸合格', ?)
                """,
                (order_id, now),
            )
            purchase_id = conn.execute(
                """
                INSERT INTO production_purchase_orders(
                    purchase_no, supplier, status, created_by, created_at, updated_at
                ) VALUES ('CG-WB-001', '测试供应商', '已下单', 'prod_workbench_purchase', ?, ?)
                """,
                (now, now),
            ).lastrowid
            conn.execute(
                """
                INSERT INTO production_purchase_items(
                    purchase_id, order_id, material_id, name, specification, quantity, unit, unit_price
                ) VALUES (?, ?, ?, '测试板材', '1200x2400', 2, '张', 100)
                """,
                (purchase_id, order_id, material_id),
            )
            conn.execute(
                """
                INSERT INTO production_inventory_transactions(
                    material_id, order_id, transaction_type, quantity, unit,
                    warehouse_location, operator_uid, created_at
                ) VALUES (?, ?, '其他入库', 2, '张', 'A-01', 'prod_workbench_warehouse', ?)
                """,
                (material_id, order_id, now),
            )
            finished_id = conn.execute(
                """
                INSERT INTO production_finished_goods(
                    finished_no, order_id, warehouse_location, status, inbound_by, inbound_at
                ) VALUES ('CP-WB-001', ?, '成品区', '已入库', 'prod_workbench_warehouse', ?)
                """,
                (order_id, now),
            ).lastrowid
            shipment_id = conn.execute(
                """
                INSERT INTO production_shipments(
                    shipment_no, customer, status, created_by, created_at, updated_at
                ) VALUES ('FH-WB-001', '看板客户1', '待发货', 'prod_workbench_shipping', ?, ?)
                """,
                (now, now),
            ).lastrowid
            conn.execute(
                """
                INSERT INTO production_shipment_items(shipment_id, order_id, finished_good_id)
                VALUES (?, ?, ?)
                """,
                (shipment_id, order_id, finished_id),
            )

        export_cases = [
            (f"/api/production/orders/{order_id}/documents/bom.xlsx", "prod_workbench_tech"),
            (f"/api/production/orders/{order_id}/documents/cutting.xlsx", "prod_workbench_tech"),
            (f"/api/production/orders/{order_id}/documents/quality.xlsx", "prod_workbench_quality"),
            (f"/api/production/purchases/{purchase_id}/export.xlsx", "prod_workbench_purchase"),
            ("/api/production/inventory/export.xlsx", "prod_workbench_warehouse"),
            (f"/api/production/shipments/{shipment_id}/export.xlsx", "prod_workbench_shipping"),
        ]
        export_success = True
        export_detail = ""
        for path, uid in export_cases:
            response = client.get(path, headers=headers(uid))
            if response.status_code != 200 or not response.content.startswith(b"PK"):
                export_success = False
                export_detail = f"{path}: {response.status_code} {response.text}"
                break
        check("六类生产单据均可导出有效Excel", export_success, export_detail)

        response = client.get(
            f"/api/production/orders/{order_id}/documents/bom/print",
            headers=headers("prod_workbench_tech"),
        )
        check(
            "生产单据打印页包含A4打印样式",
            response.status_code == 200 and "@page" in response.text and "生产BOM" in response.text,
            response.text,
        )

        response = client.get(
            f"/api/production/orders/{order_id}/documents/bom.xlsx",
            headers=headers("prod_workbench_reader"),
        )
        check("所有登录用户可导出BOM", response.status_code == 200, response.text)
    finally:
        main_module.production_db = original_main_db
        main_module.task_db = original_main_tasks
        production_routes.production_db = original_router_db
        production_routes.task_repository = original_router_tasks
        for uid in user_specs:
            cleanup_user(uid)
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\nPASS: {PASSED}")
    print(f"FAIL: {FAILED}")
    if FAILED:
        sys.exit(1)


if __name__ == "__main__":
    main()
