"""Atomic JSON persistence for door-frame cutting projects."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import DOOR_CAD_BACKUP_DIR, DOOR_CAD_PROJECTS_FILE
from database import backup_file_before_replace
from door_cad.models import FrameInput, ProjectGeometry


SCHEMA_VERSION = "1.0"
RULE_VERSION = "frame-new-v1.4.3"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class ProjectVersionError(ValueError):
    """Raised when persisted geometry cannot be handled by this release."""


def _now_iso() -> str:
    return datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")


class DoorCadProjectRepository:
    def __init__(
        self,
        file_path: str | os.PathLike[str] = DOOR_CAD_PROJECTS_FILE,
        backup_dir: str | os.PathLike[str] = DOOR_CAD_BACKUP_DIR,
    ) -> None:
        self.file_path = Path(file_path)
        self.backup_dir = Path(backup_dir)
        self._lock = threading.RLock()

    @staticmethod
    def _empty_document() -> dict:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "ruleVersion": RULE_VERSION,
            "projects": [],
        }

    @staticmethod
    def _check_version(document: dict) -> None:
        if document.get("schemaVersion") != SCHEMA_VERSION:
            raise ProjectVersionError("项目库数据结构版本不兼容")
        if document.get("ruleVersion") != RULE_VERSION:
            raise ProjectVersionError("项目库下料规则版本不兼容")
        if not isinstance(document.get("projects"), list):
            raise ValueError("项目库 projects 字段格式错误")

    def _load_unlocked(self) -> dict:
        if not self.file_path.exists():
            return self._empty_document()
        with self.file_path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
        self._check_version(document)
        for record in document["projects"]:
            if record.get("schemaVersion") != SCHEMA_VERSION or record.get("ruleVersion") != RULE_VERSION:
                raise ProjectVersionError(f"项目 {record.get('id', '')} 的版本不兼容")
        return document

    def _save_unlocked(self, document: dict) -> None:
        self._check_version(document)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(
            dir=self.file_path.parent,
            prefix=f".{self.file_path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            backup_file_before_replace(str(self.file_path), str(self.backup_dir))
            os.replace(temporary_path, self.file_path)
        except Exception:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
            raise

    @staticmethod
    def _payload(inputs: FrameInput, geometry: ProjectGeometry) -> tuple[dict, dict]:
        if geometry.inputs != inputs:
            raise ValueError("保存的输入参数与几何快照不一致")
        if geometry.schemaVersion != SCHEMA_VERSION or geometry.ruleVersion != RULE_VERSION:
            raise ProjectVersionError("几何快照版本不兼容")
        return inputs.model_dump(mode="json"), geometry.model_dump(mode="json")

    def create(self, inputs: FrameInput, geometry: ProjectGeometry, user_id: str) -> dict:
        input_data, geometry_data = self._payload(inputs, geometry)
        with self._lock:
            document = self._load_unlocked()
            now = _now_iso()
            record = {
                "id": uuid.uuid4().hex[:12],
                "schemaVersion": SCHEMA_VERSION,
                "ruleVersion": RULE_VERSION,
                "createdAt": now,
                "updatedAt": now,
                "createdBy": user_id,
                "updatedBy": user_id,
                "inputs": input_data,
                "geometry": geometry_data,
            }
            document["projects"].append(record)
            self._save_unlocked(document)
            return deepcopy(record)

    def list_summaries(self) -> list[dict]:
        with self._lock:
            records = self._load_unlocked()["projects"]
            summaries = []
            for record in records:
                project = record["geometry"].get("project", {})
                validation = record["geometry"].get("validation", {})
                summaries.append({
                    "id": record["id"],
                    "orderNo": project.get("orderNo", ""),
                    "projectName": project.get("projectName", ""),
                    "taskId": project.get("taskId"),
                    "status": validation.get("status", "ERROR"),
                    "updatedAt": record["updatedAt"],
                    "updatedBy": record["updatedBy"],
                })
            return sorted(summaries, key=lambda item: item["updatedAt"], reverse=True)

    def get(self, project_id: str) -> dict:
        with self._lock:
            for record in self._load_unlocked()["projects"]:
                if record["id"] == project_id:
                    return deepcopy(record)
        raise KeyError(project_id)

    def update(self, project_id: str, inputs: FrameInput, geometry: ProjectGeometry, user_id: str) -> dict:
        input_data, geometry_data = self._payload(inputs, geometry)
        with self._lock:
            document = self._load_unlocked()
            for index, current in enumerate(document["projects"]):
                if current["id"] != project_id:
                    continue
                updated = {
                    **current,
                    "updatedAt": _now_iso(),
                    "updatedBy": user_id,
                    "inputs": input_data,
                    "geometry": geometry_data,
                }
                document["projects"][index] = updated
                self._save_unlocked(document)
                return deepcopy(updated)
        raise KeyError(project_id)
