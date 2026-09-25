from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ACTIVE_STATUSES = {"claimed", "printing", "uploading"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _plus_seconds(value: str, seconds: int) -> str:
    return (_parse_time(value) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


class AtomicJsonFile:
    def __init__(self, path: str | Path, default: Any):
        self.path = Path(path)
        self.default = default
        self.lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save_unlocked(copy.deepcopy(default))

    def load(self) -> Any:
        with self.lock:
            return self._load_unlocked()

    def update(self, mutator):
        with self.lock:
            value = self._load_unlocked()
            result = mutator(value)
            self._save_unlocked(value)
            return copy.deepcopy(result)

    def _load_unlocked(self) -> Any:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            return copy.deepcopy(self.default)

    def _save_unlocked(self, value: Any) -> None:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise


class CadPrintDatabase:
    def __init__(
        self,
        jobs_path: str | Path,
        nodes_path: str | Path,
        lease_seconds: int = 300,
        offline_seconds: int = 45,
    ):
        self.jobs = AtomicJsonFile(jobs_path, [])
        self.nodes = AtomicJsonFile(nodes_path, {})
        self.lease_seconds = max(10, int(lease_seconds))
        self.offline_seconds = max(10, int(offline_seconds))

    def create_job(
        self,
        source_task_id: str,
        fingerprint: str,
        dxf_path: str,
        created_by: str,
        now: str | None = None,
        job_id: str | None = None,
    ) -> dict:
        timestamp = now or utc_now_iso()
        item = {
            "id": job_id or uuid.uuid4().hex[:16],
            "sourceTaskId": source_task_id.strip(),
            "fingerprint": fingerprint,
            "dxfPath": dxf_path,
            "resultPath": "",
            "resultUrl": "",
            "status": "queued",
            "createdBy": created_by,
            "deviceId": "",
            "attempts": 0,
            "leaseExpiresAt": "",
            "errorStage": "",
            "errorMessage": "",
            "logTail": "",
            "width": 0,
            "height": 0,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "completedAt": "",
        }

        def mutate(items: list[dict]) -> dict:
            items.append(item)
            return item

        return self.jobs.update(mutate)

    def get_job(self, job_id: str) -> dict | None:
        return next((item for item in self.jobs.load() if item.get("id") == job_id), None)

    def list_jobs(self, source_task_id: str = "", limit: int = 30) -> list[dict]:
        items = self.jobs.load()
        if source_task_id:
            items = [item for item in items if item.get("sourceTaskId") == source_task_id]
        items.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
        return items[: max(1, min(int(limit), 100))]

    def find_completed(self, fingerprint: str) -> dict | None:
        for item in self.list_jobs(limit=100):
            if item.get("fingerprint") == fingerprint and item.get("status") == "completed":
                return item
        return None

    def heartbeat(
        self,
        device_id: str,
        details: dict,
        now: str | None = None,
    ) -> dict:
        timestamp = now or utc_now_iso()
        node = {
            "deviceId": device_id,
            "autocadReady": bool(details.get("autocadReady")),
            "message": str(details.get("message", ""))[:500],
            "version": str(details.get("version", ""))[:80],
            "lastSeenAt": timestamp,
        }

        def mutate(items: dict[str, dict]) -> dict:
            items[device_id] = node
            return node

        return self.nodes.update(mutate)

    def node_status(self, device_id: str, now: str | None = None) -> dict:
        timestamp = now or utc_now_iso()
        node = self.nodes.load().get(device_id)
        if not node:
            return {
                "deviceId": device_id,
                "online": False,
                "autocadReady": False,
                "message": "打印节点尚未连接",
                "version": "",
                "lastSeenAt": "",
            }
        age = (_parse_time(timestamp) - _parse_time(node["lastSeenAt"])).total_seconds()
        return {**node, "online": age <= self.offline_seconds}

    def claim_next(self, device_id: str, now: str | None = None) -> dict | None:
        timestamp = now or utc_now_iso()

        def mutate(items: list[dict]) -> dict | None:
            self._release_expired(items, timestamp)
            queued = [item for item in items if item.get("status") == "queued"]
            if not queued:
                return None
            item = min(queued, key=lambda value: value.get("createdAt", ""))
            item.update({
                "status": "claimed",
                "deviceId": device_id,
                "attempts": int(item.get("attempts", 0)) + 1,
                "leaseExpiresAt": _plus_seconds(timestamp, self.lease_seconds),
                "updatedAt": timestamp,
                "errorStage": "",
                "errorMessage": "",
                "logTail": "",
            })
            return item

        return self.jobs.update(mutate)

    def update_worker_status(
        self,
        job_id: str,
        device_id: str,
        status: str,
        error_stage: str = "",
        error_message: str = "",
        log_tail: str = "",
        now: str | None = None,
    ) -> dict | None:
        if status not in {"printing", "uploading", "failed"}:
            raise ValueError("非法打印状态")
        timestamp = now or utc_now_iso()

        def mutate(items: list[dict]) -> dict | None:
            item = next((value for value in items if value.get("id") == job_id), None)
            if not item or item.get("deviceId") != device_id:
                return None
            item.update({
                "status": status,
                "leaseExpiresAt": _plus_seconds(timestamp, self.lease_seconds) if status != "failed" else "",
                "errorStage": error_stage[:120],
                "errorMessage": error_message[:1000],
                "logTail": log_tail[-8000:],
                "updatedAt": timestamp,
            })
            return item

        return self.jobs.update(mutate)

    def complete_job(
        self,
        job_id: str,
        device_id: str,
        result_path: str,
        width: int,
        height: int,
        result_url: str = "",
        now: str | None = None,
    ) -> dict | None:
        timestamp = now or utc_now_iso()

        def mutate(items: list[dict]) -> dict | None:
            item = next((value for value in items if value.get("id") == job_id), None)
            if not item or item.get("deviceId") != device_id:
                return None
            item.update({
                "status": "completed",
                "resultPath": result_path,
                "resultUrl": result_url,
                "width": int(width),
                "height": int(height),
                "leaseExpiresAt": "",
                "updatedAt": timestamp,
                "completedAt": timestamp,
                "errorStage": "",
                "errorMessage": "",
            })
            return item

        return self.jobs.update(mutate)

    def cancel_job(self, job_id: str, now: str | None = None) -> dict | None:
        timestamp = now or utc_now_iso()

        def mutate(items: list[dict]) -> dict | None:
            item = next((value for value in items if value.get("id") == job_id), None)
            if not item or item.get("status") not in {"queued", "failed"}:
                return None
            item.update({"status": "cancelled", "updatedAt": timestamp, "leaseExpiresAt": ""})
            return item

        return self.jobs.update(mutate)

    @staticmethod
    def _release_expired(items: list[dict], now: str) -> None:
        current = _parse_time(now)
        for item in items:
            lease = item.get("leaseExpiresAt", "")
            if item.get("status") in ACTIVE_STATUSES and lease and _parse_time(lease) < current:
                item.update({
                    "status": "queued",
                    "deviceId": "",
                    "leaseExpiresAt": "",
                    "updatedAt": now,
                    "errorStage": "lease_expired",
                    "errorMessage": "打印节点租约已过期，任务已重新排队",
                })
