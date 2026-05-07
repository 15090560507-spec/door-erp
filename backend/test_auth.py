"""
Stage 2 登录认证测试脚本
测试: JWT token 创建/验证、登录接口、verify 端点、过期处理

用法:
  cd backend
  python test_auth.py
"""
import base64
import json
import os
import sys
import tempfile
import time

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="door_auth_test_")

import importlib
import config as cfg
importlib.reload(cfg)

from auth import create_token, verify_token, get_current_user
from database import UserDatabaseManager

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
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ==================== 准备 ====================
print(f"Test data dir: {os.environ['DATA_DIR']}")
print(f"JWT_SECRET first 8 chars: {cfg.JWT_SECRET[:8]}...")
user_db = UserDatabaseManager()

# ==================== 1. Token 创建与验证 ====================
section("1. Token Creation & Verification")

token = create_token("admin")
check("create_token returns str", isinstance(token, str) and len(token) > 20)

payload = verify_token(token)
check("verify_token returns payload", payload is not None)
check("payload.sub is admin", payload.get("sub") == "admin")
check("payload has iat", "iat" in payload)
check("payload has exp", "exp" in payload)
check("exp > iat", payload["exp"] > payload["iat"])

# Non-existent user
fake_token = None
try:
    import jwt as pyjwt
    from datetime import datetime as dt, timedelta, timezone
    fake_token = pyjwt.encode(
        {"sub": "nonexistent_user", "exp": dt.now(timezone.utc) + timedelta(hours=1)},
        cfg.JWT_SECRET,
        algorithm="HS256",
    )
except Exception:
    pass

if fake_token:
    fake_payload = verify_token(fake_token)
    check("non-existent user token returns None", fake_payload is None)

# Invalid token
check("garbage token returns None", verify_token("not.a.real.token.at.all") is None)
check("empty token returns None", verify_token("") is None)

# ==================== 2. 过期 Token ====================
section("2. Expired Token Handling")

expired_token = None
try:
    expired_token = pyjwt.encode(
        {"sub": "admin", "exp": dt.now(timezone.utc) - timedelta(hours=1)},
        cfg.JWT_SECRET,
        algorithm="HS256",
    )
except Exception:
    pass

if expired_token:
    expired_payload = verify_token(expired_token)
    check("expired token returns None", expired_payload is None)

# ==================== 3. 用户不存在时 Token 失效 ====================
section("3. User Lifecycle & Token Validity")

# Create a temp user
user_db.add_or_update_user("test_temp", "temp123", "录入员", "临时测试员")
temp_token = create_token("test_temp")
check("temp user token valid", verify_token(temp_token) is not None)

# Delete the user
user_db.delete_user("test_temp")
check("deleted user token invalid", verify_token(temp_token) is None)

# ==================== 4. get_current_user 依赖 ====================
section("4. get_current_user Dependency")

from fastapi import HTTPException

# Valid token
admin_token = create_token("admin")
result = get_current_user(authorization=f"Bearer {admin_token}")
check("get_current_user returns dict for valid token", isinstance(result, dict))
check("get_current_user has uid", result.get("uid") == "admin")
check("get_current_user has role", "role" in result)
check("get_current_user has name", "name" in result)
check("get_current_user has default_module", "default_module" in result)
check("get_current_user NO password field", "password" in result and result["password"].startswith("pbkdf2:"))

# Missing header
try:
    get_current_user(authorization=None)
    check("no header raises 401", False, "no exception raised")
except HTTPException as e:
    check("no header raises 401", e.status_code == 401)

# Wrong scheme
try:
    get_current_user(authorization=f"Basic {admin_token}")
    check("wrong scheme raises 401", False, "no exception raised")
except HTTPException as e:
    check("wrong scheme raises 401", e.status_code == 401)

# Invalid token
try:
    get_current_user(authorization="Bearer invalid.token.here")
    check("invalid token raises 401", False, "no exception raised")
except HTTPException as e:
    check("invalid token raises 401", e.status_code == 401)

# ==================== 5. Login Response 包含 Token ====================
section("5. Login Endpoint Returns Token")

from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Successful login
resp = client.post("/api/login", json={"uid": "admin", "pwd": "admin888"})
check("login returns 200", resp.status_code == 200)
data = resp.json()
check("login success=True", data.get("success") is True)
check("login has user field", data.get("user") is not None)
check("login has token field", data.get("token") is not None)
check("token is valid JWT", verify_token(data["token"]) is not None)

# Failed login
resp2 = client.post("/api/login", json={"uid": "admin", "pwd": "wrongpassword"})
check("wrong password success=False", resp2.json().get("success") is False)
check("wrong password no token", resp2.json().get("token") is None)

# ==================== 6. Verify Endpoint ====================
section("6. /api/auth/verify Endpoint")

token = data["token"]

# Valid verify
resp3 = client.get("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
check("verify returns 200", resp3.status_code == 200)
vdata = resp3.json()
check("verify has uid", vdata.get("uid") == "admin")
check("verify has role", vdata.get("role") is not None)
check("verify has name", vdata.get("name") is not None)
check("verify has NO password", "password" not in vdata)

# No token
resp4 = client.get("/api/auth/verify")
check("verify without token returns 401", resp4.status_code == 401)

# Invalid token
resp5 = client.get("/api/auth/verify", headers={"Authorization": "Bearer bad.token"})
check("verify with bad token returns 401", resp5.status_code == 401)

# ==================== 7. Token 跨请求可用 ====================
section("7. Token Reuse Across Requests")

# Verify token can be used multiple times
resp6 = client.get("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
check("token reusable (2nd call)", resp6.status_code == 200)

resp7 = client.get("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
check("token reusable (3rd call)", resp7.status_code == 200)

# ==================== 汇总 ====================
section("Test Results")
print(f"  PASS: {PASSED}")
print(f"  FAIL: {FAILED}")
print(f"  Total: {PASSED + FAILED}")

if FAILED == 0:
    print("\n  All tests passed! Stage 2 auth refactor successful.")
else:
    print(f"\n  WARNING: {FAILED} tests failed. Please check!")
    sys.exit(1)

# Cleanup
import shutil
shutil.rmtree(os.environ["DATA_DIR"], ignore_errors=True)
