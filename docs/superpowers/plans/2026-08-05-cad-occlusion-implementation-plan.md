# CAD Occlusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in CAD occlusion layer that hides covered panel/frame lines in display and print while preserving every original editable entity.

**Architecture:** Add one backward-compatible request field and a focused `OcclusionManager` that owns WIPEOUT creation and DXF redraw ordering. Existing door geometry remains untouched; drawing calls explicitly register only physical frame and trim footprints as masks, while hardware and annotations are sorted above all structural masks.

**Tech Stack:** FastAPI, Pydantic 2, ezdxf 1.1+, Next.js 16, React 19, TypeScript, existing script-style Python regression tests.

---

## File Structure

- Create `backend/cad_occlusion.py`: mask creation, group registration, WIPEOUT variables, and redraw-order application.
- Modify `backend/models.py`: add the backward-compatible request field.
- Modify `backend/main.py`: pass the request field into drawing parameters.
- Modify `backend/drawing.py`: register physical component footprints and hardware/annotation ordering without changing dimension calculations.
- Modify `backend/cad_preview.py`: honor redraw order and render WIPEOUT regions in the SVG preview.
- Modify `backend/test_cad_new_options.py`: add request-flow and full drawing regression coverage.
- Modify `frontend/src/lib/types.ts`: add the form field and default value.
- Modify `frontend/src/components/DoorForm.tsx`: add the final default-off control.

### Task 1: Add The Backward-Compatible Form Contract

**Files:**
- Modify: `backend/models.py:10-145`
- Modify: `backend/main.py:450-540`
- Modify: `frontend/src/lib/types.ts:20-150`
- Modify: `frontend/src/lib/types.ts:220-255`
- Modify: `frontend/src/components/DoorForm.tsx:655-675`
- Test: `backend/test_cad_new_options.py`

- [ ] **Step 1: Write the failing request-flow test**

Add this test next to the other request/default tests:

```python
def test_occlusion_request_defaults_and_flow():
    default_req = CADRequest()
    check("occlusion defaults off", default_req.enable_occlusion is False, default_req.model_dump())

    enabled_req = CADRequest(enable_occlusion=True)
    _info, _checks, draw_params = build_cad_params(enabled_req)
    check("occlusion passes to drawing", draw_params["enable_occlusion"] is True, draw_params)
```

Call it from the test file's `__main__` block.

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: FAIL because `CADRequest` has no `enable_occlusion` field and `draw_params` has no matching key.

- [ ] **Step 3: Add the backend and frontend field**

Add to `CADRequest`:

```python
enable_occlusion: bool = False  # 门板/门框/门套层级遮挡，默认关闭
```

Add to `draw_params` in `build_cad_params`:

```python
"enable_occlusion": req.enable_occlusion,
```

Add to `DoorFormData`:

```ts
enable_occlusion: boolean;
```

Add to `DEFAULT_FORM_DATA`:

```ts
enable_occlusion: false,
```

At the end of the right form column, after the production notes card and before `{children}`, add:

```tsx
<Card title="遮挡关系">
  <Checkbox
    label="启用门板、门框、门套/门头门柱遮挡"
    checked={Boolean(data.enable_occlusion)}
    onChange={(value) => set("enable_occlusion", value)}
  />
</Card>
```

- [ ] **Step 4: Run the backend flow test and frontend checks**

Run:

```bash
python backend/test_cad_new_options.py
cd frontend && npm run lint && npm run build
```

Expected: existing CAD tests PASS; frontend lint and build complete without TypeScript errors.

- [ ] **Step 5: Commit the contract change**

```bash
git add backend/models.py backend/main.py backend/test_cad_new_options.py frontend/src/lib/types.ts frontend/src/components/DoorForm.tsx
git commit -m "Add optional CAD occlusion setting"
```

### Task 2: Build The Isolated Occlusion Manager

**Files:**
- Create: `backend/cad_occlusion.py`
- Test: `backend/test_cad_new_options.py`

- [ ] **Step 1: Write the failing manager test**

Add a focused test that uses an empty ezdxf document:

