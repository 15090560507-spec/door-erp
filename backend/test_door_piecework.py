"""Isolated whole-door fee, process snapshot and allocation regressions."""

import json
import unittest

import test_operations_workflow as workflows
import test_bom_generation as bom_tests
from bom_generation_service import BomGenerationService
from work_package_service import WorkPackageService


class DoorPieceworkTest(unittest.TestCase):
    setUp = workflows.OperationsWorkflowTest.setUp
    tearDown = workflows.OperationsWorkflowTest.tearDown
    create_employee = workflows.OperationsWorkflowTest.create_employee

    def publish(self, price="88.00"):
        template = self.client.get("/api/operations/route-templates").json()["templates"][0]
        for step in template["steps"]:
            if step["step_code"] == "BENDING":
                step.update(piece_rate=price, name="配置折弯", work_center="折弯二区", inspection_required=True)
        response = self.client.put(f"/api/operations/route-templates/{template['id']}", json=template)
        self.assertEqual(response.status_code, 200, response.text)
        door_id = bom_tests.create_door(self.db, bom_tests.BomGenerationTest.base_params(), sales_order_id=101)
        BomGenerationService(self.db).generate(door_id, self.user)
        package_id = self.db.fetch_one("SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=?", (door_id,))["id"]
        # This fixture tests self-made work without making any stock claims.
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM fulfillment_components WHERE technical_package_id=? AND procurement_mode!='make'", (package_id,))
        self.db.publish_bom(door_id, "隔离测试", self.user)
        fee = self.db.fetch_one("SELECT * FROM door_operation_fees WHERE door_unit_id=? AND billing_operation_code='BENDING'", (door_id,))
        self.assertIsNotNone(fee)
        return door_id, package_id, fee

    def finish(self, fee):
        with self.db.transaction() as conn:
            conn.execute("UPDATE fulfillment_work_packages SET status='已完成', completed_at='2026-09-20T10:00:00' WHERE id IN (SELECT work_package_id FROM door_operation_fee_work WHERE fee_id=?)", (fee["id"],))

    def allocate(self, fee, employee, amount="60.00", confirm=False, revision=None):
        return self.client.put(f"/api/operations/piecework/{fee['id']}/allocations", json={
            "revision": fee["revision"] if revision is None else revision,
            "confirm": confirm,
            "allocations": [{"employee_id": employee["id"], "amount": amount, "note": "测试"}],
        })

    def test_configured_route_prices_are_once_per_door(self):
        door, package, fee = self.publish()
        bends = self.db.fetch_all("SELECT * FROM fulfillment_work_packages WHERE technical_package_id=? AND operation_code='BEND'", (package,))
        self.assertGreaterEqual(len(bends), 2)
        self.assertEqual(fee["total_cents"], 8800)
        self.assertTrue(all(w["piece_rate"] == 0 and w["route_template_id"] for w in bends))
        self.assertTrue(all(w["work_center"] == "折弯二区" and w["inspection_required"] for w in bends))
        self.assertEqual(len(self.db.fetch_all("SELECT * FROM door_operation_fees WHERE door_unit_id=? AND billing_operation_code='PANEL_CUT'", (door,))), 1)
        self.assertTrue(all(json.loads(w["route_snapshot_json"])["billing_operation_code"] == "BENDING" for w in bends))

    def test_money_precision(self):
        from door_piecework_service import money_cents
        self.assertEqual(money_cents("0.10") + money_cents("0.20"), 30)
        for amount in ("-1", "0.001", "NaN", "Infinity"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                money_cents(amount)

    def test_completion_revision_and_immutable_confirmation(self):
        _, _, fee = self.publish()
        employee = self.create_employee()
        self.assertEqual(self.allocate(fee, employee, confirm=True).status_code, 409)
        self.finish(fee)
        saved = self.allocate(fee, employee)
        self.assertEqual(saved.status_code, 200, saved.text)
        saved_fee = saved.json()["fee"]
        self.assertEqual(saved_fee["remaining_cents"], 2800)
        self.assertEqual(self.allocate(fee, employee, amount="50").status_code, 409)
        confirmed = self.allocate(saved_fee, employee, confirm=True)
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["fee"]["status"], "已确认")
        repeated = self.allocate(saved_fee, employee, confirm=True)
        self.assertEqual(repeated.status_code, 200, repeated.text)
        events = self.db.fetch_all("SELECT * FROM fulfillment_events WHERE entity_type='piecework' AND entity_id=? AND action='确认计件分配'", (fee["id"],))
        self.assertEqual(len(events), 1)
        self.assertEqual(self.allocate(confirmed.json()["fee"], employee, "10").status_code, 409)
        payroll = self.client.post("/api/operations/payroll/calculate", json={"month": "2026-09"})
        self.assertEqual(payroll.status_code, 200, payroll.text)
        self.assertEqual(payroll.json()["period"]["entries"][0]["piecework_amount"], 60)
        period_id = payroll.json()["period"]["id"]
        for status in ("待审核", "已审批", "已锁定"):
            self.assertEqual(self.client.put(f"/api/operations/payroll/{period_id}/status", json={"status": status}).status_code, 200)
            if status != "待审核":
                self.assertEqual(self.client.post("/api/operations/payroll/calculate", json={"month": "2026-09"}).status_code, 409)

    def test_invalid_allocations_roll_back(self):
        _, _, fee = self.publish()
        self.finish(fee)
        employee = self.create_employee()
        for amount in ("88.01", "-1", "0.001", "NaN"):
            response = self.allocate(fee, employee, amount)
            self.assertIn(response.status_code, (400, 422), response.text)
        duplicated = self.client.put(f"/api/operations/piecework/{fee['id']}/allocations", json={"revision": 1, "allocations": [{"employee_id": employee["id"], "amount": "1"}] * 2})
        self.assertEqual(duplicated.status_code, 400, duplicated.text)
        self.assertEqual(self.db.fetch_all("SELECT * FROM door_operation_allocations"), [])
        self.assertEqual(self.db.fetch_one("SELECT revision FROM door_operation_fees WHERE id=?", (fee["id"],))["revision"], 1)

    def test_waiting_inspection_skipped_and_locked_month(self):
        _, _, fee = self.publish()
        employee = self.create_employee()
        for status in ("待质检", "返工", "已取消"):
            self.finish(fee)
            with self.db.transaction() as conn:
                conn.execute("UPDATE fulfillment_work_packages SET status=? WHERE id=(SELECT MIN(work_package_id) FROM door_operation_fee_work WHERE fee_id=?)", (status, fee["id"]))
            self.assertEqual(self.allocate(fee, employee, confirm=True).status_code, 409)
        self.finish(fee)
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO payroll_periods(month,status,created_at,updated_at) VALUES ('2026-09','已审批','now','now')")
        self.assertEqual(self.allocate(fee, employee, confirm=True).status_code, 409)
        with self.db.transaction() as conn:
            conn.execute("UPDATE payroll_periods SET status='已锁定' WHERE month='2026-09'")
        self.assertEqual(self.allocate(fee, employee, confirm=True).status_code, 409)

    def test_invalid_template_rolls_back(self):
        template = self.client.get("/api/operations/route-templates").json()["templates"][0]
        version = template["version"]
        for mutation in ("duplicate", "cycle", "inactive", "blank"):
            changed = json.loads(json.dumps(template))
            if mutation == "duplicate": changed["steps"][1]["step_code"] = changed["steps"][0]["step_code"]
            if mutation == "cycle": changed["steps"][0]["predecessor_codes"] = ["PANEL_PREP"]
            if mutation == "inactive": changed["steps"][0]["is_active"] = False
            if mutation == "blank": changed["steps"][0]["step_code"] = "  "
            response = self.client.put(f"/api/operations/route-templates/{template['id']}", json=changed)
            self.assertEqual(response.status_code, 400, response.text)
            self.assertEqual(self.client.get("/api/operations/route-templates").json()["templates"][0]["version"], version)

    def test_real_completion_does_not_create_legacy_wages_and_is_idempotent(self):
        from fulfillment_models import WorkPackageBatchAction, WorkPackageAction
        door, package, fee = self.publish()
        employee = self.create_employee()
        works = self.db.fetch_all("SELECT * FROM fulfillment_work_packages WHERE technical_package_id=? ORDER BY sequence_no,id", (package,))
        for work in works:
            # Persisted legacy rate must never leak into new-mode payroll.
            with self.db.transaction() as conn:
                conn.execute("UPDATE fulfillment_work_packages SET piece_rate=88 WHERE id=?", (work["id"],))
            if work["inspection_required"]:
                self.db.batch_work_packages(door, WorkPackageBatchAction(work_ids=[work["id"]], action="提交质检", executor_uid=employee["employee_no"]), self.user)
            self.db.batch_work_packages(door, WorkPackageBatchAction(work_ids=[work["id"]], action="确认完成", executor_uid=employee["employee_no"]), self.user)
        self.assertEqual(self.db.fetch_all("SELECT * FROM fulfillment_payroll_drafts"), [])
        bend = next(w for w in works if w["operation_code"] == "BEND")
        before = self.db.fetch_one("SELECT completed_at FROM fulfillment_work_packages WHERE id=?", (bend["id"],))["completed_at"]
        self.db.update_work_package(bend["id"], WorkPackageAction(status="已完成", executor_uid=employee["employee_no"]), self.user)
        self.assertEqual(self.db.fetch_one("SELECT completed_at FROM fulfillment_work_packages WHERE id=?", (bend["id"],))["completed_at"], before)
        self.assertEqual(self.db.fetch_all("SELECT * FROM fulfillment_payroll_drafts"), [])
        self.assertEqual(self.allocate(fee, employee, confirm=True).status_code, 200)

    def test_filtered_dependencies_snapshot_and_repeated_publication(self):
        door, package, fee = self.publish()
        before = self.db.fetch_all("SELECT * FROM fulfillment_work_packages WHERE technical_package_id=?", (package,))
        works = {w["id"]: w for w in before}
        deps = self.db.fetch_all("SELECT * FROM fulfillment_work_package_dependencies")
        for work in before:
            if work["operation_code"] in ("SURFACE", "WELD"):
                parents = [works[d["predecessor_id"]]["operation_code"] for d in deps if d["successor_id"] == work["id"]]
                self.assertEqual(parents, ["BEND"] if work["operation_code"] == "SURFACE" else ["CUT"])
        assembly = next(w for w in before if w["operation_code"] == "ASSEMBLY")
        self.assertTrue(any(d["successor_id"] == assembly["id"] for d in deps))
        template = self.client.get("/api/operations/route-templates").json()["templates"][0]
        next(s for s in template["steps"] if s["step_code"] == "BENDING").update(piece_rate="99", name="新折弯名称")
        self.assertEqual(self.client.put(f"/api/operations/route-templates/{template['id']}", json=template).status_code, 200)
        self.db.publish_bom(door, "重复发布", self.user)
        after = self.db.fetch_all("SELECT * FROM fulfillment_work_packages WHERE technical_package_id=?", (package,))
        self.assertEqual([w["route_snapshot_json"] for w in before], [w["route_snapshot_json"] for w in after])
        self.assertEqual(self.db.fetch_one("SELECT total_cents FROM door_operation_fees WHERE id=?", (fee["id"],))["total_cents"], 8800)

    def test_multiple_people_partial_precision_and_cancelled_orders(self):
        door, _, fee = self.publish("0.30")
        self.finish(fee)
        first, second = self.create_employee("E001"), self.create_employee("E002")
        payload = {"revision": 1, "confirm": True, "allocations": [
            {"employee_id": first["id"], "amount": "0.10"}, {"employee_id": second["id"], "amount": "0.20"}]}
        response = self.client.put(f"/api/operations/piecework/{fee['id']}/allocations", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["fee"]["remaining_cents"], 0)
        period = self.client.post("/api/operations/payroll/calculate", json={"month": "2026-09"}).json()["period"]
        self.assertEqual([e["piecework_amount"] for e in period["entries"]], [0.1, 0.2])
        with self.db.transaction() as conn:
            conn.execute("UPDATE fulfillment_orders SET status='已取消' WHERE id=(SELECT order_id FROM fulfillment_door_units WHERE id=?)", (door,))
        period = self.client.post("/api/operations/payroll/calculate", json={"month": "2026-09"}).json()["period"]
        self.assertTrue(all(e["piecework_amount"] == 0 for e in period["entries"]))

    def test_versions_clear_drafts_but_keep_confirmed_fees(self):
        from types import SimpleNamespace
        door, _, fee = self.publish()
        self.finish(fee)
        employee = self.create_employee()
        saved = self.allocate(fee, employee).json()["fee"]
        self.db.create_change(door, SimpleNamespace(reason="测试变更", impact_note="工艺"), self.user)
        changed_fee = next(item for item in self.db.get_door_unit(door)["operation_fees"] if item["id"] == fee["id"])
        self.assertEqual(changed_fee["status"], "需核对")
        self.assertEqual(self.allocate(saved, employee, confirm=True).status_code, 409)
        self.db.publish_bom(door, "发布变更", self.user)
        updated = self.db.fetch_one("SELECT * FROM door_operation_fees WHERE id=?", (fee["id"],))
        self.assertNotEqual(updated["technical_package_id"], fee["technical_package_id"])
        self.assertEqual(self.db.fetch_all("SELECT * FROM door_operation_allocations WHERE fee_id=?", (fee["id"],)), [])
        self.finish(updated)
        self.assertEqual(self.allocate(updated, employee, confirm=True).status_code, 200)
        frozen = self.db.fetch_one("SELECT * FROM door_operation_fees WHERE id=?", (fee["id"],))
        self.db.create_change(door, SimpleNamespace(reason="补加工", impact_note="不重复收费"), self.user)
        self.db.publish_bom(door, "发布补加工", self.user)
        self.assertEqual(frozen, self.db.fetch_one("SELECT * FROM door_operation_fees WHERE id=?", (fee["id"],)))
        latest = self.db.latest_bom_package(door)
        bends = self.db.fetch_all("SELECT route_snapshot_json FROM fulfillment_work_packages WHERE technical_package_id=? AND operation_code='BEND'", (latest["id"],))
        self.assertTrue(all(json.loads(w["route_snapshot_json"])["supplementary_work"] for w in bends))

    def test_inactive_people_zero_fee_and_migration_idempotence(self):
        door, _, fee = self.publish()
        self.finish(fee)
        employee = self.create_employee()
        with self.db.transaction() as conn:
            conn.execute("UPDATE workforce_employees SET is_active=0 WHERE id=?", (employee["id"],))
        self.assertEqual(self.allocate(fee, employee).status_code, 400)
        before = self.db.fetch_all("SELECT * FROM door_operation_fees")
        from door_piecework_service import migrate_piecework
        with self.db.transaction() as conn:
            migrate_piecework(conn)
            migrate_piecework(conn)
        self.assertEqual(before, self.db.fetch_all("SELECT * FROM door_operation_fees"))
        self.assertEqual(self.db.get_door_unit(door)["billing_mode"], "whole_door")

    def test_zero_price_does_not_block_production_but_cannot_be_allocated(self):
        _, _, fee = self.publish("0")
        self.finish(fee)
        self.assertEqual(self.allocate(fee, self.create_employee(), "0", confirm=True).status_code, 409)

    def test_explicit_split_cut_and_unconfigured_fallback(self):
        template = self.client.get("/api/operations/route-templates").json()["templates"][0]
        skin_cut = next(s for s in template["steps"] if s["step_code"] == "PANEL_CUT")
        skeleton_cut = {**skin_cut, "step_code": "SKELETON_CUT", "name": "骨架下料", "applicable_groups": ["skeleton"], "piece_rate": "12.30"}
        skin_cut.update(applicable_groups=["skin"], piece_rate="9.50")
        template["steps"].append(skeleton_cut)
        self.assertEqual(self.client.put(f"/api/operations/route-templates/{template['id']}", json=template).status_code, 200)
        door, package, _ = self.publish()
        fees = self.db.fetch_all("SELECT billing_operation_code,total_cents FROM door_operation_fees WHERE door_unit_id=?", (door,))
        self.assertEqual(next(f["total_cents"] for f in fees if f["billing_operation_code"] == "PANEL_CUT"), 950)
        self.assertEqual(next(f["total_cents"] for f in fees if f["billing_operation_code"] == "SKELETON_CUT"), 1230)
        self.assertEqual(sum(f["billing_operation_code"] == "SKELETON_CUT" for f in fees), 1)
        from component_route_service import component_route
        component = self.db.fetch_one("SELECT * FROM fulfillment_components WHERE technical_package_id=? LIMIT 1", (package,))
        component.update(operation_code="CUSTOM_PART", item_kind="manufactured_part")
        with self.db.transaction() as conn:
            nodes = component_route(conn, component)
        self.assertTrue(nodes)
        self.assertTrue(all(n.piece_rate == 0 and n.snapshot.get("process_unconfigured") and not n.snapshot.get("billing_operation_code") for n in nodes))

    def test_additive_migration_preserves_historical_money_and_mode(self):
        import sqlite3
        from door_piecework_service import migrate_piecework
        conn = sqlite3.connect(":memory:")
        try:
            conn.executescript("""
                CREATE TABLE fulfillment_door_units(id INTEGER PRIMARY KEY);
                INSERT INTO fulfillment_door_units VALUES (1);
                CREATE TABLE process_route_template_steps(step_code TEXT,piece_rate REAL);
                INSERT INTO process_route_template_steps VALUES ('BENDING',88.25);
                CREATE TABLE fulfillment_payroll_drafts(amount REAL);
                INSERT INTO fulfillment_payroll_drafts VALUES (176.50);
            """)
            migrate_piecework(conn)
            migrate_piecework(conn)
            self.assertEqual(conn.execute("SELECT billing_mode FROM fulfillment_door_units").fetchone()[0], "legacy")
            self.assertEqual(conn.execute("SELECT piece_rate FROM process_route_template_steps").fetchone()[0], 88.25)
            self.assertEqual(conn.execute("SELECT amount FROM fulfillment_payroll_drafts").fetchone()[0], 176.50)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM door_operation_fees").fetchone()[0], 0)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
