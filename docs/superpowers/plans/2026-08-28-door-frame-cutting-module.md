# Door Frame Cutting Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an authenticated Door ERP `下料` module that calculates the eight new-process door-frame parts from one parameter set, renders 2D production views, exports one audited combined DXF, exports BOM Excel, and saves versioned project JSON.

**Architecture:** Keep the existing FastAPI/Next.js application and add an isolated `backend/door_cad` bounded module plus `/door-cad/frame` page. A single `ProjectGeometry` result, produced by a v1.4.3 rule adapter, is the only source consumed by SVG, DXF, and BOM exporters. Reuse the confirmed v1.4.3 templates and geometry rules without running its Flask app or changing the existing whole-door CAD engine.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, ezdxf, openpyxl, Next.js 16, React 19, TypeScript, SVG, Playwright.

---

## Scope Guardrails

- Include only new-process left/right/top/bottom frame skeleton and skin parts.
- Include 2D overview, per-part triptych, one combined DXF, BOM/Excel, and JSON project persistence.
- Exclude 3D, per-part DXF, DXF ZIP, old-process expansion, leaves, transoms, trims, and portal parts.
- Do not modify `backend/drawing.py`, current `/api/generate_cad*`, quote calculation, or production fulfillment behavior.
- Do not commit unrelated workspace logs, backups, `.superpowers/`, runtime databases, or user files.
- Keep `ruleVersion = "frame-new-v1.4.3"` and `schemaVersion = "1.0"` in every calculation and saved project.

## Task 1: Freeze the v1.4.3 Production Baseline

**Files:**
- Create: `backend/door_cad/__init__.py`
- Create: `backend/door_cad/templates/new_lr_process_55_62_template.dxf`
- Create: `backend/door_cad/templates/top_bottom_double_door_template.dxf`
- Create: `backend/door_cad/fixtures/v143_cut_outer_expected.json`
- Create: `backend/door_cad/fixtures/v143_template_checksums.json`
- Create: `backend/test_door_cad_baseline.py`

- [ ] Copy only the two confirmed DXF templates and the v1.4.3 CUT_OUTER expected values from `Door_Frame_DXF_Generator_v1.4.3_CUT_OUTER_Rebuild.zip`; do not copy Flask, CMD, HTML, or fixed-output scripts.
- [ ] Record SHA-256 checksums for both templates so accidental template replacement becomes a visible warning.
- [ ] Write the failing baseline test first:

```python
def test_v143_cut_outer_fixture_is_frozen():
    expected = load_fixture("v143_cut_outer_expected.json")
    assert expected["outer_width"] == 324.8
    assert expected["left_notch"] == {"x1": 76.0, "x2": 239.8, "depth": 47.0}
    assert len(expected["cut_outer_vertex_order_left"]) == 12
```

- [ ] Run `python -m pytest backend/test_door_cad_baseline.py -q` and verify it fails because the baseline loader/assets do not yet exist.
- [ ] Add the minimal fixture loader and assets, then rerun the same command and expect `PASS`.
- [ ] Commit only baseline assets and the baseline test:

```bash
git add backend/door_cad backend/test_door_cad_baseline.py
git commit -m "test: freeze door frame v1.4.3 baseline"
```

## Task 2: Define Typed Inputs and the Single Geometry Contract

**Files:**
- Create: `backend/door_cad/models/__init__.py`
- Create: `backend/door_cad/models/inputs.py`
- Create: `backend/door_cad/models/geometry.py`
- Create: `backend/test_door_cad_models.py`

- [ ] Write tests for defaults, linked skeleton/skin sizing, invalid dimensions, hinge counts, optional top/bottom parts, and JSON round-trip.
- [ ] Define `FrameInput` with explicit production parameters. Preserve v1.4.3 defaults: door width `1800`, height `2700`, outer side `55/62`, linked skeleton `52/59`, side skeleton thickness `2.0`, side skin thickness `0.8`, top/bottom `55/75`, three hinges, top/bottom enabled.
- [ ] Define immutable response models:

```python
class ProjectGeometry(BaseModel):
    schemaVersion: Literal["1.0"] = "1.0"
    ruleVersion: Literal["frame-new-v1.4.3"] = "frame-new-v1.4.3"
    project: ProjectMeta
    inputs: FrameInput
    assembly: AssemblyGeometry
    parts: list[PartGeometry]
    validation: ValidationReport

class PartGeometry(BaseModel):
    partId: str
    name: str
    position: Literal["left", "right", "top", "bottom"]
    materialType: Literal["skeleton", "skin"]
    length: float
    thickness: float
    flatWidth: float
    cutOuter: ClosedPolyline
    holes: list[Shape]
    grooves: list[Groove]
    foldSection: Polyline
    flatSection: Polyline
    dimensions: list[GeometryDimension]
    process: PartProcessMeta
```

