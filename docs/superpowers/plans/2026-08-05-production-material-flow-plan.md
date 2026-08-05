# Production Material Flow Implementation Plan

**Goal:** Make the production module fully usable for every authenticated user and connect published BOMs to inventory reservation, shortage purchasing, warehouse receipt and production issue.

**Architecture:** Keep the isolated production SQLite database. Add a transactional material-allocation service used by BOM publishing and purchase receipts. Preserve the existing production-order lifecycle while splitting purchasing and warehouse UI into independent workbenches. All production routes require login but no longer require granular `production.*` permissions.

**Tech Stack:** FastAPI, SQLite, Pydantic, Next.js, React, TypeScript, Axios.

---

## Task 1: Unlock Production For All Authenticated Users

**Files:**
- Modify `backend/auth.py`
- Modify `backend/production_routes.py`
- Modify `frontend/src/app/production/page.tsx`
- Modify `frontend/src/components/production/*.tsx`
- Create/modify production permission tests

1. Add failing tests showing an ordinary authenticated account can access and operate every production workflow.
2. Keep unauthenticated requests at 401.
3. Replace production route permission dependencies with authenticated-user dependencies.
4. Return all production capabilities in authenticated user data so the existing frontend remains compatible.
5. Remove hidden production actions and permission-based empty states from the frontend.
6. Run security and production tests.

## Task 2: Add Material Requirements And Inventory Reservations

**Files:**
- Modify `backend/production_database.py`
- Modify `backend/production_models.py`
- Create `backend/production_material_service.py`
- Modify `backend/production_routes.py`
- Create `backend/test_production_material_flow.py`

1. Add additive tables for requirement headers, requirement items and inventory reservations.
2. Add purchase-item requirement linkage in a backward-compatible schema initializer.
3. Implement transactional calculations for on-hand, reserved, available and shortage quantities.
4. On BOM publish, create a frozen requirement and allocate available inventory.
5. Prevent different orders from reserving the same available quantity.
6. Add requirement list/detail and manual reallocation endpoints.
7. Test full-stock, partial-stock and multi-order allocation.

## Task 3: Connect Shortages To Purchasing

**Files:**
- Modify `backend/production_models.py`
- Modify `backend/production_routes.py`
- Modify `backend/production_material_service.py`
- Modify `backend/test_production_material_flow.py`

1. Add a request for converting selected shortage items to a purchase order.
2. Preserve requirement-item and production-order links on every purchase line.
3. Count outstanding purchase quantities in shortage calculations.
4. Support partial receipt without over-receipt.
5. On receipt, allocate the new stock to linked requirements and refresh order shortage state.
6. Test draft, placed, partial-arrival and completed states.

## Task 4: Add Production Issue And Return

**Files:**
- Modify `backend/production_models.py`
- Modify `backend/production_routes.py`
- Modify `backend/production_material_service.py`
- Modify `backend/test_production_material_flow.py`

1. Add order-based issue and return requests.
2. Issue only against reserved quantity and write inventory transactions.
3. Release reservation as material is issued.
4. Limit returns to the quantity previously issued by that order.
5. Recalculate requirement and order status after each action.
6. Test issue, partial issue, over-issue, return and over-return.

## Task 5: Enforce Clear Scheduling And Cutting Preconditions

**Files:**
- Modify `backend/production_routes.py`
- Modify `backend/production_models.py`
- Modify `backend/test_production_material_flow.py`

1. Allow cutting-sheet drafts after BOM publication.
2. Reject formal cutting release while the requirement is short.
3. Save schedules while short, but require an explicit override flag for confirmed shortage scheduling.
4. Return structured Chinese conflict details for the frontend.
5. Test normal and override paths.

## Task 6: Split And Rebuild The Production Frontend

**Files:**
- Modify `frontend/src/app/production/page.tsx`
- Modify `frontend/src/lib/productionTypes.ts`
- Modify `frontend/src/lib/productionApi.ts`
- Create `frontend/src/components/production/ProductionBomWorklist.tsx`
- Create `frontend/src/components/production/ProductionScheduleWorklist.tsx`
- Create `frontend/src/components/production/ProductionCuttingWorklist.tsx`
- Create `frontend/src/components/production/ProductionPurchasing.tsx`
- Create `frontend/src/components/production/ProductionWarehouse.tsx`
- Modify `frontend/src/components/production/ProductionOrderDetail.tsx`

1. Replace the combined supply tab with separate Purchasing and Warehouse tabs.
2. Add BOM/stock columns: required, reserved, purchased, received, issued and shortage.
3. Add shortage selection and purchase-order creation.
4. Add warehouse balance columns: on-hand, reserved and available.
5. Add purchase receipt, production issue and return forms.
6. Show every command and give a visible reason when a precondition blocks it.
7. Add clear success/failure feedback for every write operation.

## Task 7: Regression, Commit And Publish

1. Run new material-flow tests.
2. Run production MVP/workbench and security tests.
3. Run CAD, quote and render regressions.
4. Run targeted frontend ESLint and `npm run build`.
5. Inspect `git diff --check` and stage only related files.
6. Commit in focused increments.
7. Push both `main` and `codex/fix-cloud-quote-exports`.
