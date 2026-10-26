# Additional Drawing Inputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three persistent inputs without redesigning the form or changing CAD geometry.

**Architecture:** Add a shared Pydantic DrawingInputOptions model and use it for CAD requests and task-param normalization. Extend existing frontend types/defaults and reuse DoorForm's current controls. Existing task loading already merges DEFAULT_FORM_DATA with stored params.

**Tech Stack:** Pydantic, FastAPI, React, TypeScript, unittest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-26-drawing-input-options-design.md`

## Global Constraints

- Keep the outer three-column form, section order, styles, preview placement, and existing controls unchanged except for the minimum local field-row space needed for the additions.
- The fields are metadata only in this change.
- Do not move CAD locks or handles, change geometry, affect disc centers, add CAD annotations, alter BOMs, change pricing, or undo the DXF download fix.

## Task 1: Request Contract And Persistence

Files: `backend/models.py`, `backend/test_drawing_input_options.py`.

- [x] Add failing model and disk-backed route tests for the new fields and unchanged CAD builder maps.
- [x] Run `python -m unittest test_drawing_input_options -v` against isolated DATA_DIR; confirm old models lose the fields.
- [x] Implement DrawingInputOptions with finite positive height default 1050, frame assembly Literal default one-piece, and installation Literal allowing empty/unselected.
- [x] In task create/update params validators, preserve unknown params and merge only `DrawingInputOptions.model_validate(params).model_dump()`; leave None params unchanged.
- [x] Rerun model/persistence tests and existing download regressions.

## Task 2: Existing Form Controls

Files: `frontend/src/lib/types.ts`, `frontend/src/components/DoorForm.tsx`, `frontend/src/app/dashboard/page.tsx`, `frontend/src/lib/api.ts` (validation field labels only).

- [x] Extend DoorFormData and DEFAULT_FORM_DATA with `lock_core_height: 1050`, `frame_assembly: "框套一体"`, and `installation_method: ""`.
- [x] Add two Select controls below the existing door-type selector. Use the existing Combobox for height with options `["950", "1050", "1150"]` next to the hardware configuration quantity.
- [x] Reject nonfinite or nonpositive height in existing door-form validation; leave simple-product validation unaffected.
- [x] Verify preset selection, arbitrary height entry, blank/invalid validation, save and reopening, older-task defaults, and unchanged three-column section positions at desktop/mobile widths using a local dev server and isolated/mock API responses.
- [x] Run TypeScript no-emit checking and ESLint for the modified frontend files. Record pre-existing warnings without refactoring them.

## Task 3: Delivery

- [x] Record exact test and screenshot results, including metadata-only scope and deployment limits, in the verification record.
- [ ] Review the scoped diff, stage only feature files, and push to `feat/semicircle-handles-and-quote-form-improvements` on `15090560507-spec/door-erp`.
