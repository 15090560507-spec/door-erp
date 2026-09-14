"""End-to-end checks for previewed master-data imports and limited rollback."""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile

from fastapi.testclient import TestClient
from openpyxl import Workbook

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import inventory_routes
import main as main_module
from auth import create_token
from inventory_database import InventoryDatabase


def headers() -> dict:
    return {"Authorization": f"Bearer {create_token('admin')}"}


def workbook_bytes(columns: list[str], rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(columns)
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def main() -> None:
    temp_dir = tempfile.mkdtemp(prefix="door-master-import-")
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

    def import_entity(entity_type: str, columns: list[str], rows: list[list[object]]) -> dict:
        response = client.post(
            "/api/inventory/master-data/import/preview",
            headers=headers(),
            data={"entity_type": entity_type},
            files={"file": (f"{entity_type}.xlsx", workbook_bytes(columns, rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        check(f"{entity_type} 上传后完成自动预检", response.status_code == 201 and response.json().get("batch", {}).get("error_rows") == 0, response.text)
        preview = response.json()
        response = client.post(
            f"/api/inventory/master-data/import/{preview['batch']['id']}/execute",
            headers=headers(),
            json={"mapping": preview["mapping"], "duplicate_strategy": "skip"},
        )
        check(f"{entity_type} 预检通过后执行导入", response.status_code == 200 and response.json().get("batch", {}).get("imported_rows") == len(rows), response.text)
        return response.json()["batch"]

    try:
        response = client.get("/api/inventory/master-data/import/template?entity_type=materials", headers=headers())
        check("可下载物料导入模板", response.status_code == 200 and response.content[:2] == b"PK", response.text)

        material_batch = import_entity(
            "materials",
            ["物料编码", "物料名称", "基本单位", "物料类型", "安全库存", "可采购", "管理库存"],
            [["IMP-MAT-01", "迁移测试板材", "张", "原材料", 5, "是", "是"]],
        )
        supplier_batch = import_entity(
            "suppliers",
            ["供应商编码", "供应商名称", "联系人", "联系电话", "默认税率"],
            [["IMP-SUP-01", "迁移测试供应商", "李经理", "13800000000", 13]],
        )
        relation_batch = import_entity(
            "supplier_items",
            ["供应商编码", "物料编码", "供应商货号", "采购单位", "含税价", "首选供应商"],
            [["IMP-SUP-01", "IMP-MAT-01", "EXT-001", "张", 680, "是"]],
        )

        response = client.get("/api/inventory/supplier-items", headers=headers())
        relations = response.json().get("supplier_items", [])
        check("导入的供应商产品正确关联双方编码", response.status_code == 200 and len(relations) == 1 and relations[0]["tax_inclusive_price"] == 680, response.text)

        for label, batch in (("供应商产品", relation_batch), ("供应商", supplier_batch), ("物料", material_batch)):
            response = client.post(f"/api/inventory/master-data/import/{batch['id']}/rollback", headers=headers())
            check(f"{label}新增资料可按批次回滚", response.status_code == 200 and response.json().get("batch", {}).get("status") == "已回滚", response.text)

        materials = client.get("/api/inventory/materials?include_inactive=true", headers=headers()).json().get("materials", [])
        suppliers = client.get("/api/inventory/suppliers?include_inactive=true", headers=headers()).json().get("suppliers", [])
        check("逆序回滚后未残留迁移资料", not materials and not suppliers, f"materials={materials}; suppliers={suppliers}")
    finally:
        inventory_routes.configure_inventory_database(previous)
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\nMaster data import tests: {passed} PASS, {failed} FAIL")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
