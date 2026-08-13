"""Regression checks for the shared factory inventory foundation."""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from inventory_database import InventoryDatabase
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


def main() -> None:
    global PASSED, FAILED
    temp_dir = tempfile.mkdtemp(prefix="door-inventory-foundation-")
    db_path = os.path.join(temp_dir, "fulfillment.db")

    try:
        db = InventoryDatabase(db_path)
        service = InventoryService(db)

        warehouses = db.list_warehouses()
        codes = {item["code"] for item in warehouses}
        check(
            "初始化五个全厂逻辑仓",
            codes == {"RAW", "ACCESSORY", "SEMI", "SUBCONTRACT", "FINISHED"},
            str(warehouses),
        )

        InventoryDatabase(db_path)
        check("重复初始化不产生重复仓库", len(db.list_warehouses()) == 5, str(db.list_warehouses()))

        raw = next(item for item in warehouses if item["code"] == "RAW")
        material = service.create_material(
            code="PLATE-08",
            name="0.8mm 铜板",
            category="板材",
            specification="0.8mm",
            unit="张",
            material_type="原材料",
            default_warehouse_id=raw["id"],
            minimum_stock=2,
            remark="库存底座测试",
        )
        check("创建公共物料档案", material["code"] == "PLATE-08", str(material))

        duplicate_material_blocked = False
        try:
            service.create_material(
                code="PLATE-08",
                name="重复物料",
                category="板材",
                specification="1.0mm",
                unit="张",
                material_type="原材料",
            )
        except sqlite3.IntegrityError:
            duplicate_material_blocked = True
        check("物料编码不可重复", duplicate_material_blocked)

        location = service.create_location(raw["id"], "A-01", "板材一区")
        duplicate_location_blocked = False
        try:
            service.create_location(raw["id"], "A-01", "重复库位")
        except sqlite3.IntegrityError:
            duplicate_location_blocked = True
        check("同一仓库库位编码不可重复", location["code"] == "A-01" and duplicate_location_blocked)

        transaction = service.post_transaction(
            material_id=material["id"],
            warehouse_id=raw["id"],
            location_id=location["id"],
            transaction_type="盘盈",
            quantity=10,
            unit="张",
            source_type="inventory_adjustment",
            source_id="ADJ-001",
            source_line="1",
            operator_uid="admin",
            remark="期初盘盈",
        )
        balance = service.get_balance(material["id"], raw["id"], location["id"])
        check(
            "确认流水同步更新余额",
            transaction["quantity"] == 10 and balance["on_hand"] == 10 and balance["available"] == 10,
            str(balance),
        )

        duplicate_source_blocked = False
        try:
            service.post_transaction(
                material_id=material["id"],
                warehouse_id=raw["id"],
                location_id=location["id"],
                transaction_type="盘盈",
                quantity=10,
                unit="张",
                source_type="inventory_adjustment",
                source_id="ADJ-001",
                source_line="1",
                operator_uid="admin",
                remark="重复提交",
            )
        except sqlite3.IntegrityError:
            duplicate_source_blocked = True
        check("同一来源单据行不能重复入账", duplicate_source_blocked)

        negative_stock_blocked = False
        try:
            service.post_transaction(
                material_id=material["id"],
                warehouse_id=raw["id"],
                location_id=location["id"],
                transaction_type="盘亏",
                quantity=-11,
                unit="张",
                source_type="inventory_adjustment",
                source_id="ADJ-002",
                source_line="1",
                operator_uid="admin",
                remark="超量盘亏",
            )
        except ValueError:
            negative_stock_blocked = True
        check("默认禁止负库存", negative_stock_blocked)

        rollback_works = False
        try:
            with db.transaction() as conn:
                service.post_transaction(
                    material_id=material["id"],
                    warehouse_id=raw["id"],
                    location_id=location["id"],
                    transaction_type="盘盈",
                    quantity=3,
                    unit="张",
                    source_type="inventory_adjustment",
                    source_id="ADJ-ROLLBACK",
                    source_line="1",
                    operator_uid="admin",
                    remark="事务回滚测试",
                    conn=conn,
                )
                raise RuntimeError("rollback")
        except RuntimeError:
            rollback_balance = service.get_balance(material["id"], raw["id"], location["id"])
            rollback_works = rollback_balance["on_hand"] == 10
        check("库存服务可复用外层事务并完整回滚", rollback_works)

        rows = service.list_transactions(material_id=material["id"])
        check("库存流水保留来源和操作人", len(rows) == 1 and rows[0]["source_id"] == "ADJ-001" and rows[0]["operator_uid"] == "admin", str(rows))

        update_blocked = False
        delete_blocked = False
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute("UPDATE inventory_transactions SET quantity=9 WHERE id=?", (transaction["id"],))
            except sqlite3.IntegrityError:
                update_blocked = True
            conn.rollback()

            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute("DELETE FROM inventory_transactions WHERE id=?", (transaction["id"],))
            except sqlite3.IntegrityError:
                delete_blocked = True
            conn.rollback()
        finally:
            conn.close()
        check("已确认库存流水不能直接修改", update_blocked)
        check("已确认库存流水不能物理删除", delete_blocked)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\nInventory foundation tests: {PASSED} PASS, {FAILED} FAIL")
    if FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
