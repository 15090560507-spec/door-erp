# Panel Line Styles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make B2/B4 internal spacing effective, add an equidistant vertical-line pattern, and add configurable four-side and three-side diagonal panel styles that match the approved geometry.

**Architecture:** Keep the existing form, Pydantic request, CAD parameter map, and drawing pipeline. Add explicit per-panel-face geometry fields instead of reusing H-layout offsets, then implement small drawing helpers inside the current panel drawing section so lock-side mirroring continues to flow through `panel_lock_edge`.

**Tech Stack:** Next.js 16, React 19, TypeScript, FastAPI/Pydantic, Python, ezdxf.

---

## File Structure

- `frontend/src/lib/types.ts`: public form data shape, option lists, and backward-compatible defaults.
- `frontend/src/components/DoorForm.tsx`: style-specific controls and B2/B4 labels.
- `backend/models.py`: API defaults for all four panel faces.
- `backend/main.py`: request-to-template and request-to-drawing parameter transport.
- `backend/drawing.py`: B2/B4 pattern geometry and whole-panel diagonal geometry.
- `backend/test_cad_new_options.py`: parameter-chain and DXF geometry regression coverage.

### Task 1: Add the explicit panel-style data contract

**Files:**
- Modify: `backend/test_cad_new_options.py`
- Modify: `backend/models.py`
- Modify: `backend/main.py`
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Write the failing parameter-chain test**

Add a test near `test_door_panel_style_lines`:

```python
def test_diagonal_panel_style_parameters_pass_to_drawing():
    req = CADRequest(
        door_panel_style="四边对角线条",
        panel_border_inset=36,
        back_door_panel_style="三边对角线条",
        back_panel_three_side_lock_offset=145,
        back_panel_three_side_inset=58,
        child_door_panel_style="三边对角线条",
        child_panel_three_side_lock_offset=138,
        child_panel_three_side_inset=52,
    )
    _info, _checks, params = build_cad_params(req)
    check("front border inset passes to drawing", params["panel_border_inset"] == 36, params)
    check("back lock offset passes to drawing", params["back_panel_three_side_lock_offset"] == 145, params)
    check("back three-side inset passes to drawing", params["back_panel_three_side_inset"] == 58, params)
    check("child lock offset passes to drawing", params["child_panel_three_side_lock_offset"] == 138, params)
    check("child three-side inset passes to drawing", params["child_panel_three_side_inset"] == 52, params)
```

Call it from the script's existing test runner list.

- [ ] **Step 2: Run the test and verify the new request fields fail**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: `CADRequest` rejects or ignores at least one new field, or the new keys are absent from `draw_params`.

- [ ] **Step 3: Add backend fields for every panel face**

Add these fields to `CADRequest`, with the same three fields repeated under `back_panel_`, `child_panel_`, and `child_back_panel_` prefixes:

```python
panel_border_inset: int = 30
panel_three_side_lock_offset: int = 150
panel_three_side_inset: int = 60
```

In both maps in `build_cad_params`, transport every field explicitly. The drawing map uses lower-case names:

```python
"panel_border_inset": req.panel_border_inset,
"panel_three_side_lock_offset": req.panel_three_side_lock_offset,
"panel_three_side_inset": req.panel_three_side_inset,
```

The information map uses the existing upper-case convention:

```python
"PANEL_BORDER_INSET": req.panel_border_inset,
"PANEL_THREE_SIDE_LOCK_OFFSET": req.panel_three_side_lock_offset,
"PANEL_THREE_SIDE_INSET": req.panel_three_side_inset,
```

- [ ] **Step 4: Add matching TypeScript fields and defaults**

Extend `DoorFormData` for all four panel faces and add defaults:

```typescript
panel_border_inset: 30,
panel_three_side_lock_offset: 150,
panel_three_side_inset: 60,
```

Use the same values for the `back_`, `child_`, and `child_back_` forms so old saved records receive stable defaults when merged with `DEFAULT_FORM_DATA`.

- [ ] **Step 5: Run the parameter-chain test**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: the new parameter-chain checks pass and existing checks remain green.