- [ ] Make all geometry coordinates plain JSON numbers/objects, with internal rounding only at serialization (`0.001mm`), never in rule calculations.
- [ ] Run `python -m pytest backend/test_door_cad_models.py -q`; expect all tests pass.
- [ ] Commit:

```bash
git add backend/door_cad/models backend/test_door_cad_models.py
git commit -m "feat: define door frame geometry contract"
```

## Task 3: Port Common Geometry Operations and Side-Frame Rules

**Files:**
- Create: `backend/door_cad/geometry/__init__.py`
- Create: `backend/door_cad/geometry/primitives.py`
- Create: `backend/door_cad/geometry/mirror.py`
- Create: `backend/door_cad/geometry/clipping.py`
- Create: `backend/door_cad/geometry/validation.py`
- Create: `backend/door_cad/rules/__init__.py`
- Create: `backend/door_cad/rules/frame_new_skeleton.py`
- Create: `backend/door_cad/rules/frame_new_skin.py`
- Create: `backend/door_cad/rules/opening.py`
- Create: `backend/test_door_cad_side_rules.py`

- [ ] Write failing tests for the standard skeleton chain, skin chain, fixed-hole spacing, hinge placement, mirrored right frame, and CUT_OUTER notch/clipping.
- [ ] Port pure calculations from v1.4.3 into typed functions. Do not pass an `ezdxf` modelspace into rule functions.
- [ ] Implement the skin outer-cut boundary exactly as the baseline:

```python
def build_skin_cut_outer(flat_width: float, length: float, x1: float, x2: float, depth: float) -> ClosedPolyline:
    return closed_polyline([
        (0, 0), (x1, 0), (x1, depth), (x2, depth),
        (x2, 0), (flat_width, 0), (flat_width, length),
        (x2, length), (x2, length - depth),
        (x1, length - depth), (x1, length), (0, length),
    ])
```

- [ ] Clip grooves to the material intervals at both end notches; assert no groove segment crosses a removed interval.
- [ ] Generate the right side by mirroring all actual geometry and dimension witness points. Generate labels separately so text is never mirrored.
- [ ] Run `python -m pytest backend/test_door_cad_side_rules.py -q`; expect tests for 2700mm and a non-standard height to pass.
- [ ] Commit:

```bash
git add backend/door_cad/geometry backend/door_cad/rules backend/test_door_cad_side_rules.py
git commit -m "feat: port new-process side frame rules"
```

## Task 4: Port Independent Top and Bottom Frame Rules

**Files:**
- Create: `backend/door_cad/rules/top_bottom_template.py`
- Create: `backend/door_cad/rules/top_frame.py`
- Create: `backend/door_cad/rules/bottom_frame.py`
- Create: `backend/test_door_cad_top_bottom_rules.py`

- [ ] Write failing tests proving top/bottom geometry comes from the independent template rule and is not a rotated side frame.
- [ ] Port `calculate_top_bottom`, source-group recognition, piecewise mapping, outer/inner profile mapping, pin-hole handling, and top/bottom dimensions from v1.4.3.
- [ ] Convert the source template to `PartGeometry` at calculation time; no frontend or exporter may reopen the template.
- [ ] Assert top and bottom each produce one skeleton and one skin with closed outer loops and unique IDs.
- [ ] Add a clear blocking validation error if the template is absent or its expected source groups cannot be resolved.
- [ ] Run `python -m pytest backend/test_door_cad_top_bottom_rules.py -q`; expect all tests pass.
- [ ] Commit:

```bash
git add backend/door_cad/rules backend/test_door_cad_top_bottom_rules.py
git commit -m "feat: port independent top and bottom frame rules"
```

## Task 5: Assemble Eight Parts and Production Validation

**Files:**
- Create: `backend/door_cad/services/__init__.py`
- Create: `backend/door_cad/services/frame_calculator.py`
- Create: `backend/door_cad/services/validation.py`
- Create: `backend/test_door_cad_calculator.py`
- Create: `backend/test_door_cad_validation.py`

- [ ] Write the failing standard-order test:

```python
geometry = calculate_frame_project(FrameInput())
assert [part.partId for part in geometry.parts] == [
    "LF-SK", "LF-SKIN", "RF-SK", "RF-SKIN",
    "TF-SK", "TF-SKIN", "BF-SK", "BF-SKIN",
]
assert geometry.validation.status == "PASSED"
```

