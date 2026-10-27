# Reference Pattern Implementation Plan

> Execute in the current checkout task-by-task; preserve unrelated files and user data.

**Goal:** Recognize uploaded orthogonal reference motifs and apply reviewed geometry to B2 or rectangular transoms, with optional personal templates.
**Architecture:** Validated graph models and deterministic Shapely geometry; isolated SQLite job/template store with bounded worker pool; existing quotation connection shared server-side. React fields open an upload/crop/review dialog and store snapshots in DoorFormData. CAD rendering resolves the same snapshots.
**Tech Stack:** FastAPI, Pydantic, SQLite, Pillow/OpenCV, Shapely, ezdxf, React/Next.js.
**Spec:** docs/superpowers/specs/2026-10-27-reference-patterns.md

## Constraints
- No automatic AI calls from field edits, preview refreshes or reopening tasks.
- Optional templates; reviewed geometry saved with the drawing in either case.
- First version orthogonal patterns and rectangular transoms only; invalid data fails closed.
- No paid network inference during tests; credentials remain server-only.

## Task 1: Recognition and Storage
- [ ] Add failing model/geometry/job tests, including invalid/nonfinite/diagonal paths, bounds, true widths, restart/retry and role isolation.
- [ ] Implement reference_pattern_models.py, reference_pattern_geometry.py, reference_pattern_service.py and reference_pattern_routes.py.
- [ ] Reuse quote AI connection without changing quote prompts; add Shapely dependency and authenticated router.

## Task 2: CAD and Persistence
- [ ] Add typed snapshots to drawing options, task persistence and CAD parameter map.
- [ ] Draw reviewed reference contours in B2 groups and rectangular transoms; preserve front/back/child linkage and built-in choices.
- [ ] Verify actual DXF entities, dimensions, cache keys and task reload without AI.

## Task 3: Interface
- [ ] Add reference controls beside B2 and rectangular transom styles.
- [ ] Implement paste/drop/upload, crop, model status/job recovery, source/vector comparison, parameter edits, confirmation and optional template list/save.
- [ ] Verify real form persistence, desktop/mobile layout, errors and existing CAD regressions; no real inference calls.

## Task 4: Delivery
- [ ] Record verification and any model-testing limitations, commit/push approved branch and provide Tencent Cloud commands.
