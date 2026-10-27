"""Direct purchase catalog capture remains atomic and permission-scoped."""
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from inventory_database import InventoryDatabase
from inventory_service import InventoryService
from purchasing_service import PurchasingService


class PurchaseCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = InventoryDatabase(os.path.join(self.temp.name, "inventory.db"))
        self.service = PurchasingService(self.db)
        self.inventory = InventoryService(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, **changes):
        payload = {"supplier": "供应商甲", "items": [{
            "material_name": "拉手", "specification": "300mm", "unit": "付",
            "quantity": 2, "unit_price": 12.5, "allocations": [],
        }]}
        payload.update(changes)
        return payload

    def count(self, table):
        return self.db.fetch_one(f"SELECT COUNT(*) AS n FROM {table}")["n"]

    def test_draft_creates_catalog_without_publishing_price(self):
        order = self.service.create_order(self.payload(), "buyer")
        self.assertIsNotNone(order["supplier_id"])
        self.assertEqual(self.count("inventory_materials"), 1)
        self.assertEqual(self.count("inventory_suppliers"), 1)
        self.assertEqual(self.count("inventory_supplier_items"), 1)
        self.assertEqual(self.count("inventory_supplier_item_prices"), 0)
        self.service.confirm_order(order["id"], "approver")
        relation = self.inventory.list_supplier_items()[0]
        self.assertEqual(relation["tax_inclusive_price"], 12.5)
        self.assertEqual(self.count("inventory_supplier_item_prices"), 1)
        history = self.db.fetch_one("SELECT * FROM inventory_supplier_item_prices")
        self.assertEqual(history["operator_uid"], "approver")

    def test_exact_match_reuses_but_spec_or_unit_are_distinct(self):
        self.service.create_order(self.payload(), "buyer")
        self.service.create_order(self.payload(), "buyer")
        self.assertEqual(self.count("inventory_materials"), 1)
        self.assertEqual(self.count("inventory_suppliers"), 1)
        for field, value in [("specification", "400mm"), ("unit", "只")]:
            payload = self.payload()
            payload["items"][0][field] = value
            self.service.create_order(payload, "buyer")
        self.assertEqual(self.count("inventory_materials"), 3)

    def test_invalid_line_rolls_back_all_new_catalog(self):
        payload = self.payload()
        payload["items"].append({"material_id": 9999, "unit": "只", "quantity": 1})
        with self.assertRaises(LookupError):
            self.service.create_order(payload, "buyer")
        for table in ["purchase_orders", "inventory_materials", "inventory_suppliers", "inventory_supplier_items"]:
            self.assertEqual(self.count(table), 0, table)

    def test_retry_is_idempotent_and_payload_changes_are_rejected(self):
        payload = self.payload(request_key="request-123")
        first = self.service.create_order(payload, "buyer")
        second = self.service.create_order(payload, "buyer")
        self.assertEqual(first["id"], second["id"])
        payload["items"][0]["quantity"] = 3
        with self.assertRaises(ValueError):
            self.service.create_order(payload, "buyer")
        self.assertEqual(self.count("purchase_orders"), 1)

    def test_existing_metadata_conversion_and_old_order_price_preserved(self):
        first = self.service.create_order(self.payload(), "buyer")
        self.service.confirm_order(first["id"], "buyer")
        relation = self.inventory.list_supplier_items()[0]
        with self.db.transaction() as conn:
            conn.execute("UPDATE inventory_supplier_items SET purchase_unit='箱', conversion_rate=10, tax_rate=13, remark='保留' WHERE id=?", (relation["id"],))
        payload = self.payload()
        payload["items"][0]["unit_price"] = 20
        second = self.service.create_order(payload, "buyer")
        self.assertEqual(self.inventory.list_supplier_items()[0]["tax_inclusive_price"], 12.5)
        self.service.confirm_order(second["id"], "buyer")
        updated = self.inventory.list_supplier_items()[0]
        self.assertEqual(updated["tax_inclusive_price"], 200)
        self.assertEqual(updated["purchase_unit"], "箱")
        self.assertEqual(updated["tax_rate"], 13)
        self.assertEqual(updated["remark"], "保留")
        self.assertEqual(self.service.get_order(first["id"])["items"][0]["unit_price"], 12.5)
        self.assertEqual(self.count("inventory_supplier_item_prices"), 2)
        with self.assertRaises(RuntimeError):
            self.service.confirm_order(second["id"], "buyer")
        self.assertEqual(self.count("inventory_supplier_item_prices"), 2)

    def test_multiple_prices_keep_lines_and_publish_weighted_reference(self):
        payload = self.payload()
        payload["items"].append({**payload["items"][0], "unit_price": 30})
        order = self.service.create_order(payload, "buyer")
        self.service.confirm_order(order["id"], "buyer")
        self.assertEqual(self.inventory.list_supplier_items()[0]["tax_inclusive_price"], 21.25)
        self.assertEqual([item["unit_price"] for item in order["items"]], [12.5, 30])

    def test_disabled_and_ambiguous_supplier_are_not_silently_reused(self):
        self.service.create_order(self.payload(), "buyer")
        with self.db.transaction() as conn:
            conn.execute("UPDATE inventory_suppliers SET is_active=0")
        with self.assertRaises(ValueError):
            self.service.create_order(self.payload(), "buyer")
        self.assertEqual(self.count("inventory_suppliers"), 1)

    def test_schema_reinitialization_preserves_order(self):
        order = self.service.create_order(self.payload(), "buyer")
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM app_schema_versions WHERE component='inventory'")
        InventoryDatabase(self.db.db_path)
        self.assertEqual(self.service.get_order(order["id"])["total_amount"], 25)

    def test_v1_migration_preserves_text_supplier_and_prices(self):
        order = self.service.create_order(self.payload(), "buyer")
        with self.db.transaction() as conn:
            conn.execute("DROP INDEX ix_purchase_request")
            for column in ["supplier_id", "request_key", "request_hash"]:
                conn.execute(f"ALTER TABLE purchase_orders DROP COLUMN {column}")
            conn.execute("UPDATE app_schema_versions SET version=1 WHERE component='inventory'")
        InventoryDatabase(self.db.db_path)
        migrated = self.service.get_order(order["id"])
        self.assertIsNone(migrated["supplier_id"])
        self.assertEqual(migrated["supplier"], "供应商甲")
        self.assertEqual(migrated["items"][0]["unit_price"], 12.5)

    def test_concurrent_retry_creates_one_order(self):
        payload = self.payload(request_key="concurrent-save")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.service.create_order(payload, "buyer"), range(2)))
        self.assertEqual(results[0]["id"], results[1]["id"])
        self.assertEqual(self.count("purchase_orders"), 1)
        self.assertEqual(self.count("inventory_supplier_items"), 1)

    def test_ambiguous_supplier_requires_explicit_id(self):
        first = self.service.create_order(self.payload(), "buyer")
        self.inventory.create_supplier({"code": "SECOND", "name": "供应商甲"})
        with self.assertRaises(ValueError):
            self.service.create_order(self.payload(), "buyer")
        order = self.service.create_order(self.payload(supplier_id=first["supplier_id"]), "buyer")
        self.assertEqual(order["supplier_id"], first["supplier_id"])

    def test_other_supplier_price_and_legacy_orders_untouched(self):
        first = self.service.create_order(self.payload(), "buyer")
        self.service.confirm_order(first["id"], "buyer")
        other = self.service.create_order(self.payload(supplier="供应商乙"), "buyer")
        with self.db.transaction() as conn:
            conn.execute("UPDATE purchase_orders SET supplier_id=NULL WHERE id=?", (other["id"],))
        self.service.confirm_order(other["id"], "buyer")
        prices = {item["supplier_name"]: item["tax_inclusive_price"] for item in self.inventory.list_supplier_items()}
        self.assertEqual(prices, {"供应商甲": 12.5, "供应商乙": 0})

    def test_purchase_permission_scopes_catalog_creation_only(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import auth
        import inventory_routes
        user = {"uid": "E", "role": "录入员", "management_permissions": []}
        app = FastAPI()
        app.include_router(inventory_routes.router)
        app.dependency_overrides[auth.get_current_user] = lambda: user
        with patch.object(inventory_routes, "purchasing_service", self.service):
            client = TestClient(app)
            self.assertEqual(client.post("/api/inventory/purchasing/orders", json=self.payload()).status_code, 403)
            user["management_permissions"] = ["production.purchase"]
            response = client.post("/api/inventory/purchasing/orders", json=self.payload())
            self.assertEqual(response.status_code, 201, response.text)
            order_id = response.json()["order"]["id"]
            self.assertEqual(client.post(f"/api/inventory/purchasing/orders/{order_id}/confirm").status_code, 200)
            self.assertEqual(client.post("/api/inventory/suppliers", json={"code": "X", "name": "不可绕过"}).status_code, 403)
            self.assertEqual(client.put("/api/inventory/materials/1", json={}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