- [ ] Implement one orchestration service that computes all parts exactly once and derives assembly bounds, layout positions, triptych bounds, BOM metadata, and validation from those parts.
- [ ] Implement blocking validations: positive dimensions, chain sums, closed/non-self-intersecting cut loops, holes/grooves inside material, notch clipping, mirror semantics, template availability, unique part IDs, and BOM part count.
- [ ] Implement warnings for non-standard dimensions, project name missing, and template checksum changes.
- [ ] Ensure warnings require `acknowledgeWarnings=true` only at export time; calculation still returns geometry.
- [ ] Run both calculator and validation test files; expect all tests pass.
- [ ] Commit:

```bash
git add backend/door_cad/services backend/test_door_cad_calculator.py backend/test_door_cad_validation.py
git commit -m "feat: calculate and validate complete door frame geometry"
```

## Task 6: Add Atomic Project Persistence

**Files:**
- Modify: `backend/config.py`
- Create: `backend/door_cad/repository.py`
- Create: `backend/test_door_cad_repository.py`

- [ ] Add `DOOR_CAD_PROJECTS_FILE` and `DOOR_CAD_BACKUP_DIR` under the existing `DATA_DIR` and `BACKUP_DIR` patterns.
- [ ] Write repository tests using a temporary path: create, list summaries, load, update, preserve IDs/timestamps, and reject stale schema/rule versions.
- [ ] Store source inputs and the latest validated `ProjectGeometry` snapshot so reload is deterministic and traceable.
- [ ] Use the existing lock + temp file + `os.replace` + backup pattern. Never write directly over the production JSON.
- [ ] Include `createdBy`, `updatedBy`, Shanghai timestamps, `schemaVersion`, and `ruleVersion`.
- [ ] Run `python -m pytest backend/test_door_cad_repository.py -q`; expect all tests pass.
- [ ] Commit:

```bash
git add backend/config.py backend/door_cad/repository.py backend/test_door_cad_repository.py
git commit -m "feat: persist door frame cutting projects"
```

## Task 7: Expose Authenticated Calculation and Project APIs

**Files:**
- Create: `backend/door_cad/api/__init__.py`
- Create: `backend/door_cad/api/frame.py`
- Create: `backend/door_cad/api/projects.py`
- Create: `backend/door_cad/router.py`
- Modify: `backend/main.py`
- Create: `backend/test_door_cad_api.py`

- [ ] Write API tests first for 401 without login, successful calculation, 422 field errors, project create/list/get/update, and user audit fields.
- [ ] Create router prefix `/api/door-cad/frame`; every route depends on `get_current_user`.
- [ ] Implement:

```text
POST /calculate
GET  /projects
POST /projects
GET  /projects/{project_id}
PUT  /projects/{project_id}
```

- [ ] Convert domain validation errors into structured details containing `code`, `field`, `message`, and `severity`; never return raw tracebacks.
- [ ] Include the router once in `backend/main.py`; do not change the old CAD routes.
- [ ] Run `python -m pytest backend/test_door_cad_api.py -q`; expect all tests pass.
- [ ] Commit:

```bash
git add backend/door_cad/api backend/door_cad/router.py backend/main.py backend/test_door_cad_api.py
git commit -m "feat: add door frame calculation and project APIs"
```

## Task 8: Build the One Combined DXF Exporter

**Files:**
- Create: `backend/door_cad/exporters/__init__.py`
- Create: `backend/door_cad/exporters/dxf_exporter.py`
- Create: `backend/door_cad/api/dxf.py`
- Modify: `backend/door_cad/router.py`
- Create: `backend/test_door_cad_dxf_export.py`

- [ ] Write failing tests that reopen the output with ezdxf and assert: eight part IDs, expected layers, closed CUT_OUTER polylines, real `DIMENSION` entities, non-mirrored text, and zero audit errors.
- [ ] Map Geometry only to fixed layers such as `L01_OUTER_CUT`, `L02_INNER_CUT`, positive/negative groove layers, fold lines, dimensions, Chinese notes, and part IDs.
- [ ] Render each part in fixed-spaced triptych layout: folded section, flat section, unfolded plan. Use Geometry dimensions, not exporter-side formulas.
- [ ] Save to an in-memory stream or temporary file, reopen, call `doc.audit()`, and block response if errors exist.
- [ ] Add `POST /api/door-cad/frame/export-dxf`; accept inputs or saved project ID plus warning acknowledgment.
- [ ] Return filename `订单号-项目名称-门框下料图.dxf`, sanitized for Windows paths.
- [ ] Run `python -m pytest backend/test_door_cad_dxf_export.py -q`; expect all tests pass.
- [ ] Open one standard and one non-standard output in AutoCAD/WPS CAD and record the manual result in the test report before calling it production-ready.
- [ ] Commit:

