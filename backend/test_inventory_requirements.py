"""Regression checks for fulfillment material requirements and reservations."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from fulfillment_database import FulfillmentDatabase, fulfillment_now
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


def create_door(
    db: FulfillmentDatabase,
    *,
    suffix: str,
    due_date: str,
    material_id: int | None,
    quantity: float,
) -> tuple[int, int]:
    now = fulfillment_now()
    with db.transaction() as conn:
        order = conn.execute(
            """INSERT INTO fulfillment_orders(
                   order_no, source_task_id, source_revision, customer, due_date,
                   task_snapshot_json, created_by, created_at, updated_at
               ) VALUES (?, ?, 'v1', '测试客户', ?, '{}', 'admin', ?, ?)""",
            (f"DDTEST{suffix}", f"task-{suffix}", due_date, now, now),
        )
        door = conn.execute(
            """INSERT INTO fulfillment_door_units(
                   order_id, production_no, sequence_no, product_name, due_date,
                   created_at, updated_at
               ) VALUES (?, ?, 1, '测试门', ?, ?, ?)""",
            (order.lastrowid, f"SC-{suffix}", due_date, now, now),
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
               ) VALUES (?, ?, '测试板材', '板材', '0.8mm', ?, '张', '库存/采购', 1)""",
            (package.lastrowid, material_id, quantity),
        )
        conn.execute(
            """INSERT INTO fulfillment_work_packages(
                   technical_package_id, door_unit_id, name, category, route,
                   quantity, unit, inspection_required, sequence_no, updated_at
               ) VALUES (?, ?, '测试下料', '下料', '下料', 1, '项', 0, 1, ?)""",
            (package.lastrowid, door.lastrowid, now),
        )
        return int(door.lastrowid), int(package.lastrowid)


