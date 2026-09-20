from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image


STRUCTURAL_PAIRS = (("trim", "frame"), ("frame", "panel"))


def normalize_rgb_cover(rgb: np.ndarray, target_size: tuple[int, int]) -> np.ndarray:
    """Resize without distortion, then crop the excess around the center."""
    target_width, target_height = target_size
    if target_width <= 0 or target_height <= 0:
        raise ValueError("目标画布尺寸必须大于 0")
    if rgb.ndim != 3 or rgb.shape[2] < 3 or rgb.shape[0] <= 0 or rgb.shape[1] <= 0:
        raise ValueError("输入图片必须是有效的 RGB 数组")

    source = Image.fromarray(rgb[..., :3].astype(np.uint8), "RGB")
    scale = max(target_width / source.width, target_height / source.height)
    resized = source.resize(
        (
            max(target_width, round(source.width * scale)),
            max(target_height, round(source.height * scale)),
        ),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - target_width) // 2
    top = (resized.height - target_height) // 2
    return np.array(
        resized.crop((left, top, left + target_width, top + target_height)),
        dtype=np.uint8,
    )


def validate_layer_canvases(layers: dict[str, np.ndarray], size: tuple[int, int]) -> None:
    width, height = size
    if width <= 0 or height <= 0:
        raise ValueError("共享画布尺寸必须大于 0")
    for role, layer in layers.items():
        if layer.ndim != 3 or layer.shape[2] != 4:
            raise ValueError(f"{role} 图层必须是 RGBA 图像")
        if layer.shape[:2] != (height, width):
            raise ValueError(
                f"{role} 图层尺寸 {layer.shape[1]}x{layer.shape[0]} "
                f"与共享画布 {width}x{height} 不一致"
            )


def build_structural_seam(role_masks: dict[str, np.ndarray], width_px: int) -> np.ndarray:
    """Return black-gap alpha only where two structural roles approach each other."""
    if not role_masks:
        raise ValueError("缺少用于生成接缝的部件遮罩")
    shape = next(iter(role_masks.values())).shape
    if len(shape) != 2:
        raise ValueError("部件遮罩必须是二维灰度图")
    for role, mask in role_masks.items():
        if mask.shape != shape:
            raise ValueError(f"{role} 遮罩尺寸与其他部件不一致")

    seam = np.zeros(shape, dtype=np.uint8)
    radius = max(1, int(width_px))
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (radius * 2 + 1, radius * 2 + 1),
    )
    for first, second in STRUCTURAL_PAIRS:
        if first not in role_masks or second not in role_masks:
            continue
        first_mask = role_masks[first] > 0
        second_mask = role_masks[second] > 0
        near_first = cv2.dilate(first_mask.astype(np.uint8), kernel) > 0
        near_second = cv2.dilate(second_mask.astype(np.uint8), kernel) > 0
        gap = near_first & near_second & ~(first_mask | second_mask)
        seam[gap] = 255
    return seam


def seam_rgba(mask: np.ndarray) -> np.ndarray:
    if mask.ndim != 2:
        raise ValueError("接缝遮罩必须是二维灰度图")
    layer = np.zeros((*mask.shape, 4), dtype=np.uint8)
    layer[..., 3] = mask.astype(np.uint8)
    return layer


def encode_jpeg(rgba: np.ndarray, quality: int = 95) -> bytes:
    if rgba.ndim != 3 or rgba.shape[2] < 3:
        raise ValueError("JPEG 输出必须来自 RGB 或 RGBA 图像")
    output = io.BytesIO()
    Image.fromarray(rgba[..., :3].astype(np.uint8), "RGB").save(
        output,
        "JPEG",
        quality=max(95, int(quality)),
        subsampling=0,
        optimize=True,
    )
    return output.getvalue()
