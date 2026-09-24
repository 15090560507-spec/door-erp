# Render History And Precise Canvas Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore every available rendering input when a history task is opened and make DXF precise rendering generate one selected door face on a shared, structure-bounded canvas.

**Architecture:** The frontend will hydrate its editor state from a typed `RenderTask` snapshot, converting persisted render-file URLs back into upload-compatible `File` objects only when needed. The backend will add a selected-face rendering path that derives one authoritative crop from panel/frame/trim/glass geometry, clips accessory outliers to that envelope, and applies every material layer on the same cropped canvas.

**Tech Stack:** Next.js 16, React 19, TypeScript, FastAPI, Python, ezdxf, NumPy, Pillow, OpenCV, pytest.

---

### Task 1: Type And Restore Rendering History Inputs

**Files:**
- Modify: `frontend/src/lib/renderApi.ts`
- Create: `frontend/src/lib/renderHistory.ts`
- Modify: `frontend/src/app/render/page.tsx`

- [ ] **Step 1: Add explicit persisted-file and history snapshot types**

Define `RenderTaskFile` with `role`, `url`, `filePath`, `originalName`, `mimeType`, `targetRole`, and `category`; change `RenderTask.files` to `RenderTaskFile[]`; add optional file entries to reference bindings.

- [ ] **Step 2: Add pure history-to-editor mapping**

Create a helper with this contract:

```ts
export interface RestoredRenderHistory {
  configId: string;
  prompt: string;
  size: string;
  sourceType: RenderTask["sourceType"];
  sourceSide: RenderTask["sourceSide"];
  sourceTaskId: string;
  lineArtFile?: RenderTaskFile;
  referenceGroups: Array<{
    role: RenderReferenceRole;
    assetIds: string[];
    persistedFiles: RenderTaskFile[];
  }>;
  segmentation: RenderSegmentation | null;
}

export function restoreRenderHistory(task: RenderTask): RestoredRenderHistory;
```

The helper must map every role, deduplicate asset IDs, prefer the `line_art` task file, and preserve confirmed segmentation.

- [ ] **Step 3: Add authenticated persisted-file conversion**

Add `renderFileToFile(file)` in `renderApi.ts`, using the existing Axios instance and the same `/api/` path normalization as `lineArtViewToFile`.

- [ ] **Step 4: Hydrate the render page from history**

Replace both history `setActiveTask(task)` handlers with `void restoreHistoryTask(task)`. The handler must set the active task immediately, then restore model, prompt, size, source, side, drawing task, line art, segmentation, library asset IDs, and uploaded reference files. For drawing-task history, call `extractTaskLineArt(sourceTaskId)` so both face previews return. Missing legacy files must produce a message without hiding the result.

- [ ] **Step 5: Verify TypeScript and production compilation**

Run: `npm run build`

Expected: Next.js compile, TypeScript validation, and static generation all succeed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/renderApi.ts frontend/src/lib/renderHistory.ts frontend/src/app/render/page.tsx
git commit -m "fix: restore render history inputs"
```

### Task 2: Create A Structure-Bounded Selected-Face Canvas

**Files:**
- Modify: `backend/rendering/layered_render.py`
- Modify: `backend/test_layered_render.py`

- [ ] **Step 1: Write failing selected-face and accessory-outlier tests**

Add tests that monkeypatch `_apply_ai_material`, capture each submitted image shape, and render a two-face DXF with an accessory helper line far outside the door. Assert:

```python
assert result["selected_side"] == "front"
assert result["canvas_size"] == result["front_size"]
assert all(shape == provider_shapes[0] for shape in provider_shapes)
assert result["canvas_size"][0] < result["canvas_size"][1]
assert result["canvas_size"][0] / result["canvas_size"][1] > 0.25
```

The outlier must not create a mostly blank wide image.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest backend/test_layered_render.py -k "selected_face or accessory_outlier" -q`

Expected: FAIL because `render_layered_dxf` has no selected-face canvas path.

- [ ] **Step 3: Implement structural face bounds**

Add helpers that:

