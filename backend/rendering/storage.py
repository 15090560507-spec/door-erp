import os
import shutil
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from typing import BinaryIO

from PIL import Image

from config import DATA_DIR


RENDER_DIR = os.path.join(DATA_DIR, "render")
RENDER_FILES_DIR = os.path.join(RENDER_DIR, "files")
LIBRARY_DIR = os.path.join(RENDER_FILES_DIR, "library")
TEMP_DIR = os.path.join(RENDER_FILES_DIR, "temp")
RESULTS_DIR = os.path.join(RENDER_FILES_DIR, "results")
THUMB_DIR = os.path.join(RENDER_FILES_DIR, "thumbs")

for _path in (RENDER_DIR, RENDER_FILES_DIR, LIBRARY_DIR, TEMP_DIR, RESULTS_DIR, THUMB_DIR):
    os.makedirs(_path, exist_ok=True)


def public_file_url(path: str) -> str:
    normalized = path.replace("\\", "/")
    marker = "/data/render/files/"
    if marker in normalized:
        return f"/api/render/files/{normalized.split(marker, 1)[1]}"
    marker = "data/render/files/"
    if marker in normalized:
        return f"/api/render/files/{normalized.split(marker, 1)[1]}"
    return ""


def save_upload(file_obj: BinaryIO, filename: str, subdir: str) -> dict:
    folder = {"library": LIBRARY_DIR, "temp": TEMP_DIR, "results": RESULTS_DIR}.get(subdir, TEMP_DIR)
    os.makedirs(folder, exist_ok=True)
    ext = _safe_ext(filename)
    file_id = uuid.uuid4().hex
    saved_name = f"{file_id}{ext}"
    path = os.path.join(folder, saved_name)
    with open(path, "wb") as handle:
        shutil.copyfileobj(file_obj, handle)
    thumb_path = create_thumbnail(path)
    return {
        "fileId": file_id,
        "filePath": path,
        "fileName": saved_name,
        "originalName": filename or saved_name,
        "thumbnailPath": thumb_path,
        "url": public_file_url(path),
        "thumbnailUrl": public_file_url(thumb_path) if thumb_path else public_file_url(path),
    }


def save_bytes(data: bytes, filename: str, subdir: str = "results") -> dict:
    return save_upload(BytesIO(data), filename, subdir)


def create_thumbnail(path: str) -> str:
    try:
        with Image.open(path) as image:
            image.thumbnail((360, 360))
            thumb_name = f"{os.path.splitext(os.path.basename(path))[0]}.jpg"
            thumb_path = os.path.join(THUMB_DIR, thumb_name)
            image.convert("RGB").save(thumb_path, "JPEG", quality=85)
            return thumb_path
    except Exception:
        return ""


def image_size(path: str) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def temp_expiry(days: int = 7) -> str:
    return (datetime.now() + timedelta(days=days)).isoformat()


def _safe_ext(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    return ext if ext in {".png", ".jpg", ".jpeg", ".webp"} else ".png"

