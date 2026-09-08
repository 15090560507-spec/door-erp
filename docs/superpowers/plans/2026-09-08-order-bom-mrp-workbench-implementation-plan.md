# Order Confirmation, Whole-Order BOM, and Lightweight MRP Implementation Plan

> **For agentic workers:** Execute tasks in order. Write the failing test first, make the smallest compatible change, run the targeted regression, and commit only files from the current task.

**Goal:** Connect approved drawings and quotations to confirmed sales orders, automatically create independently traceable door units and draft BOMs, integrate door-frame processing into the BOM workbench, and drive inventory, purchasing, and workshop work packages from published BOM versions.

**Architecture:** Keep the existing FastAPI, Next.js, and shared `fulfillment.db` architecture. Treat `fulfillment_technical_packages` as BOM version headers and `fulfillment_components` as BOM items instead of introducing a parallel manufacturing database. Bridge the separate sales-order database to fulfillment with an idempotent provisioning job. Reuse the current inventory, supplier, purchasing, requirement, work-package, inspection, and finished-goods records. Existing APIs remain available through compatibility adapters while new workbench APIs expose clearer BOM terminology.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLite, Next.js 16, React 19, TypeScript, Axios, Tailwind CSS, Lucide React, Playwright.

---

## Scope Guardrails

- Use only approved drawing tasks as selectable automatic order sources.
- Match the latest valid quotation group for each selected drawing, while allowing the user to choose another saved quotation.
- Keep manual sales-order lines for exceptional products, but never fabricate a drawing revision for them.
- Preserve one production number, technical snapshot, BOM version, work history, inspection history, and finished-goods record per physical door.
- Allow purchasing demand to merge; preserve allocation back to sales-order line, door unit, BOM version, and BOM item.
- Reuse `fulfillment_technical_packages` and `fulfillment_components`; do not create duplicate `manufacturing_boms` tables.
- Preserve the current door-frame v1.4.3 geometry contract and DXF output. The BOM adapter consumes geometry; it must not duplicate frame formulas.
- Keep current login and access behavior in this phase. Do not add a new permission matrix.
- Do not rewrite the legacy `production_database.py` workflow. The current `/production` page uses the newer fulfillment center and is the migration target.
- Do not implement finite-capacity scheduling, accounting, payroll settlement, barcode scanning, or automatic supplier approval.
- Never rewrite published BOM rows in place. Changes create a new technical-package/BOM version.
- Do not commit runtime databases, user DXF files, logs, backups, `.superpowers/`, or unrelated working-tree files.

## Canonical Data Mapping

| Business concept | Existing canonical storage | Planned extension |
| --- | --- | --- |
| Sales order | `sales_orders` | provisioning state and retry metadata |
| Sales-order line/source snapshot | `sales_order_door_lines` | source type and stable fulfillment links |
| Door unit | `fulfillment_door_units` | sales-order line ID and BOM summary fields |
| BOM version | `fulfillment_technical_packages` | generation state, rule version, warning summary |
| BOM item | `fulfillment_components` | theoretical/planned quantities, loss, source, match and verification fields |
| Work package | `fulfillment_work_packages` | readiness and dependency-aware state |
| Material demand | `material_requirements` | keep and link to BOM version/item |
| Purchase demand/allocation | existing inventory purchasing tables | preserve door/BOM allocation |
| Inventory | `inventory_*` tables | reuse balances, reservations and immutable transactions |
| Frame calculation | `backend/door_cad` geometry services | add fulfillment-to-frame input adapter |

## Task 1: Freeze the Existing Order-to-Fulfillment Baseline

**Files:**
- Modify: `backend/test_sales_orders.py`
- Modify: `backend/test_fulfillment_center.py`
- Create: `backend/test_sales_order_fulfillment_bridge.py`

