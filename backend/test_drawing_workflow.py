import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="door_drawing_workflow_test_")
os.environ["JWT_SECRET"] = "test-secret-for-drawing-workflow-0123456789"
os.environ["ADMIN_PASSWORD"] = "admin888"

from fastapi.testclient import TestClient  # noqa: E402

import main as app_module  # noqa: E402


app_module.app.router.on_startup.clear()
client = TestClient(app_module.app)
login = client.post("/api/login", json={"uid": "A", "pwd": "123"})
HEADERS = {"Authorization": f"Bearer {login.json()['token']}"}

VALID_PARAMS = {
    "product_name": "不锈钢镀铜门",
    "material": "0.8mm",
    "ys": "2号色",
    "mshd": 80,
    "st_val": "标准锁体",
    "dhdw": "复制测试客户",
    "gdmc": "任务工作流",
    "ddh": "COPY-001",
    "dhrq": "2026.09.30",
    "door_type": "单门",
    "sel_kx": "左右开",
    "sel_nk": "内外开",
    "dw": 980,
    "dh": 2200,
}


def test_combined_openings_select_both_directions():
    assert app_module._opening_selected("左右开", "左开")
    assert app_module._opening_selected("左右开", "右开")
    assert app_module._opening_selected("内外开", "内开")
    assert app_module._opening_selected("内外开", "外开")


def test_required_fields_copy_and_overview_flow():
    for field, message in (
        ("ys", "颜色为必填项"),
        ("mshd", "门扇厚度为必填项"),
        ("sel_kx", "左右开向至少选择一项"),
        ("sel_nk", "内外开向至少选择一项"),
    ):
        invalid = dict(VALID_PARAMS)
        invalid[field] = ""
        response = client.post("/api/tasks", json={"params": invalid}, headers=HEADERS)
        assert response.status_code == 400
        assert response.json()["detail"] == message

    response = client.post(
        "/api/tasks",
        json={"params": VALID_PARAMS, "ref_text": "复制沟通记录", "ref_images": []},
        headers=HEADERS,
    )
    assert response.status_code == 200
    source = response.json()
    assert source["created_at"]
    assert source["status"] == "待绘制"

    response = client.post(f"/api/tasks/{source['id']}/copy", headers=HEADERS)
    assert response.status_code == 200
    copied = response.json()
    assert copied["id"] != source["id"]
    assert copied["params"] == source["params"]
    assert copied["ref_text"] == source["ref_text"]
    assert copied["status"] == "待绘制"
    assert copied["drawing_img_b64"] is None
    assert copied["history"] == []
    assert copied["quote_status"] == "未报价"
    assert copied["confirm_status"] == "未确认"

    response = client.put(f"/api/tasks/{source['id']}", json={"status": "已通过"}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["approved_at"]

    response = client.get("/api/tasks/overview", headers=HEADERS)
    assert response.status_code == 200
    overview = response.json()
    assert overview["total"] == 2
    assert overview["today_created"] == 2
    assert overview["status_counts"]["已通过"] == 1
    assert overview["status_counts"]["待绘制"] == 1
    assert sum(item["created"] for item in overview["trend"]) == 2
    assert sum(item["approved"] for item in overview["trend"]) == 1


def test_simple_products_do_not_require_opening_or_thickness():
    params = {
        "product_name": "牌匾",
        "material": "0.8mm",
        "ys": "3号色",
        "dhdw": "牌匾客户",
        "sl": "1件",
        "dw": 1200,
        "dh": 600,
        "sel_kx": "",
        "sel_nk": "",
        "mshd": "",
    }
    response = client.post("/api/tasks", json={"params": params}, headers=HEADERS)
    assert response.status_code == 200
