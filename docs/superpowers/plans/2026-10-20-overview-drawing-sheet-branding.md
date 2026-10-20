# Overview Drawing Navigation and Sheet Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open overview tasks directly in drawing and apply user-selected blank branding cells with centered titles.

**Architecture:** Reuse dashboard module switching with a pending task ref consumed inside its reset callback. Add one backend sheet-branding module operating after adaptive layout, with TT excluded from generic left-aligned cell fitting. Shared CAD generation feeds all outputs.

**Tech Stack:** React/Next.js, FastAPI, ezdxf, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-20-overview-drawing-sheet-branding-design.md`, approved in chat including the left-cell blank choice. Execute inline; named execution sub-skills are unavailable.

## Global Constraints

- Keep navigation guards, permissions and business workflows; no task copy or state change just by opening.
- Add exact title option 众鼎门业; preserve custom text without suffix changes.
- Only the default title keeps brand content; other titles leave the original brand cell blank.
- Center TT in the original title cell with bounded proportional font size.
- Do not move/scale door or dimension entities, remove grid lines, change sheet aspect ratio or mutate the cached template.
- No cloud deployment or business/account data changes.

## Task 1: CAD Branding and Title

Files: new `backend/cad_sheet_branding.py`, new `backend/test_cad_sheet_branding.py`, `backend/cad_order_layout.py`, `backend/drawing.py`, `backend/main.py`.

Interface: `normalize_order_title(value) -> str`, `apply_order_sheet_branding(doc, title) -> None`, constant `DEFAULT_ORDER_TITLE`.

- [x] Add failing real-template tests for default brand retention, three nondefault titles, title alignment and containment, unmodified grid/door entities, blank-title fallback and unsupported-template errors.
  ```python
  apply_order_sheet_branding(doc, '众鼎门业')
  self.assertFalse(list(doc.blocks['ORDER_FORM'].query('SPLINE CIRCLE')))
  self.assertEqual(title.dxf.halign, 1)
  self.assertEqual(title.dxf.valign, 2)
  ```
- [x] Run `pytest test_cad_sheet_branding.py -q` and confirm missing-module failures.
- [x] Locate the original brand rectangle and title-cell bottom from `_template_grid` and horizontal dividers; stage title copies using `TextEntityAlignment.MIDDLE_CENTER`, bounded by full cell width/height. Remove only interior brand text/graphics for nondefault titles and commit changes after validation.
- [x] Skip generic TT shrinking in adaptive layout, bump `ORDER_LAYOUT_VERSION`, normalize TT input in `build_cad_params`, and apply branding after adaptive layout. Run focused layout/branding/download/print tests including actual generation and template isolation.

## Task 2: Overview Entry and Title Option

Files: `frontend/src/app/dashboard/page.tsx`, `frontend/src/lib/types.ts`, new `tools/verify_overview_drawing_branding.mjs`.

- [x] Write a browser fixture test for overview task opening and verify it fails because drawing actions are absent before the fix.
- [x] Add pending drawing-task ref. On overview click await `requestAppNavigation`, store ID and set drawing module; consume the ref inside the module-reset timer and then use the existing task loader:
  ```ts
  const taskId = activeModule === '图纸绘制' ? pendingDrawingTaskRef.current : null;
  pendingDrawingTaskRef.current = null;
  setActiveTaskId(taskId);
  ```
- [x] Add 众鼎门业 to `ORDER_TITLES`. Check pointer/keyboard entry, two task IDs, standalone buttons, unchanged state before save, cancel/leave guard paths and selectable/custom titles at desktop/mobile widths.

Browser verification also exposed a mobile sidebar covering the unsaved dialog. TopNav now closes the mobile drawer before awaiting the existing guard; cancellation leaves the module unchanged. TaskCard keyboard activation ignores nested button events, with Enter/Space supported on the card itself.

## Task 3: Verify and Deliver

- [x] Run TypeScript/scoped ESLint and focused backend tests; keep unrelated existing CAD failures separate.
- [x] Generate default/众鼎/兰庭/custom long-title DXF, SVG, JPG and editable copies in `F:/codex/overview-branding-verification`. Inspect blank cells, title position and output consistency; verify simple-product mode as well.
- [x] Record verification, review scoped diff, commit and push the authorized branch without account data or `.superpowers/`.

Implementation and verification committed as `2b0dffc` and pushed to `origin/feat/semicircle-handles-and-quote-form-improvements`.
