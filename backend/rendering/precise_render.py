from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageFilter

from .layered_render import _apply_ai_material


ROLE_ORDER = ("trim", "frame", "panel", "glass", "hardware")
ROLE_PROMPTS = {
    "panel": "只为门扇区域生成参考图中的门扇款式、颜色和材质。严格保持线稿比例、分格和边界，不得改变门框、门套、玻璃或五金。",
    "trim": "只为门套、门头和门柱区域生成参考图中的造型和材质。严格保持线稿外轮廓、尺寸与遮挡关系，不得改变门扇或门框。",
    "frame": "只为门框区域生成表面颜色和材质。严格保持门框宽度、边界和比例，不得改变门扇或门套。",
    "glass": "只为玻璃区域生成颜色、透明度、纹理和真实反光。严格保持玻璃边界，不得改变周围线条。",
    "hardware": "只为线稿中已有的拉手、锁具、合页、花件等五金生成参考款式。不得移动、增加、删除或改变配件比例。",
}


def render_precise_image(
    line_art_path: str,
    masks: dict[str, dict],
    ai_config: dict,
    reference_bindings: dict[str, list[dict]],
) -> dict:
    source = Image.open(line_art_path).convert("RGB")
    width, height = source.size
    source_rgb = np.array(source, dtype=np.uint8)
    role_masks = {role: _load_mask((masks.get(role) or {}).get("filePath", ""), (width, height)) for role in ROLE_ORDER}
    generated: dict[str, np.ndarray] = {}
    notes: list[str] = []

    for role in ("panel", "trim", "frame", "glass", "hardware"):
        mask = role_masks[role]
        if not np.any(mask):
            generated[role] = _transparent(width, height)
            continue
        references = reference_bindings.get(role, [])
        if not references and role == "frame" and "panel" in generated:
            generated[role] = _rgba_with_mask(generated["panel"][..., :3], mask)
            continue
        if not references:
            generated[role] = _rgba_with_mask(source_rgb, mask)
            continue
        try:
            rgb = _apply_ai_material(source_rgb, ai_config, references, ROLE_PROMPTS[role])
        except Exception as exc:
            notes.append(f"{role}：{exc}")
            rgb = source_rgb
        generated[role] = _rgba_with_mask(rgb, mask)

    union_mask = np.maximum.reduce([role_masks[role] for role in ROLE_ORDER])
    lighting = _lighting_layer(union_mask)
    outline = _outline_layer(source_rgb)
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    for role in ROLE_ORDER:
        canvas.alpha_composite(Image.fromarray(generated[role], "RGBA"))
    canvas.alpha_composite(Image.fromarray(lighting, "RGBA"))
    canvas.alpha_composite(Image.fromarray(outline, "RGBA"))

    jpg = io.BytesIO()
    canvas.convert("RGB").save(jpg, "JPEG", quality=90)
    layer_pngs = {role: _png_bytes(generated[role]) for role in ROLE_ORDER}
    layer_pngs["lighting"] = _png_bytes(lighting)
    layer_pngs["outline"] = _png_bytes(outline)
    return {
        "image_bytes": jpg.getvalue(),
        "layer_pngs": layer_pngs,
        "canvas_size": (width, height),
        "material_note": "部分部件处理失败并保留线稿底色：" + "；".join(notes) if notes else "",
    }


def _load_mask(path: str, size: tuple[int, int]) -> np.ndarray:
    if not path:
        return np.zeros((size[1], size[0]), dtype=np.uint8)
    mask = Image.open(path).convert("L")
    if mask.size != size:
        mask = mask.resize(size, Image.Resampling.NEAREST)
    return np.where(np.array(mask) >= 128, 255, 0).astype(np.uint8)


def _rgba_with_mask(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    return np.dstack((rgb[..., :3], mask)).astype(np.uint8)


def _transparent(width: int, height: int) -> np.ndarray:
    return np.zeros((height, width, 4), dtype=np.uint8)


def _lighting_layer(mask: np.ndarray) -> np.ndarray:
    alpha = Image.fromarray(mask, "L").filter(ImageFilter.GaussianBlur(radius=max(2, min(mask.shape) / 220)))
    shifted = Image.new("L", alpha.size, 0)
    shifted.paste(alpha, (max(1, alpha.size[0] // 300), max(2, alpha.size[1] // 260)))
    values = (np.array(shifted, dtype=np.float32) * 0.14).astype(np.uint8)
    layer = np.zeros((mask.shape[0], mask.shape[1], 4), dtype=np.uint8)
    layer[..., :3] = 20
    layer[..., 3] = values
    return layer


def _outline_layer(source_rgb: np.ndarray) -> np.ndarray:
    gray = np.mean(source_rgb, axis=2)
    alpha = np.where(gray < 105, np.clip((125 - gray) * 2.0, 0, 210), 0).astype(np.uint8)
    layer = np.zeros((source_rgb.shape[0], source_rgb.shape[1], 4), dtype=np.uint8)
    layer[..., :3] = 35
    layer[..., 3] = alpha
    return layer


def _png_bytes(layer: np.ndarray) -> bytes:
    output = io.BytesIO()
    Image.fromarray(layer, "RGBA").save(output, "PNG")
    return output.getvalue()