```python
from cad_occlusion import OcclusionManager


def test_occlusion_manager_creates_hidden_frame_and_order():
    doc = ezdxf.new("R2010")
    ms = doc.modelspace()
    manager = OcclusionManager(doc, ms, enabled=True)

    panel = ms.add_lwpolyline([(0, 0), (100, 0), (100, 200), (0, 200)], close=True,
                              dxfattribs={"layer": "A-DOOR-PANEL"})
    frame_mask = manager.add_mask([(0, 0), (10, 0), (10, 200), (0, 200)], "frame_mask")
    frame = ms.add_lwpolyline([(0, 0), (10, 0), (10, 200), (0, 200)], close=True,
                              dxfattribs={"layer": "A-DOOR-FRAME"})
    manager.register(panel, "panel")
    manager.register(frame, "frame")
    manager.apply()

    check("mask uses isolated layer", frame_mask.dxf.layer == "A-DOOR-OCCLUSION", frame_mask.dxfattribs())
    check("wipeout frame is hidden", doc.objects.get_wipeout_frame_setting() == 0, doc.objects.get_wipeout_frame_setting())
    redraw = dict(ms.get_redraw_order())
    check("panel draws before frame mask", int(redraw[panel.dxf.handle], 16) < int(redraw[frame_mask.dxf.handle], 16), redraw)
    check("frame mask draws before frame", int(redraw[frame_mask.dxf.handle], 16) < int(redraw[frame.dxf.handle], 16), redraw)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: FAIL with `ModuleNotFoundError: cad_occlusion`.

- [ ] **Step 3: Implement `OcclusionManager`**

Create `backend/cad_occlusion.py` with these concrete group values and methods:

```python
from __future__ import annotations

from collections import defaultdict
from typing import Iterable


SORT_HANDLES = {
    "panel": "10",
    "frame_mask": "20",
    "frame": "30",
    "trim_mask": "40",
    "trim": "50",
    "hardware_mask": "60",
    "hardware": "70",
    "annotation": "80",
}


class OcclusionManager:
    def __init__(self, doc, modelspace, enabled: bool):
        self.doc = doc
        self.ms = modelspace
        self.enabled = bool(enabled)
        self._groups: dict[str, list[str]] = defaultdict(list)

    def register(self, entity, group: str):
        if entity is not None and entity.is_alive and entity.dxf.handle:
            self._groups[group].append(entity.dxf.handle)
        return entity

    def add_mask(self, points: Iterable[tuple[float, float]], group: str):
        if not self.enabled:
            return None
        vertices = [(float(x), float(y)) for x, y in points]
        if len(vertices) < 3:
            return None
        wipeout = self.ms.add_wipeout(vertices)
        wipeout.dxf.layer = "A-DOOR-OCCLUSION"
        return self.register(wipeout, group)

    def apply(self):
        if not self.enabled:
            return
        self.doc.set_wipeout_variables(frame=0)
        redraw = {
            handle: SORT_HANDLES[group]
            for group, handles in self._groups.items()
            for handle in handles
        }
        self.ms.set_redraw_order(redraw)
```

- [ ] **Step 4: Run the manager test**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: the new manager assertions PASS.

- [ ] **Step 5: Commit the manager**

```bash
git add backend/cad_occlusion.py backend/test_cad_new_options.py
git commit -m "Add CAD occlusion manager"
```

### Task 3: Register Structural Footprints Without Changing Geometry

**Files:**
- Modify: `backend/drawing.py:226-460`
- Modify: `backend/drawing.py:461-1708`
- Modify: `backend/drawing.py:1825-1870`
- Test: `backend/test_cad_new_options.py`

- [ ] **Step 1: Write geometry-preservation tests**

Add helpers that generate the same request with the flag off and on, then compare every non-WIPEOUT entity by type, layer, and geometric DXF attributes:

```python
def build_doc(req: CADRequest):
    info, checks, draw_params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("CAD generation succeeds", buffer is not None, msg)
    return ezdxf.read(io.StringIO(buffer.getvalue()))


def stable_dxf_value(value):
    if isinstance(value, (list, tuple)):
        return tuple(stable_dxf_value(item) for item in value)
    if hasattr(value, "x") and hasattr(value, "y"):
        return tuple(float(item) for item in value)
    return value


def structural_signature(doc):
    signature = []
    for entity in doc.modelspace():
        if entity.dxftype() == "WIPEOUT":
            continue
        if entity.dxf.layer == "A-DOOR-OCCLUSION":
            continue
        attrs = entity.dxfattribs().copy()
        attrs.pop("handle", None)
        attrs.pop("owner", None)
        stable_attrs = tuple(sorted((name, stable_dxf_value(value)) for name, value in attrs.items()))
        signature.append((entity.dxftype(), entity.dxf.layer, stable_attrs))
    return signature


def test_occlusion_preserves_original_geometry():
    base = build_doc(CADRequest(enable_occlusion=False, sel_hys="暗合页", fingerprint_lock="无"))
    masked = build_doc(CADRequest(enable_occlusion=True, sel_hys="暗合页", fingerprint_lock="无"))
    check("occlusion preserves original entities", structural_signature(base) == structural_signature(masked), "geometry changed")
    base_wipeouts = [e for e in base.modelspace().query("WIPEOUT") if e.dxf.layer == "A-DOOR-OCCLUSION"]
    check("disabled occlusion adds nothing", len(base_wipeouts) == 0, len(base_wipeouts))
    wipeouts = [e for e in masked.modelspace().query("WIPEOUT") if e.dxf.layer == "A-DOOR-OCCLUSION"]
    check("occlusion adds structural masks", len(wipeouts) > 0, len(wipeouts))
