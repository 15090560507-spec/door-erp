from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageFilter

from .image_geometry import build_structural_seam, encode_jpeg, seam_rgba, validate_layer_canvases
from .layered_render import _apply_ai_material


ROLE_ORDER = ("trim", "frame", "panel", "glass", "hardware")
VISIBLE_LAYER_ORDER = ("seam", "trim", "frame", "panel", "glass", "hardware", "lighting")
OUTPUT_QUALITY = 95
ROLE_FALLBACK_COLORS = {
    "trim": (108, 66, 31),
    "frame": (140, 90, 43),
    "panel": (196, 138, 61),
    "glass": (185, 215, 225),
    "hardware": (72, 72, 76),
}
ROLE_PROMPTS = {
    "panel": "只为门扇区域生成参考图中的门扇款式、颜色和材质。严格保持原始比例、分格和边界，不得改变门框、门套、玻璃或五金。输出真实产品材质，不显示线稿、尺寸、文字或辅助轮廓。",
    "trim": "只为门套、门头和门柱区域生成参考图中的造型和材质。严格保持原始外轮廓、尺寸与遮挡关系，不得改变门扇或门框。输出真实产品材质，不显示线稿、尺寸、文字或辅助轮廓。",
    "frame": "只为门框区域生成表面颜色和材质。严格保持门框宽度、边界和比例，不得改变门扇或门套。输出真实产品材质，不显示线稿、尺寸、文字或辅助轮廓。",
    "glass": "只为玻璃区域生成颜色、透明度、纹理和真实反光。严格保持玻璃边界，不得改变周围结构。输出真实产品材质，不显示线稿、尺寸、文字或辅助轮廓。",
    "hardware": "只为已有的拉手、锁具、合页、花件等五金区域生成参考款式。不得移动、增加、删除或改变配件比例。输出真实产品材质，不显示线稿、尺寸、文字或辅助轮廓。",
}


def render_precise_image(
    line_art_path: str,
    masks: dict[str, dict],
    ai_config: dict,
    reference_bindings: dict[str, list[dict]],
    target_long_edge: int | None = None,
) -> dict:
    source = Image.open(line_art_path).convert("RGB")
    if target_long_edge and target_long_edge > 0 and max(source.size) != target_long_edge:
        scale = target_long_edge / max(source.size)
        source = source.resize(
            (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
            Image.Resampling.LANCZOS,
        )
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
            generated[role] = _rgba_with_mask(_solid_rgb(width, height, ROLE_FALLBACK_COLORS[role]), mask)
            continue
        try:
            rgb = _apply_ai_material(source_rgb, ai_config, references, ROLE_PROMPTS[role])
        except Exception as exc:
            notes.append(f"{role}：{exc}")
            rgb = _solid_rgb(width, height, ROLE_FALLBACK_COLORS[role])
        generated[role] = _rgba_with_mask(rgb, mask)

    union_mask = np.maximum.reduce([role_masks[role] for role in ROLE_ORDER])
    lighting = _lighting_layer(union_mask)
    seam = seam_rgba(
        build_structural_seam(
            role_masks,
            width_px=max(1, round(min(width, height) / 900)),
        )
    )
    layers = {"seam": seam, **generated, "lighting": lighting}
    validate_layer_canvases(layers, (width, height))
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    for role in VISIBLE_LAYER_ORDER:
        canvas.alpha_composite(Image.fromarray(layers[role], "RGBA"))

    image_bytes = encode_jpeg(np.array(canvas, dtype=np.uint8), quality=OUTPUT_QUALITY)
    layer_pngs = {role: _png_bytes(generated[role]) for role in ROLE_ORDER}
    layer_pngs["seam"] = _png_bytes(seam)
    layer_pngs["lighting"] = _png_bytes(lighting)
    return {
        "image_bytes": image_bytes,
        "layer_pngs": layer_pngs,
        "canvas_size": (width, height),
        "visible_layer_order": list(VISIBLE_LAYER_ORDER),
        "output_quality": OUTPUT_QUALITY,
        "material_note": "部分部件处理失败并使用默认材质：" + "；".join(notes) if notes else "",
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


def _solid_rgb(width: int, height: int, color: tuple[int, int, int]) -> np.ndarray:
    rgb = np.empty((height, width, 3), dtype=np.uint8)
    rgb[...] = color
    return rgb


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