```bash
git add backend/door_cad/exporters/dxf_exporter.py backend/door_cad/api/dxf.py backend/door_cad/router.py backend/test_door_cad_dxf_export.py
git commit -m "feat: export audited combined door frame DXF"
```

## Task 9: Build BOM and Excel Export

**Files:**
- Create: `backend/door_cad/services/bom.py`
- Create: `backend/door_cad/exporters/bom_excel.py`
- Create: `backend/door_cad/api/bom.py`
- Modify: `backend/door_cad/router.py`
- Create: `backend/test_door_cad_bom.py`

- [ ] Write tests that compare every BOM row length, thickness, width, quantity, and part ID with its `PartGeometry` source.
- [ ] Build BOM rows directly from `geometry.parts`; default standard project produces exactly eight rows.
- [ ] Create an `.xlsx` with title, order/project metadata, rule version, validation result, fixed columns, autofilter, frozen header, wrapped notes, and widths that display values without `####`.
- [ ] Add `POST /api/door-cad/frame/export-bom` returning `订单号-项目名称-门框BOM.xlsx`.
- [ ] Reopen the generated workbook with openpyxl in the test and verify all cells and number formats.
- [ ] Run `python -m pytest backend/test_door_cad_bom.py -q`; expect all tests pass.
- [ ] Commit:

```bash
git add backend/door_cad/services/bom.py backend/door_cad/exporters/bom_excel.py backend/door_cad/api/bom.py backend/door_cad/router.py backend/test_door_cad_bom.py
git commit -m "feat: export door frame BOM workbook"
```

## Task 10: Add Frontend Navigation, Types, and API Client

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/components/TopNav.tsx`
- Modify: `frontend/src/middleware.ts`
- Create: `frontend/src/lib/doorCadTypes.ts`
- Create: `frontend/src/lib/doorCadApi.ts`

- [ ] Add `"下料"` to `ModuleName` and `MODULE_OPTIONS` immediately after `图纸终审` and before `效果渲染`.
- [ ] Route it explicitly to `/door-cad/frame` in `TopNav`; add `/door-cad` to protected paths and matcher.
- [ ] Mirror Pydantic request/response shapes in `doorCadTypes.ts`; keep property names identical to JSON.
- [ ] Add authenticated API helpers for calculate, project list/save/load/update, DXF Blob download, and BOM Blob download.
- [ ] For Blob failures, reuse/export the existing structured error decoder so users see backend validation details rather than `[object Blob]`.
- [ ] Run `npm run lint` from `frontend`; expect zero errors in changed files.
- [ ] Commit:

```bash
git add frontend/src/lib/types.ts frontend/src/components/TopNav.tsx frontend/src/middleware.ts frontend/src/lib/doorCadTypes.ts frontend/src/lib/doorCadApi.ts
git commit -m "feat: add door frame cutting navigation and client API"
```

## Task 11: Implement Geometry-Only SVG Components

**Files:**
- Create: `frontend/src/components/door-cad/GeometryViewport.tsx`
- Create: `frontend/src/components/door-cad/Overview2D.tsx`
- Create: `frontend/src/components/door-cad/PartDetail2D.tsx`
- Create: `frontend/src/components/door-cad/BomTable.tsx`
- Create: `frontend/src/components/door-cad/ProductionValidation.tsx`
- Create: `frontend/src/components/door-cad/ProjectActions.tsx`
- Create: `frontend/src/components/door-cad/svgGeometry.ts`

- [ ] Implement `svgGeometry.ts` as coordinate-to-SVG projection only; it must not calculate manufacturing widths, holes, grooves, folds, or BOM values.
- [ ] Render cut, hole, groove, fold, and dimension layers with distinct restrained colors and stable non-scaling strokes.
- [ ] Add fit-to-view, wheel zoom, drag pan, reset, layer toggles, and part selection using SVG `viewBox`; avoid decorative cards and nested cards.
- [ ] Overview displays all enabled parts in a stable grid. Detail displays the selected part's folded section, flat section, and unfolded plan in a fixed vertical order.
- [ ] Empty/loading/error states keep stable dimensions and never show a blank SVG without explanation.
- [ ] Build `BomTable`, validation error/warning list, and JSON import/export controls.
- [ ] Run `npm run lint`; expect pass.
- [ ] Commit:

```bash
git add frontend/src/components/door-cad
git commit -m "feat: render door frame geometry workbench components"
```

## Task 12: Build the `/door-cad/frame` Workbench

**Files:**
- Create: `frontend/src/app/door-cad/frame/page.tsx`
- Create: `frontend/src/app/door-cad/frame/loading.tsx`
- Create: `frontend/src/components/door-cad/ParameterPanel.tsx`
- Create: `frontend/src/components/door-cad/NoticeDialog.tsx`

- [ ] Build a quiet operational layout: top project/actions row, left parameter column, right tabbed work area (`整套总览`, `单件详图`, `BOM`).
- [ ] Add fields for order/project metadata, width/height, linked/unlinked side dimensions, skin/skeleton thickness and grooves, hinge options/positions, top/bottom dimensions and component toggles.
- [ ] Add a 350ms debounced calculation with request cancellation/sequence guards. During failure, retain the last valid geometry and show the exact blocking issue in `NoticeDialog`.
- [ ] Track `idle/calculating/passed/warning/error`, dirty state, saved project ID, and warning acknowledgment separately.
- [ ] Project actions: new, save, save-as, load, import JSON, export JSON, export combined DXF, export BOM Excel.
- [ ] Associate an optional terminal-review task by loading existing `/api/tasks` results; copy only order/project dimensions into `FrameInput`, never mutate the task.
- [ ] Ensure buttons are actual commands, numeric controls do not shift layout, labels fit at 1280px and mobile widths, and horizontal scrolling is limited to tables/graphics where needed.
- [ ] Run `npm run lint` and `npm run build`; expect both pass.
- [ ] Commit:

```bash
git add frontend/src/app/door-cad frontend/src/components/door-cad/ParameterPanel.tsx frontend/src/components/door-cad/NoticeDialog.tsx
git commit -m "feat: build door frame cutting workbench"
```

## Task 13: End-to-End Regression and Docker Verification

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/door-cad-frame.spec.ts`
- Modify: `frontend/package.json`
- Create: `docs/door-frame-cutting-verification.md`