- [ ] **Step 6: Commit the data contract**

```bash
git add backend/models.py backend/main.py backend/test_cad_new_options.py frontend/src/lib/types.ts
git commit -m "feat: add panel diagonal style parameters"
```

### Task 2: Make B2/B4 spacing effective and add vertical lines

**Files:**
- Modify: `backend/test_cad_new_options.py`
- Modify: `backend/drawing.py`
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Write failing vertical-pattern geometry checks**

Add a helper that returns long vertical `A-DOOR-PANEL` lines, then compare two requests:

```python
def _panel_vertical_xs(doc):
    return sorted({
        round(float(entity.dxf.start.x), 3)
        for entity in doc.modelspace().query("LINE")
        if entity.dxf.layer == "A-DOOR-PANEL"
        and abs(float(entity.dxf.start.x) - float(entity.dxf.end.x)) < 0.01
        and abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) > 150
    })

def test_panel_vertical_pattern_uses_internal_spacing():
    def render(spacing):
        req = CADRequest(
            door_panel_style="H型布局",
            panel_b2_glass_style="竖条",
            glass_line_inset=20,
            glass_line_spacing=40 if spacing == 40 else 80,
            fingerprint_lock="无",
            sel_hys="暗合页",
        )
        info, checks, params = build_cad_params(req)
        msg, buffer = run_integrated_system(info, checks, params)
        check(f"vertical pattern {spacing} generates CAD", buffer is not None, msg)
        return ezdxf.read(io.StringIO(buffer.getvalue()))

    xs_40 = _panel_vertical_xs(render(40))
    xs_80 = _panel_vertical_xs(render(80))
    check("smaller spacing creates more vertical lines", len(xs_40) > len(xs_80), (xs_40, xs_80))
```

Add a second comparison for `双边框`: render spacing `20` and `40`, extract the paired border centers, and assert the corresponding center offset changes by `20mm`. This guards the existing control as well as the new `竖条` option.

- [ ] **Step 2: Run the test and verify `竖条` produces no internal lines**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: `smaller spacing creates more vertical lines` fails.

- [ ] **Step 3: Add the vertical pattern option and drawing rule**

Append `竖条` to `GLASS_LINE_STYLES`. In `draw_glass_template_rect`, after the outer frame is drawn and spacing is validated, add:

```python
if style == "竖条":
    count_each_side = int((inner_width / 2) // spacing)
    center_x = (ix1 + ix2) / 2
    for offset_index in range(-count_each_side, count_each_side + 1):
        x = center_x + offset_index * spacing
        if ix1 < x < ix2:
            line(x, iy1, x, iy2)
    return
```

Change spacing normalization so positive user input is not replaced by the old visual minimum:

```python
requested_spacing = float(spacing if spacing is not None else p.get("glass_line_spacing", 20))
if requested_spacing <= 0:
    raise ValueError("图案内部线距必须大于0mm")
spacing = min(requested_spacing, inner_width / 2, inner_height / 2)
```

Keep six-grid and eight-grid fixed by count; they do not call the spacing-driven branch.

Replace the existing hidden minimums in the spacing-driven styles. `双边框` must use `spacing` as its requested border-center offset, limited only by available region size and the fixed `15mm` band width. `四角回纹` must use the same direct spacing value for `frame_gap`; it may raise a clear validation error when the requested distance cannot contain the `15mm` band instead of silently substituting `50mm`.

- [ ] **Step 4: Run the geometry checks**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: both vertical-pattern render checks pass, and existing glass-template tests remain green.

- [ ] **Step 5: Commit B2/B4 drawing behavior**

```bash
git add backend/drawing.py backend/test_cad_new_options.py frontend/src/lib/types.ts
git commit -m "feat: add spacing-aware panel vertical lines"
```

### Task 3: Draw four-side and approved three-side diagonal panels

**Files:**
- Modify: `backend/test_cad_new_options.py`
- Modify: `backend/drawing.py`

- [ ] **Step 1: Write failing DXF geometry tests**

