"""
数据库引擎层 - 从 door_26.py 原封不动提取
包含: UserDatabaseManager, TaskDatabaseManager, ImageStore
使用本地 JSON 文件进行数据持久化（后续迁移到 PostgreSQL）

v1.1 数据安全增强:
  - ImageStore: 图片文件独立存储，解除 JSON 膨胀风险
  - 自动备份: 每次写入前备份旧文件（保留最近 20 份）
  - 启动迁移: 自动将历史内联 Base64 图片迁移至文件系统
  - 数据校验: 写入前检查任务必填字段完整性
"""
import base64
import glob
import hashlib
import json
import os
import shutil
import tempfile
import threading
from datetime import datetime
from typing import Dict, List, Optional

from config import (
    USERS_DB_FILE, TASKS_DB_FILE, USERS_BACKUP_DIR, TASKS_BACKUP_DIR, IMAGES_DIR,
)

# ===================== 常量 =====================
_HASH_ITERATIONS = 100_000
_HASH_PREFIX = "pbkdf2:sha256:"
BACKUP_MAX_COUNT = 20

# 任务必填字段
_TASK_REQUIRED_FIELDS = ["id", "date", "status", "customer", "project", "door_type", "size", "params"]

# 有效的任务状态
_VALID_TASK_STATUSES = ["待绘制", "待初审", "待终审", "待修改", "已通过"]


# ===================== 密码哈希工具 =====================
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
        _, hash_method, iterations_str, salt_hex, dk_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        dk_stored = bytes.fromhex(dk_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations_str))
        return dk == dk_stored
    except (ValueError, AttributeError):
        return False


def is_hashed(stored: str) -> bool:
    return stored.startswith(_HASH_PREFIX)


# ===================== 自动备份工具 =====================
def backup_file_before_replace(file_path: str, backup_dir: str):
    """在原子替换前备份现有文件，并清理超出保留数量的旧备份"""
    if not os.path.exists(file_path):
        return
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    basename = os.path.basename(file_path)
    backup_path = os.path.join(backup_dir, f"{basename}.{timestamp}.bak")
    try:
        shutil.copy2(file_path, backup_path)
    except OSError:
        return

    # 清理旧备份：保留最近 BACKUP_MAX_COUNT 份
    pattern = os.path.join(backup_dir, f"{basename}.*.bak")
    backups = sorted(glob.glob(pattern))
    while len(backups) > BACKUP_MAX_COUNT:
        oldest = backups.pop(0)
        try:
            os.unlink(oldest)
        except OSError:
            pass


# ===================== 图片文件存储 =====================
class ImageStore:
    """
    将任务中的 Base64 图片从 JSON 字段中分离，存储为独立文件。

    存储规则:
      - 文件路径: IMAGES_DIR / {task_id}_{field}.png
      - JSON 中仅保留文件名引用 ({task_id}_{field}.png)
      - 读取时透明还原为 Base64，对外接口不变
    """

    def __init__(self, base_dir: str = IMAGES_DIR):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def save_from_task(self, task: dict) -> dict:
        """
        从 task 字典中提取 Base64 图片 → 写入文件 → 替换为文件名引用。
        如果某字段为空/None → 同时删除对应的旧图片文件。
        """
        for field in ("ref_img_b64", "drawing_img_b64"):
            val = task.get(field)
            if val and len(val) > 200:
                # 看起来是内联 Base64 数据
                try:
                    image_bytes = base64.b64decode(val)
                except Exception:
                    continue
                filename = f"{task['id']}_{field}.png"
                filepath = os.path.join(self.base_dir, filename)
                try:
                    with open(filepath, "wb") as f:
                        f.write(image_bytes)
                except OSError:
                    continue
                task[field] = filename  # 替换为文件名引用
            elif not val:
                # 清空该字段 → 同时删除旧图片文件
                old_file = os.path.join(self.base_dir, f"{task['id']}_{field}.png")
                if os.path.exists(old_file):
                    try:
                        os.unlink(old_file)
                    except OSError:
                        pass
        return task

    def load_to_task(self, task: dict) -> dict:
        """
        读取 task 时，将文件名引用还原为完整的 Base64 字符串。
        """
        for field in ("ref_img_b64", "drawing_img_b64"):
            val = task.get(field)
            if val and len(val) < 200:
                # 文件名引用 → 读文件 → Base64
                filepath = os.path.join(self.base_dir, val)
                if os.path.exists(filepath):
                    try:
                        with open(filepath, "rb") as f:
                            task[field] = base64.b64encode(f.read()).decode("utf-8")
                    except OSError:
                        task[field] = None
                else:
                    task[field] = None
        return task

    def delete_task_images(self, task_id: str):
        """删除某个任务的所有关联图片文件"""
        for field in ("ref_img_b64", "drawing_img_b64"):
            filepath = os.path.join(self.base_dir, f"{task_id}_{field}.png")
            if os.path.exists(filepath):
                try:
                    os.unlink(filepath)
                except OSError:
                    pass

    def migrate_existing_tasks(self, tasks: list) -> tuple:
        """
        启动迁移：扫描已有任务，将内联 Base64 图片迁移到文件系统。
        返回 (tasks, modified) — modified=True 表示有改动需要回写。
        """
        modified = False
        for task in tasks:
            if "id" not in task:
                continue
            for field in ("ref_img_b64", "drawing_img_b64"):
                val = task.get(field)
                if val and len(val) > 200:
                    # 内联 Base64 → 写入文件
                    filename = f"{task['id']}_{field}.png"
                    filepath = os.path.join(self.base_dir, filename)
                    if not os.path.exists(filepath):
                        try:
                            with open(filepath, "wb") as f:
                                f.write(base64.b64decode(val))
                        except Exception:
                            continue
                    task[field] = filename
                    modified = True
        return tasks, modified