- [ ] Add baseline tests proving current confirmed orders retain immutable drawing/quotation snapshots.
- [ ] Add a failing bridge test for one confirmed sales order containing two drawing lines, with quantities two and one.
- [ ] Assert the desired result is one fulfillment order, three unique door units, and stable links to both sales-order lines.
- [ ] Add a retry assertion: running provisioning twice returns the same fulfillment order and does not add door units.
- [ ] Add a partial-failure assertion: confirmed sales-order state survives a failed fulfillment attempt and exposes a retryable error.
- [ ] Run:

```powershell
python backend/test_sales_orders.py
python backend/test_fulfillment_center.py
python backend/test_sales_order_fulfillment_bridge.py
```

- [ ] Verify only the new bridge test fails before implementation.
- [ ] Commit:

```powershell
git add backend/test_sales_orders.py backend/test_fulfillment_center.py backend/test_sales_order_fulfillment_bridge.py
git commit -m "test: define sales order fulfillment bridge"
```

## Task 2: Add Idempotent Sales-Order Provisioning

**Files:**
- Modify: `backend/sales_order_database.py`
- Modify: `backend/sales_order_models.py`
- Modify: `backend/sales_order_routes.py`
- Modify: `backend/fulfillment_database.py`
- Modify: `backend/fulfillment_models.py`
- Modify: `backend/fulfillment_routes.py`
- Create: `backend/sales_order_fulfillment_service.py`
- Modify: `backend/main.py`
- Modify: `backend/test_sales_order_fulfillment_bridge.py`

- [ ] Add backward-compatible sales-order columns: `provisioning_status`, `provisioning_error`, `provisioning_attempts`, `provisioned_at`, and `fulfillment_order_id`.
- [ ] Add `sales_order_id` and `sales_order_no` to `fulfillment_orders`; add a unique partial index for non-null `sales_order_id`.
- [ ] Add `sales_order_line_id`, `source_task_id`, and `source_quantity_index` to `fulfillment_door_units`.
- [ ] Add `source_type` to `sales_order_door_lines`; use `drawing` for current records and a stable `manual:<uuid>` source key for manual lines.
- [ ] Implement `SalesOrderFulfillmentService.provision(order_id, idempotency_key, user)`:
  - Load the confirmed order and frozen line snapshots.
  - Return the existing fulfillment order when `sales_order_id` is already provisioned.
  - Create one fulfillment order for the sales order.
  - Expand every order-line quantity into independent door units.
  - Create one version-1 technical package per door using the order-line drawing snapshot.
  - Record one provisioning event in each database.
- [ ] Keep database transactions local to each SQLite file. Persist `failed` plus a readable error when the fulfillment transaction fails.
- [ ] Add `POST /api/sales-orders/{id}/retry-provisioning`.
- [ ] Call provisioning immediately after sales-order confirmation; return the confirmed order even when provisioning needs retry.
- [ ] Keep `/api/fulfillment/orders/from-task/{task_id}` for legacy records, but remove it from the primary UI after migration.
- [ ] Run the three tests from Task 1 and expect all pass.
- [ ] Commit:

```powershell
git add backend/sales_order_database.py backend/sales_order_models.py backend/sales_order_routes.py backend/fulfillment_database.py backend/fulfillment_models.py backend/fulfillment_routes.py backend/sales_order_fulfillment_service.py backend/main.py backend/test_sales_order_fulfillment_bridge.py
git commit -m "feat: provision door units from confirmed sales orders"
```

## Task 3: Make Approved Drawings and Quotations the Order Source

**Files:**
- Modify: `backend/sales_order_models.py`
- Modify: `backend/sales_order_routes.py`
- Modify: `backend/sales_order_database.py`
- Modify: `backend/test_sales_orders.py`
- Modify: `frontend/src/lib/salesOrderTypes.ts`
- Modify: `frontend/src/lib/salesOrderApi.ts`

