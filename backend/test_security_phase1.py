import json
import os
import sys

from fastapi.testclient import TestClient

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from auth import create_token
from database import verify_password
from main import app, user_db
from quote_routes import ai_config_db


PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name} -- {detail}")


def auth_headers(uid: str) -> dict:
    return {"Authorization": f"Bearer {create_token(uid)}"}


def cleanup_user(uid: str):
    users = user_db.load_all_users()
    if uid in users and uid != "admin":
        del users[uid]
        user_db.save(users)


def main():
    client = TestClient(app)
    normal_uid = "security_normal"
    managed_uid = "security_created"
    secret_key = "sk-security-phase1-secret"
    old_ai_config = ai_config_db.get()

    cleanup_user(normal_uid)
    cleanup_user(managed_uid)
    user_db.add_or_update_user(normal_uid, "security123", "录入员", "安全测试普通用户")

    try:
        regular = auth_headers(normal_uid)
        admin = auth_headers("admin")

        resp = client.get("/api/users")
        check("未登录访问 /users 返回 401", resp.status_code == 401, resp.text)

        resp = client.get("/api/users", headers=regular)
        check("普通用户访问 /users 返回 403", resp.status_code == 403, resp.text)

        resp = client.post("/api/ai-config", json={"baseUrl": "https://example.test/v1", "apiKey": "sk-nope", "model": "m"}, headers=regular)
        check("普通用户不能修改 AI 配置", resp.status_code == 403, resp.text)

        resp = client.post(
            "/api/render/model-configs",
            json={
                "name": "普通用户不应创建",
                "provider": "image2_proxy",
                "baseUrl": "https://example.test",
                "apiKey": "sk-nope",
                "model": "gpt-image-2",
                "endpoint": "/images/edits",
                "apiType": "openai_images_edits",
            },
            headers=regular,
        )
        check("普通用户不能修改图片模型配置", resp.status_code == 403, resp.text)

        resp = client.post("/api/login", json={"uid": normal_uid, "pwd": "security123"})
        login_data = resp.json()
        check("登录响应成功", resp.status_code == 200 and login_data.get("success") is True, login_data)
        check("登录响应不包含 password", "password" not in (login_data.get("user") or {}), login_data)

        resp = client.post(
            "/api/users",
            json={"uid": managed_uid, "pwd": "created123", "role": "录入员", "name": "安全测试创建用户"},
            headers=admin,
        )
        check("超级管理员能新增用户", resp.status_code == 200, resp.text)

        resp = client.get("/api/users", headers=admin)
        users_data = resp.json()
        users = users_data.get("users", {})
        check("用户列表不包含 password", resp.status_code == 200 and all("password" not in info for info in users.values()), users_data)

        resp = client.put(f"/api/users/{managed_uid}/reset-password", json={"new_pwd": "new-created123"}, headers=admin)
        users_after_reset = user_db.load_all_users()
        check(
            "超级管理员能重置用户密码",
            resp.status_code == 200 and verify_password("new-created123", users_after_reset.get(managed_uid, {}).get("password", "")),
            resp.text,
        )

        resp = client.delete(f"/api/users/{managed_uid}", headers=admin)
        check("超级管理员能删除用户", resp.status_code == 200 and managed_uid not in user_db.load_all_users(), resp.text)

        resp = client.post(
            "/api/ai-config",
            json={
                "baseUrl": "https://example.test/v1",
                "endpointPath": "/chat/completions",
                "apiKey": secret_key,
                "model": "vision-test",
                "prompt": "只输出 JSON",
            },
            headers=admin,
        )
        data = resp.json()
        check(
            "AI 配置保存响应不包含完整 apiKey",
            resp.status_code == 200 and "apiKey" not in data.get("config", {}) and secret_key not in json.dumps(data, ensure_ascii=False),
            data,
        )

        resp = client.get("/api/ai-config", headers=admin)
        data = resp.json()
        check(
            "AI 配置响应不包含完整 apiKey 且返回 hasApiKey",
            resp.status_code == 200
            and data.get("config", {}).get("hasApiKey") is True
            and "apiKey" not in data.get("config", {})
            and secret_key not in json.dumps(data, ensure_ascii=False),
            data,
        )

    finally:
        ai_config_db.update(old_ai_config)
        cleanup_user(normal_uid)
        cleanup_user(managed_uid)

    print(f"\nPASS: {PASSED}")
    print(f"FAIL: {FAILED}")
    if FAILED:
        sys.exit(1)


if __name__ == "__main__":
    main()
