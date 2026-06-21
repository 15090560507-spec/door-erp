"""
西州将军铜门 - 生产图纸协同系统 后端配置
从 door_26.py 原封不动提取的核心配置
"""
import os
from typing import Dict, List
from dataclasses import dataclass, field

# ===================== 环境与路径配置 =====================
# 开发环境：__file__ 推导的父目录（F:\Door\）
# Docker 环境：当前工作目录 /app/
_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir(_base):
    _base = os.getcwd()

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(_base, 'data'))
os.makedirs(DATA_DIR, exist_ok=True)

HISTORY_FILE = os.path.join(DATA_DIR, 'order_history.json')
CUSTOM_OPTIONS_FILE = os.path.join(DATA_DIR, 'custom_options.json')
TASKS_DB_FILE = os.path.join(DATA_DIR, 'tasks_database.json')
USERS_DB_FILE = os.path.join(DATA_DIR, 'users_database.json')
ACCESSORIES_DB_FILE = os.path.join(DATA_DIR, 'accessories_database.json')
QUOTES_DB_FILE = os.path.join(DATA_DIR, 'quotes_database.json')
AI_CONFIG_FILE = os.path.join(DATA_DIR, 'ai_config.json')

TEMPLATE_PATH = os.environ.get("TEMPLATE_PATH", os.path.join(_base, 'template.dxf'))

# ===================== 数据安全：备份与图片路径 =====================
BACKUP_DIR = os.path.join(DATA_DIR, 'backups')
IMAGES_DIR = os.path.join(DATA_DIR, 'images')
USERS_BACKUP_DIR = os.path.join(BACKUP_DIR, 'users')
TASKS_BACKUP_DIR = os.path.join(BACKUP_DIR, 'tasks')
ACCESSORIES_BACKUP_DIR = os.path.join(BACKUP_DIR, 'accessories')
QUOTES_BACKUP_DIR = os.path.join(BACKUP_DIR, 'quotes')

for _d in (BACKUP_DIR, IMAGES_DIR, USERS_BACKUP_DIR, TASKS_BACKUP_DIR, ACCESSORIES_BACKUP_DIR, QUOTES_BACKUP_DIR):
    os.makedirs(_d, exist_ok=True)


# ===================== 核心配置 =====================
@dataclass
class Config:
    HINGE_TYPES: Dict[str, str] = field(default_factory=lambda: {
        "葫芦头合页": "hlt",
        "可拆卸合页": "kcx",
        "三维可调合页": "kcx",
        "三位可调合页": "kcx",
        "暗合页": "暗合页块",
        "北京暗合页": "暗合页块",
        "明合页暗装": "明合页暗装块",
        "明合页": "明合页块"
    })
    BRIGHT_HINGE_TYPES: List[str] = field(default_factory=lambda: ["明合页"])
    HINGE_CONFIG: Dict[str, int] = field(default_factory=lambda: {
        "first_offset": 200,
        "second_offset": 200,
        "subsequent_spacing": 360,
        "min_clearance": 50
    })
    MATERIAL_OPTIONS: List[str] = field(default_factory=lambda: [
        "0.8的不锈钢镀铜", "1.0的不锈钢镀铜", "1.2的不锈钢镀铜",
        "0.8的纯铜", "1.0的纯铜", "1.2的纯铜", "纯铝"
    ])
    HANDLE_OPTIONS: List[str] = field(default_factory=lambda: [
        "标配拉手", "A1022", "铝雕拉手", "铝雕滑盖拉手", "铝雕长拉手", "自制长拉手", "背包拉手"
    ])
    LOCK_OPTIONS: List[str] = field(default_factory=lambda: [
        "连体锁", "标准锁体", "防盗锁体", "霸王锁体", "快装锁体"
    ])
    FINGERPRINT_LOCK_OPTIONS: List[str] = field(default_factory=lambda: [
        "", "无", "安志杰AF-12", "Q3指纹锁", "T5指纹锁", "客备指纹锁"
    ])


# ===================== JWT 认证配置 =====================
import secrets
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

CONFIG = Config()
