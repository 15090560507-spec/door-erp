# Direct Purchasing Catalog Implementation Plan

> Execute task-by-task in the current checkout; preserve unrelated user changes.

**Goal:** Create purchases directly and safely retain their supplier/product catalog.
**Architecture:** Transaction-scoped catalog resolver and price synchronization called by PurchasingService. An extracted dialog owns catalog loading and free-input form state; the page owns its top-right entry.
**Tech Stack:** FastAPI/Pydantic, SQLite, React/Next.js, existing UI controls.
**Spec:** docs/superpowers/specs/2026-10-27-purchase-catalog.md

## Constraints
- Additive migrations only; no master permission broadening or historical price rewriting.
- Draft save is atomic; confirmation controls price history; canceled editing writes nothing.
- Preserve units, conversion and tax metadata; exact match deduplication only.

## Task 1: Backend
- [x] Add failing tests in backend/test_purchase_catalog.py for reuse, ambiguity, rollback, price history, conversion, retry and legacy behavior.
- [x] Add supplier identity/request key migration in inventory_database.py and optional input fields in inventory_models.py.
- [x] Implement backend/purchase_catalog.py and integrate create/confirm in purchasing_service.py.
- [x] Run focused tests and existing purchasing/security regressions.

## Task 2: Interface
- [x] Extract PurchaseOrderDialog.tsx with searchable free supplier/material input, specs, units and editable suggested price.
- [x] Add top-right action in purchasing/page.tsx and remove old manual dialog from PurchasingCenter.tsx; preserve demand merge.
- [x] Extend inventoryApi.ts request types; verify TypeScript, lint and browser desktop/mobile flows.

## Task 3: Delivery
- [x] Record verification, review scoped diff, commit and push the approved branch (implementation a098170).
- [x] Prepare Tencent Cloud update commands without deleting data or volumes; deliver with the completion response.
