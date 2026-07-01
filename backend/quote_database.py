"""
报价系统数据库层
包含: AccessoryDatabaseManager, QuoteDatabaseManager, AiConfigManager
使用本地 JSON 文件进行数据持久化，遵循与 database.py 相同的安全模式（原子写入、自动备份）。
"""
import json
import os
import tempfile
import threading
from datetime import datetime
from typing import Dict, List, Optional

from config import (
    ACCESSORIES_DB_FILE, QUOTES_DB_FILE, AI_CONFIG_FILE,
    ACCESSORIES_BACKUP_DIR, QUOTES_BACKUP_DIR,
)
from database import backup_file_before_replace


ACCESSORY_EXTRA_FIELDS = ("priceType", "priceMode", "frontStyle", "backStyle")


def _normalize_accessory(data: Dict, accessory_id: int) -> Dict:
    accessory = {
        "id": accessory_id,
        "name": data.get("name", ""),
        "category": data.get("category", ""),
        "model": data.get("model", ""),
        "keywords": data.get("keywords", ""),
        "unit": data.get("unit", ""),
        "unitPrice": float(data.get("unitPrice", 0) or 0),
        "remark": data.get("remark", ""),
        "active": 1,
    }
    for field in ACCESSORY_EXTRA_FIELDS:
        accessory[field] = data.get(field, "")
    return accessory