- [ ] Add tests showing `/api/sales-orders/candidates` returns only `status == "已通过"` drawing tasks.
- [ ] Add server-side filters for customer, project, door type, dimensions, quote state, final-review date, pagination, and current order ID.
- [ ] Return the latest quotation first and include all alternate quotation choices.
- [ ] Preserve the full approved drawing snapshot and selected quotation-group snapshot on every order line.
- [ ] Add optional manual line input with explicit product, dimensions, quantity, unit price, and technical remark.
- [ ] Require a selected quotation before confirmation for drawing-sourced rows; allow manual rows only when price and dimensions are valid.
- [ ] Return structured validation errors with line number and field name.
- [ ] Run `python backend/test_sales_orders.py`; expect pass.
- [ ] Run `cd frontend; npm run build`; expect pass.
- [ ] Commit:

```powershell
git add backend/sales_order_models.py backend/sales_order_routes.py backend/sales_order_database.py backend/test_sales_orders.py frontend/src/lib/salesOrderTypes.ts frontend/src/lib/salesOrderApi.ts
git commit -m "feat: refine approved order source selection"
```

## Task 4: Upgrade Technical Packages into Versioned BOMs

**Files:**
- Modify: `backend/fulfillment_database.py`
- Modify: `backend/fulfillment_models.py`
- Create: `backend/bom_generation_service.py`
- Create: `backend/bom_rules.py`
- Create: `backend/test_bom_generation.py`
- Create: `backend/test_bom_versions.py`

- [ ] Add technical-package fields: `generation_status`, `rule_version`, `generated_at`, `generation_summary_json`, and `blocking_warning_count`.
- [ ] Add component fields: `line_no`, `group_code`, `theoretical_quantity`, `waste_rate`, `planned_quantity`, `source_type`, `source_rule_version`, `source_payload_json`, `match_status`, `verification_status`, `operation_code`, `supplier_id`, `required_date`, and `attachments_json`.
- [ ] Create `fulfillment_bom_generation_runs` and `fulfillment_bom_generation_warnings` with order, door, package, rule version, severity, field path, message, and timestamps.
- [ ] Migrate existing components as `legacy_manual`, using current `quantity` as both theoretical and planned quantity.
- [ ] Define typed rule output objects independent of SQLite rows.
- [ ] Implement baseline BOM groups: frame/sill, leaf/panel, skeleton/profile, trim/header/column, glass/lines, hardware/opening mechanism, purchased ornaments, consumables, packaging, and subcontracting.
- [ ] Generate exact rows only when a known parameter exists. Generate a `待确认` or `缺少资料` row instead of inventing specifications or quantities.
- [ ] Match inventory materials by explicit rule mapping first, then normalized code/name/specification. Never silently pick among multiple matches.
- [ ] Store calculation inputs and the rule version on every generated row.
- [ ] Prove partial success: one missing hardware mapping does not erase valid panel or frame rows.
- [ ] Prove published version immutability and V2 creation through the existing production-change flow.
- [ ] Run:

```powershell
python -m pytest backend/test_bom_generation.py backend/test_bom_versions.py -q
python backend/test_fulfillment_center.py
```

- [ ] Commit:

```powershell
git add backend/fulfillment_database.py backend/fulfillment_models.py backend/bom_generation_service.py backend/bom_rules.py backend/test_bom_generation.py backend/test_bom_versions.py
git commit -m "feat: add versioned automatic whole-door BOM"
```

## Task 5: Integrate Door-Frame Processing without Duplicating Geometry

**Files:**
- Create: `backend/door_cad/services/fulfillment_adapter.py`
- Modify: `backend/door_cad/api/frame.py`
- Modify: `backend/door_cad/api/dxf.py`
- Modify: `backend/fulfillment_routes.py`
- Modify: `backend/bom_generation_service.py`
- Create: `backend/test_bom_frame_adapter.py`
- Modify: `backend/test_door_cad_calculator.py`
- Modify: `backend/test_door_cad_dxf_export.py`

