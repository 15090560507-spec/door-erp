"""Dependency, material gate and weighted workshop progress tests."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from fulfillment_database import FulfillmentDatabase, fulfillment_now
from fulfillment_models import WorkPackageAction, WorkPackageBatchAction
from inventory_service import InventoryService
from material_flow_service import MaterialFlowService
from test_bom_generation import create_door


class WorkPackageDependenciesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="door-work-packages-")
        self.db = FulfillmentDatabase(
            os.path.join(self.temp_dir, "fulfillment.db"),
            os.path.join(self.temp_dir, "files"),
        )
        self.user = {"uid": "A", "name": "销售小A"}
        self.inventory = InventoryService(self.db.inventory_db)
        self.flow = MaterialFlowService(self.db.inventory_db)
        warehouse = next(row for row in self.inventory.list_warehouses() if row["code"] == "RAW")
        self.warehouse = warehouse
        self.location = self.inventory.create_location(warehouse["id"], "WP-01", "工作包测试区")
        self.panel_material = self._material("WP-PANEL", "门板原料", "张")
        self.fitting_material = self._material("WP-HINGE", "合页", "个")
        for material, quantity in ((self.panel_material, 2), (self.fitting_material, 3)):
            self.inventory.post_transaction(
                material_id=material["id"], warehouse_id=warehouse["id"],
                location_id=self.location["id"], transaction_type="期初入库",
                quantity=quantity, unit=material["unit"], source_type="test",
                source_id=f"opening-{material['id']}",
            )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _material(self, code: str, name: str, unit: str) -> dict:
        return self.inventory.create_material(
            code=code, name=name, category="测试", specification="标准",
            unit=unit, material_type="原材料",
            default_warehouse_id=self.warehouse["id"],
            default_location_id=self.location["id"],
        )

    def _prepare(self) -> int:
        door_id = create_door(self.db, {
            "product_name": "不锈钢镀铜门", "door_type": "单门",
            "dw": 1000, "dh": 2200,
        }, sales_order_id=81)
        package = self.db.latest_bom_package(door_id)
        now = fulfillment_now()
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM fulfillment_components WHERE technical_package_id=?", (package["id"],))
            conn.execute(
                """INSERT INTO fulfillment_components(
                       technical_package_id, material_id, name, category, specification,
                       quantity, unit, acquisition_method, sequence_no, line_no, group_code,
                       theoretical_quantity, planned_quantity, source_type, match_status,
                       verification_status, operation_code
                   ) VALUES
                       (?, ?, '门板原料', '门板', '标准', 2, '张', '库存领用', 1, 1,
                        'panel', 2, 2, 'manual', '已匹配', '已核验', 'PANEL'),
                       (?, ?, '合页', '五金', '标准', 3, '个', '库存领用', 2, 2,
                        'hardware', 3, 3, 'manual', '已匹配', '已核验', 'HINGE'),
                       (?, NULL, '门框加工总成', '门框', '后续完善', 1, '套', '内部加工', 3, 3,
                        'frame', 1, 1, 'manual', '无需物料', '已核验', 'FRAME_ASSEMBLY')""",
                (package["id"], self.panel_material["id"], package["id"], self.fitting_material["id"], package["id"]),
            )
            conn.execute("UPDATE fulfillment_technical_packages SET generation_status='已生成', updated_at=? WHERE id=?", (now, package["id"]))
        self.db.publish_bom(door_id, "测试发布", self.user)
        return door_id

    @staticmethod
    def _by_code(door: dict) -> dict[str, dict]:
        return {
            row["operation_code"]: row
            for row in door["technical_package"]["work_packages"]
        }

    def _issue_component(self, door_id: int, operation_code: str) -> None:
        door = self.db.get_door_unit(door_id)
        requirement = door["material_requirement"]
        item = next(
            row for row in requirement["items"]
            if self.db.fetch_one("SELECT operation_code FROM fulfillment_components WHERE id=?", (row["component_id"],))["operation_code"] == operation_code
        )
        reservation = self.db.fetch_one(
            "SELECT * FROM inventory_reservations WHERE requirement_item_id=? AND status='有效' ORDER BY id LIMIT 1",
            (item["id"],),
        )
        self.flow.issue({
            "requirement_id": requirement["id"],
            "items": [{
                "requirement_item_id": item["id"],
                "reservation_id": reservation["id"],
                "quantity": item["required_quantity"],
            }],
        }, "warehouse-a")

    def test_parallel_material_gates_and_dependencies(self):
        door_id = self._prepare()
        door = self.db.get_door_unit(door_id)
        packages = self._by_code(door)

        self.assertNotIn("FRAME_ASSEMBLY", packages)
        self.assertEqual(packages["TECH_PREP"]["readiness_status"], "可执行")
        self.assertEqual(packages["PANEL_PREP"]["readiness_status"], "待前序")
        self.assertEqual(packages["FITTINGS_PREP"]["readiness_status"], "待前序")

        tech_id = packages["TECH_PREP"]["id"]
        self.db.update_work_package(tech_id, WorkPackageAction(status="进行中"), self.user)
        self.db.update_work_package(tech_id, WorkPackageAction(status="已完成", actual_quantity=1), self.user)
        packages = self._by_code(self.db.get_door_unit(door_id))
        self.assertEqual(packages["PANEL_PREP"]["readiness_status"], "待物料")
        self.assertEqual(packages["FITTINGS_PREP"]["readiness_status"], "待物料")

        self._issue_component(door_id, "PANEL")
        packages = self._by_code(self.db.get_door_unit(door_id))
        self.assertEqual(packages["PANEL_PREP"]["readiness_status"], "可执行")
        self.assertEqual(packages["FITTINGS_PREP"]["readiness_status"], "待物料")
        with self.assertRaisesRegex(RuntimeError, "尚不可执行"):
            self.db.update_work_package(
                packages["FITTINGS_PREP"]["id"], WorkPackageAction(status="进行中"), self.user,
            )

        panel_prep_id = packages["PANEL_PREP"]["id"]
        self.db.update_work_package(panel_prep_id, WorkPackageAction(status="进行中"), self.user)
        self.db.update_work_package(panel_prep_id, WorkPackageAction(status="已完成", actual_quantity=1), self.user)
        packages = self._by_code(self.db.get_door_unit(door_id))
        self.assertEqual(packages["PANEL_CUT"]["readiness_status"], "可执行")

        self._issue_component(door_id, "HINGE")
        packages = self._by_code(self.db.get_door_unit(door_id))
        self.assertEqual(packages["FITTINGS_PREP"]["readiness_status"], "可执行")
        self.assertGreater(self.db.get_door_unit(door_id)["progress"], 0)

    def test_skip_requires_reason_and_is_audited(self):
        door_id = self._prepare()
        work_id = self._by_code(self.db.get_door_unit(door_id))["TECH_PREP"]["id"]
        with self.assertRaisesRegex(ValueError, "必须填写原因"):
            self.db.batch_work_packages(
                door_id, WorkPackageBatchAction(work_ids=[work_id], action="跳过"), self.user,
            )
        door, changed = self.db.batch_work_packages(
            door_id,
            WorkPackageBatchAction(work_ids=[work_id], action="跳过", remark="该工序由已确认外部工艺替代"),
            self.user,
        )
        skipped = self._by_code(door)["TECH_PREP"]
        self.assertEqual(changed, 1)
        self.assertEqual(skipped["readiness_status"], "已跳过")
        self.assertEqual(skipped["skip_reason"], "该工序由已确认外部工艺替代")
        self.assertTrue(any(event["action"] == "批量跳过" for event in door["events"]))

    def test_batch_completion_follows_dependencies_without_repeated_start_clicks(self):
        door_id = self._prepare()
        packages = self._by_code(self.db.get_door_unit(door_id))
        self._issue_component(door_id, "PANEL")
        self._issue_component(door_id, "HINGE")

        ordered_ids = [
            row["id"]
            for row in self.db.get_door_unit(door_id)["technical_package"]["work_packages"]
            if not row["inspection_required"]
        ]
        door, changed = self.db.batch_work_packages(
            door_id,
            WorkPackageBatchAction(
                work_ids=ordered_ids, action="确认完成", executor_uid="worker-a",
                scrap_quantity=0, actual_minutes=30, remark="按依赖顺序批量报工",
            ),
            self.user,
        )
        current = self._by_code(door)
        self.assertEqual(changed, len(ordered_ids))
        self.assertTrue(all(current[code]["status"] == "已完成" for code in current if code != "QC_HANDOFF"))
        self.assertEqual(current["QC_HANDOFF"]["readiness_status"], "可执行")
        self.assertEqual(current["PANEL_CUT"]["actual_minutes"], 30)


if __name__ == "__main__":
    unittest.main()
