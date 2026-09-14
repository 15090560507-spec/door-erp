# Hierarchical BOM, Production Steps, and Payroll Implementation Plan

> Execute tasks in order. Add a failing focused test first, preserve published and historical records, and commit only the files owned by the current task.

**Goal:** Merge BOM preparation into production management, represent door-frame and door-leaf assemblies with self-made skin and skeleton children, replace the empty status board with a BOM-oriented process table, assign assembly responsibility, and complete traceable piecework and monthly payroll.

**Architecture:** Extend the existing FastAPI, Next.js, SQLite, fulfillment BOM, inventory, and work-package architecture. `fulfillment_technical_packages` remains the BOM header and `fulfillment_components` remains the BOM row table. Add hierarchy and item-kind fields to BOM rows, introduce route templates and immutable door-step snapshots, then attach employees, production assignments, piecework, attendance, adjustments, and payroll periods to those steps. Do not introduce a parallel manufacturing order system.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLite, Next.js 16, React 19, TypeScript, Axios, Tailwind CSS, Lucide React.

---

## Scope Guardrails

- Keep one production number and one active BOM version per physical door.
- Keep procurement and inventory writable only in their existing workbenches.
- Treat assemblies and manufactured parts as drawing-driven records, never as required inventory matches.
- Match only real materials, purchased parts, services, and subcontracting records.
- Preserve existing published BOMs and historical work packages; migrate by compatibility projection or new BOM version.
- Keep door-frame CAD geometry rules unchanged in this phase.
- Keep the current single-account testing behavior; do not add a new permission matrix.
- Do not commit runtime databases, logs, generated DXF files, backups, `.superpowers/`, or unrelated files.

## Task 1: Freeze Hierarchical BOM and Process Semantics

**Files:**
- Create: `backend/test_hierarchical_bom.py`
- Create: `backend/test_process_route_templates.py`
- Modify: `backend/test_bom_generation.py`

- [ ] Assert generated BOM contains door-frame assembly, frame skin, frame skeleton, door-leaf assembly, leaf skin, and leaf skeleton.
- [ ] Assert assemblies and manufactured parts are publishable without `material_id`.
- [ ] Assert raw sheets, profiles, hardware, glass, and purchased parts still require material matching.
- [ ] Assert a route template can be copied to a door snapshot without later template edits changing the snapshot.
- [ ] Assert material status and process status are independent.

## Task 2: Extend BOM Rows and Generate Hierarchy

**Files:**
- Modify: `backend/fulfillment_database.py`
- Modify: `backend/fulfillment_models.py`
- Modify: `backend/bom_rules.py`
- Modify: `backend/bom_generation_service.py`
- Modify: `backend/requirement_service.py`
- Modify: `backend/bom_routes.py`
- Modify: `backend/test_hierarchical_bom.py`
- Modify: `backend/test_bom_generation.py`

- [ ] Add compatible columns: `parent_component_id`, `item_kind`, `procurement_mode`, and `drawing_parameter_json`.
- [ ] Generate stable parent-child codes for frame and leaf assemblies.
- [ ] Split the frame into frame skin and frame skeleton; split each leaf into leaf skin and leaf skeleton.
- [ ] Keep dimensions and per-door quantities on BOM rows, not in material master data.
- [ ] Change validation so `make` rows display `按图自制` and do not require material matching.
- [ ] Exclude assembly rows from material requirements while retaining their child material demands.
- [ ] Preserve manual add/delete and version rules.

## Task 3: Add Configurable Process Routes and Door Snapshots

**Files:**
- Create: `backend/process_route_service.py`
- Create: `backend/process_route_routes.py`
- Create: `backend/process_route_models.py`
- Modify: `backend/fulfillment_database.py`
- Modify: `backend/main.py`
- Modify: `backend/work_package_service.py`
- Modify: `backend/test_process_route_templates.py`
- Modify: `backend/test_work_package_dependencies.py`

- [ ] Add route template headers and ordered steps with predecessor, inspection, standard time, piece rate, default role, and work center.
- [ ] Seed editable default routes for frame skin, frame skeleton, leaf skin, leaf skeleton, hardware, and final assembly.
- [ ] Copy the selected route to immutable door process steps at BOM publication.
- [ ] Allow a door-specific route override with mandatory reason and event log.
- [ ] Prevent physical deletion of completed, inspected, or paid steps.
- [ ] Calculate readiness from predecessor completion and required material issue.

## Task 4: Merge BOM Preparation into Production Management

**Files:**
- Modify: `frontend/src/components/TopNav.tsx`
- Modify: `frontend/src/components/BomWorkbench.tsx`
- Modify: `frontend/src/app/cutting/page.tsx`
- Modify: `frontend/src/app/production/page.tsx`
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/src/lib/bomApi.ts`
- Modify: `frontend/src/lib/bomTypes.ts`

- [ ] Remove the independent `BOM与下料` navigation item.
- [ ] Make the cutting route a compatibility entry that redirects to production with a selected door when possible.
- [ ] Reuse the BOM editor inside the production preparation stage.
- [ ] Keep generation, manual row maintenance, verification, publishing, version history, and warnings available.
- [ ] Preserve a clear return to the selected door and stage after any full-page compatibility flow.

## Task 5: Remove Repeated Production Summaries

**Files:**
- Modify: `frontend/src/app/production/page.tsx`
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/src/lib/fulfillmentTypes.ts`
- Modify: `backend/fulfillment_database.py`