```python
STRUCTURAL_CATEGORIES = ("panel", "frame", "trim", "glass")

def _expanded_bbox(bbox, ratio=0.03):
    min_x, max_x, min_y, max_y = bbox
    margin = max(max_x - min_x, max_y - min_y) * ratio
    return min_x - margin, max_x + margin, min_y - margin, max_y + margin

def _primitive_intersects_bbox(primitive, bbox):
    min_x, max_x, min_y, max_y = _bbox(primitive.points)
    left, right, bottom, top = bbox
    return max_x >= left and min_x <= right and max_y >= bottom and min_y <= top

def _selected_face_categories(front_cat, back_cat, side):
    source = front_cat if side == "front" else back_cat
    structural = [primitive for name in STRUCTURAL_CATEGORIES for primitive in source[name]]
    structural_bbox = _category_bbox(structural)
    if structural_bbox is None:
        raise ValueError(f"{side} 视图缺少门扇、门框、门套或玻璃结构")
    clip_bbox = _expanded_bbox(structural_bbox)
    return {
        **source,
        "accessory": [item for item in source["accessory"] if _primitive_intersects_bbox(item, clip_bbox)],
    }, clip_bbox
```

The authoritative bbox comes only from structural categories. Keep accessories only when their primitive bbox intersects the expanded structural bbox.

- [ ] **Step 4: Render the selected face before AI calls**

Extend the function contract without breaking legacy callers:

```python
def render_layered_dxf(
    dxf_text: str,
    dpi: int = 300,
    target_long_edge: int = 2600,
    ai_config: Optional[dict] = None,
    references: Optional[list[dict]] = None,
    reference_bindings: Optional[dict[str, list[dict]]] = None,
    include_psd: bool = True,
    selected_side: Optional[str] = None,
) -> dict:
```

When `selected_side` is `front` or `back`, create a face-local canvas from the filtered categories. Build the flat input, role masks, seams, lighting, AI materials, final JPEG, and encoded layers entirely on that canvas. Do not render or resize the opposite face in this path.

- [ ] **Step 5: Run focused and existing layered-render tests**

Run: `python -m pytest backend/test_layered_render.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/rendering/layered_render.py backend/test_layered_render.py
git commit -m "fix: render precise dxf on selected face canvas"
```

### Task 3: Wire Precise Tasks To The Selected-Face Renderer

**Files:**
- Modify: `backend/rendering/service.py`
- Modify: `backend/test_render_background_task.py`

- [ ] **Step 1: Write a failing service wiring test**

Monkeypatch `render_layered_dxf` and assert `execute_precise_render_task` passes the task's side:

```python
assert captured["selected_side"] == "back"
```

- [ ] **Step 2: Run the test and verify failure**

Run: `python -m pytest backend/test_render_background_task.py -k selected_side -q`

Expected: FAIL because the service does not pass `selected_side`.

- [ ] **Step 3: Pass the selected side and consume face-local outputs**

Call:

```python
result = render_layered_dxf(
    _decode_dxf(dxf_bytes),
    target_long_edge=_target_long_edge(task.get("size", "original")),
    ai_config=provider_request.config,
    reference_bindings=references,
    include_psd=False,
    selected_side=side,
)
final_bytes = result["selected_jpg"]
layer_pngs = result["selected_layer_pngs"]
```

Reject a missing selected-face payload with a clear error.

- [ ] **Step 4: Run service rendering tests**

Run: `python -m pytest backend/test_render_background_task.py backend/test_render_precise_mode.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/rendering/service.py backend/test_render_background_task.py
git commit -m "fix: use selected face for precise render tasks"
```

### Task 4: Regression, Visual Inspection, And Delivery

**Files:**
- Modify only if verification exposes a defect in the files above.

- [ ] **Step 1: Run focused backend rendering suites**

Run: `python -m pytest backend/test_layered_render.py backend/test_render_background_task.py backend/test_render_precise_mode.py -q`

Expected: all focused tests pass.

- [ ] **Step 2: Run the CAD baseline**

Run: `python backend/test_cad_new_options.py`

Expected: no new failures beyond the established nine unrelated failures.

- [ ] **Step 3: Build the frontend**

Run: `npm run build` from `frontend`.

Expected: build succeeds.

- [ ] **Step 4: Inspect a generated selected-face sample**

Generate one front and one back precise sample with a fake deterministic material provider. Confirm the door fills the canvas, all role layers share dimensions, seams remain black, and the line drawing is absent from the final JPEG.

- [ ] **Step 5: Push the verified commits**

```bash
git push origin HEAD:feat/semicircle-handles-and-quote-form-improvements
```

Expected: the remote feature branch advances without force push.