# ===================== 配件数据库管理 =====================
class AccessoryDatabaseManager:
    """管理 data/accessories_database.json - 门业配件/材料清单"""

    def __init__(self, file_path: str = ACCESSORIES_DB_FILE, backup_dir: str = ACCESSORIES_BACKUP_DIR):
        self.file_path = file_path
        self.backup_dir = backup_dir
        self._lock = threading.Lock()
        os.makedirs(backup_dir, exist_ok=True)

        if not os.path.exists(self.file_path):
            seed_data = [
                {"id": 1, "name": "0.8厚钢铜蚀刻子母门", "category": "铜门", "model": "ZMM-08", "keywords": "子母门,铜门,蚀刻,0.8", "unit": "m2", "unitPrice": 1680, "remark": "示例数据，可删除或修改", "active": 1},
                {"id": 2, "name": "铜门拉手A款", "category": "五金", "model": "LS-A", "keywords": "拉手,把手,五金", "unit": "套", "unitPrice": 280, "remark": "示例数据，可删除或修改", "active": 1},
                {"id": 3, "name": "门锁B款", "category": "五金", "model": "MS-B", "keywords": "门锁,锁具,五金", "unit": "套", "unitPrice": 360, "remark": "示例数据，可删除或修改", "active": 1},
            ]
            self._atomic_save(seed_data)

    # ---------- 公开 API ----------

    def search(self, query: str) -> List[Dict]:
        """按名称/类别/型号/关键词搜索，仅返回有效配件，最新在前，最多 30 条"""
        with self._lock:
            items = self._load_unlocked()
            q = (query or "").strip().lower()
            if not q:
                active = [it for it in items if it.get("active", 0) == 1]
                active.reverse()
                return active[:30]
            results = []
            for it in items:
                if it.get("active", 0) != 1:
                    continue
                haystack = " ".join([
                    it.get("name", ""),
                    it.get("category", ""),
                    it.get("model", ""),
                    it.get("keywords", ""),
                    it.get("priceType", ""),
                    it.get("priceMode", ""),
                    it.get("frontStyle", ""),
                    it.get("backStyle", ""),
                ]).lower()
                if q in haystack:
                    results.append(it)
            results.reverse()
            return results[:30]

    def get_all(self) -> List[Dict]:
        """返回所有有效配件"""
        with self._lock:
            items = self._load_unlocked()
            return [it for it in items if it.get("active", 0) == 1]

    def add(self, data: Dict) -> Dict:
        """新增配件，自动递增 id，active=1"""
        with self._lock:
            items = self._load_unlocked()
            max_id = max((it.get("id", 0) for it in items), default=0)
            accessory = _normalize_accessory(data, max_id + 1)
            items.append(accessory)
            self._atomic_save(items)
            return accessory

    def soft_delete(self, accessory_id: int):
        """软删除：将 active 置为 0"""
        with self._lock:
            items = self._load_unlocked()
            found = False
            for it in items:
                if it.get("id") == accessory_id:
                    it["active"] = 0
                    found = True
                    break
            if not found:
                raise ValueError(f"配件不存在: {accessory_id}")
            self._atomic_save(items)

    def import_batch(self, items: List[Dict]) -> int:
        """批量导入配件列表，自动分配 id，返回导入数量"""
        with self._lock:
            existing = self._load_unlocked()
            max_id = max((it.get("id", 0) for it in existing), default=0)
            count = 0
            for data in items:
                name = str(data.get("name", "")).strip()
                category = str(data.get("category", "")).strip()
                if not name:
                    continue
                matched = next(
                    (
                        it for it in existing
                        if it.get("active", 0) == 1
                        and str(it.get("name", "")).strip() == name
                        and str(it.get("category", "")).strip() == category
                    ),
                    None,
                )
                if matched:
                    matched.update(_normalize_accessory(data, matched.get("id", 0)))
                else:
                    max_id += 1
                    existing.append(_normalize_accessory(data, max_id))
                count += 1
            self._atomic_save(existing)
            return count

    # ---------- 内部方法 ----------

    def _load_unlocked(self) -> List[Dict]:
        """内部读取（调用方必须持锁）"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _atomic_save(self, data: List[Dict]):
        """原子写入：先写临时文件再原子替换（需在锁内调用），写入前自动备份"""
        dirname = os.path.dirname(self.file_path) or "."
        os.makedirs(dirname, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dirname, suffix=".json")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            backup_file_before_replace(self.file_path, self.backup_dir)
            os.replace(tmp, self.file_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


# ===================== 报价单数据库管理 =====================
class QuoteDatabaseManager:
    """管理 data/quotes_database.json - 报价单"""

    def __init__(self, file_path: str = QUOTES_DB_FILE, backup_dir: str = QUOTES_BACKUP_DIR):
        self.file_path = file_path
        self.backup_dir = backup_dir
        self._lock = threading.Lock()
        os.makedirs(backup_dir, exist_ok=True)

        if not os.path.exists(self.file_path):
            self._atomic_save([])

    # ---------- 公开 API ----------

    def get_all(self, limit: int = 50) -> List[Dict]:
        """返回报价单列表（不含 items 明细），最新在前"""
        with self._lock:
            quotes = self._load_unlocked()
            quotes_sorted = sorted(quotes, key=lambda q: q.get("id", 0), reverse=True)
            result = []
            for q in quotes_sorted[:limit]:
                summary = {k: v for k, v in q.items() if k != "items"}
                result.append(summary)
            return result

    def get_by_id(self, quote_id: int) -> Optional[Dict]:
        """返回单个报价单（含 items）"""
        with self._lock:
            quotes = self._load_unlocked()
            for q in quotes:
                if q.get("id") == quote_id:
                    return dict(q)
            return None

    def create(self, quote_data: Dict) -> Dict:
        """创建报价单，自动验证、分配 id、设置 createdAt"""
        # 验证
        if not quote_data.get("customerName", "").strip():
            raise ValueError("customerName 为必填字段")
        if not quote_data.get("projectName", "").strip():
            raise ValueError("projectName 为必填字段")
        if not quote_data.get("quoteDate", "").strip():
            raise ValueError("quoteDate 为必填字段")

        items = quote_data.get("items", [])
        if not isinstance(items, list) or len(items) == 0:
            raise ValueError("items 不能为空")
        if len(items) > 8:
            raise ValueError("最多只能有 8 个项目")

        for idx, item in enumerate(items):
            if not item.get("productName", "").strip():
                raise ValueError(f"第 {idx + 1} 个项目的 productName 为必填字段")

        with self._lock:
            quotes = self._load_unlocked()
            max_id = max((q.get("id", 0) for q in quotes), default=0)

            now = datetime.now().isoformat()
            quote = {
                "id": max_id + 1,
                "customerName": quote_data["customerName"].strip(),
                "projectName": quote_data["projectName"].strip(),
                "quoteDate": quote_data["quoteDate"].strip(),
                "noticeText": quote_data.get("noticeText", "").strip() or "\u672c\u62a5\u4ef7\u4e0d\u542b\u7a0e\u5de5\u5382\u7ed3\u7b97\u4ef7\uff0c\u542b\u6728\u7bb1\u3002",
                "createdAt": now,
                "items": [],
            }

            for idx, item in enumerate(items):
                quote["items"].append({
                    "id": idx + 1,
                    "accessoryId": item.get("accessoryId"),
                    "productName": item.get("productName", "").strip(),
                    "width": item.get("width"),
                    "height": item.get("height"),
                    "openDirection": item.get("openDirection", ""),
                    "unit": item.get("unit", ""),
                    "unitPrice": item.get("unitPrice", 0),
                    "rowOrder": idx,
                })

            quotes.append(quote)
            self._atomic_save(quotes)
            return dict(quote)

    def delete(self, quote_id: int):
        """删除报价单"""
        with self._lock:
            quotes = self._load_unlocked()
            filtered = [q for q in quotes if q.get("id") != quote_id]
            if len(filtered) == len(quotes):
                raise ValueError(f"报价单不存在: {quote_id}")
            self._atomic_save(filtered)

    # ---------- 内部方法 ----------

    def _load_unlocked(self) -> List[Dict]:
        """内部读取（调用方必须持锁）"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _atomic_save(self, data: List[Dict]):
        """原子写入：先写临时文件再原子替换（需在锁内调用），写入前自动备份"""
        dirname = os.path.dirname(self.file_path) or "."
        os.makedirs(dirname, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dirname, suffix=".json")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            backup_file_before_replace(self.file_path, self.backup_dir)
            os.replace(tmp, self.file_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


# ===================== AI 配置管理 =====================
class AiConfigManager:
    """管理 data/ai_config.json - AI 识别配置（简单读写，无需备份）"""

    def __init__(self, file_path: str = AI_CONFIG_FILE):
        self.file_path = file_path
        self._lock = threading.Lock()

        if not os.path.exists(self.file_path):
            default_prompt = (
                "你是一名门业报价助理，请根据上传的图纸图片提取报价需要的字段。\n"
                "请只输出 JSON，不要输出 Markdown，不要输出解释。\n"
                "JSON 结构必须如下：\n"
                "{\n"
                '  "customerName": "",\n'
                '  "projectName": "",\n'
                '  "outerWidth": null,\n'
                '  "outerHeight": null,\n'
                '  "openDirection": "",\n'
                '  "items": [\n'
                "    {\n"
                '      "productName": "",\n'
                '      "width": null,\n'
                '      "height": null,\n'
                '      "openDirection": "",\n'
                '      "unit": "",\n'
                '      "unitPrice": null\n'
                "    }\n"
                "  ],\n"
                '  "accessories": ["配件名称1", "配件名称2"],\n'
                '  "notes": ""\n'
                "}\n"
                "如果识别不到某个字段，请返回空字符串、null 或空数组。"
            )
            defaults = {
                "baseUrl": "",
                "endpointPath": "/chat/completions",
                "apiKey": "",
                "model": "",
                "prompt": default_prompt,
                "updatedAt": "",
            }
            self._save(defaults)

    # ---------- 公开 API ----------

    def get(self) -> Dict:
        """返回当前 AI 配置"""
        with self._lock:
            return self._load()

    def update(self, data: Dict) -> Dict:
        """合并更新配置，自动设置 updatedAt"""
        with self._lock:
            config = self._load()
            config.update(data)
            config["updatedAt"] = datetime.now().isoformat()
            self._save(config)
            return dict(config)

    # ---------- 内部方法 ----------

    def _load(self) -> Dict:
        """读取配置（调用方必须持锁）"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: Dict):
        """直接写入（调用方必须持锁）"""
        dirname = os.path.dirname(self.file_path) or "."
        os.makedirs(dirname, exist_ok=True)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
