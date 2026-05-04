"""
数据库引擎层 - 从 door_26.py 原封不动提取
包含: UserDatabaseManager, TaskDatabaseManager
使用本地 JSON 文件进行数据持久化（后续迁移到 PostgreSQL）
"""
import hashlib
import json
import os
import tempfile
from typing import Dict, List, Optional

from config import USERS_DB_FILE, TASKS_DB_FILE

# ===================== 密码哈希工具 =====================
_HASH_ITERATIONS = 100_000
_HASH_PREFIX = "pbkdf2:sha256:"


def hash_password(password: str) -> str:
    """使用 PBKDF2-SHA256 对密码进行哈希"""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _HASH_ITERATIONS)
    return _HASH_PREFIX + str(_HASH_ITERATIONS) + ":" + salt.hex() + ":" + dk.hex()


def verify_password(password: str, stored: str) -> bool:
    """验证密码是否匹配存储的哈希值"""
    if not stored.startswith(_HASH_PREFIX):
        return False
    try:
        _, iterations_str, salt_hex, dk_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        dk_stored = bytes.fromhex(dk_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations_str))
        return dk == dk_stored
    except (ValueError, AttributeError):
        return False


def is_hashed(stored: str) -> bool:
    return stored.startswith(_HASH_PREFIX)


# ===================== 用户权限管理 =====================
class UserDatabaseManager:
    def __init__(self, file_path: str = USERS_DB_FILE):
        self.file_path = file_path
        if not os.path.exists(self.file_path):
            default_users = {
                "admin": {"password": hash_password("admin888"), "role": "超级管理员", "name": "系统管理员", "default_module": "后台管理"},
                "A": {"password": hash_password("123"), "role": "录入员", "name": "销售小A", "default_module": "图纸信息录入"},
                "B": {"password": hash_password("123"), "role": "绘图员", "name": "技术小B", "default_module": "图纸绘制"},
                "C": {"password": hash_password("123"), "role": "初审员", "name": "初审小C", "default_module": "图纸初审"},
                "D": {"password": hash_password("123"), "role": "总工", "name": "总工小D", "default_module": "图纸终审"}
            }
            self._atomic_save(default_users)
        else:
            # 每次启动：确保 admin 存在 + 迁移明文密码
            self._startup_ensure_and_migrate()

    def load_all_users(self) -> Dict:
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self, users: Dict):
        self._atomic_save(users)

    def _atomic_save(self, users: Dict):
        """原子写入：先写临时文件再原子替换，防止并发读写导致数据损坏"""
        dirname = os.path.dirname(self.file_path) or "."
        os.makedirs(dirname, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dirname, suffix=".json")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.file_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _startup_ensure_and_migrate(self):
        """启动时：确保 admin 存在 + 强制更新密码 + 迁移所有明文密码"""
        try:
            users = self.load_all_users()
            changed = False

            # 1. 确保 admin 存在，并强制使用加密后的 admin888
            if "admin" not in users or not is_hashed(users["admin"].get("password", "")):
                users["admin"] = {
                    "password": hash_password("admin888"),
                    "role": "超级管理员",
                    "name": "系统管理员",
                    "default_module": "后台管理"
                }
                changed = True

            # 2. 迁移所有其他用户的明文密码
            for uid, info in users.items():
                pwd = info.get("password", "")
                if pwd and not is_hashed(pwd):
                    # 明文密码 -> 哈希（保留原密码，登录时自动升级）
                    info["password"] = hash_password(pwd)
                    changed = True

            if changed:
                self._atomic_save(users)
        except Exception:
            # 启动时的自动检查失败不应阻止服务启动
            pass

    def authenticate(self, uid: str, pwd: str) -> Optional[Dict]:
        """验证用户登录。支持哈希密码，并自动升级遗留的明文记录"""
        users = self.load_all_users()
        if uid not in users:
            return None
        stored = users[uid].get("password", "")

        if is_hashed(stored):
            if not verify_password(pwd, stored):
                return None
        else:
            # 遗留明文密码 — 直接比对后升级为哈希
            if stored != pwd:
                return None
            users[uid]["password"] = hash_password(pwd)
            self._atomic_save(users)

        user_info = users[uid].copy()
        user_info["uid"] = uid
        return user_info

    def add_or_update_user(self, uid: str, pwd: str, role: str, name: str):
        users = self.load_all_users()
        module_map = {
            "超级管理员": "后台管理",
            "录入员": "图纸信息录入",
            "绘图员": "图纸绘制",
            "初审员": "图纸初审",
            "总工": "图纸终审"
        }
        users[uid] = {
            "password": hash_password(pwd),
            "role": role,
            "name": name,
            "default_module": module_map.get(role, "图纸信息录入")
        }
        self.save(users)

    def delete_user(self, uid: str):
        users = self.load_all_users()
        if uid in users and uid != "admin":
            del users[uid]
            self.save(users)


# ===================== 任务流转管理 =====================
class TaskDatabaseManager:
    def __init__(self, file_path: str = TASKS_DB_FILE):
        self.file_path = file_path
        if not os.path.exists(self.file_path):
            self._atomic_save([])

    def load_all_tasks(self) -> List[Dict]:
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def save(self, tasks: List[Dict]):
        self._atomic_save(tasks)

    def _atomic_save(self, tasks: List[Dict]):
        """原子写入：先写临时文件再原子替换"""
        dirname = os.path.dirname(self.file_path) or "."
        os.makedirs(dirname, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dirname, suffix=".json")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.file_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def add_task(self, new_task: Dict):
        tasks = self.load_all_tasks()
        tasks.insert(0, new_task)
        self.save(tasks)

    def update_task(self, task_id: str, updated_data: Dict):
        tasks = self.load_all_tasks()
        for i, task in enumerate(tasks):
            if task["id"] == task_id:
                tasks[i].update(updated_data)
                break
        self.save(tasks)

    def get_task(self, task_id: str) -> Optional[Dict]:
        tasks = self.load_all_tasks()
        for task in tasks:
            if task["id"] == task_id:
                return task
        return None

    def delete_task(self, task_id: str):
        tasks = self.load_all_tasks()
        filtered_tasks = []
        for t in tasks:
            if t["id"] != task_id:
                filtered_tasks.append(t)
        self.save(filtered_tasks)
