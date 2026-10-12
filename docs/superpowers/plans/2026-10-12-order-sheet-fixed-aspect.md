# Fixed-Aspect Order Sheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the template aspect ratio and all door entities while fitting manufacturing notes to their region.

**Architecture:** Correct the existing isolated CAD layout helper. Uniformly scale the template, translate it around stationary drawings, and fit owned MTEXT notes separately. Execute inline as the user requested; the named execution sub-skills are not installed.

**Tech Stack:** Python, ezdxf, pytest, existing JPG renderer.

**Spec:** `docs/superpowers/specs/2026-10-12-order-sheet-fixed-aspect-design.md`

## Global Constraints

- Original ORDER_FORM width/height ratio is invariant, not the paper ratio.
- Drawing entity coordinates, dimensions, annotation heights and view placement never change.
- Preserve all text, fonts, metadata and logo proportions; no text stretching.
- Retain current print profile and unsupported-template fallback.
- Isolated DATA_DIR only; exclude existing user data and `.superpowers/`.

## Task 1: Regression Coverage

Files: `backend/test_cad_order_layout.py`.

- [x] Assert original frame ratio for multiple widths/heights and front-only views:
  ```python
  self.assertAlmostEqual((new[1]-new[0])/(new[3]-new[2]), original_ratio, places=9)
  ```
- [x] Replace the old requirement that notes always shrink with checks for note-region containment, preserved contents and largest fitting height. Test Chinese/Latin/short/long/no-note cases and unsupported entities without partial changes.
- [x] Run the new tests and observe the aspect-ratio failure before implementation.

## Task 2: Uniform Sheet and Note Fitting

Files: `backend/cad_order_layout.py`, version consumed by `backend/main.py` unchanged.

Interface retained: `adapt_order_sheet(doc, drawing_entities, notes) -> str | None`.

- [x] Add note wrapping/measurement and maximum fitting height helpers:
  ```python
  lines = [_wrap(text, width, height) for text in texts]
  needed_height = sum(len(paragraph) for paragraph in lines) * height * 1.7
  ```
- [x] Derive one template scale from drawing bounds plus note/metadata reserves. Grow scale when notes cannot fit at the readability floor; no clipping upper scale cap.
  ```python
  transform = Matrix44.scale(scale)
  origin = drawing_min - drawing_offset_in_scaled_sheet
  ```
- [x] Stage copied template entities and attributes using the same uniform scale. Wrap footer within its scaled region and fit cell values. Preserve fonts and paragraph contents.
- [x] Place fitted notes in the available left-panel space above the unchanged drawings. Retain warnings and no-door fallback; update ORDER_LAYOUT_VERSION.
- [x] Run layout and print-window tests; check actual generated door DXF tags and audits against disabled layout.

## Task 3: Visual Verification and Delivery

Files: verification notes beside the spec, checklist updates.

- [x] Render before/after actual doors, inspect notes/metadata/clearances and original ratio. JPGs are not native AutoCAD verification.
- [x] Run focused tests and full option suite with/without correction; report unchanged baseline failures.
- [x] Run `git diff --check`, commit only this correction, push the authorized GitHub branch and verify status.

Self-review: the plan covers scale invariance, text fitting, fallback, cache invalidation, print compatibility and verification. No quote-history or render-workbench changes are included.
