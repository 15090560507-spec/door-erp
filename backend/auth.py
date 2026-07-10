"""
JWT 认证模块
提供 token 创建、验证、以及 FastAPI 依赖注入
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import jwt
from fastapi import Cookie, Depends, Header, HTTPException

from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS
from database import UserDatabaseManager


user_db = UserDatabaseManager()

SUPER_ADMIN_ROLE = "超级管理员"
ENTRY_ROLES = {SUPER_ADMIN_ROLE, "录入员", "绘图员"}
TASK_ROLES = {SUPER_ADMIN_ROLE, "录入员", "绘图员", "初审员", "总工"}


def public_user_info(user_info: Dict, uid: str | None = None) -> Dict:
    """Return user data that is safe to send to the browser."""
    data = dict(user_info or {})
    data.pop("password", None)
    if uid is not None:
        data["uid"] = uid
    return data


def public_users_map(users: Dict) -> Dict:
    return {uid: public_user_info(info, uid) for uid, info in (users or {}).items()}


def create_token(uid: str) -> str:
    """为用户创建 JWT token，默认 24 小时过期"""
    payload = {
        "sub": uid,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[Dict]:
    """
    验证 JWT token，成功返回 payload，失败返回 None。
    同时检查用户是否仍然存在于数据库中。
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        uid = payload.get("sub")
        if not uid:
            return None
        # 确保用户仍存在
        users = user_db.load_all_users()
        if uid not in users:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user(authorization: str = Header(None), auth_token: str = Cookie(None)) -> Dict:
    """
    FastAPI 依赖：从 Authorization header 提取并验证 token，
    返回用户信息字典 {uid, role, name, default_module}。
    未认证或 token 无效时抛出 401。
    """
    token = ""
    if authorization:
        scheme, _, header_token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not header_token:
            raise HTTPException(status_code=401, detail="认证格式错误，应为 Bearer <token>")
        token = header_token
    elif auth_token:
        token = auth_token
    else:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="令牌无效或已过期，请重新登录")

    uid = payload["sub"]
    users = user_db.load_all_users()
    if uid not in users:
        raise HTTPException(status_code=401, detail="用户不存在")

    return public_user_info(users[uid], uid)


def require_roles(*roles: str):
    allowed = set(roles)

    def dependency(current_user: Dict = Depends(get_current_user)) -> Dict:
        if current_user.get("role") not in allowed:
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user

    return dependency


require_super_admin = require_roles(SUPER_ADMIN_ROLE)
