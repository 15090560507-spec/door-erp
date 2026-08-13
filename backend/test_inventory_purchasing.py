"""Regression checks for merged purchasing and inspected inbound stock."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from fulfillment_database import FulfillmentDatabase, fulfillment_now
from inventory_service import InventoryService
from purchasing_service import PurchasingService


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


def create_requirement(db: FulfillmentDatabase, material_id: int, suffix: str, quantity: float, due_date: str) -> dict:
    now = fulfillment_now()
    with db.transaction() as conn:
        order = conn.execute(
            """INSERT INTO fulfillment_orders(
                   order_no, source_task_id, source_revision, customer, due_date,
                   task_snapshot_json, created_by, created_at, updated_at
               ) VALUES (?, ?, 'v1', '测试客户', ?, '{}', 'admin', ?, ?)""",
            (f"DDCG{suffix}", f"cg-{suffix}", due_date, now, now),
        )
        door = conn.execute(
            """INSERT INTO fulfillment_door_units(
                   order_id, production_no, sequence_no, product_name, due_date,
                   created_at, updated_at
               ) VALUES (?, ?, 1, '测试门', ?, ?, ?)""",
            (order.lastrowid, f"SC-CG-{suffix}", due_date, now, now),
        )
        package = conn.execute(
            """INSERT INTO fulfillment_technical_packages(
                   door_unit_id, version, product_snapshot_json, created_by,
                   created_at, updated_at
               ) VALUES (?, 1, '{}', 'admin', ?, ?)""",
            (door.lastrowid, now, now),
        )
        conn.execute(
            """INSERT INTO fulfillment_components(
                   technical_package_id, material_id, name, category,
                   specification, quantity, unit, acquisition_method, sequence_no
               ) VALUES (?, ?, '合页', '配件', '标准', ?, '只', '库存/采购', 1)""",
            (package.lastrowid, material_id, quantity),
        )
        requirement = db.requirement_service.create_for_package(
            conn=conn,
            door_id=int(door.lastrowid),
            package_id=int(package.lastrowid),
            created_by="admin",
        )
    return db.requirement_service.get_requirement(requirement["id"])


def main() -> None:
    global PASSED, FAILED
    temp_dir = tempfile.mkdtemp(prefix="door-inventory-purchasing-")
    try:
        db = FulfillmentDatabase(os.path.join(temp_dir, "fulfillment.db"), os.path.join(temp_dir, "files"))
        inventory = InventoryService(db.inventory_db)
        purchasing = PurchasingService(db.inventory_db)
        warehouse = next(item for item in inventory.list_warehouses() if item["code"] == "ACCESSORY")
        location = inventory.create_location(warehouse["id"], "HJ-01", "合页区")
        material = inventory.create_material(
            code="HJ-001",
            name="暗合页",
            category="合页",
            specification="标准",
            unit="只",
            material_type="配件",
            default_warehouse_id=warehouse["id"],
            default_location_id=location["id"],
            default_supplier="五金供应商",
        )
        first = create_requirement(db, material["id"], "EARLY", 3, "2026-09-01")
        second = create_requirement(db, material["id"], "LATE", 3, "2026-09-10")
        shortages = purchasing.list_shortages()
        check("缺口池汇总两个门樘需求", len(shortages) == 2 and sum(row["demand_quantity"] for row in shortages) == 6, str(shortages))

        order = purchasing.create_order(
            {
                "supplier": "五金供应商",
                "expected_date": "2026-08-25",
                "remark": "合并采购并超采一只",
                "items": [{
                    "material_id": material["id"],
                    "quantity": 7,
                    "unit": "只",
                    "unit_price": 20,
                    "remark": "",
                    "allocations": [
                        {"requirement_item_id": first["items"][0]["id"], "quantity": 3},
                        {"requirement_item_id": second["items"][0]["id"], "quantity": 3},
                    ],
                }],
            },
            "buyer",
        )
        check("跨订单合并采购保留需求分配", len(order["items"][0]["allocations"]) == 2 and order["total_amount"] == 140, str(order))
        order = purchasing.confirm_order(order["id"], "buyer")
        first = db.requirement_service.get_requirement(first["id"])
        second = db.requirement_service.get_requirement(second["id"])
        check("确认采购后覆盖需求缺口", first["status"] == "采购覆盖" and second["status"] == "采购覆盖", f"{first}; {second}")
        check("在途采购未增加现存库存", inventory.get_balance(material["id"], warehouse["id"], location["id"])["on_hand"] == 0)

        receipt = purchasing.create_receipt(
            order["id"],
            {"arrival_date": "2026-08-24", "remark": "全部到货", "items": [{"purchase_order_item_id": order["items"][0]["id"], "quantity": 7}]},
            "warehouse",
        )
        check("到货登记进入待检而非库存", receipt["status"] == "待检" and inventory.get_balance(material["id"], warehouse["id"], location["id"])["on_hand"] == 0, str(receipt))
        receipt = purchasing.inspect_receipt_item(
            receipt["items"][0]["id"],
            {
                "qualified_quantity": 6,
                "concession_quantity": 1,
                "rejected_quantity": 0,
                "warehouse_id": warehouse["id"],
                "location_id": location["id"],
                "remark": "一只让步接收",
            },
            "quality",
        )
        balance = inventory.get_balance(material["id"], warehouse["id"], location["id"])
        first = db.requirement_service.get_requirement(first["id"])
        second = db.requirement_service.get_requirement(second["id"])
        check("合格及让步接收数量正式入库", receipt["status"] == "已检验" and balance["on_hand"] == 7, f"receipt={receipt}; balance={balance}")
        check("入库后按交期自动预留并保留超采公共库存", balance["reserved"] == 6 and balance["available"] == 1 and first["items"][0]["reserved_quantity"] == 3 and second["items"][0]["reserved_quantity"] == 3, f"balance={balance}; first={first}; second={second}")
        duplicate_blocked = False
        try:
            purchasing.inspect_receipt_item(
                receipt["items"][0]["id"],
                {"qualified_quantity": 7, "concession_quantity": 0, "rejected_quantity": 0, "warehouse_id": warehouse["id"], "location_id": location["id"], "remark": ""},
                "quality",
            )
        except RuntimeError:
            duplicate_blocked = True
        check("同一到货明细禁止重复检验入账", duplicate_blocked)

        cancel_requirement = create_requirement(db, material["id"], "CANCEL", 2, "2026-09-20")
        cancel_order = purchasing.create_order(
            {
                "supplier": "五金供应商",
                "items": [{
                    "material_id": material["id"], "quantity": 1, "unit": "只", "unit_price": 20,
                    "allocations": [{"requirement_item_id": cancel_requirement["items"][0]["id"], "quantity": 1}],
                }],
            },
            "buyer",
        )
        cancel_order = purchasing.confirm_order(cancel_order["id"], "buyer")
        purchasing.cancel_order(cancel_order["id"])
        cancel_requirement = db.requirement_service.get_requirement(cancel_requirement["id"])
        check("取消未到货采购会释放需求覆盖", cancel_requirement["items"][0]["purchased_quantity"] == 0, str(cancel_requirement))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\nInventory purchasing tests: {PASSED} PASS, {FAILED} FAIL")
    if FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
