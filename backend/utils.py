"""
工具函数 - 从 door_26.py 原封不动提取
"""
from typing import Tuple


def parse_gap_str(gap_str: str, default: int = 0) -> Tuple[int, int]:
    if not gap_str.strip():
        return (default, default)
    try:
        parts = gap_str.replace("，", "/").replace(",", "/").split("/")
        if len(parts) == 2:
            return (int(parts[0].strip()), int(parts[1].strip()))
        else:
            return (int(parts[0].strip()), int(parts[0].strip()))
    except Exception:
        return (default, default)


def parse_dim_str(val_str: str, default_out: float, default_in: float) -> Tuple[float, float]:
    try:
        parts = val_str.replace('，', '/').replace(',', '/').split('/')
        if len(parts) >= 2:
            return (float(parts[0]), float(parts[1]))
        else:
            return (float(parts[0]), float(parts[0]))
    except Exception:
        return (default_out, default_in)