```

Also assert that `enable_occlusion=False` does not create `A-DOOR-OCCLUSION` WIPEOUT entities.

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: FAIL because no structural masks are generated.

- [ ] **Step 3: Wire the manager into the drawer**

In `EzdxfDrawer.__init__`, accept `enable_occlusion=False`, initialize `OcclusionManager`, and keep existing methods backward compatible:

```python
self.occlusion = OcclusionManager(doc, ms, enable_occlusion)
```

Make `draw_poly`, `draw_bulged_poly`, `draw_line`, `draw_arc`, `draw_text`, and `insert_custom_block` return the created entity. Add these two focused helpers:

```python
def draw_occluding_poly(self, points, layer, group):
    if self.occlusion.enabled:
        mask_group = "frame_mask" if group == "frame" else "trim_mask"
        self.occlusion.add_mask(points, mask_group)
    return self.occlusion.register(self.draw_poly(points, layer), group)

def draw_occluding_arch_band(self, outer_points, inner_points, layer, group):
    polygon = list(outer_points) + list(reversed(inner_points))
    if self.occlusion.enabled:
        mask_group = "frame_mask" if group == "frame" else "trim_mask"
        self.occlusion.add_mask(polygon, mask_group)
    return polygon
```

Register ordinary panel/hatch entities as `panel`, frame entities as `frame`, trim entities as `trim`, existing `A-DOOR-MASK` WIPEOUTs as `hardware_mask`, hardware entities as `hardware`, and `YQ_DIM`/`A-DOOR-mark` entities as `annotation`.

When drawing arched bands, also register the existing editable ARC/LINE entities in the matching `frame` or `trim` group. The sampled polygon is a mask boundary only; it must not replace or duplicate the editable arc geometry.

- [ ] **Step 4: Mark only physical frame and trim footprints as occluders**

Replace physical closed frame and trim calls with `draw_occluding_poly(...)`. Do not mark glass openings, dimension helper geometry, panel region dividers, or annotation leaders as occluders.

For arched frame/trim bands, build exact polygons from the existing sampled inner and outer arcs:

```python
inner_points = arch_poly_points(inner_geom, inner_delta, segments=48)
outer_points = arch_poly_points(outer_geom, outer_delta, segments=48)
drawer.draw_occluding_arch_band(outer_points, inner_points, "A-DOOR-FRAME", "frame")
```

Continue drawing the existing true ARC entities for editable geometry; the sampled polygon is used only by WIPEOUT.

- [ ] **Step 5: Apply ordering after both views are complete**

Create the drawer with the request flag, add the new layer, draw both views, then finalize ordering:

```python
drawer = EzdxfDrawer(
    doc,
    ms,
    hinge_name,
    progress_callback,
    enable_occlusion=bool(draw_p.get("enable_occlusion", False)),
)
drawer.batch_add_layers({
    "A-DOOR-OCCLUSION": 7,
    # existing layers remain unchanged
})

draw_door_in_frame(drawer, "正面", draw_p, False, use_light, lw, lh)
draw_door_in_frame(drawer, "背面", draw_p, True, use_light, lw, lh)
drawer.occlusion.apply()
```

- [ ] **Step 6: Run geometry and round-trip tests**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: original geometry signatures match, structural masks exist only when enabled, and all existing CAD tests remain green.

- [ ] **Step 7: Commit structural masking**

```bash
git add backend/drawing.py backend/test_cad_new_options.py
git commit -m "Apply structural CAD occlusion masks"
```

### Task 4: Cover Portal And Arched Shapes

**Files:**
- Modify: `backend/drawing.py:610-910`
- Test: `backend/test_cad_new_options.py`

- [ ] **Step 1: Add portal and arch regression tests**

Add one portal request and one arched-door request with occlusion enabled:

```python
def test_occlusion_matches_portal_and_arch_shapes():
    portal_doc = build_doc(CADRequest(
        enable_occlusion=True,
        has_outer=False,
        has_outer_portal=True,
        outer_portal_pillar_width=160,
        outer_portal_header_height=220,
        sel_hys="暗合页",
        fingerprint_lock="无",
    ))
    portal_masks = [e for e in portal_doc.modelspace().query("WIPEOUT") if e.dxf.layer == "A-DOOR-OCCLUSION"]
    check("portal creates separate structural masks", len(portal_masks) >= 3, len(portal_masks))

    arch_doc = build_doc(CADRequest(
        enable_occlusion=True,
        is_arch_door=True,
        arch_spring_height=1800,
        dh=2400,
        has_outer=True,
        sel_hys="暗合页",
        fingerprint_lock="无",
    ))
    arch_masks = [e for e in arch_doc.modelspace().query("WIPEOUT") if e.dxf.layer == "A-DOOR-OCCLUSION"]
    vertex_counts = [len(e.boundary_path_wcs()) for e in arch_masks]
    check("arched masks follow sampled arcs", any(count > 12 for count in vertex_counts), vertex_counts)