- [ ] Add `test:e2e` using Playwright and a test that logs in, opens `下料`, waits for `PASSED`, verifies the overview SVG has visible path content, opens a part detail, checks BOM has eight rows, saves/reloads a project, and downloads DXF/BOM.
- [ ] Add desktop and narrow viewport assertions for no incoherent overlap, readable controls, nonblank SVG, and usable pan/zoom controls.
- [ ] Run the complete backend suite:

```bash
python -m pytest backend/test_door_cad_*.py -q
```

Expected: all new door-CAD tests pass, no warnings treated as failures.

- [ ] Run existing high-risk regression tests:

```bash
python backend/test_security_phase1.py
python backend/test_quote_api.py
python backend/test_cad_preview.py
```

Expected: no regression in auth, quote, or whole-door CAD preview.

- [ ] Run frontend checks:

```bash
cd frontend
npm run lint
npm run build
npm run test:e2e
```

- [ ] Run Docker verification:

```bash
docker compose build backend frontend
docker compose up -d backend frontend https-proxy
docker compose ps
```

- [ ] Through HTTPS, verify authenticated calculate, project save/load, combined DXF download, BOM download, and frontend route load. Confirm backend/frontend ports remain internal.
- [ ] Record exact test counts, DXF audit results, template checksums, AutoCAD/WPS CAD manual opening result, and any remaining warnings in `docs/door-frame-cutting-verification.md`.
- [ ] Confirm `git status --short` contains only intended tracked changes; leave unrelated local files untouched.
- [ ] Final commit:

```bash
git add frontend/playwright.config.ts frontend/e2e/door-cad-frame.spec.ts frontend/package.json docs/door-frame-cutting-verification.md
git commit -m "test: verify door frame cutting workflow"
```

## Final Acceptance Checklist

- [ ] `下料` is visible between `图纸终审` and `效果渲染` and requires login.
- [ ] Standard calculation returns eight uniquely identified parts and production validation passes.
- [ ] Overview and triptych SVGs are nonblank and consume only `ProjectGeometry`.
- [ ] The combined DXF contains all enabled parts, real dimensions/text, closed cut boundaries, correct notch clipping, and zero ezdxf audit errors.
- [ ] BOM page and workbook exactly match Geometry values.
- [ ] Project JSON save/load/import/export preserves inputs, schema version, rule version, and geometry.
- [ ] Clear field-level errors block unsafe export; warnings require explicit acknowledgment.
- [ ] Existing whole-door CAD, quote, render, task, and fulfillment workflows remain operational.
- [ ] No 3D, per-part DXF, or DXF ZIP controls/endpoints are present.
