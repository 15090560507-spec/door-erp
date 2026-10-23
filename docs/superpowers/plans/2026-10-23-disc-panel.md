# Disc Panel Implementation Plan

> Execute inline against the user-approved design. Named execution sub-skills are unavailable.

**Goal:** Three disc styles using actual DXF blocks, lock-edge anchors, and handle-linked height.

**Spec:** `docs/superpowers/specs/2026-10-23-disc-panel-design.md`

**Architecture:** A focused backend geometry helper resolves disc placement and closed exclusion boundaries. Existing drawing and fill APIs consume it. Four panel groups share frontend controls and new persisted parameters.

## Constraints

- Only work in the user-selected main directory; preserve the supplied template and account changes.
- Scale flower blocks by radius/1000, never by bounding-box width.
- Explicit height overrides auto linkage; explicit empty fill overrides flower default stripes.
- No silent clipping/shrinking of flower geometry; clip only surrounding fill.

## Tasks

- [x] Add backend geometry tests first: shape/scale/anchor, auto/manual height, outer contour, fill exclusion and invalid parameters.
- [x] Implement `backend/disc_panel.py`; wire four groups through `models.py`, both mappings in `main.py`, and `drawing.py`.
- [x] Add subtype, nullable center height and nullable outer fill to frontend types/defaults; render shared controls in `DoorForm.tsx`. A blank height explicitly means auto linkage, with a reset icon; no stale copied numeric height.
- [x] Generate real CAD fixtures, run focused regression/type/lint checks, exercise desktop/mobile UI with isolated mock tasks, inspect screenshots.
- [ ] Commit only feature files plus supplied DXF template; exclude account data, other local files and credentials. Push the authorized branch and report exact verification.
