# Additional Drawing Inputs Verification

Date: 2026-10-26. Main workspace: `F:/Vibe Coding/door-erp-main - 26.5.28`.

## Scope

The user rejected the layout redesign. The outer three-column grid, section order, styling, preview placement, and original controls remain in place. Only two dropdowns were added under Structure and Opening, and one editable preset input next to Hardware configuration quantity.

- Lock core height: default 1050mm; presets 950/1050/1150 and custom finite positive numbers.
- Frame/trim assembly: one-piece by default, or split.
- Installation: unselected by default; mounting tabs or expansion screws.

Values are stored in task params and survive editing and copying. Old task forms receive frontend defaults through the existing DEFAULT_FORM_DATA merge; create/update requests normalize only the three new fields while retaining other params. No bulk migration was run. State-only updates leave params unchanged.

These are input metadata, not CAD geometry controls in this delivery. A test confirms changing all three options leaves build_cad_params output identical. Drawing code, template files, pricing/BOM logic, and the prior DXF response repair were not modified.

## Tests

- Backend: **52 unittest tests passed** across new input options, editable CAD downloads, sheet layout, sheet branding, and disc panels. New options contribute eight tests with additional subcases for invalid and custom inputs.
- Existing task summary/search script: **29 PASS / 0 FAIL** in its own temporary data directory.
- Frontend lib tests: **18 passed**.
- TypeScript `--noEmit --incremental false`: passed.
- ESLint on DoorForm, dashboard, types, and api: **0 errors**, seven pre-existing warnings (unused variables/props, an existing image element, and an existing hook dependency).
- `git diff --check`: passed.

The model tests failed on the prior implementation because defaults and height/choice validation were missing. A test-fixture role was corrected to the existing allowed role `录入员`; no authorization code changed.

## Browser Verification

Real local services, not production or mocked save responses:

- Frontend: `http://127.0.0.1:3164`, backend: `http://127.0.0.1:8164`.
- Backend data isolated under `F:/codex/drawing-options-ui`.
- Confirmed default values, 950/1150 selection, custom 1088.5mm, and both assembly/installation choices.
- Submitted a test task with 1088.5mm, split assembly, and expansion-screw installation. Reopened the task and verified all values.
- Saved 950mm, one-piece assembly, and mounting-tab installation; verified through the API and again after a browser reload.
- Zero height was rejected before saving, and the stored 950mm value remained unchanged.
- Desktop 1600px retained three form columns and the same section sequence.
- Mobile 390px had zero horizontal overflow after responsive layout settled.
- No browser runtime errors. No paid AI calls or production data operations.

Artifacts:

```text
F:/codex/drawing-input-options-verification/desktop-1600.png
F:/codex/drawing-input-options-verification/mobile-390.png
F:/codex/drawing-input-options-verification/report.json
F:/codex/verify-drawing-input-options.cjs
```

## Limits

The full legacy CAD baseline and production Next build were not rerun for this metadata-only feature. The existing shared Combobox behavior was reused rather than redesigned. Tencent cloud deployment was not performed; both backend and frontend must be rebuilt there to receive this change. User account data, untracked assets, layout mockups, local environment files, and test artifacts are excluded from the feature commit.

## Delivery

Feature commit `46c4032` was pushed to `15090560507-spec/door-erp` on `feat/semicircle-handles-and-quote-form-improvements`. The first SSH attempt was reset; the retry succeeded. Local test services remain on ports 3164/8164 with isolated data. Tencent cloud has not been updated from this session.
