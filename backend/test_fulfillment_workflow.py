"""Focused checks for the five-stage door fulfillment projection."""

import unittest

from fulfillment_database import build_fulfillment_workflow


def make_door() -> dict:
    return {
        "status": "技术准备中",
        "technical_package": {
            "version": 1,
            "status": "草稿",
            "generation_status": "已生成",
            "blocking_warning_count": 0,
            "components": [
                {
                    "name": "测试物料", "category": "门板", "planned_quantity": 1,
                    "unit": "件", "acquisition_method": "库存领料",
                    "procurement_mode": "stock", "item_kind": "material",
                    "material_id": 1,
                    "match_status": "已匹配",
                    "verification_status": "已核验",
                }
            ],
            "work_packages": [{"status": "草稿", "readiness_status": "待发布"}],
        },
        "material_requirement": None,
        "inspections": [],
        "inventory_movements": [],
        "shipments": [],
        "exceptions": [],
    }


class FulfillmentWorkflowTests(unittest.TestCase):
    def test_draft_bom_blocks_production_preparation(self) -> None:
        workflow = build_fulfillment_workflow(make_door())

        self.assertEqual(workflow["current_stage"], "preparation")
        self.assertEqual(workflow["stages"][0]["state"], "blocked")
        self.assertIn("BOM尚未发布", workflow["stages"][0]["blockers"])

    def test_published_bom_requires_calculation_before_execution(self) -> None:
        door = make_door()
        door["technical_package"]["status"] = "已确认"
        workflow = build_fulfillment_workflow(door)

        self.assertEqual(workflow["current_stage"], "calculation")
        self.assertEqual(workflow["stages"][0]["state"], "complete")
        self.assertEqual(workflow["stages"][1]["state"], "blocked")
        self.assertIn("尚未建立算料清单", workflow["stages"][1]["blockers"])

    def test_material_shortage_blocks_only_the_combined_execution_stage(self) -> None:
        door = make_door()
        door["technical_package"]["status"] = "已确认"
        door["calculation"] = {"status": "已发布"}
        door["technical_package"]["work_packages"] = [
            {"status": "待排单", "readiness_status": "待物料", "blocked_reason": "板材待发料"}
        ]
        door["material_requirement"] = {
            "items": [
                {
                    "required_quantity": 2,
                    "issued_quantity": 0,
                    "returned_quantity": 0,
                    "shortage_quantity": 2,
                }
            ]
        }

        workflow = build_fulfillment_workflow(door)
        self.assertEqual(workflow["current_stage"], "execution")
        self.assertEqual(workflow["stages"][0]["state"], "complete")
        self.assertEqual(workflow["stages"][1]["state"], "complete")
        self.assertEqual(workflow["stages"][2]["state"], "blocked")

        door["material_requirement"]["items"][0].update({"issued_quantity": 2, "shortage_quantity": 0})
        door["technical_package"]["work_packages"][0].update(
            {"readiness_status": "可执行", "blocked_reason": ""}
        )
        workflow = build_fulfillment_workflow(door)
        self.assertEqual(workflow["current_stage"], "execution")
        self.assertEqual(workflow["stages"][2]["state"], "current")

        door["technical_package"]["work_packages"][0]["status"] = "已完成"
        workflow = build_fulfillment_workflow(door)
        self.assertEqual(workflow["current_stage"], "quality")
        self.assertIn("尚未通过成品质检", workflow["stages"][3]["blockers"])

        door["inspections"] = [{"inspection_type": "成品质检", "result": "合格"}]
        door["inventory_movements"] = [{"movement_type": "成品入库"}]
        door["sales_finance"] = {"unpaid_amount": 500}
        workflow = build_fulfillment_workflow(door)
        self.assertEqual(workflow["current_stage"], "delivery")
        self.assertIn("订单尚有未收款500.00元", workflow["stages"][4]["blockers"])

        door["shipments"] = [{"status": "已签收"}]
        workflow = build_fulfillment_workflow(door)
        self.assertEqual(workflow["current_stage"], "complete")
        self.assertTrue(all(stage["state"] == "complete" for stage in workflow["stages"]))


if __name__ == "__main__":
    unittest.main()
