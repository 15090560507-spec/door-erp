# Inventory Consistency Implementation Plan

> **For agentic workers:** Use inline execution in the current task. Each task has a focused regression gate.

**Goal:** Keep production and warehouse semi-finished balances consistent after assembly issues.

**Architecture:** Replay existing movements through one shared inventory calculator. Write new issues against their real source positions, without changing historical movements or manufacturing states.

**Tech Stack:** Python, SQLite, unittest, Next.js, TypeScript, Node test runner.

**Spec:** `docs/superpowers/specs/2026-10-03-management-inventory-consistency-design.md`

## Global Constraints

- No schema migration or rewrite of existing inventory movements.
- Unfinished parts may enter semi-finished inventory; inventory must not change machining status.
- Scope balances by door, technical package, component, warehouse and location.
- Do not combine quantities with different units.
- Leave the user's existing data changes untouched.
- Run backend checks against disposable databases.

### Task 1: Shared Position Balances and Regression Cases

**Files:**
- Create: `backend/production_inventory.py`
- Create: `backend/test_production_inventory_positions.py`
- Modify: `backend/test_hierarchical_bom.py`

**Interfaces:** `semi_finished_balances(connection, door_id=None, package_id=None)` returns position dictionaries with identity, signed quantity, cumulative inbound/issued quantities, inference and anomaly flags.

- [x] Reproduce the current failure with `test_custom_components_move_through_semi_finished_without_material_master`, asserting warehouse overview is empty after issue.
- [x] Cover split locations, partial legacy issues, alternate warehouse names, explicit wrong-location issues, insufficient stock rollback, repeated issues and separate subjects.
- [x] Implement chronological movement replay. Explicit issues reduce their position only; legacy blank-location issues consume matching warehouse first and only the legacy default name may fall back to other positions of the same subject.
- [x] Verify `sum(row['quantity'] for row in positions)` matches inbound minus issued; preserve anomalies rather than dropping negative positions.

### Task 2: Production and Warehouse Consumers

**Files:**
- Modify: `backend/fulfillment_database.py`
- Modify: `backend/inventory_service.py`

**Interfaces:** Existing component inventory and warehouse overview endpoints remain compatible; add nullable `warehouse_id`, `source_inferred`, `stock_anomaly`, `warehouse_inferred` to tracked rows.

- [x] Reuse shared balances for component detail, preflight all assembly parts before writing, and split each issue across actual source positions within the existing transaction.
- [x] Use the same replay for tracked overview and preserve negative anomalous positions with zero available quantity.
- [x] Resolve warehouse by exact name first; infer a type match only when there is one candidate; otherwise keep `warehouse_id=None`.
- [x] Run inventory, hierarchical BOM and material-flow regressions; no manufacturing status changes are permitted.

### Task 3: Warehouse Filtering and Complete List Access

**Files:**
- Modify: `frontend/src/lib/inventoryTypes.ts`
- Create: `frontend/src/lib/trackedInventory.ts`
- Create: `frontend/src/lib/trackedInventory.test.ts`
- Modify: `frontend/src/components/inventory/InventoryOverview.tsx`
- Modify: `frontend/tsconfig.json` (allow the explicit TypeScript extensions already used by Node tests)

**Interfaces:** `filterTrackedInventory(items, filters)` filters by resolved warehouse ID, committed search query and low-stock mode.

- [x] Assert two same-type warehouses remain separate and unknown warehouse rows only appear in the all-warehouse view.
- [x] Filter search across production number, item, door type, specification, customer and project; exclude tracked inventory in low-stock-only mode.
- [x] Remove the 24-row truncation, use complete position identities for row keys and show source/warehouse inference and stock anomaly badges.
- [x] Show public SKU count and tracked count separately on warehouse cards.
- [x] Run Node tests, targeted ESLint and TypeScript checks; inspect desktop/mobile inventory using a temporary frontend fixture, without reading or changing live business data.

### Task 4: Final Verification and Delivery

- [x] Run `git diff --check`, review changes against the spec and verify the pre-existing data file remains unstaged.
- [ ] Mark completed plan tasks, commit only this batch's files and push to the user's confirmed GitHub branch.
- [ ] Report tests, limitations and the next batch without claiming that deferred modules are fixed.

## Verification Results

- Backend unittest modules: 24 tests passed, including 11 new position regressions.
- Existing inventory scripts: 60 checks passed (foundation 19, material flow 17, purchasing 14, requirements 10).
- Node tracked-inventory tests: 5 passed.
- Targeted ESLint and normal `tsc --noEmit --incremental false`: passed.
- Browser fixture: 31 rows accessible; selecting warehouse 2 shows only its 15 rows; search finds row 30; low-stock-only hides unclassified tracked parts.
- Desktop default/1200px and mobile 390px checked; no document horizontal overflow. Filters moved above both detail lists.
- UI screenshots saved outside the repo in `F:/codex/inventory-ui-verification/`.
- No production database, migration, paid rendering API or full production build was used.
- Remaining work is batches 2-4 in the approved spec, not inventory migration or historical-flow editing.