- [ ] Keep four top metrics only: in-process doors, due risk, material shortage, and unresolved exceptions.
- [ ] Move the five stages into compact list-filter controls.
- [ ] Keep a single five-stage rail inside the selected door detail.
- [ ] Show production number, TM order, customer, dimensions, due date, BOM version, assembly owner, and blocker in the summary.

## Task 6: Replace the Status Board with a BOM Process Table

**Files:**
- Modify: `frontend/src/app/production/page.tsx`
- Create: `frontend/src/components/production/BomProcessTable.tsx`
- Create: `frontend/src/components/production/ProcessStepDialog.tsx`
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/src/lib/fulfillmentApi.ts`
- Modify: `frontend/src/lib/fulfillmentTypes.ts`
- Modify: `backend/fulfillment_routes.py`
- Modify: `backend/fulfillment_database.py`

- [ ] Render parent-child BOM rows grouped by frame, leaf, trim, glass, and hardware.
- [ ] Display material status separately from route progress and current process step.
- [ ] Allow row expansion for material allocations, issue history, time records, and inspections.
- [ ] Support multi-select assignment, start, submit inspection, complete, pause, and exception actions.
- [ ] Show pause, exception, and rework inline instead of empty status columns.
- [ ] Link material shortages to inventory or purchasing without duplicating their write operations.

## Task 7: Add Employee Master Data and Assembly Assignment

**Files:**
- Create: `backend/workforce_database.py`
- Create: `backend/workforce_models.py`
- Create: `backend/workforce_routes.py`
- Modify: `backend/main.py`
- Modify: `backend/fulfillment_database.py`
- Modify: `backend/fulfillment_routes.py`
- Create: `backend/test_workforce_assignment.py`
- Create: `frontend/src/lib/workforceApi.ts`
- Create: `frontend/src/lib/workforceTypes.ts`
- Modify: `frontend/src/app/master-data/page.tsx`
- Modify: `frontend/src/app/production/page.tsx`

- [ ] Add employee number, name, team, role, active state, process capabilities, default work center, wage type, and employment dates.
- [ ] Replace free-text executors with employee selection while preserving legacy text values read-only.
- [ ] Add primary assembler, collaborators, work center, planned dates, actual dates, and notes to each door.
- [ ] Block final assembly until required parts are complete, with reasoned override.
- [ ] Carry assembly responsibility into finished inspection and traceability views.

## Task 8: Complete Piecework and Monthly Payroll

**Files:**
- Create: `backend/payroll_database.py`
- Create: `backend/payroll_models.py`
- Create: `backend/payroll_routes.py`
- Modify: `backend/main.py`
- Modify: `backend/work_package_service.py`
- Create: `backend/test_payroll.py`
- Create: `frontend/src/lib/payrollApi.ts`
- Create: `frontend/src/lib/payrollTypes.ts`
- Create: `frontend/src/app/payroll/page.tsx`
- Modify: `frontend/src/components/TopNav.tsx`
- Modify: `frontend/src/app/globals.css`

- [ ] Add salary schemes for fixed, piecework, and combined wages.
- [ ] Generate one idempotent piecework draft from each accepted process completion.
- [ ] Record reversal or supplemental entries instead of deleting approved piecework.
- [ ] Support manual entry and Excel import for attendance, overtime, allowances, bonuses, deductions, social insurance, tax, and other withholding.
- [ ] Calculate monthly employee payroll with visible component breakdown.
- [ ] Implement draft, review, approval, lock, authorized unlock, and export.
- [ ] Prevent direct edits to locked periods and retain a complete audit trail.

## Task 9: Migrate Compatibility Data

**Files:**
- Modify: `backend/fulfillment_database.py`
- Modify: `backend/bom_generation_service.py`
- Create: `backend/test_hierarchical_bom_migration.py`

- [ ] Project legacy `FRAME_ASSEMBLY`, `PANEL`, and `SKELETON` rows into the new labels without rewriting published facts.
- [ ] Display legacy `无需物料` self-made rows as `按图自制`.
- [ ] Continue displaying historical work packages in the event timeline.
- [ ] Create new hierarchy only for regenerated drafts or new BOM versions.
- [ ] Verify no inventory, procurement, inspection, shipment, or payroll reference becomes orphaned.

## Task 10: End-to-End Verification and Release

**Files:**
- Modify: `backend/test_fulfillment_center.py`
- Modify: `backend/test_bom_material_flow.py`
- Modify: `backend/test_sales_order_fulfillment_bridge.py`
- Create: `backend/test_production_payroll_e2e.py`
- Modify: relevant user documentation after behavior is stable

- [ ] Run focused hierarchy, process route, assignment, and payroll tests.
- [ ] Run the existing fulfillment, BOM, inventory, purchasing, sales-order, and data-safety regressions.
- [ ] Run `npm run build`.
- [ ] Verify production preparation, process table, process dialogs, assembly assignment, payroll, empty states, and responsive layouts in the browser.
- [ ] Confirm repeated clicks do not duplicate BOM versions, process steps, inventory movements, piecework, or payroll items.
- [ ] Commit and push each completed stage to `feat/semicircle-handles-and-quote-form-improvements`.

