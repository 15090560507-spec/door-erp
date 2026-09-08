"""BOM version immutability and production-change tests."""

import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from bom_generation_service import BomGenerationService
from fulfillment_database import FulfillmentDatabase
from test_bom_generation import create_door


class BomVersionTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="door-bom-version-")
        self.db = FulfillmentDatabase(
            os.path.join(self.temp_dir, "fulfillment.db"),
            os.path.join(self.temp_dir, "files"),
        )
        self.service = BomGenerationService(self.db)
        self.user = {"uid": "A", "name": "销售小A"}
        self.door_id = create_door(self.db, {
            "product_name": "不锈钢镀铜门", "door_type": "单门",
            "dw": 1000, "dh": 2200, "material": "304不锈钢", "ys": "紫铜色",
            "fw_left_str": "55/75", "fw_right_str": "55/75", "fw_top_str": "85/100",
            "threshold_type": "高低槛", "zmks": "大板布局", "fmks": "大板布局",
            "sel_hys": "半钢暗合页", "hysl": "3个/扇", "sel_bz": "木箱",
        })

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_confirmed_version_is_immutable_and_change_creates_editable_v2(self):
        generated = self.service.generate(self.door_id, self.user)
        v1_id = int(generated["technical_package_id"])
        v1_count = len(generated["components"])
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE fulfillment_technical_packages SET status='已确认' WHERE id=?",
                (v1_id,),
            )

        with self.assertRaisesRegex(RuntimeError, "已确认"):
            self.service.generate(self.door_id, self.user)

        changed = self.db.create_change(
            self.door_id,
            SimpleNamespace(reason="客户变更颜色", impact_note="重新核验面板与表面处理"),
            self.user,
        )
        v2 = changed["technical_package"]
        self.assertEqual(v2["version"], 2)
        self.assertEqual(v2["status"], "草稿")
        self.assertEqual(len(v2["components"]), v1_count)

        self.service.generate(self.door_id, self.user)
        v1 = self.db.fetch_one("SELECT status FROM fulfillment_technical_packages WHERE id=?", (v1_id,))
        self.assertEqual(v1["status"], "已确认")
        self.assertEqual(
            self.db.fetch_one("SELECT COUNT(*) AS total FROM fulfillment_components WHERE technical_package_id=?", (v1_id,))["total"],
            v1_count,
        )


if __name__ == "__main__":
    unittest.main()