Create request-driven checks for both new styles. Normalize line endpoints before comparing them:

```python
def _panel_segments(doc):
    return {
        tuple(sorted((
            (round(float(line.dxf.start.x), 3), round(float(line.dxf.start.y), 3)),
            (round(float(line.dxf.end.x), 3), round(float(line.dxf.end.y), 3)),
        )))
        for line in doc.modelspace().query("LINE")
        if line.dxf.layer == "A-DOOR-PANEL"
    }
```

For `四边对角线条`, assert one inset rectangle and four corner connectors are added at `30mm`. For `三边对角线条`, assert:

- one lock-side line spans the full panel height;
- the upper, hinge, and lower inner lines use `60mm`;
- exactly two diagonal connectors exist, both at the hinge side;
- right-open and left-open requests mirror the x coordinates.

Use `panel_positions` derived by the generated drawing rather than hard-coding the outer frame width; filter coordinates to the front-view panel region before assertions.

- [ ] **Step 2: Run the geometry tests and verify they fail**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: no new-style geometry is present.

- [ ] **Step 3: Include new fields in `panel_settings`**

Add:

```python
"border_inset": float(p.get(f"{prefix}border_inset", p.get("panel_border_inset", 30)) or 0),
"three_side_lock_offset": float(p.get(
    f"{prefix}three_side_lock_offset",
    p.get("panel_three_side_lock_offset", 150),
) or 0),
"three_side_inset": float(p.get(
    f"{prefix}three_side_inset",
    p.get("panel_three_side_inset", 60),
) or 0),
```

- [ ] **Step 4: Implement validated panel geometry helpers**

Inside the panel drawing section add focused helpers:

```python
def validate_inset(value: float, panel_width: float, panel_height: float, label: str) -> float:
    if value <= 0:
        raise ValueError(f"{label}必须大于0mm")
    if value * 2 >= min(panel_width, panel_height):
        raise ValueError(f"{label}{value:g}mm超出门板可用尺寸")
    return value

def draw_four_side_diagonal(px1, px2, y1, y2, inset, fill_name):
    inset = validate_inset(inset, px2 - px1, y2 - y1, "四边外边距")
    ix1, ix2 = px1 + inset, px2 - inset
    iy1, iy2 = y1 + inset, y2 - inset
    draw_fill_area(ix1, iy1, ix2, iy2, fill_name)
    draw_panel_line(ix1, iy1, ix2, iy1)
    draw_panel_line(ix2, iy1, ix2, iy2)
    draw_panel_line(ix2, iy2, ix1, iy2)
    draw_panel_line(ix1, iy2, ix1, iy1)
    for start, end in (((px1, y1), (ix1, iy1)), ((px2, y1), (ix2, iy1)),
                       ((px2, y2), (ix2, iy2)), ((px1, y2), (ix1, iy2))):
        draw_panel_line(*start, *end)
```

The three-side helper must calculate `lock_x = lock_edge + direction * lock_offset` and `hinge_x = hinge_edge - direction * inset`, draw the lock line from `panel_y_bot` to `panel_y_top`, draw the three inner segments, and connect only `(hinge_edge, panel_y_bot/top)` to `(hinge_x, inner_bottom/top)`. Validate `lock_offset + inset < panel_width` and `inset * 2 < panel_height` before drawing.

- [ ] **Step 5: Dispatch the two styles before legacy layout handling**

In the per-panel loop, after computing lock/hinge direction and before `大板布局`:

```python
if panel_style == "四边对角线条":
    draw_four_side_diagonal(px1, px2, panel_y_bot, panel_y_top,
                            float(settings["border_inset"]), str(settings.get("fill_a", "")))
    continue
if panel_style == "三边对角线条":
    draw_three_side_diagonal(lock_edge, hinge_edge, direction, panel_y_bot, panel_y_top,
                             float(settings["three_side_lock_offset"]),
                             float(settings["three_side_inset"]), str(settings.get("fill_a", "")))
    continue
```

- [ ] **Step 6: Run geometry and regression tests**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: new four-side, three-side, mirror, fill, and validation checks pass with all existing checks green.

