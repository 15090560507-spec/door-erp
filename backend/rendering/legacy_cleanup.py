from __future__ import annotations

import json
import os

from config import DATA_DIR

from .storage import RENDER_FILES_DIR


LEGACY_RECORDS_PATH = os.path.join(DATA_DIR, "layered_render_records.json")
CLEANUP_MARKER_PATH = os.path.join(DATA_DIR, "render", "layered_render_cleanup_v2.done")


def cleanup_legacy_layered_outputs() -> None:
    if os.path.exists(CLEANUP_MARKER_PATH):
        return
    root = os.path.abspath(RENDER_FILES_DIR)
    for record in _load_records():
        for value in (record.get("files") or {}).values():
            url = str((value or {}).get("url", ""))
            relative = ""
            for marker in ("/api/render/files/", "/data/render/files/"):
                if marker in url:
                    relative = url.split(marker, 1)[1]
                    break
            if not relative:
                continue
            relative = relative.replace("/", os.sep)
            target = os.path.abspath(os.path.join(root, relative))
            try:
                if os.path.commonpath([root, target]) == root and os.path.isfile(target):
                    os.remove(target)
            except (OSError, ValueError):
                continue
    try:
        if os.path.isfile(LEGACY_RECORDS_PATH):
            os.remove(LEGACY_RECORDS_PATH)
    finally:
        os.makedirs(os.path.dirname(CLEANUP_MARKER_PATH), exist_ok=True)
        with open(CLEANUP_MARKER_PATH, "w", encoding="utf-8") as handle:
            handle.write("legacy layered render records and referenced files removed\n")


def _load_records() -> list[dict]:
    try:
        with open(LEGACY_RECORDS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, list) else []
    except Exception:
        return []
