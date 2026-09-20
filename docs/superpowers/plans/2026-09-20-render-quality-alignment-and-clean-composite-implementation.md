# Clean Aligned Render Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make quick rendering default to 2K and precise rendering default to 4K while keeping DXF geometry fixed, removing visible CAD annotations from ordinary images, preserving realistic black assembly seams, and keeping glass and hardware above the door panel.

**Architecture:** Add one focused image-geometry utility for aspect-preserving normalization, canvas validation, and structural seam generation. Both bitmap-precise and DXF-precise paths will use the same clean composition order, while the service layer will own mode-aware size defaults and regeneration composition. Quick mode remains provider-driven but receives a strict clean-product prompt and a 2K default.

**Tech Stack:** Python 3, Pillow, NumPy, OpenCV, ezdxf, pytest, FastAPI service helpers, Next.js/React/TypeScript, Tailwind CSS.

---

## File Map

- Create `backend/rendering/image_geometry.py`: shared aspect-preserving image normalization, exact-canvas validation, structural seam masks, and high-quality JPEG encoding.
- Create `backend/test_render_image_geometry.py`: focused unit tests for normalization, validation, seams, and encoding.
- Modify `backend/rendering/precise_render.py`: clean bitmap-precise composition, structural seams, fixed order, no visible outline.
- Modify `backend/rendering/layered_render.py`: clean DXF composition, glass classification, hidden PSD CAD layers, shared normalization, 95-quality output.
- Modify `backend/rendering/dxf_geometry.py`: include optional glass geometry in the shared manifest and validation.
- Modify `backend/rendering/service.py`: mode-aware defaults, clean provider prompts, exact layer recomposition, no `outline` in normal results.
- Modify `backend/test_render_precise_mode.py`: bitmap precise and component regeneration regression coverage.
- Modify `backend/test_layered_render.py`: DXF clean-image, PSD visibility, geometry, and layer-order regression coverage.
- Modify `backend/test_render_background_task.py`: task-size and quick-prompt behavior.
- Modify `frontend/src/app/render/page.tsx`: mode-aware automatic resolution and clear actual-size display.

### Task 1: Shared image geometry and quality helpers

**Files:**
- Create: `backend/rendering/image_geometry.py`
- Create: `backend/test_render_image_geometry.py`

- [ ] **Step 1: Write failing normalization and validation tests**

```python
import io

import numpy as np
import pytest
from PIL import Image

from rendering.image_geometry import (
    build_structural_seam,
    encode_jpeg,
    normalize_rgb_cover,
    validate_layer_canvases,
)


def test_normalize_rgb_cover_keeps_aspect_ratio_and_center_crops():
    source = np.zeros((100, 200, 3), dtype=np.uint8)
    source[:, :100] = (255, 0, 0)
    source[:, 100:] = (0, 0, 255)

    result = normalize_rgb_cover(source, (100, 100))

    assert result.shape == (100, 100, 3)
    assert tuple(result[50, 5]) == (255, 0, 0)
    assert tuple(result[50, 95]) == (0, 0, 255)


def test_validate_layer_canvases_names_the_invalid_role():
    layers = {
        "panel": np.zeros((100, 80, 4), dtype=np.uint8),
        "hardware": np.zeros((90, 80, 4), dtype=np.uint8),
    }
    with pytest.raises(ValueError, match="hardware"):
        validate_layer_canvases(layers, (80, 100))


def test_structural_seam_only_appears_between_adjacent_parts():
    frame = np.zeros((60, 80), dtype=np.uint8)
    panel = np.zeros_like(frame)
    frame[10:50, 8:35] = 255
    panel[10:50, 37:72] = 255

    seam = build_structural_seam({"frame": frame, "panel": panel}, width_px=2)

    assert seam[30, 35] > 0 or seam[30, 36] > 0
    assert seam[5, 5] == 0
    assert seam[30, 75] == 0


def test_jpeg_encoder_uses_high_quality_rgb_output():
    rgba = np.full((40, 50, 4), 255, dtype=np.uint8)
    data = encode_jpeg(rgba)
    decoded = Image.open(io.BytesIO(data))
    assert decoded.mode == "RGB"
    assert decoded.size == (50, 40)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
python -m pytest backend/test_render_image_geometry.py -q
```