- [ ] Write tests mapping supported approved drawing parameters to `FrameInput`.
- [ ] Return structured missing-field warnings for unsupported products or incomplete frame parameters.
- [ ] Call `calculate_frame_project()` exactly once; create BOM candidates from its `ProjectGeometry.parts`.
- [ ] Map each frame part ID, name, material type, length, thickness, flat width, quantity, rule version, and geometry reference into the “门框与门槛” BOM group.
- [ ] Add `GET /api/fulfillment/door-units/{id}/frame-input`.
- [ ] Add `POST /api/fulfillment/door-units/{id}/bom/frame/recalculate` with current BOM version and idempotency checks.
- [ ] Allow combined DXF export by `door_unit_id`; derive project metadata and frame input from the frozen technical snapshot.
- [ ] Do not change v1.4.3 calculation rules, template checksums, layer mapping, or standard DXF annotations.
- [ ] Run frame and adapter tests; expect pass.
- [ ] Commit:

```powershell
git add backend/door_cad/services/fulfillment_adapter.py backend/door_cad/api/frame.py backend/door_cad/api/dxf.py backend/fulfillment_routes.py backend/bom_generation_service.py backend/test_bom_frame_adapter.py backend/test_door_cad_calculator.py backend/test_door_cad_dxf_export.py
git commit -m "feat: connect frame processing to whole-door BOM"
```

## Task 6: Expose BOM Workbench APIs

**Files:**
- Create: `backend/bom_routes.py`
- Create: `backend/bom_models.py`
- Modify: `backend/main.py`
- Modify: `backend/fulfillment_database.py`
- Create: `backend/test_bom_api.py`

- [ ] Add authenticated APIs:

```text
GET  /api/bom/workbench
GET  /api/bom/door-units/{door_unit_id}
POST /api/bom/door-units/{door_unit_id}/generate
PUT  /api/bom/door-units/{door_unit_id}/draft
POST /api/bom/door-units/{door_unit_id}/verify
POST /api/bom/door-units/{door_unit_id}/publish
POST /api/bom/door-units/{door_unit_id}/new-version
GET  /api/bom/door-units/{door_unit_id}/diff/{from_version}/{to_version}
```

- [ ] Workbench response includes pending generation, verification, missing-data, shortage, published, and changed counts.
- [ ] Detail response returns groups, rows, warnings, version history, frame status, and downstream impact.
- [ ] Support batch verification only for unambiguous `已匹配` rows.
- [ ] Block publish when any blocking warning, missing material mapping, invalid planned quantity, or unresolved frame error remains.
- [ ] Use HTTP 409 for state conflicts and HTTP 422 for field validation. Include `code`, `field`, `door_unit_id`, `bom_item_id`, `message`, and `suggestion`.
- [ ] Preserve old technical-package endpoints as adapters until the frontend migration is complete.
- [ ] Run `python -m pytest backend/test_bom_api.py -q`; expect pass.
- [ ] Commit:

```powershell
git add backend/bom_routes.py backend/bom_models.py backend/main.py backend/fulfillment_database.py backend/test_bom_api.py
git commit -m "feat: expose whole-order BOM workbench APIs"
```

## Task 7: Publish BOM into Material Requirements and Purchase Demand

**Files:**
- Modify: `backend/requirement_service.py`
- Modify: `backend/inventory_database.py`
- Modify: `backend/inventory_service.py`
- Modify: `backend/purchasing_service.py`
- Modify: `backend/bom_routes.py`
- Create: `backend/test_bom_material_flow.py`
- Modify: `backend/test_inventory_requirements.py`
- Modify: `backend/test_inventory_purchasing.py`

