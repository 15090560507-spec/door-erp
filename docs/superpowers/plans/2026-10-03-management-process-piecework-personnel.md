# Management Process, Piecework and Personnel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This session executes inline because the user has already requested continued implementation.

**Goal:** Connect configurable component processes to BOM production, charge each whole-door operation once, allocate its fee manually, and display accurate personnel status.

**Architecture:** Keep work packages as production subjects and add independent whole-door operation fees, work memberships and employee allocations. Freeze process snapshots at publication; additive migration leaves existing doors in legacy mode. Focused services own route selection and fee validation; existing database/API entry points call them inside their transactions.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite, unittest, Next.js, React, TypeScript, lucide-react.

**Spec:** `docs/superpowers/specs/2026-10-03-management-process-piecework-personnel-design.md`

## Global Constraints

- Production progress remains BOM-component based; prices are per whole-door operation.
- No automatic splitting, legacy migration, historical price changes, or payment execution.
- Store monetary amounts as integer cents; reject negative, nonfinite and greater-than-two-decimal inputs.
- Confirmed allocations are immutable; approval/locked completion months reject new confirmations.
- Existing orders retain legacy wages; newly created doors use whole-door mode exclusively.
- No CAD, stock deduction, account data, broad navigation or paid rendering changes.
- All database/payroll verification uses isolated temporary fixtures.

### Task 1: Configured Routes and Additive Schema

**Files:** Create `backend/component_route_service.py`, `backend/door_piecework_service.py`, `backend/test_door_piecework.py`; modify `backend/fulfillment_database.py`, `backend/work_package_service.py`, `backend/operations_models.py`, `backend/operations_routes.py`.

**Interfaces:** `component_route(conn, component) -> list[RouteNode]`; `money_cents(value) -> int`; `DoorPieceworkService.publish(conn, door_id, package_id, now) -> None`; new door `billing_mode='whole_door'`, migration default `legacy`.

- [x] Write tests for two BEND work rows linked to one 8800-cent fee, template metadata and zero per-work payable rates; duplicate route codes/cycles/invalid inactive predecessors must roll back.
```python
fees = db.fetch_all("SELECT * FROM door_operation_fees WHERE billing_operation_code='BENDING'")
assert len(fees) == 1
assert fees[0]['total_cents'] == 8800
assert all(w['piece_rate'] == 0 for w in bend_work)
```
- [x] Run `python -m unittest test_door_piecework -v` with temporary `DATA_DIR`; expect missing schema/service assertions to fail.
- [x] Add tables `door_operation_fees`, `door_operation_fee_work`, `door_operation_allocations`; unique door+code and fee+employee. Add template `applicable_groups_json`, door billing mode, schema version 2. Seed known code groups only for the newly added column, preserving all existing prices.
- [x] Filter template nodes by skin/skeleton/assembly/packaging/other; recursively bridge excluded predecessors. Map known component execution codes, preserve template billing codes and child-to-assembly dependencies. Fallback route snapshot declares `process_unconfigured`.
```python
snapshot = {'billing_operation_code': step['step_code'], 'template_version': template['version'],
            'applicable_groups': groups, 'piece_rate': step['piece_rate']}
# Whole-door prices never become payable component prices.
node = RouteNode(code=execution_code, name=step['name'], piece_rate=0, snapshot=snapshot)
```
- [x] Freeze fees only during BOM publication; regenerate draft routes to current template, never alter already-published snapshots. Run route/BOM/dependency regressions and commit this deliverable.

### Task 2: Allocation Transactions, Completion and Payroll

**Files:** Modify `backend/door_piecework_service.py`, `backend/fulfillment_database.py`, `backend/operations_routes.py`, `backend/operations_models.py`, `backend/test_door_piecework.py`.

**Interfaces:** `DoorPieceworkService.list(conn, door_id) -> list[dict]`; `save_allocations(conn, fee_id, revision, allocations, confirm, now) -> dict`; allocation amounts are decimal strings. API `PUT /api/operations/piecework/{fee_id}/allocations` returns `fee`.