Expected: collection fails because `rendering.image_geometry` does not exist.

- [ ] **Step 3: Implement the shared helpers**

Create `backend/rendering/image_geometry.py` with these public functions:

```python
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image


STRUCTURAL_PAIRS = (("trim", "frame"), ("frame", "panel"))


def normalize_rgb_cover(rgb: np.ndarray, target_size: tuple[int, int]) -> np.ndarray:
    target_width, target_height = target_size
    source = Image.fromarray(rgb[..., :3].astype(np.uint8), "RGB")
    scale = max(target_width / source.width, target_height / source.height)
    resized = source.resize(
        (max(target_width, round(source.width * scale)), max(target_height, round(source.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - target_width) // 2
    top = (resized.height - target_height) // 2
    return np.array(resized.crop((left, top, left + target_width, top + target_height)), dtype=np.uint8)


def validate_layer_canvases(layers: dict[str, np.ndarray], size: tuple[int, int]) -> None:
    width, height = size
    for role, layer in layers.items():
        if layer.shape[:2] != (height, width):
            raise ValueError(f"{role} 图层尺寸 {layer.shape[1]}x{layer.shape[0]} 与共享画布 {width}x{height} 不一致")


def build_structural_seam(role_masks: dict[str, np.ndarray], width_px: int) -> np.ndarray:
    seam = np.zeros_like(next(iter(role_masks.values())), dtype=np.uint8)
    radius = max(1, int(width_px))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
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
    layer = np.zeros((*mask.shape, 4), dtype=np.uint8)
    layer[..., :3] = 0
    layer[..., 3] = mask
    return layer


def encode_jpeg(rgba: np.ndarray, quality: int = 95) -> bytes:
    output = io.BytesIO()
    Image.fromarray(rgba[..., :3].astype(np.uint8), "RGB").save(
        output,
        "JPEG",
        quality=max(95, quality),
        subsampling=0,
        optimize=True,
    )
    return output.getvalue()
```

- [ ] **Step 4: Run the focused tests and make them pass**

Run:

```powershell
python -m pytest backend/test_render_image_geometry.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the shared helper**

```powershell
git add backend/rendering/image_geometry.py backend/test_render_image_geometry.py
git commit -m "feat: add shared render geometry helpers"
```

### Task 2: Clean bitmap-precise composition

**Files:**
- Modify: `backend/rendering/precise_render.py:11-109`
- Modify: `backend/test_render_precise_mode.py`

- [ ] **Step 1: Add failing clean-composite and layer-order tests**

Add tests that create colored overlapping masks and assert:

```python
def test_precise_bitmap_result_has_no_source_outline_and_keeps_foreground_order(monkeypatch, tmp_path):
    # White source contains an intentionally black CAD cross that must not survive the final image.
    # Provider colors: panel red, glass blue, hardware green.
    # Hardware overlaps glass and panel; its center pixel must be green.
    result = render_precise_image(source_path, masks, ai_config, references)
    image = np.array(Image.open(io.BytesIO(result["image_bytes"])).convert("RGB"))
    assert image[180, 120, 1] > image[180, 120, 0]
    assert not np.all(image[30:330, 118:122] < 70)
    assert "outline" not in result["visible_layer_order"]
    assert result["visible_layer_order"] == [
        "seam", "trim", "frame", "panel", "glass", "hardware", "lighting"
    ]
```

Add a second assertion to the existing mask test:

```python
assert result["canvas_size"] == (width, height)
assert result["output_quality"] == 95
```

- [ ] **Step 2: Run the precise bitmap tests and verify failure**

Run:

```powershell
python -m pytest backend/test_render_precise_mode.py -q
```

Expected: the new test fails because the outline is visible and metadata is absent.

- [ ] **Step 3: Replace outline composition with seam-first clean composition**

In `render_precise_image`:

```python
from .image_geometry import build_structural_seam, encode_jpeg, seam_rgba, validate_layer_canvases

VISIBLE_LAYER_ORDER = ("seam", "trim", "frame", "panel", "glass", "hardware", "lighting")

