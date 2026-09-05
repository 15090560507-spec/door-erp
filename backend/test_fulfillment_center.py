"""End-to-end regression checks for the new door-unit fulfillment center."""

import json
import os
import shutil
import sys
import tempfile

from fastapi.testclient import TestClient

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import fulfillment_routes
import main as main_module
from auth import create_token
from database import TaskDatabaseManager
from fulfillment_database import FulfillmentDatabase
from inventory_service import InventoryService


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


def headers(uid: str = "admin") -> dict:
    return {"Authorization": f"Bearer {create_token(uid)}"}


def approved_task() -> dict:
    return {
        "id": "fulfillment-approved-1",
        "status": "已通过",
        "date": "2026-08-13",
        "history": [{"action": "终审通过", "user": "总工", "time": "2026-08-13T09:30:00+08:00"}],
        "params": {
            "dhdw": "测试订货单位",
            "gdmc": "履约中心测试项目",
            "product_name": "不锈钢镀铜门",
            "door_type": "对门",
            "dw": 1800,
            "dh": 2600,
            "sel_kx": "右开",
            "sel_nk": "内开",
            "zzcl": "1.0mm",
            "zmks": "紫荆花款",
            "fmks": "竖条款",
        },
    }


def main() -> None:
    global PASSED, FAILED
    temp_dir = tempfile.mkdtemp(prefix="door-fulfillment-test-")
    task_file = os.path.join(temp_dir, "tasks.json")
    with open(task_file, "w", encoding="utf-8") as stream:
        json.dump([approved_task()], stream, ensure_ascii=False)
    task_db = TaskDatabaseManager(task_file, os.path.join(temp_dir, "task-backups"))
    test_db = FulfillmentDatabase(os.path.join(temp_dir, "fulfillment.db"), os.path.join(temp_dir, "files"))
    old_db = fulfillment_routes.fulfillment_db
    old_tasks = fulfillment_routes.task_repository
    old_sales_orders = fulfillment_routes.sales_order_repository
    fulfillment_routes.fulfillment_db = test_db
    fulfillment_routes.task_repository = task_db
    # This suite exercises fulfillment itself. The sales-order gate has its own
    # end-to-end coverage in test_sales_orders.py.
    fulfillment_routes.sales_order_repository = None
    inventory_service = InventoryService(test_db.inventory_db)
    panel_material = inventory_service.create_material(
        code="TEST-PANEL", name="门扇板件", category="板件", specification="按图",
        unit="扇", material_type="自制件",
    )
    flower_material = inventory_service.create_material(
        code="TEST-FLOWER", name="花件", category="花件", specification="客户确认款",
        unit="件", material_type="采购件",
    )
    client = TestClient(main_module.app)

    try:
        response = client.get("/api/fulfillment/dashboard")
        check("未登录不能访问履约中心", response.status_code == 401, response.text)

        response = client.get("/api/fulfillment/pending-release", headers=headers())
        tasks = response.json().get("tasks", []) if response.status_code == 200 else []
        check("终审任务显示为待下达", len(tasks) == 1 and tasks[0]["task_id"] == "fulfillment-approved-1", response.text)

        response = client.get("/api/fulfillment/people", headers=headers())
        people_text = response.text.lower()
        check("履约人员接口不泄露密码", response.status_code == 200 and "password" not in people_text and '"pwd"' not in people_text, response.text)

        response = client.post("/api/production/orders/from-task/fulfillment-approved-1", headers=headers(), json={})
        check("旧生产写入口默认停用", response.status_code == 410, response.text)

        response = client.post(
            "/api/fulfillment/orders/from-task/fulfillment-approved-1",
            headers=headers(),
            json={"door_count": 2, "due_date": "2026-09-01", "owner_uid": "leader-a", "sales_note": "分两樘生产"},
        )
        order = response.json().get("order", {}) if response.status_code == 200 else {}
        doors = order.get("door_units", [])
        check("下达订单生成两个独立门樘编号", response.status_code == 200 and len(doors) == 2 and doors[0]["production_no"] != doors[1]["production_no"], response.text)

        response = client.get("/api/fulfillment/pending-release", headers=headers())
        check("同一终审版本不会重复待下达", response.status_code == 200 and response.json().get("tasks") == [], response.text)

        response = client.post(
            "/api/fulfillment/orders/from-task/fulfillment-approved-1",
            headers=headers(), json={"door_count": 1},
        )
        check("同一终审版本禁止重复下达", response.status_code == 409, response.text)

        door_id = doors[0]["id"]
        response = client.get(f"/api/fulfillment/door-units/{door_id}", headers=headers())
        detail = response.json().get("door_unit", {})
        package = detail.get("technical_package", {})
        check("门樘自动建立技术包和默认工作包草稿", package.get("status") == "草稿" and len(package.get("work_packages", [])) >= 1, response.text)

        update_payload = {
            "product_summary": "1.0mm不锈钢镀铜对门 / 紫荆花款",
            "special_requirements": "花件采购，玻璃定制",
            "components": [
                {"id": 100, "material_id": panel_material["id"], "name": "门扇板件", "category": "板件", "specification": "按图", "quantity": 2, "unit": "扇", "acquisition_method": "内部加工", "remark": ""},
                {"id": 101, "material_id": flower_material["id"], "name": "花件", "category": "花件", "specification": "客户确认款", "quantity": 2, "unit": "件", "acquisition_method": "采购", "remark": ""},
            ],
            "work_packages": [
                {"component_id": 100, "name": "板件下料折弯", "category": "内部加工", "route": "剪板→折弯", "acquisition_method": "内部加工", "executor_uid": "worker-a", "planned_end": "2026-08-20", "quantity": 2, "unit": "扇", "piece_rate": 80, "inspection_required": False},
                {"component_id": 101, "name": "花件采购", "category": "采购", "route": "询价→下单→到货", "acquisition_method": "采购", "executor_uid": "buyer-a", "planned_end": "2026-08-18", "quantity": 2, "unit": "件", "piece_rate": 0, "inspection_required": True},
            ],
        }
        response = client.put(f"/api/fulfillment/door-units/{door_id}/technical-package", headers=headers(), json=update_payload)
        detail = response.json().get("door_unit", {})
        check("下料人员可保存手工技术包并进入技术准备", response.status_code == 200 and detail.get("status") == "技术准备中", response.text)

        response = client.post(f"/api/fulfillment/door-units/{door_id}/technical-package/confirm", headers=headers())
        detail = response.json().get("door_unit", {})
        works = detail.get("technical_package", {}).get("work_packages", [])
        check("确认技术包冻结版本并释放工作包", response.status_code == 200 and detail.get("active_version") == 1 and all(item["status"] == "待排单" for item in works), response.text)

        response = client.put(
            f"/api/fulfillment/door-units/{door_id}/technical-package", headers=headers(), json=update_payload,
        )
        check("已冻结技术包禁止直接覆盖", response.status_code == 409, response.text)

        work_id = works[0]["id"]
        response = client.put(f"/api/fulfillment/work-packages/{work_id}", headers=headers(), json={"status": "进行中", "executor_uid": "worker-a", "remark": "已领料"})
        check("执行人可启动已释放工作包", response.status_code == 200 and response.json()["door_unit"]["progress"] > 0, response.text)

        response = client.put(f"/api/fulfillment/work-packages/{work_id}", headers=headers(), json={"status": "已完成", "executor_uid": "worker-a", "actual_quantity": 2, "remark": "完成"})
        check("执行人可提交实际完成", response.status_code == 200, response.text)

        response = client.post(f"/api/fulfillment/door-units/{door_id}/exceptions", headers=headers(), json={"category": "缺料", "title": "花件延期", "detail": "供应商晚三天", "severity": "较高", "owner_uid": "leader-a"})
        detail = response.json().get("door_unit", {})
        exception_id = detail.get("exceptions", [{}])[0].get("id")
        check("异常独立登记且不覆盖任务状态", response.status_code == 200 and exception_id, response.text)

        response = client.post(f"/api/fulfillment/exceptions/{exception_id}/resolve", headers=headers(), json={"resolution": "改用备用供应商"})
        check("整单异常可关闭并保留处理结果", response.status_code == 200 and response.json()["door_unit"]["exceptions"][0]["status"] == "已解决", response.text)

        response = client.post(f"/api/fulfillment/door-units/{door_id}/changes", headers=headers(), json={"reason": "客户调整花件", "impact_note": "采购和交期需重评"})
        changed = response.json().get("door_unit", {})
        check("生产变更生成 V2 草稿而非覆盖 V1", response.status_code == 200 and changed.get("technical_package", {}).get("version") == 2 and changed.get("technical_package", {}).get("status") == "草稿", response.text)

        response = client.put(f"/api/fulfillment/door-units/{door_id}/technical-package", headers=headers(), json=update_payload)
        response = client.post(f"/api/fulfillment/door-units/{door_id}/technical-package/confirm", headers=headers())
        current_works = response.json().get("door_unit", {}).get("technical_package", {}).get("work_packages", [])
        skippable_id = next(item["id"] for item in current_works if not item["inspection_required"])
        response = client.post(
            f"/api/fulfillment/door-units/{door_id}/work-packages/batch", headers=headers(),
            json={"work_ids": [skippable_id], "action": "跳过", "executor_uid": "worker-a", "remark": ""},
        )
        check("跳过工作包必须记录原因", response.status_code == 400, response.text)
        response = client.post(
            f"/api/fulfillment/door-units/{door_id}/work-packages/batch", headers=headers(),
            json={"work_ids": [skippable_id], "action": "跳过", "executor_uid": "worker-a", "remark": "客户取消该项"},
        )
        check("工作包可带审计原因受控跳过", response.status_code == 200 and response.json().get("changed") == 1, response.text)
        response = client.post(
            f"/api/fulfillment/door-units/{door_id}/work-packages/batch", headers=headers(),
            json={"work_ids": [item["id"] for item in current_works if not item["inspection_required"]], "action": "确认完成", "executor_uid": "worker-a", "remark": "批量完成"},
        )
        inspected_ids = [item["id"] for item in current_works if item["inspection_required"]]
        if inspected_ids:
            client.post(f"/api/fulfillment/door-units/{door_id}/work-packages/batch", headers=headers(), json={"work_ids": inspected_ids, "action": "提交质检", "executor_uid": "worker-a", "remark": "批量送检"})
            response = client.post(f"/api/fulfillment/door-units/{door_id}/work-packages/batch", headers=headers(), json={"work_ids": inspected_ids, "action": "确认完成", "executor_uid": "worker-a", "remark": "检验完成"})
        check("工作包支持受控批量快捷流转", response.status_code == 200 and response.json().get("door_unit", {}).get("status") == "待成品质检", response.text)
        response = client.post(f"/api/fulfillment/door-units/{door_id}/inspections", headers=headers(), json={"inspection_type": "成品质检", "result": "合格", "target_name": changed["production_no"], "quantity": 1, "defect_detail": "", "remark": "当前版本总检"})
        check("成品质检只校验当前技术版本工作包", response.status_code == 200 and response.json().get("door_unit", {}).get("status") == "待成品入库", response.text)

        response = client.get("/api/fulfillment/supplies/workbench?scope=purchase", headers=headers())
        check("采购工作台集中展示当前版本外购事项", response.status_code == 200 and isinstance(response.json().get("supplies"), list), response.text)
        response = client.get("/api/fulfillment/supplies/workbench?scope=warehouse", headers=headers())
        check("仓库工作台独立展示待检入库发料事项", response.status_code == 200 and isinstance(response.json().get("supplies"), list), response.text)

        closed_loop_id = doors[1]["id"]
        response = client.put(f"/api/fulfillment/door-units/{closed_loop_id}/technical-package", headers=headers(), json=update_payload)
        check("第二樘可独立维护技术包", response.status_code == 200, response.text)
        response = client.post(f"/api/fulfillment/door-units/{closed_loop_id}/technical-package/confirm", headers=headers())
        closed_loop = response.json().get("door_unit", {})
        check("技术包确认自动生成供应事项", response.status_code == 200 and len(closed_loop.get("supplies", [])) == 2, response.text)

        supply = closed_loop["supplies"][1]
        response = client.put(f"/api/fulfillment/supplies/{supply['id']}", headers=headers(), json={"status": "到货待检", "handler_uid": "buyer-a", "supplier": "花件厂", "actual_quantity": 2, "unit_cost": 120, "remark": "已到货"})
        check("供应事项支持采购经办和到货登记", response.status_code == 200, response.text)
        response = client.put(f"/api/fulfillment/supplies/{supply['id']}", headers=headers(), json={"status": "已入库", "handler_uid": "buyer-a", "supplier": "花件厂", "actual_quantity": 2, "unit_cost": 120, "remark": "尝试直接入库"})
        check("未经来料检验禁止入库", response.status_code == 409, response.text)
        response = client.post(f"/api/fulfillment/door-units/{closed_loop_id}/inspections", headers=headers(), json={"inspection_type": "来料检验", "result": "合格", "target_name": supply["name"], "quantity": 2, "defect_detail": "", "remark": "尺寸合格"})
        check("独立登记来料检验", response.status_code == 200, response.text)
        response = client.put(f"/api/fulfillment/supplies/{supply['id']}", headers=headers(), json={"status": "已入库", "handler_uid": "buyer-a", "supplier": "花件厂", "actual_quantity": 2, "unit_cost": 120, "remark": "检验合格入库"})
        check("来料检验合格后生成仓储流水", response.status_code == 200 and any(item["movement_type"] == "来料入库" for item in response.json()["door_unit"]["inventory_movements"]), response.text)
        response = client.put(f"/api/fulfillment/supplies/{supply['id']}", headers=headers(), json={"status": "已发料", "handler_uid": "warehouse-a", "supplier": "花件厂", "actual_quantity": 2, "unit_cost": 120, "remark": "仓库逐项确认发料"})
        check("仓库确认发料形成独立库存流水", response.status_code == 200 and any(item["movement_type"] == "生产发料" for item in response.json()["door_unit"]["inventory_movements"]), response.text)

        loop_works = response.json()["door_unit"]["technical_package"]["work_packages"]
        for item in loop_works:
            client.put(f"/api/fulfillment/work-packages/{item['id']}", headers=headers(), json={"status": "进行中", "executor_uid": "worker-b", "remark": "开工"})
            if item["inspection_required"]:
                client.put(f"/api/fulfillment/work-packages/{item['id']}", headers=headers(), json={"status": "待质检", "executor_uid": "worker-b", "remark": "提交检验"})
            response = client.put(f"/api/fulfillment/work-packages/{item['id']}", headers=headers(), json={"status": "已完成", "executor_uid": "worker-b", "actual_quantity": item["quantity"], "remark": "完成"})
        closed_loop = response.json()["door_unit"]
        check("全部工作包完成后进入待成品质检", closed_loop["status"] == "待成品质检", response.text)
        check("计件工作完成自动形成工资草稿", len(closed_loop["payroll_drafts"]) == 1 and closed_loop["payroll_drafts"][0]["amount"] == 160, response.text)

        response = client.post(f"/api/fulfillment/door-units/{closed_loop_id}/inspections", headers=headers(), json={"inspection_type": "成品质检", "result": "合格", "target_name": closed_loop["production_no"], "quantity": 1, "defect_detail": "", "remark": "总检合格"})
        check("成品质检合格后进入待入库", response.status_code == 200 and response.json()["door_unit"]["status"] == "待成品入库", response.text)
        response = client.post(f"/api/fulfillment/door-units/{closed_loop_id}/finished-inbound", headers=headers(), json={"warehouse": "成品仓", "location": "A-01", "quantity": 1, "remark": "包装完整"})
        check("成品必须办理入库", response.status_code == 200 and response.json()["door_unit"]["status"] == "已入库待发货", response.text)

        response = client.post(f"/api/fulfillment/door-units/{closed_loop_id}/shipments", headers=headers(), json={"required_payment": 10000, "carrier": "自送", "vehicle_no": "浙A12345", "contact": "13800000000", "authorization_reason": "", "authorized_by": "", "remark": ""})
        check("未达到规定收款禁止发货", response.status_code == 409, response.text)
        response = client.post(f"/api/fulfillment/door-units/{closed_loop_id}/payments", headers=headers(), json={"amount": 10000, "payment_date": "2026-08-20", "reference": "PAY-001", "remark": "发货款"})
        check("财务可登记订单收款", response.status_code == 200 and response.json()["door_unit"]["paid_amount"] == 10000, response.text)
        response = client.post(f"/api/fulfillment/door-units/{closed_loop_id}/shipments", headers=headers(), json={"required_payment": 10000, "carrier": "自送", "vehicle_no": "浙A12345", "contact": "13800000000", "authorization_reason": "", "authorized_by": "", "remark": "装车完成"})
        shipped = response.json().get("door_unit", {})
        check("满足收款后发货出库并进入运输中", response.status_code == 200 and shipped.get("status") == "运输中", response.text)
        shipment_id = shipped["shipments"][0]["id"]
        response = client.post(f"/api/fulfillment/shipments/{shipment_id}/sign", headers=headers(), json={"signed_by": "客户代表", "signed_at": "2026-08-21T10:00:00+08:00", "remark": "完好签收"})
        check("签收后门樘履约完成", response.status_code == 200 and response.json()["door_unit"]["status"] == "已签收", response.text)

        response = client.get("/api/fulfillment/dashboard", headers=headers())
        status_counts = response.json().get("status_counts", {}) if response.status_code == 200 else {}
        check("履约看板汇总门樘与异常", response.status_code == 200 and sum(status_counts.values()) >= 2, response.text)
    finally:
        fulfillment_routes.fulfillment_db = old_db
        fulfillment_routes.task_repository = old_tasks
        fulfillment_routes.sales_order_repository = old_sales_orders
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\nPASS: {PASSED}")
    print(f"FAIL: {FAILED}")
    if FAILED:
        sys.exit(1)


if __name__ == "__main__":
    main()
