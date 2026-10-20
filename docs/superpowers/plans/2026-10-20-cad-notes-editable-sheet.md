# Proportional CAD Notes and Editable Sheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scale workshop notes with the sheet and return an editable, sheet-only exploded DXF download.

**Architecture:** Keep the shared generated DXF intact. Scale note text in template coordinates before applying the same uniform sheet scale; convert only sheet references in a separately parsed download copy and cache that output independently.

**Tech Stack:** Python, ezdxf, FastAPI, pytest.

**Spec:** `docs/superpowers/specs/2026-10-20-cad-notes-editable-sheet-design.md`, reviewed by the user with the subsequent request to continue.

## Global Constraints

- Door geometry, hardware and dimension entities do not scale or move.
- The sheet aspect ratio remains unchanged; note height equals original note height times sheet scale.
- Retain full note text and explicit line breaks; wrap automatically, never enlarge the note font independently.
- Explode ORDER_FORM / ORDERFORM only in download copies; preserve actual attribute values, visibility and appearance.
- Preview, print and render consumers retain the original sheet INSERT and unchanged cached bytes.
- Use isolated test data; preserve existing account-data changes. Execute inline as requested; the named execution sub-skills are unavailable.

## Task 1: Proportional Notes

Files: `backend/cad_order_layout.py`, `backend/test_cad_order_layout.py`.

- [x] Add a failing test comparing note height and sheet scale for small, large and multi-note sheets.
  ```python
  scale = new_sheet_width / original_sheet_width
  self.assertAlmostEqual(note.dxf.char_height, original_height * scale)
  ```
- [x] Run the new proportional test and confirm it fails against the old largest-font behavior (three size variants).
- [x] Replace `_fit_notes` with template-coordinate note layout using original per-note heights. Compute content height before the uniform sheet scale:
  ```python
  available = header - body_bottom - padding_base * 2 - note_used_base
  scale = max(0.35, draw_width / usable_width, draw_height / available)
  ```
  Reject nonpositive remaining space with the existing atomic layout warning. Keep original note heights and per-note spacing proportional, and update the layout cache version.
- [x] Replace obsolete largest-font tests with proportional, wrapping, full-text, oversize-warning and unchanged-geometry assertions; run the layout suite.

## Task 2: Editable Download Copy

Files: new `backend/cad_download.py`, new `backend/test_cad_download.py`.

Interface: `editable_sheet_dxf(dxf_bytes: bytes) -> bytes`; module constant `CAD_DOWNLOAD_VERSION`.

- [x] Add failing tests using actual and small synthetic sheets: no sheet INSERT remains, Chinese attribute values survive, hidden attributes/placeholders stay hidden, nested sheet parts become editable, exterior hardware INSERT and DIMENSION are unchanged.
  ```python
  result = editable_sheet_dxf(source)
  self.assertEqual(source, original_bytes)
  self.assertFalse(any(is_sheet(e) for e in parsed.modelspace().query('INSERT')))
  ```
- [x] Run `pytest test_cad_download.py -q` and confirm missing module/function failures.
- [x] Parse a private document, resolve sheet-only virtual entities with skipped-entity errors, convert visible attribute copies to TEXT/MTEXT, and inherit layer-0/BYBLOCK display values. Recursively expand nested sheet INSERTs only, with cycle and unsupported-transform checks; reject unsupported clipped/xref references. Add resolved entities then remove the original sheet references only in this private document. Missing sheets return original bytes unchanged.
- [x] Run download tests, re-read outputs and audit them. Ensure errors return no partial download.

## Task 3: Download Route and Shared Cache

Files: `backend/main.py`, `backend/test_cad_download.py`.

Interface: `_cached_cad_download(key: str, dxf_bytes: bytes) -> tuple[bytes, bool]`.

- [x] Add failing route/cache tests for repeated download, original bytes unchanged, preview/print receiving originals, version invalidation, and conversion error responses.
- [x] Add an independently versioned download cache field, call the helper only from `/api/generate_cad`, and expose `X-CAD-Download-Cache` without changing other CAD routes.
  ```python
  key, original, cache_hit = _cached_cad(req)
  download, download_hit = _cached_cad_download(key, original)
  ```
- [x] Run focused layout/download/preview/print and existing CAD-cache tests: 43 passed and 24 subtests passed. Full CAD counter suite: 389 PASS / 9 FAIL with exactly the same failures using pre-change layout code from `f2b618a`.

## Task 4: Verify and Deliver

- [x] Generate actual baseline/internal/download DXF samples and small/large Chinese-note previews in `F:/codex/cad-editable-sheet-verification` with isolated DATA_DIR; inspect the rendered images and compare protected entities before/after.
- [x] Write `docs/superpowers/specs/2026-10-20-cad-notes-editable-sheet-verification.md` with test and artifact results, limitations and no cloud deployment claim.
- [x] Review staged diff, commit only scoped changes, and push to `feat/semicircle-handles-and-quote-form-improvements`; leave account data and `.superpowers/` untouched. Functional commit `6b56d4a`, remote push confirmed.