seam_mask = build_structural_seam(role_masks, width_px=max(1, round(min(width, height) / 900)))
layers = {
    "seam": seam_rgba(seam_mask),
    **generated,
    "lighting": lighting,
}
validate_layer_canvases(layers, (width, height))
canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
for role in VISIBLE_LAYER_ORDER:
    canvas.alpha_composite(Image.fromarray(layers[role], "RGBA"))
image_bytes = encode_jpeg(np.array(canvas, dtype=np.uint8))
```

Keep `outline` only as optional hidden PSD/reference data if callers need it, but do not return it as a visible component layer and do not composite it into `image_bytes`. Update the material prompts to say “输出真实产品材质，不显示线稿、尺寸、文字或辅助轮廓”.

- [ ] **Step 4: Run precise tests**

Run:

```powershell
python -m pytest backend/test_render_precise_mode.py -q
```

Expected: all bitmap-precise tests pass.

- [ ] **Step 5: Commit bitmap-precise changes**

```powershell
git add backend/rendering/precise_render.py backend/test_render_precise_mode.py
git commit -m "fix: produce clean precise bitmap renders"
```

### Task 3: Clean DXF composition and hidden PSD references

**Files:**
- Modify: `backend/rendering/layered_render.py:451-735`
- Modify: `backend/rendering/dxf_geometry.py:74-123,221-255`
- Modify: `backend/test_layered_render.py`

- [ ] **Step 1: Add failing DXF clean-image and PSD visibility tests**

Extend `test_layered_render`:

```python
complete = np.array(Image.open(io.BytesIO(result["complete_jpg"])).convert("RGB"))
assert result["visible_layer_order"] == [
    "seam", "trim", "frame", "panel", "glass", "hardware", "lighting"
]
assert result["output_quality"] == 95

cad_outline = next((layer for layer in psd if layer.name == "04_CAD轮廓"), None)
info = next((layer for layer in psd if layer.name == "01_订货单信息"), None)
assert cad_outline is not None and not cad_outline.visible
assert info is not None and not info.visible
```

Add a provider normalization assertion to `test_ai_material_and_fallback` by returning an 800x600 image for a tall target and checking that the material pixels are not stretched and every emitted layer has the exact canvas size.

- [ ] **Step 2: Run DXF tests and verify failure**

Run:

```powershell
python -m pytest backend/test_layered_render.py -q
```

Expected: visibility, quality, clean composition, or normalization assertions fail.

- [ ] **Step 3: Add optional glass as a first-class DXF role**

Extend the category and manifest maps without making glass mandatory:

```python
# layered_render.py
CATEGORY_BY_LAYER = {
    **CATEGORY_BY_LAYER,
    "A-DOOR-GLASS": "glass",
}
PALETTE["glass"] = (185, 215, 225)

# dxf_geometry.py
role_categories = {
    "panel": "panel",
    "frame": "frame",
    "trim": "trim",
    "glass": "glass",
    "hardware": "accessory",
}
```

Include `glass` in front/back splitting, geometry masks, role prompts, face groups, layer arrays, and output bounding boxes. In validation, keep only panel and frame required; glass is optional but must have a closed contour when present. Add `A-DOOR-GLASS` to `_KNOWN_STRUCTURAL_LAYERS`.

- [ ] **Step 4: Use aspect-preserving AI normalization**

Replace the direct resize in `_apply_ai_material`:

```python
from .image_geometry import normalize_rgb_cover