- [ ] Make BOM publish call the existing requirement service in the same `fulfillment.db` transaction.
- [ ] Freeze `technical_package_id`, version, component ID, door unit, production number, material, specification, planned quantity, and unit on requirement rows.
- [ ] Calculate shortage with decimal-safe quantities; centralize rounding and epsilon behavior.
- [ ] Allocate available stock without reducing on-hand balance.
- [ ] Create purchase-demand candidates only for remaining shortages and explicit purchase supply mode.
- [ ] When purchase lines are merged, keep allocation rows back to every requirement item and BOM item.
- [ ] Preserve partial receipt, incoming inspection, warehouse receipt, reservation refresh, issue, return, transfer, subcontract, and scrap behavior.
- [ ] Make repeated BOM publish and purchase conversion idempotent.
- [ ] Run:

```powershell
python -m pytest backend/test_bom_material_flow.py -q
python backend/test_inventory_requirements.py
python backend/test_inventory_purchasing.py
python backend/test_inventory_material_flow.py
```

- [ ] Commit:

```powershell
git add backend/requirement_service.py backend/inventory_database.py backend/inventory_service.py backend/purchasing_service.py backend/bom_routes.py backend/test_bom_material_flow.py backend/test_inventory_requirements.py backend/test_inventory_purchasing.py
git commit -m "feat: drive material flow from published BOM"
```

## Task 8: Add Dependency-Aware Workshop Work Packages

**Files:**
- Modify: `backend/fulfillment_database.py`
- Modify: `backend/fulfillment_models.py`
- Modify: `backend/fulfillment_routes.py`
- Create: `backend/work_package_service.py`
- Create: `backend/test_work_package_dependencies.py`
- Modify: `backend/test_fulfillment_center.py`

- [ ] Create `fulfillment_work_package_dependencies` with unique predecessor/successor pairs.
- [ ] Add work-package readiness fields: `readiness_status`, `material_ready`, `blocked_reason`, `ready_at`, `submitted_at`, `scrap_quantity`, and `actual_minutes`.
- [ ] Generate work packages from published BOM operation codes and the applicable route template.
- [ ] Default route groups include technical preparation, frame/panel preparation, cutting, bending, welding/body, surface treatment, assembly, packaging, and inspection handoff.
- [ ] Mark unrelated packages ready in parallel; require only declared predecessors and required material allocations.
- [ ] Recompute readiness after BOM publish, stock allocation, issue, work completion, inspection, and production change.
- [ ] Keep controlled skip support with a mandatory reason and audit event.
- [ ] Do not let historical-version packages block current-version finished inspection.
- [ ] Derive order and door progress from weighted milestones and actual package events; remove manual progress writes from commands.
- [ ] Run dependency and fulfillment tests; expect pass.
- [ ] Commit:

```powershell
git add backend/fulfillment_database.py backend/fulfillment_models.py backend/fulfillment_routes.py backend/work_package_service.py backend/test_work_package_dependencies.py backend/test_fulfillment_center.py
git commit -m "feat: orchestrate dependency-aware workshop packages"
```

## Task 9: Build Shared Management Workspace Components

**Files:**
- Create: `frontend/src/components/workspace/WorkspaceHeader.tsx`
- Create: `frontend/src/components/workspace/MetricStrip.tsx`
- Create: `frontend/src/components/workspace/FilterBar.tsx`
- Create: `frontend/src/components/workspace/MasterDetail.tsx`
- Create: `frontend/src/components/workspace/StatusChip.tsx`
- Create: `frontend/src/components/workspace/EmptyState.tsx`
- Create: `frontend/src/components/workspace/LoadingPanel.tsx`
- Create: `frontend/src/components/workspace/ViewportDialog.tsx`
- Create: `frontend/src/components/workspace/InlineError.tsx`
- Modify: `frontend/src/app/globals.css`

- [ ] Extract stable operational page primitives instead of repeating long Tailwind class strings.
- [ ] Keep panels at 6-8px radius and avoid cards nested inside cards.
- [ ] Ensure primary text meets clear contrast; muted text never carries required values.
- [ ] Use blue/graphite primary buttons and reserve black for the sidebar or rare high-priority actions.
- [ ] Implement dialogs through `createPortal(document.body)` with fixed positioning, current-viewport centering, independent body scrolling, and fixed header/footer.
- [ ] Add 140-180ms opacity/status transitions. Do not transform route ancestors or animate every table row.
- [ ] Add `prefers-reduced-motion` behavior.
- [ ] Verify components at 1440x900, 1920x1080, and 390x844 before adoption.
- [ ] Run `cd frontend; npm run build`; expect pass.
- [ ] Commit:

```powershell
git add frontend/src/components/workspace frontend/src/app/globals.css
git commit -m "feat: add management workspace primitives"
```

## Task 10: Rebuild Order Confirmation UX

**Files:**
- Modify: `frontend/src/app/orders/page.tsx`
- Create: `frontend/src/components/orders/OrderList.tsx`
- Create: `frontend/src/components/orders/OrderSummary.tsx`
- Create: `frontend/src/components/orders/OrderEditor.tsx`
- Create: `frontend/src/components/orders/ApprovedSourcePicker.tsx`
- Create: `frontend/src/components/orders/OrderLineEditor.tsx`
- Create: `frontend/src/components/orders/ProvisioningStatus.tsx`
- Modify: `frontend/src/lib/salesOrderTypes.ts`
- Modify: `frontend/src/lib/salesOrderApi.ts`

- [ ] Split the current monolithic page into list, summary, editor, source picker, and line editor components.
- [ ] Default new-order mode to approved drawing/quotation selection; provide a visible “手工录入” mode.
- [ ] Allow multiple approved drawings only after the first selected row establishes the customer.
- [ ] Auto-fill customer, project, dimensions, product, configuration summary, latest quotation, quantity, delivery, and payment nodes.
- [ ] Keep imported values editable while the order is a draft.
- [ ] Show per-line source version, quote choice, amount, and validation without horizontal scrolling.
- [ ] Confirm through a centered dialog summarizing width, height, quantity, order total, and source warnings.
- [ ] After confirmation, show provisioning as generating, ready, or failed with a retry command and exact reason.
- [ ] Do not show the old production “manual release” panel for newly provisioned sales orders.
- [ ] Run frontend build and manually verify create, edit, confirm, failure, retry, cancel, and reload paths.
- [ ] Commit:

```powershell
git add frontend/src/app/orders/page.tsx frontend/src/components/orders frontend/src/lib/salesOrderTypes.ts frontend/src/lib/salesOrderApi.ts
git commit -m "feat: rebuild order confirmation workspace"
```

## Task 11: Replace the Cutting Entry with the Whole-Order BOM Workbench

**Files:**
- Create: `frontend/src/app/cutting/page.tsx`
- Create: `frontend/src/app/cutting/loading.tsx`
- Create: `frontend/src/components/bom/BomWorkbench.tsx`
- Create: `frontend/src/components/bom/BomOrderList.tsx`
- Create: `frontend/src/components/bom/DoorUnitTree.tsx`
- Create: `frontend/src/components/bom/BomEditor.tsx`
- Create: `frontend/src/components/bom/BomWarningPanel.tsx`
- Create: `frontend/src/components/bom/BomVersionHistory.tsx`
- Create: `frontend/src/components/bom/FrameProcessingPanel.tsx`
- Create: `frontend/src/lib/bomTypes.ts`
- Create: `frontend/src/lib/bomApi.ts`
- Modify: `frontend/src/components/TopNav.tsx`
- Modify: `frontend/src/lib/types.ts`
- Refactor: `frontend/src/app/door-cad/frame/page.tsx`
- Create: `frontend/src/components/door-cad/FrameCuttingWorkspace.tsx`

