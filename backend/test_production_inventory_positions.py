"""Position-aware semi-finished balances and assembly issues."""

import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_hierarchical_bom as helpers
import test_bom_generation as bom_helpers
from inventory_service import InventoryService
from fulfillment_database import fulfillment_now
from production_inventory import semi_finished_balances


class ProductionInventoryPositionTest(unittest.TestCase):
    def setUp(self):
        self.helper = helpers.HierarchicalBomTest()
        self.helper.setUp()
        self.db, self.user = self.helper.db, self.helper.user
        self.door_id = bom_helpers.create_door(self.db, bom_helpers.BomGenerationTest.base_params(), sales_order_id=501)
        result = self.helper.service.generate(self.door_id, self.user)
        self.parts = [row for row in result["components"] if row["item_kind"] == "manufactured_part"]
        self.package_id = self.parts[0]["technical_package_id"]
        with self.db.transaction() as conn:
            conn.execute("UPDATE fulfillment_components SET planned_quantity=4 WHERE technical_package_id=? AND item_kind='manufactured_part'", (self.package_id,))
        self.service = InventoryService(self.db.inventory_db)

    def tearDown(self):
        self.helper.tearDown()

    def inbound(self, part, quantity=4, warehouse="半成品仓", location="A"):
        return self.db.component_inbound(self.door_id, SimpleNamespace(component_id=part["id"], quantity=quantity, warehouse=warehouse, location=location, remark="test"), self.user)

    def issue(self, part, quantity, warehouse="半成品仓", location=""):
        with self.db.transaction() as conn:
            conn.execute("""INSERT INTO fulfillment_inventory_movements(
                door_unit_id, technical_package_id, component_id, movement_type, item_name,
                warehouse, location, quantity, unit, operator_uid, created_at
                ) VALUES (?, ?, ?, '拼装领用', ?, ?, ?, ?, ?, 'A', ?)""",
                (self.door_id, self.package_id, part["id"], part["name"], warehouse, location, quantity, part["unit"], fulfillment_now()))

    def test_new_issue_uses_actual_locations_and_keeps_manufacturing_status(self):
        original_status = self.db.get_door_unit(self.door_id)["status"]
        for part in self.parts:
            self.inbound(part, 1, "定制半成品仓", "A")
            self.inbound(part, 3, "定制半成品仓", "B")
        _, changed = self.db.issue_assembly_components(self.door_id, "test", self.user)
        self.assertEqual(changed, len(self.parts))
        rows = self.db.fetch_all("SELECT warehouse, location, quantity FROM fulfillment_inventory_movements WHERE movement_type='拼装领用'")
        self.assertEqual(len(rows), len(self.parts) * 2)
        self.assertTrue(all(row["warehouse"] == "定制半成品仓" for row in rows))
        self.assertEqual({row["location"] for row in rows}, {"A", "B"})
        self.assertEqual(self.service.warehouse_overview()["tracked_items"], [])
        self.assertEqual(self.db.get_door_unit(self.door_id)["status"], original_status)
        with self.assertRaises(RuntimeError):
            self.db.issue_assembly_components(self.door_id, "repeat", self.user)

    def test_legacy_issue_consumes_fifo_without_rewriting_history(self):
        part = self.parts[0]
        self.inbound(part, 1, location="A")
        self.inbound(part, 3, location="B")
        self.issue(part, 2)
        before = self.db.fetch_all("SELECT * FROM fulfillment_inventory_movements")
        rows = self.service.warehouse_overview()["tracked_items"]
        self.assertEqual([(row["location"], row["quantity"]) for row in rows], [("B", 2)])
        self.assertTrue(rows[0]["source_inferred"])
        self.assertEqual(before, self.db.fetch_all("SELECT * FROM fulfillment_inventory_movements"))
        detail = self.db.get_door_unit(self.door_id)["component_inventory"][0]
        self.assertEqual(detail["available_quantity"], 2)
        self.assertTrue(detail["source_inferred"])

    def test_legacy_default_warehouse_can_consume_alternate_name(self):
        self.inbound(self.parts[0], warehouse="车间半成品", location="A")
        self.issue(self.parts[0], 4)
        self.assertEqual(self.service.warehouse_overview()["tracked_items"], [])

    def test_explicit_wrong_location_preserves_negative_anomaly(self):
        self.inbound(self.parts[0])
        self.issue(self.parts[0], 1, location="missing")
        rows = self.service.warehouse_overview()["tracked_items"]
        self.assertEqual(sum(row["quantity"] for row in rows), 3)
        negative = next(row for row in rows if row["location"] == "missing")
        self.assertEqual(negative["quantity"], -1)
        self.assertEqual(negative["available_quantity"], 0)
        self.assertTrue(negative["stock_anomaly"])

    def test_shortage_rolls_back_all_issues(self):
        self.inbound(self.parts[0])
        with self.assertRaises(RuntimeError):
            self.db.issue_assembly_components(self.door_id, "shortage", self.user)
        self.assertEqual(self.db.fetch_all("SELECT id FROM fulfillment_inventory_movements WHERE movement_type='拼装领用'"), [])

    def test_exact_warehouse_wins_over_type_and_ambiguous_name_stays_unassigned(self):
        warehouse = self.service.create_warehouse("SEMI2", "半成品二仓", "半成品")
        self.inbound(self.parts[0], warehouse="半成品二仓")
        self.inbound(self.parts[1], warehouse="旧仓库名")
        rows = self.service.warehouse_overview()["tracked_items"]
        exact = next(row for row in rows if row["component_id"] == self.parts[0]["id"])
        unknown = next(row for row in rows if row["component_id"] == self.parts[1]["id"])
        self.assertEqual(exact["warehouse_id"], warehouse["id"])
        self.assertIsNone(unknown["warehouse_id"])
        summary = next(row for row in self.service.warehouse_overview()["warehouses"] if row["id"] == warehouse["id"])
        self.assertEqual(summary["tracked_count"], 1)

    def test_unique_type_fallback_is_marked_inferred(self):
        self.inbound(self.parts[0], warehouse="历史半成品库")
        row = self.service.warehouse_overview()["tracked_items"][0]
        self.assertIsNotNone(row["warehouse_id"])
        self.assertTrue(row["warehouse_inferred"])

    def test_other_component_stock_is_not_consumed(self):
        self.inbound(self.parts[0])
        self.inbound(self.parts[1])
        self.issue(self.parts[0], 4)
        rows = self.service.warehouse_overview()["tracked_items"]
        self.assertEqual([(row["component_id"], row["quantity"]) for row in rows], [(self.parts[1]["id"], 4)])

    def test_new_issue_after_partial_legacy_issue_uses_remaining_sources(self):
        for part in self.parts:
            self.inbound(part, 1, location="A")
            self.inbound(part, 3, location="B")
            self.issue(part, 2)
        self.db.issue_assembly_components(self.door_id, "remaining", self.user)
        self.assertEqual(self.service.warehouse_overview()["tracked_items"], [])
        rows = self.db.fetch_all("SELECT location, quantity FROM fulfillment_inventory_movements WHERE movement_type='拼装领用' AND location!=''")
        self.assertEqual(len(rows), len(self.parts))
        self.assertTrue(all(row["location"] == "B" and row["quantity"] == 2 for row in rows))

    def test_version_and_door_scopes_do_not_consume_each_others_stock(self):
        self.inbound(self.parts[0])
        other_door = bom_helpers.create_door(self.db, bom_helpers.BomGenerationTest.base_params(), sales_order_id=502)
        with self.db.transaction() as conn:
            now = fulfillment_now()
            version = conn.execute("""INSERT INTO fulfillment_technical_packages(
                door_unit_id, version, product_snapshot_json, created_by, created_at, updated_at
                ) VALUES (?, 2, '{}', 'A', ?, ?)""", (self.door_id, now, now)).lastrowid
            # Deliberately reuse a component ID to test the complete inventory subject key.
            for door, package in [(self.door_id, version), (other_door, self.package_id)]:
                conn.execute("""INSERT INTO fulfillment_inventory_movements(
                    door_unit_id, technical_package_id, component_id, movement_type,
                    item_name, warehouse, quantity, unit, operator_uid, created_at
                    ) VALUES (?, ?, ?, '拼装领用', 'isolated', '半成品仓', 1, '件', 'A', ?)""",
                    (door, package, self.parts[0]["id"], now))
            rows = semi_finished_balances(conn, door_id=self.door_id, package_id=self.package_id)
        self.assertEqual(sum(row["quantity"] for row in rows), 4)

    def test_anomalous_sources_block_assembly_without_partial_writes(self):
        for part in self.parts:
            self.inbound(part)
        self.issue(self.parts[-1], 1, location="wrong")
        before = self.db.fetch_all("SELECT * FROM fulfillment_inventory_movements")
        with self.assertRaises(RuntimeError):
            self.db.issue_assembly_components(self.door_id, "anomaly", self.user)
        self.assertEqual(before, self.db.fetch_all("SELECT * FROM fulfillment_inventory_movements"))


if __name__ == "__main__":
    unittest.main()
