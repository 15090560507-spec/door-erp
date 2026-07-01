import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from config import BACKUP_DIR, DATA_DIR
from database import backup_file_before_replace
from .models import ProviderCapabilities


RENDER_DB_DIR = os.path.join(DATA_DIR, "render")
MODEL_CONFIGS_FILE = os.path.join(RENDER_DB_DIR, "model_configs.json")
ASSETS_FILE = os.path.join(RENDER_DB_DIR, "assets.json")
TASKS_FILE = os.path.join(RENDER_DB_DIR, "tasks.json")
RENDER_BACKUP_DIR = os.path.join(BACKUP_DIR, "render")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class JsonTable:
    def __init__(self, file_path: str, default: Any):
        self.file_path = file_path
        self.default = default
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        os.makedirs(RENDER_BACKUP_DIR, exist_ok=True)
        if not os.path.exists(file_path):
            self._save_unlocked(default)

    def load(self):
        with self._lock:
            return self._load_unlocked()

    def save(self, value):
        with self._lock:
            self._save_unlocked(value)

    def update(self, mutator):
        with self._lock:
            value = self._load_unlocked()
            result = mutator(value)
            self._save_unlocked(value)
            return result

    def _load_unlocked(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return self.default.copy() if isinstance(self.default, dict) else list(self.default)

    def _save_unlocked(self, value):
        folder = os.path.dirname(self.file_path) or "."
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=folder, suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
            backup_file_before_replace(self.file_path, RENDER_BACKUP_DIR)
            os.replace(tmp, self.file_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


class RenderDatabase:
    def __init__(self):
        self.model_configs = JsonTable(MODEL_CONFIGS_FILE, [])
        self.assets = JsonTable(ASSETS_FILE, [])
        self.tasks = JsonTable(TASKS_FILE, [])
        self._ensure_default_config()

    def list_model_configs(self, include_disabled: bool = False) -> list[dict]:
        items = self.model_configs.load()
        if not include_disabled:
            items = [item for item in items if item.get("enabled", True)]
        return [_public_config(item) for item in items]

    def get_model_config(self, config_id: str, include_secret: bool = False) -> dict | None:
        for item in self.model_configs.load():
            if item.get("id") == config_id:
                return dict(item) if include_secret else _public_config(item)
        return None

    def create_model_config(self, data: dict) -> dict:
        now = utc_now_iso()
        item = {
            "id": uuid.uuid4().hex[:12],
            "name": data.get("name", "").strip(),
            "provider": data.get("provider", "image2_proxy"),
            "baseUrl": data.get("baseUrl", "").strip(),
            "apiKey": data.get("apiKey", "").strip(),
            "model": data.get("model", "").strip(),
            "endpoint": data.get("endpoint", "/images/edits").strip() or "/images/edits",
            "apiType": data.get("apiType", "openai_images_edits"),
            "capabilities": _capabilities_dict(data.get("capabilities")),
            "defaultSize": data.get("defaultSize", "original"),
            "timeoutSeconds": int(data.get("timeoutSeconds", 180) or 180),
            "enabled": bool(data.get("enabled", True)),
            "createdAt": now,
            "updatedAt": now,
        }

        def mutate(items):
            items.append(item)
            return _public_config(item)

        return self.model_configs.update(mutate)

    def update_model_config(self, config_id: str, patch: dict) -> dict | None:
        def mutate(items):
            for item in items:
                if item.get("id") != config_id:
                    continue
                for key, value in patch.items():
                    if value is None:
                        continue
                    if key == "apiKey" and value == "":
                        continue
                    item[key] = _capabilities_dict(value) if key == "capabilities" else value
                item["updatedAt"] = utc_now_iso()
                return _public_config(item)
            return None

        return self.model_configs.update(mutate)

    def list_assets(self, category: str = "", q: str = "", favorite: bool | None = None) -> list[dict]:
        query = q.strip().lower()
        items = [item for item in self.assets.load() if item.get("active", True)]
        if category:
            items = [item for item in items if item.get("category") == category]
        if favorite is not None:
            items = [item for item in items if bool(item.get("favorite")) is favorite]
        if query:
            items = [
                item for item in items
                if query in " ".join([item.get("name", ""), item.get("category", ""), " ".join(item.get("tags", [])), item.get("remark", "")]).lower()
            ]
        return sorted(items, key=lambda item: item.get("updatedAt", ""), reverse=True)

    def get_asset(self, asset_id: str) -> dict | None:
        for item in self.assets.load():
            if item.get("id") == asset_id and item.get("active", True):
                return dict(item)
        return None

    def create_asset(self, data: dict) -> dict:
        now = utc_now_iso()
        item = {
            "id": uuid.uuid4().hex[:12],
            "name": data.get("name", "").strip() or data.get("originalName", "素材"),
            "category": data.get("category", "其他") or "其他",
            "filePath": data.get("filePath", ""),
            "thumbnailPath": data.get("thumbnailPath", ""),
            "url": data.get("url", ""),
            "thumbnailUrl": data.get("thumbnailUrl", data.get("url", "")),
            "tags": data.get("tags", []),
            "remark": data.get("remark", ""),
            "favorite": bool(data.get("favorite", False)),
            "active": True,
            "createdAt": now,
            "updatedAt": now,
        }
        return self.assets.update(lambda items: items.append(item) or item)

    def update_asset(self, asset_id: str, patch: dict) -> dict | None:
        def mutate(items):
            for item in items:
                if item.get("id") != asset_id:
                    continue
                for key in ["name", "category", "tags", "remark", "favorite"]:
                    if key in patch and patch[key] is not None:
                        item[key] = patch[key]
                item["updatedAt"] = utc_now_iso()
                return item
            return None

        return self.assets.update(mutate)

    def delete_asset(self, asset_id: str) -> bool:
        def mutate(items):
            for item in items:
                if item.get("id") == asset_id:
                    item["active"] = False
                    item["updatedAt"] = utc_now_iso()
                    return True
            return False

        return self.assets.update(mutate)

    def create_task(self, data: dict) -> dict:
        now = utc_now_iso()
        item = {
            "id": uuid.uuid4().hex[:12],
            "status": "pending",
            "modelConfigId": data.get("modelConfigId"),
            "modelConfigSnapshot": data.get("modelConfigSnapshot", {}),
            "prompt": data.get("prompt", ""),
            "size": data.get("size", "original"),
            "count": int(data.get("count", 1) or 1),
            "files": data.get("files", []),
            "selectedAssetIds": data.get("selectedAssetIds", []),
            "images": [],
            "errorType": "",
            "errorMessage": "",
            "upstreamRawError": "",
            "raw": None,
            "createdAt": now,
            "startedAt": "",
            "finishedAt": "",
        }
        return self.tasks.update(lambda items: items.append(item) or item)

    def update_task(self, task_id: str, patch: dict) -> dict | None:
        def mutate(items):
            for item in items:
                if item.get("id") == task_id:
                    item.update(patch)
                    return item
            return None

        return self.tasks.update(mutate)

    def get_task(self, task_id: str) -> dict | None:
        for item in self.tasks.load():
            if item.get("id") == task_id:
                return dict(item)
        return None

    def list_tasks(self, limit: int = 30) -> list[dict]:
        items = self.tasks.load()
        return sorted(items, key=lambda item: item.get("createdAt", ""), reverse=True)[:limit]

    def _ensure_default_config(self):
        if self.model_configs.load():
            return
        self.create_model_config({
            "name": "默认 Image2 中转站",
            "provider": "image2_proxy",
            "baseUrl": "",
            "apiKey": "",
            "model": "",
            "endpoint": "/images/edits",
            "apiType": "openai_images_edits",
            "capabilities": ProviderCapabilities().model_dump(),
            "defaultSize": "original",
            "timeoutSeconds": 180,
            "enabled": False,
        })


def _public_config(item: dict) -> dict:
    public = dict(item)
    public.pop("apiKey", None)
    public["hasApiKey"] = bool(item.get("apiKey"))
    return public


def _capabilities_dict(value) -> dict:
    if isinstance(value, ProviderCapabilities):
        return value.model_dump()
    if isinstance(value, dict):
        return ProviderCapabilities(**value).model_dump()
    return ProviderCapabilities().model_dump()


render_db = RenderDatabase()