result = Image.open(io.BytesIO(data)).convert("RGB")
return normalize_rgb_cover(np.array(result, dtype=np.uint8), (flat_rgb.shape[1], flat_rgb.shape[0]))
```

- [ ] **Step 5: Build DXF output from clean layers only**

Create `glass_layer` from `part_layer("glass", prims("glass"))`; when no glass geometry exists it naturally remains transparent. Build the normal result with this order:

```python
visible_layers = {
    "seam": seam_rgba(build_structural_seam(geometry_role_masks, seam_width)),
    "trim": part_layer("trim", prims("trim")),
    "frame": part_layer("frame", prims("frame")),
    "panel": part_layer("panel", prims("panel")),
    "glass": glass_layer,
    "hardware": part_layer("accessory", prims("accessory")),
    "lighting": _build_shadow(canvas, prims("panel") + prims("frame") + prims("trim")),
}
validate_layer_canvases(visible_layers, (canvas.width, canvas.height))
complete = _composite([white_bg] + [visible_layers[name] for name in VISIBLE_LAYER_ORDER])
```

Do not include `outline_arr`, `text_arr`, or `dim_arr` in `complete`, `front_jpg`, `back_jpg`, or normal component recomposition. Encode all final JPEGs through `encode_jpeg` at quality 95.

- [ ] **Step 6: Keep CAD information in PSD but hide it by default**

Use:

```python
info_group = PsdNode("01_订货单信息", children=[...], visible=False)
cad_outline = PsdNode("04_CAD轮廓", _to_pil(outline_arr), visible=False)
raw_cad = PsdNode("06_原始CAD底图", _to_pil(raw_cad), visible=False)
```

Reorder the visible face-group children so panel is below glass/hardware and shadow/highlight is highest in the composed result. Preserve existing layer names for compatibility.

- [ ] **Step 7: Run DXF tests**

Run:

```powershell
python -m pytest backend/test_layered_render.py -q
```

Expected: all DXF, geometry, AI material, and PSD tests pass.

- [ ] **Step 8: Commit DXF composition changes**

```powershell
git add backend/rendering/layered_render.py backend/rendering/dxf_geometry.py backend/test_layered_render.py
git commit -m "fix: clean and align dxf render composites"
```

### Task 4: Mode defaults, clean prompts, and safe component recomposition

**Files:**
- Modify: `backend/rendering/service.py:226-250,290-300,319-385,430-490,594-628`
- Modify: `backend/test_render_background_task.py`
- Modify: `backend/test_render_precise_mode.py`

- [ ] **Step 1: Add failing mode-default tests**

Add focused tests:

```python
@pytest.mark.parametrize(
    ("mode", "requested", "expected"),
    [
        ("quick", "", "2k"),
        ("quick", "original", "2k"),
        ("precise", "", "4k"),
        ("precise", "original", "4k"),
        ("precise", "2k", "2k"),
    ],
)
def test_resolve_render_size(mode, requested, expected):
    assert render_service._resolve_render_size(mode, requested) == expected


def test_clean_product_prompt_removes_visible_drafting_artifacts():
    prompt = render_service._effective_prompt("铜色门", "quick")
    assert "不显示线稿" in prompt
    assert "不显示尺寸线" in prompt
    assert "真实产品效果图" in prompt
```

Add a recomposition test that stores an `outline` layer and asserts the output ignores it while hardware wins an overlap pixel.

- [ ] **Step 2: Run service tests and verify failure**

Run:

```powershell
python -m pytest backend/test_render_background_task.py backend/test_render_precise_mode.py -q
```

Expected: helper functions are missing and recomposition still includes `outline`.

- [ ] **Step 3: Implement mode-aware resolution and prompt helpers**

Add:

```python
def _resolve_render_size(render_mode: str, requested: str | None) -> str:
    value = str(requested or "").lower()
    if value in {"", "original", "auto"}:
        return "4k" if render_mode == "precise" else "2k"
    return value


def _effective_prompt(prompt: str, render_mode: str) -> str:
    policy = (
        "输出清晰的真实门类产品效果图；严格保持原门体比例和部件位置；"
        "最终图片不显示线稿、尺寸线、文字、标注箭头或辅助轮廓；"
        "玻璃和五金位于门扇表面上方，接缝仅表现为真实窄黑缝。"
    )
    return f"{prompt.strip()}\n{policy}" if prompt.strip() else policy
```

Use resolved size and effective prompt consistently in both the stored task and `RenderProviderRequest`. Update `_target_long_edge` so `2k` maps to 2048 and `4k` maps to 4096.

- [ ] **Step 4: Make component recomposition strict and clean**

Change `_compose_component_layers` to:

```python
ordered = ("seam", "trim", "frame", "panel", "glass", "hardware", "lighting")
```

Reject mismatched component canvas sizes instead of resizing them. Encode through `encode_jpeg` at quality 95. Keep a saved `outline` layer for compatibility if it exists, but never include it in an ordinary image.

- [ ] **Step 5: Run service and precise tests**

Run:

```powershell
python -m pytest backend/test_render_background_task.py backend/test_render_precise_mode.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit service behavior**

