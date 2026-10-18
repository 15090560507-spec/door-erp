# Quote Door Quantity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the user-approved group quantity mockup and linked outer dimensions end to end.

**Architecture:** Add default-one group quantities without changing per-door item values. Extend existing preview/export and sales-order handoff paths; reuse the drawing dimension calculator. Execute inline as requested; the named execution sub-skills are unavailable.

**Tech Stack:** FastAPI/Pydantic, JSON persistence, React/Next.js, openpyxl, shared Node renderer, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-18-quote-door-quantity-design.md` (approved written proposal and interactive mockup).

## Global Constraints

- `doorQuantity` is a positive integer, legacy default 1; items remain per-door.
- Sum existing rounded per-door item amounts, then multiply once by door quantity.
- Preserve current area rules and all saved order snapshots.
- Isolated DATA_DIR; never stage user account data or `.superpowers/`.

## Task 1: Persistence and Arithmetic

Files: `backend/quote_models.py`, `backend/quote_database.py`, `backend/test_quote_door_quantity.py`.

- [x] Write failing tests for save/update/reload, default-one legacy, invalid values, and summed history counts.
  ```python
  assert saved['doorGroups'][0]['doorQuantity'] == 2
  assert db.get_all()[0]['doorCount'] == 2
  ```
- [x] Validate at request and database boundaries, persist quantity and normalize only missing legacy fields.
- [x] Run new and existing quote tests.

## Task 2: Editor, Preview and Dimensions

Files: quote types/page/table/preview/combobox, new `QuoteDoorQuantity.tsx`, dimension label helper.

- [x] Add shared per-door/group helpers and typed quantity; header stepper with positive-integer validation. Preserve invalid local input until corrected and block saves while invalid.
  ```typescript
  groupTotal = quoteGroupUnitTotal(group) * group.doorQuantity;
  ```
- [x] Save/reload quantity, show single-door row labels, extended totals, and correct preview totals/group labels.
- [x] Append resolved outer sizes to selected and search project labels without changing dimensions.
- [x] Run TypeScript/ESLint and browser interaction checks.

## Task 3: Exports and Order Handoff

Files: `backend/quote_excel.py`, `quote-template-pdf/src/renderQuote.mjs`, sales-order routes/types/workspace.

- [x] Add group subtotal rows when quantity exceeds one, even for one group. Label per-door quantities and group multiplication; compute grand totals from group totals.
  ```python
  subtotal_formula = f'=SUM({row_refs})*{door_quantity}'
  ```
- [x] Keep order quote `amount` per-door, add `door_quantity`, initialize quoted order line quantity and regenerate charges once on quote selection.
- [x] Test renderer/Excel and order API contracts; render actual JPG/PDF/XLSX samples.

## Task 4: Delivery

- [x] Review desktop/mobile screenshots, focused regressions and generated outputs; document verification.
- [x] Check diff, commit only scoped files, push the authorized branch and confirm status. Feature commit: `21a5c44`; push confirmed to `feat/semicircle-handles-and-quote-form-improvements`.