def main() -> None:
    global PASSED, FAILED
    temp_dir = tempfile.mkdtemp(prefix="door-inventory-requirements-")
    db_path = os.path.join(temp_dir, "fulfillment.db")
    files_dir = os.path.join(temp_dir, "files")
    try:
        db = FulfillmentDatabase(db_path, files_dir)
        inventory = InventoryService(db.inventory_db)
        raw = next(item for item in inventory.list_warehouses() if item["code"] == "RAW")
        location = inventory.create_location(raw["id"], "A-01", "板材区")
        material = inventory.create_material(
            code="PLATE-08",
            name="0.8mm 板材",
            category="板材",
            specification="0.8mm",
            unit="张",
            material_type="原材料",
            default_warehouse_id=raw["id"],
            default_location_id=location["id"],
        )
        inventory.post_transaction(
            material_id=material["id"],
            warehouse_id=raw["id"],
            location_id=location["id"],
            transaction_type="期初入库",
            quantity=10,
            unit="张",
            source_type="test",
            source_id="opening",
        )

        later_door, later_package = create_door(
            db, suffix="LATER", due_date="2026-09-20", material_id=material["id"], quantity=8
        )
        with db.transaction() as conn:
            later = db.requirement_service.create_for_package(
                conn=conn, door_id=later_door, package_id=later_package, created_by="admin"
            )
        later_detail = db.requirement_service.get_requirement(later["id"])
        check("库存充足时需求全部预留", later_detail["status"] == "已预留" and later_detail["items"][0]["reserved_quantity"] == 8, str(later_detail))

        early_door, early_package = create_door(
            db, suffix="EARLY", due_date="2026-09-10", material_id=material["id"], quantity=6
        )
        with db.transaction() as conn:
            early = db.requirement_service.create_for_package(
                conn=conn, door_id=early_door, package_id=early_package, created_by="admin"
            )
        early_detail = db.requirement_service.get_requirement(early["id"])
        later_detail = db.requirement_service.get_requirement(later["id"])
        balance = inventory.get_balance(material["id"], raw["id"], location["id"])
        check("两个订单竞争时较早交期优先", early_detail["items"][0]["reserved_quantity"] == 6 and later_detail["items"][0]["reserved_quantity"] == 4, f"early={early_detail}; later={later_detail}")
        check("部分库存正确形成缺口", later_detail["items"][0]["shortage_quantity"] == 4 and later_detail["items"][0]["status"] == "部分缺料", str(later_detail))
        check("库存不会被重复预留", balance["reserved"] == 10 and balance["available"] == 0, str(balance))

        zero_door, zero_package = create_door(
            db, suffix="ZERO", due_date="2026-09-30", material_id=material["id"], quantity=2
        )
        with db.transaction() as conn:
            zero = db.requirement_service.create_for_package(
                conn=conn, door_id=zero_door, package_id=zero_package, created_by="admin"
            )
        zero_detail = db.requirement_service.get_requirement(zero["id"])
        check("零可用库存形成全部缺料", zero_detail["items"][0]["reserved_quantity"] == 0 and zero_detail["items"][0]["shortage_quantity"] == 2, str(zero_detail))

        with db.transaction() as conn:
            duplicate = db.requirement_service.create_for_package(
                conn=conn, door_id=zero_door, package_id=zero_package, created_by="admin"
            )
        requirement_count = db.fetch_one("SELECT COUNT(*) AS total FROM material_requirements WHERE technical_package_id=?", (zero_package,))
        check("重复确认需求保持幂等", duplicate["id"] == zero["id"] and requirement_count["total"] == 1, str(requirement_count))

        missing_door, missing_package = create_door(
            db, suffix="MISSING", due_date="2026-10-01", material_id=None, quantity=1
        )
        missing_blocked = False
        try:
            with db.transaction() as conn:
                db.requirement_service.create_for_package(
                    conn=conn, door_id=missing_door, package_id=missing_package, created_by="admin"
                )
        except ValueError as exc:
            missing_blocked = "尚未关联物料档案" in str(exc)
        check("物料未关联时禁止确认", missing_blocked)

        with db.transaction() as conn:
            db.requirement_service.freeze_for_package(conn, early_package)
        later_detail = db.requirement_service.get_requirement(later["id"])
        balance = inventory.get_balance(material["id"], raw["id"], location["id"])
        check("技术变更冻结旧需求并释放预留", db.requirement_service.get_requirement(early["id"])["status"] == "已冻结")
        zero_detail = db.requirement_service.get_requirement(zero["id"])
        check(
            "释放库存自动按交期补给后续需求",
            later_detail["items"][0]["reserved_quantity"] == 8
            and zero_detail["items"][0]["reserved_quantity"] == 2
            and balance["reserved"] == 10,
            f"later={later_detail}; zero={zero_detail}; balance={balance}",
        )

        integration_material = inventory.create_material(
            code="PLATE-10",
            name="1.0mm 板材",
            category="板材",
            specification="1.0mm",
            unit="张",
            material_type="原材料",
            default_warehouse_id=raw["id"],
            default_location_id=location["id"],
        )
        inventory.post_transaction(
            material_id=integration_material["id"],
            warehouse_id=raw["id"],
            location_id=location["id"],
            transaction_type="期初入库",
            quantity=5,
            unit="张",
            source_type="test",
            source_id="confirm-integration",
        )
        confirm_door, _ = create_door(
            db,
            suffix="CONFIRM",
            due_date="2026-10-10",
            material_id=integration_material["id"],
            quantity=3,
        )
        confirmed = db.confirm_technical_package(confirm_door, {"uid": "admin", "name": "管理员"})
        check(
            "确认技术包自动生成需求并预留库存",
            confirmed["technical_package"]["status"] == "已确认"
            and confirmed["material_requirement"]["status"] == "已预留"
            and confirmed["material_requirement"]["items"][0]["reserved_quantity"] == 3,
            str(confirmed.get("material_requirement")),
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\nInventory requirement tests: {PASSED} PASS, {FAILED} FAIL")
    if FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
