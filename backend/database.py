"""
数据库引擎层 - 从 door_26.py 原封不动提取
包含: UserDatabaseManager, TaskDatabaseManager
使用本地 JSON 文件进行数据持久化（后续迁移到 PostgreSQL）
"""
import json
import os
from typing import Dict, List, Optional

from config import USERS_DB_FILE, TASKS_DB_FILE


# ===================== 用户权限管理 =====================
class UserDatabaseManager:
    def __init__(self, file_path: str = USERS_DB_FILE):
        self.file_path = file_path
        if not os.path.exists(self.file_path):
            default_users = {
                "admin": {"password": "888888", "role": "超级管理员", "name": "系统管理员", "default_module": "后台管理"},
                "A": {"password": "123", "role": "录入员", "name": "销售小A", "default_module": "图纸信息录入"},
                "B": {"password": "123", "role": "绘图员", "name": "技术小B", "default_module": "图纸绘制"},
                "C": {"password": "123", "role": "初审员", "name": "初审小C", "default_module": "图纸初审"},
                "D": {"password": "123", "role": "总工", "name": "总工小D", "default_module": "图纸终审"}
            }
            self.save(default_users)

    def load_all_users(self) -> Dict:
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self, users: Dict):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

    def authenticate(self, uid: str, pwd: str) -> Optional[Dict]:
        users = self.load_all_users()
        if uid in users and users[uid]["password"] == pwd:
            user_info = users[uid].copy()
            user_info["uid"] = uid
            return user_info
        return None

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
            "password": pwd,
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
            self.save([])

    def load_all_tasks(self) -> List[Dict]:
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def save(self, tasks: List[Dict]):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)

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
