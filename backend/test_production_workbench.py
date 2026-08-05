"""Regression checks for the expanded production workbench."""

import json
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
        check("无生产权限不能查看待下达任务", response.status_code == 403, response.text)

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