```

- [ ] **Step 2: Run the tests and verify the arch assertion fails if only rectangles exist**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected before completion: portal or sampled-arc assertion FAILS.

- [ ] **Step 3: Complete physical footprint registration**

Ensure the following shapes produce separate masks:

- left frame, right frame, top/bottom/middle frame rails;
- outer trim left leg, right leg, and top band;
- portal left pillar, right pillar, and header as three masks;
- inner trim equivalents on the back view;
- arched top frame and arched trim band using sampled curved boundaries.

Do not mask the rectangular transom opening itself.

- [ ] **Step 4: Run the complete CAD regression**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: portal masks are separate, at least one arch mask has more than twelve boundary vertices, and all prior geometry tests PASS.

- [ ] **Step 5: Commit shape coverage**

```bash
git add backend/drawing.py backend/test_cad_new_options.py
git commit -m "Cover portal and arch CAD occlusion"
```

### Task 5: Make The SVG Preview Respect WIPEOUT And Redraw Order

**Files:**
- Modify: `backend/cad_preview.py:1-275`
- Test: `backend/test_cad_new_options.py`

- [ ] **Step 1: Add a failing SVG preview test**

Extend the preview test:

```python
req = CADRequest(enable_occlusion=True, sel_hys="暗合页", fingerprint_lock="无")
info, checks, draw_params = build_cad_params(req)
msg, buffer = run_integrated_system(info, checks, draw_params)
svg = render_dxf_svg(buffer.getvalue())
check("preview renders structural wipeouts", 'class="cad-wipeout"' in svg, svg[:500])
check("preview hides wipeout borders", '.cad-wipeout{fill:#f8fafc;stroke:none}' in svg, svg[:500])
```

- [ ] **Step 2: Run the preview test and verify it fails**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: FAIL because `cad_preview.py` ignores WIPEOUT entities.

- [ ] **Step 3: Collect entities in redraw order and render wipeouts**

Change collection from direct modelspace iteration to:

```python
for entity in doc.modelspace().entities_in_redraw_order():
    _collect_entity(entity, primitives)
```

Add WIPEOUT collection:

```python
elif kind == "WIPEOUT":
    points = [(float(p.x), float(p.y)) for p in entity.boundary_path_wcs()]
    if len(points) >= 3:
        primitives.append(Primitive("wipeout", layer, points, {}))
```

Add the CSS and SVG branch:

```python
".cad-wipeout{fill:#f8fafc;stroke:none}",
```

```python
elif primitive.kind == "wipeout":
    points = " ".join(f"{fmt(sx(x))},{fmt(sy(y))}" for x, y in primitive.points)
    parts.append(f'<polygon class="cad-wipeout" points="{points}"/>')
```

- [ ] **Step 4: Run preview and CAD tests**

Run:

```bash
python backend/test_cad_new_options.py
```

Expected: preview contains WIPEOUT polygons in redraw order and all tests PASS.

- [ ] **Step 5: Commit preview support**

```bash
git add backend/cad_preview.py backend/test_cad_new_options.py
git commit -m "Render CAD occlusion in SVG preview"
```

### Task 6: Final Verification

**Files:**
- Verify only; no new files expected.

- [ ] **Step 1: Run the full backend regression suite**

Run:

```bash
python backend/test_cad_new_options.py
python backend/test_api.py
python backend/test_security_phase1.py
```

Expected: all scripts report zero failures.

- [ ] **Step 2: Run frontend verification**

Run:

```bash
cd frontend
npm run lint
npm run build
```

Expected: lint and production build PASS.

- [ ] **Step 3: Generate visual artifacts for manual QA**

Generate at least these four requests with the switch both off and on:

- single rectangular door with outer trim;
- double door with inner and outer trim;
- arched door with trim;
- outer portal with two pillars and one header.

Open the enabled DXFs in AutoCAD 2022 and verify:

- covered lines are not visible or printed;
- `A-DOOR-OCCLUSION` can be frozen to reveal complete source geometry;
- panel entities remain single selectable closed entities;
- hardware, text, and dimensions remain visible;
- PDF print and system preview match the CAD view.

- [ ] **Step 4: Commit any verification-only test adjustments**

```bash
git add backend/test_cad_new_options.py
git commit -m "Verify CAD occlusion behavior"
```

Skip this commit if verification required no file changes.
