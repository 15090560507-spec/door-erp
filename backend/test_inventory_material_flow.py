"""Regression tests for production issue, return, transfer and scrap."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from fulfillment_database import FulfillmentDatabase, fulfillment_now
from inventory_service import InventoryService
from material_flow_service import MaterialFlowService

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


def create_requirement(db: FulfillmentDatabase, material_id: int) -> dict:
    now = fulfillment_now()
    with db.transaction() as conn:
        order = conn.execute(
            """INSERT INTO fulfillment_orders(order_no,source_task_id,source_revision,customer,due_date,
                   task_snapshot_json,created_by,created_at,updated_at)
               VALUES('DDFLOW001','flow-task','v1','测试客户','2026-09-01','{}','admin',?,?)""", (now, now)
        )
        door = conn.execute(
            """INSERT INTO fulfillment_door_units(order_id,production_no,sequence_no,product_name,due_date,created_at,updated_at)
               VALUES(?,'SC-FLOW-01',1,'测试门','2026-09-01',?,?)""", (order.lastrowid, now, now)
        )
        package = conn.execute(
            """INSERT INTO fulfillment_technical_packages(door_unit_id,version,product_snapshot_json,created_by,created_at,updated_at)
               VALUES(?,1,'{}','admin',?,?)""", (door.lastrowid, now, now)
        )
        conn.execute(
            """INSERT INTO fulfillment_components(technical_package_id,material_id,name,category,specification,
                   quantity,unit,acquisition_method,sequence_no)
               VALUES(?,?,'测试板材','板材','0.8mm',8,'张','库存/采购',1)""", (package.lastrowid, material_id)
        )
        return db.requirement_service.create_for_package(
            conn=conn, door_id=int(door.lastrowid), package_id=int(package.lastrowid), created_by="admin"
        )


def main() -> None:
    global PASSED, FAILED
    temp_dir = tempfile.mkdtemp(prefix="door-inventory-flow-")
    try:
        db = FulfillmentDatabase(os.path.join(temp_dir, "flow.db"), os.path.join(temp_dir, "files"))
        inventory = InventoryService(db.inventory_db)
        flow = MaterialFlowService(db.inventory_db)
        warehouses = {item["code"]: item for item in inventory.list_warehouses()}
        raw_a = inventory.create_location(warehouses["RAW"]["id"], "A-01", "原料一区")
        raw_b = inventory.create_location(warehouses["RAW"]["id"], "B-01", "原料二区")
        material = inventory.create_material(
            code="FLOW-PLATE", name="测试板材", category="板材", specification="0.8mm", unit="张",
            material_type="原材料", default_warehouse_id=warehouses["RAW"]["id"], default_location_id=raw_a["id"],
        )
        inventory.post_transaction(
            material_id=material["id"], warehouse_id=warehouses["RAW"]["id"], location_id=raw_a["id"],
            transaction_type="期初入库", quantity=10, unit="张", source_type="test", source_id="opening",
        )
        requirement = create_requirement(db, material["id"])
        detail = db.requirement_service.get_requirement(requirement["id"])
        item = detail["items"][0]; reservation = item["reservations"][0]
        check("需求形成待发料预留", reservation["quantity"] == 8 and len(flow.list_pending_issues()) == 1, str(detail))

        issue = flow.issue({"requirement_id": requirement["id"], "remark": "首批领料", "items": [{
            "requirement_item_id": item["id"], "reservation_id": reservation["id"], "quantity": 5, "remark": ""
        }]}, "warehouse")
        after_issue = db.requirement_service.get_requirement(requirement["id"])
        balance_a = inventory.get_balance(material["id"], warehouses["RAW"]["id"], raw_a["id"])
        check("部分发料扣减库存并累计领料", issue["document_type"] == "生产发料" and after_issue["items"][0]["issued_quantity"] == 5 and balance_a["on_hand"] == 5, str(after_issue))
        check("发料后剩余需求重新预留", after_issue["items"][0]["reserved_quantity"] == 3 and balance_a["reserved"] == 3, str(balance_a))

        over_issue = False
        try:
            current_reservation = after_issue["items"][0]["reservations"][-1]
            flow.issue({"requirement_id": requirement["id"], "items": [{
                "requirement_item_id": item["id"], "reservation_id": current_reservation["id"], "quantity": 4
            }]}, "warehouse")
        except ValueError as exc:
            over_issue = "超过预留" in str(exc)
        check("禁止超预留发料且整单回滚", over_issue and len(flow.list_orders("生产发料")) == 1)

        returned = flow.return_material({"requirement_id": requirement["id"], "items": [{
            "requirement_item_id": item["id"], "material_id": material["id"], "warehouse_id": warehouses["RAW"]["id"],
            "location_id": raw_a["id"], "quantity": 2, "unit": "张", "remark": "余料"
        }]}, "warehouse")
        after_return = db.requirement_service.get_requirement(requirement["id"])
        check("退料恢复库存并累计退料", returned["document_type"] == "生产退料" and after_return["items"][0]["returned_quantity"] == 2)

        over_return = False
        try:
            flow.return_material({"requirement_id": requirement["id"], "items": [{
                "requirement_item_id": item["id"], "material_id": material["id"], "warehouse_id": warehouses["RAW"]["id"],
                "location_id": raw_a["id"], "quantity": 4, "unit": "张"
            }]}, "warehouse")
        except ValueError as exc:
            over_return = "超过净领料" in str(exc)
        check("禁止超净领料退料", over_return and len(flow.list_orders("生产退料")) == 1)

        transfer = flow.transfer({"remark": "移库", "items": [{
            "material_id": material["id"], "source_warehouse_id": warehouses["RAW"]["id"], "source_location_id": raw_a["id"],
            "target_warehouse_id": warehouses["RAW"]["id"], "target_location_id": raw_b["id"], "quantity": 1, "unit": "张"
        }]}, "warehouse")
        balance_b = inventory.get_balance(material["id"], warehouses["RAW"]["id"], raw_b["id"])
        check("调拨生成成对流水并转入目标库位", transfer["document_type"] == "库存调拨" and balance_b["on_hand"] == 1)

        transfer_rollback = False
        try:
            flow.transfer({"items": [{
                "material_id": material["id"], "source_warehouse_id": warehouses["RAW"]["id"], "source_location_id": raw_b["id"],
                "target_warehouse_id": warehouses["RAW"]["id"], "target_location_id": raw_a["id"], "quantity": 2, "unit": "张"
            }]}, "warehouse")
        except ValueError as exc:
            transfer_rollback = "库存不足" in str(exc)
        check("调拨库存不足时整单回滚", transfer_rollback and inventory.get_balance(material["id"], warehouses["RAW"]["id"], raw_b["id"])["on_hand"] == 1)

        scrap = flow.scrap({"production_no": "SC-FLOW-01", "items": [{
            "material_id": material["id"], "warehouse_id": warehouses["RAW"]["id"], "location_id": raw_b["id"],
            "quantity": 1, "unit": "张", "remark": "损坏"
        }]}, "warehouse")
        check("报废出库扣减现存", scrap["document_type"] == "报废出库" and inventory.get_balance(material["id"], warehouses["RAW"]["id"], raw_b["id"])["on_hand"] == 0)

        negative_blocked = False
        try:
            flow.scrap({"items": [{"material_id": material["id"], "warehouse_id": warehouses["RAW"]["id"],
                "location_id": raw_b["id"], "quantity": 1, "unit": "张"}]}, "warehouse")
        except ValueError as exc:
            negative_blocked = "库存不足" in str(exc)
        check("报废不能造成负库存", negative_blocked)

        semi_location = inventory.create_location(warehouses["SEMI"]["id"], "SEMI-01", "外协回件区")
        subcontract_material = inventory.create_material(
            code="FLOW-SEMI", name="待精雕板件", category="板件", specification="门面板", unit="件",
            material_type="半成品", default_warehouse_id=warehouses["SEMI"]["id"],
            default_location_id=semi_location["id"],
        )
        inventory.post_transaction(
            material_id=subcontract_material["id"], warehouse_id=warehouses["RAW"]["id"], location_id=raw_b["id"],
            transaction_type="期初入库", quantity=4, unit="件", source_type="test", source_id="subcontract-opening",
        )
        subcontract = flow.send_subcontract({
            "supplier": "测试精雕厂", "work_package": "精雕板件", "expected_return_date": "2026-09-05",
            "items": [{"material_id": subcontract_material["id"], "source_warehouse_id": warehouses["RAW"]["id"],
                       "source_location_id": raw_b["id"], "quantity": 3, "unit": "件", "production_no": "SC-FLOW-01"}],
        }, "outsourcing")
        subcontract_item = subcontract["items"][0]
        transit_balance = inventory.get_balance(
            subcontract_material["id"], subcontract_item["transit_warehouse_id"], subcontract_item["transit_location_id"]
        )
        check("外协发出转入在途仓", transit_balance["on_hand"] == 3 and subcontract["status"] == "外协中", str(subcontract))

        receipt = flow.receive_subcontract(subcontract["id"], {
            "return_date": "2026-09-03", "items": [{"subcontract_item_id": subcontract_item["id"], "quantity": 2}]
        }, "warehouse")
        check("外协支持分批返回待检", receipt["status"] == "待检" and receipt["items"][0]["returned_quantity"] == 2, str(receipt))

        over_receive = False
        try:
            flow.receive_subcontract(subcontract["id"], {
                "items": [{"subcontract_item_id": subcontract_item["id"], "quantity": 2}]
            }, "warehouse")
        except ValueError as exc:
            over_receive = "超过待回数量" in str(exc)
        check("禁止外协超量返回", over_receive and len(flow.list_subcontract_receipts()) == 1)

        inspected = flow.inspect_subcontract(receipt["items"][0]["id"], {
            "accepted_quantity": 1, "rejected_quantity": 1,
            "warehouse_id": warehouses["SEMI"]["id"], "location_id": semi_location["id"], "remark": "一件瑕疵",
        }, "inspector")
        semi_balance = inventory.get_balance(subcontract_material["id"], warehouses["SEMI"]["id"], semi_location["id"])
        transit_balance = inventory.get_balance(
            subcontract_material["id"], subcontract_item["transit_warehouse_id"], subcontract_item["transit_location_id"]
        )
        check("外协合格件进入半成品仓", inspected["status"] == "已检验" and semi_balance["on_hand"] == 1)
        check("外协不合格件核销但不入可用库存", transit_balance["on_hand"] == 1 and semi_balance["on_hand"] == 1)

        repeat_blocked = False
        try:
            flow.inspect_subcontract(receipt["items"][0]["id"], {
                "accepted_quantity": 2, "rejected_quantity": 0,
                "warehouse_id": warehouses["SEMI"]["id"], "location_id": semi_location["id"],
            }, "inspector")
        except RuntimeError as exc:
            repeat_blocked = "已经检验" in str(exc)
        check("禁止重复检验外协返回", repeat_blocked and semi_balance["on_hand"] == 1)

        final_receipt = flow.receive_subcontract(subcontract["id"], {
            "return_date": "2026-09-04", "items": [{"subcontract_item_id": subcontract_item["id"], "quantity": 1}]
        }, "warehouse")
        flow.inspect_subcontract(final_receipt["items"][0]["id"], {
            "accepted_quantity": 1, "rejected_quantity": 0,
            "warehouse_id": warehouses["SEMI"]["id"], "location_id": semi_location["id"],
        }, "inspector")
        completed = flow.get_subcontract_order(subcontract["id"])
        check("全部返回并检验后外协单完结", completed["status"] == "已完成" and completed["items"][0]["accepted_quantity"] == 2, str(completed))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\nInventory material flow tests: {PASSED} PASS, {FAILED} FAIL")
    if FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