- [ ] Route “下料” to `/cutting` and place it immediately after “订单确认” in the expandable management group.
- [ ] Show workbench metrics, filterable sales-order list, door-unit tree, BOM groups, and current version.
- [ ] Support generate, regenerate, batch verify, row edit, publish, new version, version diff, and exception-only filtering.
- [ ] Keep stable table dimensions; use group sections and responsive row details instead of a full-page horizontal scrollbar.
- [ ] Extract the current frame page into `FrameCuttingWorkspace` and render it in the “门框加工” tab with frozen door input.
- [ ] Preserve standalone legacy project loading for old saved frame projects.
- [ ] Show DXF generation errors with field-level cause and suggestion.
- [ ] Run frontend build and targeted backend BOM/frame tests.
- [ ] Use Playwright screenshots to verify non-overlap, readable text, dialog centering, and table behavior at desktop and mobile widths.
- [ ] Commit:

```powershell
git add frontend/src/app/cutting frontend/src/components/bom frontend/src/lib/bomTypes.ts frontend/src/lib/bomApi.ts frontend/src/components/TopNav.tsx frontend/src/lib/types.ts frontend/src/app/door-cad/frame/page.tsx frontend/src/components/door-cad/FrameCuttingWorkspace.tsx
git commit -m "feat: add whole-order BOM cutting workbench"
```

## Task 12: Rebuild Production, Purchasing, Inventory, and Master Data Workspaces

**Files:**
- Modify: `frontend/src/app/production/page.tsx`
- Modify: `frontend/src/app/purchasing/page.tsx`
- Modify: `frontend/src/app/inventory/page.tsx`
- Modify: `frontend/src/app/master-data/page.tsx`
- Modify: `frontend/src/components/inventory/*.tsx`
- Create: `frontend/src/components/fulfillment/ProductionProgressBoard.tsx`
- Create: `frontend/src/components/fulfillment/ReadyWorkPackages.tsx`
- Create: `frontend/src/components/fulfillment/ExceptionQueue.tsx`
- Modify: `frontend/src/lib/fulfillmentApi.ts`
- Modify: `frontend/src/lib/fulfillmentTypes.ts`

- [ ] Remove the legacy pending-release panel for sales orders already provisioned by the bridge.
- [ ] Make production default to an exception-first summary plus ready work packages.
- [ ] Show package states: waiting material, waiting predecessor, ready, in progress, submitted, completed, exception, and rework.
- [ ] Preserve batch start, submit, controlled skip, quality, finished inbound, payment gate, shipment, and change-order workflows.
- [ ] Rebuild purchasing around demand pool, purchase orders, and arrivals; show allocation trace without exposing a very wide table.
- [ ] Rebuild inventory around balances, receiving/inspection, issue/return, movement documents, finished goods, and immutable transactions.
- [ ] Keep the unified material item as the master record and supplier-item rows as relationships.
- [ ] Reuse shared workspace components, status colors, centered dialogs, empty states, and local error recovery.
- [ ] Run frontend build and the fulfillment/inventory regression suite.
- [ ] Commit:

```powershell
git add frontend/src/app/production/page.tsx frontend/src/app/purchasing/page.tsx frontend/src/app/inventory/page.tsx frontend/src/app/master-data/page.tsx frontend/src/components/inventory frontend/src/components/fulfillment frontend/src/lib/fulfillmentApi.ts frontend/src/lib/fulfillmentTypes.ts
git commit -m "feat: redesign management execution workspaces"
```

## Task 13: Eliminate Navigation Delay and Normalize Errors

