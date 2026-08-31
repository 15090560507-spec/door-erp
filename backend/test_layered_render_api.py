"""
分层效果图 API 端到端测试。

测试:
  1. 创建图纸任务
  2. POST /api/layered-render/generate 生成分层效果图
  3. 记录含 PSD/完整/正面/反面 文件 URL
  4. 文件可通过 /api/render/files/... 下载
  5. 历史记录列表 / 删除

用法:
  cd backend
  py -3.12 test_layered_render_api.py
"""
import os
import sys
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="door_layered_api_test_")
os.environ["JWT_SECRET"] = "test-secret-for-layered-api-0123456789abcdef"
os.environ["ADMIN_PASSWORD"] = "admin888"

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


print(f"Test data dir: {os.environ['DATA_DIR']}")
client = TestClient(app_module.app)

resp = client.post("/api/login", json={"uid": "admin", "pwd": "admin888"})
token = resp.json().get("token")
check("admin login returns token", bool(token), str(resp.json()))
HEADERS = {"Authorization": f"Bearer {token}"}

BASE_PARAMS = {
    "product_name": "不锈钢镀铜门",
    "material": "0.8mm",
    "ys": "2号色",
    "mshd": 80,
    "st_val": "标准锁体",
    "dhdw": "分层效果图测试客户",
    "gdmc": "测试项目",
    "ddh": "DDH-LAYER-001",
    "dhrq": "2026.01.15",
    "door_type": "单门",
    "sel_kx": "右开",
    "sel_nk": "内开",
    "dw": 1200,
    "dh": 2300,
}

resp = client.post("/api/tasks", json={"params": BASE_PARAMS, "ref_text": "", "ref_images": []}, headers=HEADERS)
check("create task returns 200", resp.status_code == 200, str(resp.text[:200]))
task = resp.json()
task_id = task.get("id", "")
check("task has id", bool(task_id))

resp = client.post("/api/layered-render/generate", json={"taskId": task_id, "dpi": 300, "targetLongEdge": 1600, "faces": "both"}, headers=HEADERS)
check("generate returns 200", resp.status_code == 200, str(resp.text[:300]))
record = resp.json().get("record", {}) if resp.status_code == 200 else {}
files = record.get("files", {})
check("record has psd file", bool(files.get("psd", {}).get("url")), str(list(files.keys())))
check("record has complete file", bool(files.get("complete", {}).get("url")))
check("record has front file", bool(files.get("front", {}).get("url")))
check("record has back file", bool(files.get("back", {}).get("url")))

# 下载文件验证（PSD 字节以 8BPS 开头）
psd_url = files.get("psd", {}).get("url", "")
if psd_url:
    path = psd_url.split("/api", 1)[1]
    resp = client.get(f"/api{path}", headers=HEADERS)
    check("psd file downloadable", resp.status_code == 200 and resp.content[:4] == b"8BPS", f"status={resp.status_code}")
    resp = client.get(f"/api{path}", params={"download": "1", "name": "测试客户-分层效果图.psd"}, headers=HEADERS)
    check("download param sets attachment header", resp.status_code == 200 and "attachment" in resp.headers.get("content-disposition", ""), str(resp.headers.get("content-disposition", "")))

# 无 AI 时 materialMode 应为 flat
check("flat material mode without model config", record.get("materialMode") == "flat", str(record.get("materialMode")))

# AI 模型配置接入：配置不可达的模型 → 生成成功并回退默认材质，且带原因
resp = client.post("/api/render/model-configs", json={
    "name": "分层测试模型",
    "provider": "openai_compatible",
    "baseUrl": "https://fake.example.com",
    "apiKey": "test-key",
    "model": "test-model",
    "endpoint": "/images/edits",
    "apiType": "openai_images_edits",
    "timeoutSeconds": 5,
    "enabled": True,
}, headers=HEADERS)
check("create model config returns 200", resp.status_code == 200, str(resp.text[:200]))
config_id = resp.json().get("config", {}).get("id", "") if resp.status_code == 200 else ""

resp = client.post("/api/layered-render/generate", json={
    "taskId": task_id,
    "dpi": 300,
    "targetLongEdge": 1600,
    "faces": "both",
    "modelConfigId": config_id,
    "referenceAssetIds": [],
}, headers=HEADERS)
check("ai generate returns 200 (fallback)", resp.status_code == 200, str(resp.text[:300]))
ai_record = resp.json().get("record", {}) if resp.status_code == 200 else {}
check("ai fallback materialMode=flat", ai_record.get("materialMode") == "flat", str(ai_record.get("materialMode")))
check("ai fallback has materialNote", bool(ai_record.get("materialNote")), str(ai_record.get("materialNote")))

# 历史列表
resp = client.get("/api/layered-render/records", headers=HEADERS)
check("records list returns record", resp.status_code == 200 and len(resp.json().get("records", [])) >= 1, str(resp.text[:200]))

# 删除
if record.get("id"):
    resp = client.delete(f"/api/layered-render/records/{record['id']}", headers=HEADERS)
    check("delete record returns ok", resp.status_code == 200, str(resp.text[:200]))

print(f"\n{PASSED} PASS / {FAILED} FAIL")
sys.exit(1 if FAILED else 0)