# ===================== 用户权限管理 =====================
class UserDatabaseManager:
    def __init__(self, file_path: str = USERS_DB_FILE, backup_dir: str = USERS_BACKUP_DIR):
        self.file_path = file_path
        self.backup_dir = backup_dir
        os.makedirs(backup_dir, exist_ok=True)
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
            backup_file_before_replace(self.file_path, self.backup_dir)
            os.replace(tmp, self.file_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _startup_ensure_and_migrate(self):
        """启动时：确保 admin 存在 + 迁移所有明文密码 + 环境变量密码覆盖"""
        try:
            users = self.load_all_users()
            changed = False

            # 1. 仅在 admin 不存在时创建默认 admin
            if "admin" not in users:
                users["admin"] = {
                    "password": hash_password("admin888"),
                    "role": "超级管理员",
                    "name": "系统管理员",
                    "default_module": "后台管理"
                }
                changed = True

            # 2. 环境变量 ADMIN_PASSWORD 覆盖：云端部署时强制同步 admin 密码
            env_pwd = os.environ.get("ADMIN_PASSWORD", "").strip()
            if env_pwd and "admin" in users:
                stored = users["admin"].get("password", "")
                if not is_hashed(stored) or not verify_password(env_pwd, stored):
                    users["admin"]["password"] = hash_password(env_pwd)
                    changed = True

            # 3. 迁移所有明文密码
            for uid, info in users.items():
                pwd = info.get("password", "")
                if pwd and not is_hashed(pwd):
                    info["password"] = hash_password(pwd)
                    changed = True

            if changed:
                self._atomic_save(users)
        except Exception:
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
    def __init__(
        self,
        file_path: str = TASKS_DB_FILE,
        backup_dir: str = TASKS_BACKUP_DIR,
        image_store: Optional[ImageStore] = None,
    ):
        self.file_path = file_path
        self.backup_dir = backup_dir
        self.image_store = image_store or ImageStore()
        self._lock = threading.Lock()
        os.makedirs(backup_dir, exist_ok=True)

        if not os.path.exists(self.file_path):
            self._atomic_save([])
        else:
            self._migrate_images_on_startup()

    def _migrate_images_on_startup(self):
        """启动时：扫描已有任务，将内联 Base64 图片迁移到文件系统"""
        try:
            with self._lock:
                tasks = self._load_unlocked()
                migrated, modified = self.image_store.migrate_existing_tasks(tasks)
                if modified:
                    self._atomic_save(migrated)
                    print(f"[ImageStore] 启动迁移完成：已迁移 {modified} 条任务的内联图片")
        except Exception:
            pass

    def load_all_tasks(self) -> List[Dict]:
        """线程安全读取：持锁防止读到写中间态"""
        with self._lock:
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []

    def save(self, tasks: List[Dict]):
        self._atomic_save(tasks)

    def _validate_task(self, task: dict, is_update: bool = False):
        """校验任务数据完整性"""
        if not is_update:
            for field in _TASK_REQUIRED_FIELDS:
                if field not in task:
                    raise ValueError(f"任务缺少必填字段: {field}")
        if "status" in task and task["status"] not in _VALID_TASK_STATUSES:
            raise ValueError(f"无效的任务状态: {task['status']}，合法值: {_VALID_TASK_STATUSES}")

    def _atomic_save(self, tasks: List[Dict]):
        """原子写入：先写临时文件再原子替换（需在锁内调用），写入前自动备份"""
        dirname = os.path.dirname(self.file_path) or "."
        os.makedirs(dirname, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dirname, suffix=".json")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
            backup_file_before_replace(self.file_path, self.backup_dir)
            os.replace(tmp, self.file_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def add_task(self, new_task: Dict):
        """原子操作：验证 → 提取图片 → 持锁写入"""
        self._validate_task(new_task)
        with self._lock:
            tasks = self._load_unlocked()
            new_task = dict(new_task)
            new_task = self.image_store.save_from_task(new_task)
            tasks.insert(0, new_task)
            self._atomic_save(tasks)

    def update_task(self, task_id: str, updated_data: Dict):
        """原子操作：持锁完成读-改-写，并处理图片字段"""
        with self._lock:
            tasks = self._load_unlocked()
            found = False
            for i, task in enumerate(tasks):
                if task["id"] == task_id:
                    tasks[i].update(updated_data)
                    # 将该任务的图片字段提取到文件
                    tasks[i] = self.image_store.save_from_task(tasks[i])
                    found = True
                    break
            if not found:
                raise ValueError(f"任务不存在: {task_id}")
            self._atomic_save(tasks)

    def get_task(self, task_id: str) -> Optional[Dict]:
        """只读操作：持锁确保读到一致数据，透明还原图片 Base64"""
        with self._lock:
            tasks = self._load_unlocked()
            for task in tasks:
                if task["id"] == task_id:
                    task_copy = dict(task)
                    return self.image_store.load_to_task(task_copy)
            return None

    def delete_task(self, task_id: str):
        """原子操作：持锁完成读-改-写，同时清理关联图片文件"""
        with self._lock:
            tasks = self._load_unlocked()
            filtered_tasks = []
            deleted = False
            for t in tasks:
                if t["id"] == task_id:
                    deleted = True
                else:
                    filtered_tasks.append(t)
            if not deleted:
                raise ValueError(f"任务不存在: {task_id}")
            self._atomic_save(filtered_tasks)
            # 锁外删除图片（不影响数据一致性）
            self.image_store.delete_task_images(task_id)

    def _load_unlocked(self) -> List[Dict]:
        """内部读取（调用方必须持锁）"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