**Files:**
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/components/TopNav.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/renderApi.ts`
- Modify: `frontend/src/app/render/page.tsx`
- Modify: management data hooks/components created in Tasks 9-12
- Create: `frontend/src/lib/requestScope.ts`
- Create: `backend/request_timing.py`
- Modify: `backend/main.py`

- [ ] Add AbortController support to list/detail/preview requests and cancel requests when the page unmounts or selection changes.
- [ ] Keep route navigation independent of preview generation and background polling.
- [ ] Lazy-load heavy render, DXF preview, and frame-processing components.
- [ ] Prevent stale responses from replacing newer selections.
- [ ] Use server pagination for large order/BOM/purchase/inventory lists.
- [ ] Normalize API errors into field errors, business conflicts, authentication errors, and retryable server failures.
- [ ] Add a response timing header and slow-request logs without recording customer payloads or secrets.
- [ ] Measure navigation away from render, order, BOM, production, purchase, and inventory pages. Target visible route response within 300ms after click when the server is local.
- [ ] Run frontend build and manual performance traces.
- [ ] Commit:

```powershell
git add frontend/src/components/AppShell.tsx frontend/src/components/TopNav.tsx frontend/src/lib/api.ts frontend/src/lib/renderApi.ts frontend/src/app/render/page.tsx frontend/src/lib/requestScope.ts backend/request_timing.py backend/main.py
git commit -m "perf: isolate heavy workbench requests from navigation"
```

## Task 14: Migration, Full Regression, and Release Readiness

**Files:**
- Create: `backend/migrations/backfill_sales_order_fulfillment.py`
- Create: `backend/test_mrp_migration.py`
- Create: `docs/superpowers/reports/2026-09-08-order-bom-mrp-verification.md`
- Modify only files required by defects discovered in this task

- [ ] Backfill current rows with safe defaults; do not auto-provision historical orders unless explicitly selected.
- [ ] Mark existing technical-package components as `legacy_manual` and preserve IDs.
- [ ] Allow old fulfillment orders and frame projects to remain viewable and executable.
- [ ] Make migration repeatable and print created, skipped, and failed counts.
- [ ] Back up both SQLite files before migration in deployment instructions.
- [ ] Run backend suites:

```powershell
python backend/test_sales_orders.py
python backend/test_sales_order_fulfillment_bridge.py
python backend/test_fulfillment_center.py
python -m pytest backend/test_bom_generation.py backend/test_bom_versions.py backend/test_bom_frame_adapter.py backend/test_bom_api.py backend/test_bom_material_flow.py backend/test_work_package_dependencies.py backend/test_mrp_migration.py -q
python backend/test_inventory_foundation.py
python backend/test_inventory_requirements.py
python backend/test_inventory_purchasing.py
python backend/test_inventory_material_flow.py
python -m pytest backend/test_door_cad_baseline.py backend/test_door_cad_calculator.py backend/test_door_cad_dxf_export.py -q
```

- [ ] Run frontend verification:

```powershell
cd frontend
npm run lint
npm run build
```

- [ ] Use Playwright to verify 1440x900, 1920x1080, and 390x844 screenshots for order confirmation, BOM, production, purchasing, inventory, master data, and all dialogs.
- [ ] Test the complete scenario: approved drawings -> quotation -> confirmed order -> door units -> generated BOM -> frame processing -> BOM publish -> reservation/shortage -> purchase/receipt/inspection -> issue -> parallel work packages -> finished inspection -> finished inbound.
- [ ] Test one production change after purchasing and prove V2 impact is visible without altering V1.
- [ ] Write exact commands, results, screenshots, residual risks, and migration backup paths to the verification report.
- [ ] Inspect `git diff --check` and `git status --short`; stage no unrelated files.
- [ ] Commit:

```powershell
git add backend/migrations/backfill_sales_order_fulfillment.py backend/test_mrp_migration.py docs/superpowers/reports/2026-09-08-order-bom-mrp-verification.md
git commit -m "test: verify order BOM and MRP workflow"
```

## Delivery Order

The implementation must be deployable after each checkpoint:

1. **Checkpoint A, Tasks 1-3:** confirmed orders reliably create traceable door units.
2. **Checkpoint B, Tasks 4-6:** whole-door BOM generation, versioning, frame integration, and BOM UI APIs are complete.
3. **Checkpoint C, Tasks 7-8:** BOM drives material demand, purchasing, inventory, and dependency-aware work packages.
4. **Checkpoint D, Tasks 9-13:** management workspaces and performance are upgraded.
5. **Checkpoint E, Task 14:** migration and full regression are complete.

Do not start a later checkpoint while the previous checkpoint has failing tests or an unresolved data migration issue.