- [x] Test incomplete/QC/rework/skipped gates, 60+30 partial allocation, 60+50 excess, duplicate/inactive employees, stale revisions, idempotent repeated confirmation, immutable confirmation and locked/approved months. Verify transactions leave no partial rows.
```python
assert money_cents('0.10') + money_cents('0.20') == 30
with self.assertRaises(ValueError): money_cents('0.001')
```
- [x] Run failing focused tests; add readiness derived from frozen memberships and current valid order/package. Completion month is the latest relevant actual completion time, not confirmation time.
- [x] Implement revision guarded saves, immutable confirmation and integer-cent totals. Version changes mark drafts for review; publication replaces draft memberships/clears allocations with an event; confirmed fees remain and new work receives supplementary-work snapshot.
- [x] Prevent new-mode old work-package wage inserts in single/batch completion. Payroll reads legacy drafts only for legacy doors and confirmed allocation cents only for whole-door doors; exclude cancelled orders and guard approved recalculation for new allocations.
```python
piecework = legacy_total + confirmed_allocation_cents / 100
```
- [x] Run allocation/version/payroll tests plus existing operations workflow, then commit.

### Task 3: Personnel Status and Compact Production UI

**Files:** Modify `backend/operations_routes.py`, `backend/test_personnel_work.py`, `frontend/src/lib/operationsTypes.ts`, `frontend/src/lib/operationsApi.ts`, `frontend/src/lib/fulfillmentTypes.ts`, `frontend/src/components/inventory/RouteTemplateCatalog.tsx`, `frontend/src/components/production/PersonnelWorkBoard.tsx`, `frontend/src/app/production/page.tsx`; create `frontend/src/components/production/DoorPieceworkTable.tsx`.

**Interfaces:** Personnel status union `工作中|待开工|待检|暂停|异常|返工|空闲`; `DoorOperationFee` exposes cents, revision, status and allocations; `savePieceworkAllocations` calls Task 2 API.

- [x] Test scheduled/waiting-QC/cancelled/old-version/inactive personnel and stable ongoing-first selection. Run failing personnel tests.
- [x] Query active employees and valid orders/latest executable packages, map statuses explicitly; working counts use `status === '工作中'`, idle counts `status === '空闲'`.
```typescript
const working = employees.filter(item => item.status === "工作中").length;
```
- [x] Add applicability checkboxes to route editor; compact whole-door fee table after component progress, allocation dialog with personnel/decimal amount/note, remainder, explicit save/confirm and disabled immutable rows. Keep mobile table scroll within its own boundary; use lucide command icons/tooltips.
- [x] Run TypeScript noEmit, targeted ESLint and existing frontend tests. Inspect isolated desktop/mobile fixture screenshots including partial allocation and true personnel states; no real wages are changed. Commit.

### Task 4: Cross-module Verification and Delivery

**Files:** Update this plan and spec status; add verification notes under `docs/superpowers/`.

- [x] Run all focused and prior inventory/BOM/material/purchasing/requirements tests; verify migration runs twice without historical monetary writes.
- [x] Inspect `git diff --check`, verify only intended source/tests/docs are staged, leave `data/users_database.json` and `.superpowers/` alone.
- [x] Commit verified changes, push `HEAD:feat/semicircle-handles-and-quote-form-improvements` to the existing remote, report tests and remaining limitations accurately.

## Self-review

Tasks 1-2 cover schema, template/dependency snapshots, money, payroll, version and legacy protections; Task 3 covers personnel and UI; Task 4 covers isolated regressions and push. Signatures and API/type names above are the implementation contract. No unconfigured route is assigned an invented fee.

## Progress

Implementation committed and pushed as `34ea5c7` to `15090560507-spec/door-erp`, branch `feat/semicircle-handles-and-quote-form-improvements`. Tasks 1-4 completed on 2026-10-03. Final results: 41 backend unittest cases, 60 inventory checks and 7 frontend tests passed; TypeScript noEmit passed, targeted ESLint had no errors and three existing warnings. Desktop/mobile isolation screenshots verified. Real business data was not changed; no cloud deployment was performed.
