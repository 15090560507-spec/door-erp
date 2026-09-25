from __future__ import annotations

import io
import re
from pathlib import Path

from PIL import Image

from config import DATA_DIR


CAD_PRINT_DIR = Path(DATA_DIR) / "cad_print"
SAFE_JOB_ID = re.compile(r"^[a-f0-9]{12,40}$")


def _job_dir(job_id: str) -> Path:
    if not SAFE_JOB_ID.fullmatch(job_id):
        raise ValueError("非法打印任务编号")
    path = CAD_PRINT_DIR / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def dxf_path(job_id: str) -> Path:
    return _job_dir(job_id) / "source.dxf"


def result_path(job_id: str) -> Path:
    return _job_dir(job_id) / "result.jpg"


def save_dxf(job_id: str, content: bytes) -> Path:
    path = dxf_path(job_id)
    path.write_bytes(content)
    return path


def save_result(job_id: str, content: bytes) -> tuple[Path, int, int]:
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
            image_format = image.format
    except Exception as exc:
        raise ValueError("上传文件不是有效 JPG") from exc
    if image_format not in {"JPEG", "MPO"}:
        raise ValueError("打印结果必须是 JPG")
    if (width, height) != (5940, 4200):
        raise ValueError(f"打印结果尺寸错误：{width}x{height}，要求 5940x4200")
    path = result_path(job_id)
    path.write_bytes(content)
    return path, width, height

