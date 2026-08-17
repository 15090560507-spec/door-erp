"""
任务汇总表/搜索/报价状态 后端测试脚本
测试:
  1. 创建任务后汇总表字段（时间/客户/项目/门型/尺寸）正确
  2. 修改表单参数后汇总表字段同步刷新（时间不再停留在第一次录入值）
  3. 未报价/已报价、未确认/已确认 状态切换与校验
  4. GET /api/tasks 关键词搜索 q

用法:
  cd backend
  py -3.12 test_task_summary_search.py
"""
import os
import sys
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="door_task_summary_test_")
os.environ["JWT_SECRET"] = "test-secret-for-task-summary-0123456789abcdef"
os.environ["ADMIN_PASSWORD"] = "admin888"

import config as cfg  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
import main as app_module  # noqa: E402

PASSED = 0
FAILED = 0


def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}  -- {detail}")


def section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


print(f"Test data dir: {os.environ['DATA_DIR']}")

client = TestClient(app_module.app)

# 登录 admin
resp = client.post("/api/login", json={"uid": "admin", "pwd": "admin888"})
token = resp.json().get("token")
check("admin login returns token", bool(token), str(resp.json()))
HEADERS = {"Authorization": f"Bearer {token}"}

BASE_PARAMS = {
    "product_name": "不锈钢镀铜门",
    "material": "0.8mm",
    "st_val": "标准锁体",
    "dhdw": "杭州测试客户",
    "gdmc": "湖畔花园项目",
    "ddh": "DDH-2026-001",
    "dhrq": "2026.01.15",
    "door_type": "单门",
    "sel_kx": "右开",
    "sel_nk": "内开",
    "dw": 980,
    "dh": 2200,
}

# ==================== 1. 创建任务：汇总表字段 ====================
section("1. Create task summary fields")
resp = client.post("/api/tasks", json={"params": BASE_PARAMS, "ref_text": "", "ref_images": []}, headers=HEADERS)
check("create task returns 200", resp.status_code == 200, str(resp.text[:200]))
task = resp.json() if resp.status_code == 200 else {}
task_id = task.get("id", "")
check("task has id", bool(task_id))
check("summary date = dhrq", task.get("date") == "2026.01.15", str(task.get("date")))
check("summary customer = dhdw", task.get("customer") == "杭州测试客户", str(task.get("customer")))
check("summary project = gdmc", task.get("project") == "湖畔花园项目", str(task.get("project")))
check("summary size from dw x dh", task.get("size") == "980 x 2200 (洞口)", str(task.get("size")))
check("default quote_status 未报价", task.get("quote_status") == "未报价", str(task.get("quote_status")))
check("default confirm_status 未确认", task.get("confirm_status") == "未确认", str(task.get("confirm_status")))

# ==================== 2. 修改表单参数 → 汇总表同步刷新 ====================
section("2. Summary refresh after param update")
updated_params = dict(BASE_PARAMS, dhrq="2026.03.20", dhdw="上海新客户", gdmc="外滩项目", dw=1080, dh=2300, door_type="对开门")
resp = client.put(f"/api/tasks/{task_id}", json={"params": updated_params}, headers=HEADERS)
check("update task returns 200", resp.status_code == 200, str(resp.text[:200]))
updated = resp.json() if resp.status_code == 200 else {}
check("summary date refreshed to new dhrq", updated.get("date") == "2026.03.20", str(updated.get("date")))
check("summary customer refreshed", updated.get("customer") == "上海新客户", str(updated.get("customer")))
check("summary project refreshed", updated.get("project") == "外滩项目", str(updated.get("project")))
check("summary size refreshed", updated.get("size") == "1080 x 2300 (洞口)", str(updated.get("size")))
check("summary door_type refreshed", updated.get("door_type") == "对开门", str(updated.get("door_type")))

# ==================== 3. 报价/确认状态切换 ====================
section("3. Quote / confirm status toggles")
resp = client.put(f"/api/tasks/{task_id}", json={"quote_status": "已报价"}, headers=HEADERS)
check("set quote_status 已报价", resp.status_code == 200 and resp.json().get("quote_status") == "已报价", str(resp.text[:200]))
resp = client.put(f"/api/tasks/{task_id}", json={"quote_status": "未报价"}, headers=HEADERS)
check("set quote_status back 未报价", resp.status_code == 200 and resp.json().get("quote_status") == "未报价", str(resp.text[:200]))
resp = client.put(f"/api/tasks/{task_id}", json={"confirm_status": "已确认"}, headers=HEADERS)
check("set confirm_status 已确认", resp.status_code == 200 and resp.json().get("confirm_status") == "已确认", str(resp.text[:200]))
resp = client.put(f"/api/tasks/{task_id}", json={"quote_status": "随便写"}, headers=HEADERS)
check("invalid quote_status rejected with 400", resp.status_code == 400, str(resp.status_code))
resp = client.put(f"/api/tasks/{task_id}", json={"confirm_status": "随便写"}, headers=HEADERS)
check("invalid confirm_status rejected with 400", resp.status_code == 400, str(resp.status_code))

# ==================== 4. 搜索检索 q ====================
section("4. Keyword search q")
client.post("/api/tasks", json={"params": dict(BASE_PARAMS, dhdw="宁波装饰城", gdmc="市场门店", ddh="DDH-NB-009", dhrq="2026.02.02")}, headers=HEADERS)

resp = client.get("/api/tasks", params={"q": "上海新客户"}, headers=HEADERS)
matches = resp.json().get("tasks", [])
check("q matches customer", len(matches) == 1 and matches[0]["customer"] == "上海新客户", str([t["customer"] for t in matches]))

resp = client.get("/api/tasks", params={"q": "外滩"}, headers=HEADERS)
matches = resp.json().get("tasks", [])
check("q matches project keyword", len(matches) >= 1 and all("外滩" in (t.get("project") or "") or "外滩" in str((t.get("params") or {}).get("gdmc") or "") for t in matches), str([t["project"] for t in matches]))

resp = client.get("/api/tasks", params={"q": "DDH-NB-009"}, headers=HEADERS)
matches = resp.json().get("tasks", [])
check("q matches order number", len(matches) == 1 and matches[0]["customer"] == "宁波装饰城", str([t["customer"] for t in matches]))

resp = client.get("/api/tasks", params={"q": "不存在的关键词xyz"}, headers=HEADERS)
check("q with no hit returns empty", resp.json().get("total") == 0, str(resp.json().get("total")))

resp = client.get("/api/tasks", params={"q": "2026.03.20"}, headers=HEADERS)
matches = resp.json().get("tasks", [])
check("q matches date text", len(matches) >= 1 and matches[0]["date"] == "2026.03.20", str([t["date"] for t in matches]))

print(f"\nPASS: {PASSED}")
print(f"FAIL: {FAILED}")
if FAILED:
    sys.exit(1)