```powershell
git add backend/rendering/service.py backend/test_render_background_task.py backend/test_render_precise_mode.py
git commit -m "fix: apply mode render defaults and clean recomposition"
```

### Task 5: Frontend mode-aware resolution

**Files:**
- Modify: `frontend/src/app/render/page.tsx:39,139,339-418,1048-1061`

- [ ] **Step 1: Change the selection state to automatic mode**

Use:

```tsx
const [size, setSize] = useState("auto");

function resolveRenderSize(renderMode: "quick" | "precise", selectedSize: string) {
  if (selectedSize === "auto") return renderMode === "precise" ? "4k" : "2k";
  return selectedSize;
}
```

Inside `submitTask`, send:

```tsx
const effectiveSize = resolveRenderSize(renderMode, size);
// request payload
size: effectiveSize,
```

- [ ] **Step 2: Update the size selector and mode buttons**

Replace the current “原比例” default with:

```tsx
<Select
  label="输出清晰度"
  value={size}
  onChange={setSize}
  options={[
    ["auto", "自动（快速 2K / 精准 4K）"],
    ["1k", "1K"],
    ["2k", "2K"],
    ["4k", "4K"],
  ]}
/>
```

Show the resolved size in each button label or adjacent status text without adding a new card:

```tsx
快速 AI 生成 · {resolveRenderSize("quick", size).toUpperCase()}
精准分区生成 · {resolveRenderSize("precise", size).toUpperCase()}
```

- [ ] **Step 3: Strengthen the default prompt**

Set `DEFAULT_PROMPT` to request a clean final product rendering and explicitly exclude visible CAD line art, dimensions, text, and arrows. Keep structure and component-position constraints.

- [ ] **Step 4: Run the frontend production build**

Run:

```powershell
npm run build
```

Working directory: `frontend`

Expected: Next.js production build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit frontend controls**

```powershell
git add frontend/src/app/render/page.tsx
git commit -m "feat: add mode-aware render resolution defaults"
```

### Task 6: Full regression and visual verification

**Files:**
- Modify only if a test reveals a defect in the files listed above.

- [ ] **Step 1: Run all targeted backend tests**

Run:

```powershell
python -m pytest backend/test_render_image_geometry.py backend/test_render_precise_mode.py backend/test_layered_render.py backend/test_render_background_task.py backend/test_render_provider_urls.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 2: Run frontend build again after final backend integration**

Run from `frontend`:

```powershell
npm run build
```

Expected: build succeeds.

- [ ] **Step 3: Generate fixed DXF regression artifacts**

Use the existing single-door, double-door/A1022, arched-door, and header/trim fixtures. For each front and back result, assert or inspect:

- actual output long edge is 4096 in automatic precise mode;
- trim, frame, and panel share the geometry manifest transform ID;
- glass and hardware remain visible over the panel;
- black appears only at structural joins;
- no CAD text, dimension, arrow, or full outline is visible;
- regenerated hardware stays at the same pixel coordinates.

- [ ] **Step 4: Verify quick mode through the configured provider**

Submit one simple drawing in automatic quick mode. Confirm the stored task size is `2k`, the provider prompt requests a clean final product image, and the returned original can be downloaded independently of the thumbnail.

- [ ] **Step 5: Check the final staged diff**

Run:

```powershell
git status --short
git diff --check
```

Expected: only intended render code, tests, frontend control, and plan/spec files are changed; `git diff --check` has no output.

- [ ] **Step 6: Commit any final regression-only adjustment**

Only when Step 1-4 required a correction:

```powershell
git add backend/rendering backend/test_render_image_geometry.py backend/test_render_precise_mode.py backend/test_layered_render.py backend/test_render_background_task.py frontend/src/app/render/page.tsx
git commit -m "test: verify clean aligned render pipeline"
```

- [ ] **Step 7: Push the completed branch**

```powershell
git push origin feat/semicircle-handles-and-quote-form-improvements
```