- [ ] **Step 7: Commit CAD geometry**

```bash
git add backend/drawing.py backend/test_cad_new_options.py
git commit -m "feat: draw diagonal panel line styles"
```

### Task 4: Expose style-specific controls and finish verification

**Files:**
- Modify: `frontend/src/components/DoorForm.tsx`
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Add the two style names and style predicates**

Extend `DOOR_PANEL_STYLES`:

```typescript
export const DOOR_PANEL_STYLES = [
  "无造型", "大板布局", "两列式布局", "三列式布局", "两横式", "三横式",
  "H型布局", "H+型布局", "圆盘造型", "四边对角线条", "三边对角线条",
];
```

Add predicates near the existing `uses*Panel` helpers:

```typescript
const usesFourSideDiagonal = (style: string) => style === "四边对角线条";
const usesThreeSideDiagonal = (style: string) => style === "三边对角线条";
```

- [ ] **Step 2: Pass dedicated keys into `renderPanelControls`**

Add `borderInsetKey`, `threeSideLockOffsetKey`, and `threeSideInsetKey` to its typed arguments. Supply front, back, child, and child-back keys at every call site.

Render only the relevant inputs:

```tsx
{usesFourSideDiagonal(style) && (
  <Input label={`${title}外边距(mm)`} value={(data[borderInsetKey] as number) ?? 30}
    type="number" onChange={(v) => setField(borderInsetKey, Number(v))} />
)}
{usesThreeSideDiagonal(style) && (
  <>
    <Input label={`${title}锁边偏移(mm)`} value={(data[threeSideLockOffsetKey] as number) ?? 150}
      type="number" onChange={(v) => setField(threeSideLockOffsetKey, Number(v))} />
    <Input label={`${title}上下及合页边宽度(mm)`} value={(data[threeSideInsetKey] as number) ?? 60}
      type="number" onChange={(v) => setField(threeSideInsetKey, Number(v))} />
  </>
)}
```

For both new styles, show one `内部填充` select bound to that panel face's existing `fillAKey`.

- [ ] **Step 3: Rename B2/B4 controls and explain fixed-grid behavior**

Change labels to `${title}B2` and `${title}B4`. When the selected option is `六格线条` or `八格线条`, show a small neutral note stating `固定格数按区域均分，不使用图案内部线距` rather than hiding or silently ignoring the input.

- [ ] **Step 4: Run frontend and backend verification**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: all custom CAD checks pass.

Run:

```bash
cd frontend
npm run build
```

Expected: Next.js production build completes without TypeScript or rendering errors.

- [ ] **Step 5: Inspect generated DXF examples**

Generate one right-opening and one left-opening `三边对角线条` sample plus one `四边对角线条` sample. Confirm in the DXF entity coordinates that:

- the lock-side line mirrors with opening direction;
- only the hinge-side corners contain diagonals;
- default offsets are `150mm`, `60mm`, and `30mm`;
- the internal hatch is bounded by the inner region.

- [ ] **Step 6: Commit the UI and final verification changes**

```bash
git add frontend/src/components/DoorForm.tsx frontend/src/lib/types.ts backend/test_cad_new_options.py
git commit -m "feat: expose panel diagonal style controls"
```

### Task 5: Integrate and publish

**Files:**
- Review: all modified files

- [ ] **Step 1: Review the complete diff**

Run:

```bash
git diff feat/semicircle-handles-and-quote-form-improvements...HEAD --check
git status --short
```

Expected: no whitespace errors and only intended files changed.

- [ ] **Step 2: Push the verified commits to the feature branch**

```bash
git push origin HEAD:feat/semicircle-handles-and-quote-form-improvements
```

Expected: remote feature branch advances without force push.

- [ ] **Step 3: Fast-forward the original checkout without touching unrelated files**

Run from the original checkout:

```bash
git merge --ff-only codex/panel-line-styles-20260924
```

Expected: tracked source files fast-forward while existing unrelated untracked files and `data/users_database.json` remain untouched.
