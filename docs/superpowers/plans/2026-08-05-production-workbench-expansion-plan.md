# Production Workbench Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make approved-but-unreleased drawings visible at the top of production orders and expand the production module into a mixed workbench with alerts, timeline, richer documents, authenticated Excel exports, and printable PDF-ready pages.

**Architecture:** Keep approved drawing tasks in the existing task JSON database and production execution records in the isolated SQLite production database. Add read-only aggregation endpoints that join the two domains by `source_task_id` and `source_revision`, while retaining the existing release endpoint as the only write transition. Generate production documents in a focused backend service and download them through the existing authenticated Axios client.

**Tech Stack:** FastAPI, SQLite, Pydantic, openpyxl, Next.js 16, React, TypeScript, Tailwind CSS, Axios.

---

## File Structure

**Backend**

- Create `backend/production_document_service.py`: build production workbook files and authenticated print HTML.
- Create `backend/test_production_workbench.py`: pending-release, dashboard, timeline, permissions, export, and state regression tests.
- Modify `backend/production_database.py`: enhanced order filters, dashboard metrics, timeline aggregation helpers, and document data queries.
- Modify `backend/production_models.py`: pending-release and enhanced filter response structures only where request validation is needed.
- Modify `backend/production_routes.py`: pending-release, enhanced dashboard/order filters, timeline, DXF download, and document routes.
- Modify `backend/main.py`: expose the task database to the production router through a configured dependency and keep release logic unchanged.

**Frontend**

- Modify `frontend/src/lib/productionTypes.ts`: pending task, timeline, alert, and document types.
- Modify `frontend/src/lib/productionApi.ts`: new queries and authenticated download/print helpers.
- Create `frontend/src/components/production/PendingReleaseList.tsx`: compact approved-task table and release action.
- Create `frontend/src/components/production/ProductionFilters.tsx`: combined production-order filters.
- Create `frontend/src/components/production/ProductionTimeline.tsx`: event timeline.
- Create `frontend/src/components/production/ProductionDocumentActions.tsx`: Excel download and print/PDF commands.
- Modify `frontend/src/components/production/ProductionDashboard.tsx`: expanded alert and progress metrics.
- Modify `frontend/src/components/production/ProductionOrderList.tsx`: owner, progress, warning and latest-update columns.
- Modify `frontend/src/components/production/ProductionOrderDetail.tsx`: overview, timeline, documents, confirmations, and better separation of operational tabs.
- Modify `frontend/src/components/production/ProductionReleaseButton.tsx`: reusable compact mode and completion callback.
- Modify `frontend/src/app/production/page.tsx`: mixed workbench composition and shared filter state.

---

### Task 1: Pending-Release Query and Duplicate Exclusion

**Files:**
- Create: `backend/test_production_workbench.py`
- Modify: `backend/production_routes.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write failing pending-release tests**

Create an isolated task JSON file with one `已通过` task and an isolated production database. Assert that the endpoint returns the task before release and excludes it after a matching direct production order exists.

```python
response = client.get("/api/production/pending-release", headers=headers("prod_reader"))
assert response.status_code == 200
assert [row["task_id"] for row in response.json()["tasks"]] == ["approved-1"]

test_db.create_order(
    source_task_id="approved-1",
    source_revision=response.json()["tasks"][0]["source_revision"],
    customer="测试客户",
    project="",
    due_date="",
    sales_note="",
    include_quote=False,
    task_snapshot=approved_task,
    quote_snapshot=None,
    dxf_bytes=b"0\nEOF\n",
    created_by="prod_sales",
)
response = client.get("/api/production/pending-release", headers=headers("prod_reader"))
assert response.json()["tasks"] == []
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `py -3 test_production_workbench.py`

Expected: FAIL because `/api/production/pending-release` does not exist.

- [ ] **Step 3: Add a configured task database dependency**

Expose a setter in `production_routes.py` so `main.py` and tests provide the active `TaskDatabaseManager` without importing `main` back into the router.

```python
task_repository = None

def configure_task_repository(repository: Any) -> None:
    global task_repository
    task_repository = repository
```

Call `configure_task_repository(task_db)` immediately after `task_db` is created in `main.py`.

- [ ] **Step 4: Implement pending-release projection**

For every stored task with `status == "已通过"`, calculate the same SHA-256 revision used by the release endpoint, query `production_orders` for a matching non-void direct release, and return only unreleased tasks. Return compact fields and never restore Base64 reference images.

```python
{
    "task_id": task["id"],
    "source_revision": revision,
    "customer": params.get("dhdw", ""),
    "project": params.get("gdmc", ""),
    "door_type": params.get("door_type", ""),
    "width": params.get("dw"),
    "height": params.get("dh"),
    "opening": f"{params.get('sel_kx', '')}{params.get('sel_nk', '')}",
    "approved_at": task.get("updated_at") or task.get("date", ""),
    "approved_by": task.get("reviewer") or "",
}
```

- [ ] **Step 5: Run tests and commit**

Run: `py -3 test_production_workbench.py`

Expected: PASS for visibility, exclusion, 401 and 403 cases.

Commit:

```bash
git add backend/main.py backend/production_routes.py backend/test_production_workbench.py
git commit -m "Show approved tasks awaiting production release"
```

### Task 2: Dashboard Metrics and Combined Order Filters

**Files:**
- Modify: `backend/production_database.py`
- Modify: `backend/production_routes.py`
- Modify: `backend/test_production_workbench.py`

- [ ] **Step 1: Add failing dashboard and filter tests**

Seed orders with past, near-future and later due dates, different owners and shortage states. Assert counts for `待下达`, `今日下达`, `即将到期`, `已逾期`, `缺料`, and stage metrics. Assert combined filters for owner, shortage and due-date range.

```python
response = client.get(
    "/api/production/orders",
    params={"owner": "王师傅", "shortage": "缺料", "due_from": "2026-08-01", "due_to": "2026-08-31"},
    headers=headers("prod_reader"),
)
assert all(row["owner"] == "王师傅" for row in response.json()["orders"])
```

- [ ] **Step 2: Extend `list_orders` with joined schedule fields**

Use a `LEFT JOIN production_schedules s ON s.order_id=o.id`, return `owner`, `producer`, `planned_start` and `planned_end`, and build parameterized conditions for owner, shortage, due dates, stage, status and text query.

- [ ] **Step 3: Calculate alert metrics using Shanghai dates**

Use `date.today()` in the Shanghai timezone. Exclude `已完成`, `已作废` and `已撤回` from due alerts. Define near due as today through today plus three days.

- [ ] **Step 4: Include pending-release count in dashboard response**

The route combines SQLite metrics with `len(pending_release_tasks())`; the database repository remains independent of the task JSON store.

- [ ] **Step 5: Run tests and commit**

Run: `py -3 test_production_workbench.py`

Expected: all dashboard and filter assertions pass.

Commit:

```bash
git add backend/production_database.py backend/production_routes.py backend/test_production_workbench.py
git commit -m "Expand production dashboard and filters"
```

### Task 3: Timeline and Frozen DXF Download

**Files:**
- Modify: `backend/production_database.py`
- Modify: `backend/production_routes.py`
- Modify: `backend/test_production_workbench.py`

- [ ] **Step 1: Write failing timeline and DXF tests**

Assert the timeline returns newest-first normalized entries and the DXF endpoint returns `application/dxf` with an attachment filename containing the production order number. Assert unrelated production readers can download, while unauthenticated users receive 401.

- [ ] **Step 2: Implement timeline aggregation**

Normalize event rows to:

```python
{
    "id": f"event-{row['id']}",
    "type": "event",
    "title": row["action"],
    "detail": row["detail"],
    "operator": row["operator_name"],
    "created_at": row["created_at"],
}
```

Production events already cover all state changes; add missing event writes to purchase status, receipt, shipment creation/status and inventory transactions before relying on the timeline.

- [ ] **Step 3: Implement safe DXF response**

Resolve `dxf_path` under `production_db.files_dir`, reject paths escaping the root, and return `FileResponse` with filename `{order_no}_终审冻结图.dxf`.

- [ ] **Step 4: Run tests and commit**

Run: `py -3 test_production_workbench.py`

Expected: timeline and DXF tests pass.

Commit:

```bash
git add backend/production_database.py backend/production_routes.py backend/test_production_workbench.py
git commit -m "Add production timeline and frozen drawing download"
```

### Task 4: Production Document Service

**Files:**
- Create: `backend/production_document_service.py`
- Modify: `backend/production_routes.py`
- Modify: `backend/test_production_workbench.py`

- [ ] **Step 1: Write failing document tests**

For BOM, purchase, inventory, cutting, quality and shipment documents, assert authenticated requests return valid XLSX ZIP bytes or printable UTF-8 HTML. Assert unsupported document types return 404 and unauthorized requests return 401/403.

```python
response = client.get(
    f"/api/production/orders/{order_id}/documents/bom.xlsx",
    headers=headers("prod_technical"),
)
assert response.status_code == 200
assert response.content[:2] == b"PK"
```

- [ ] **Step 2: Implement reusable workbook formatting**

Create helpers for title, metadata rows, headers, body rows, widths, wrapping, borders, print area and page setup. Use Song font fallbacks and enable automatic workbook calculation.

```python
sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
sheet.page_setup.orientation = "landscape"
sheet.sheet_properties.pageSetUpPr.fitToPage = True
sheet.page_setup.fitToWidth = 1
sheet.page_setup.fitToHeight = 0
```

- [ ] **Step 3: Implement document-specific row builders**

Use explicit builders `build_bom_rows`, `build_purchase_rows`, `build_inventory_rows`, `build_cutting_rows`, `build_quality_rows`, and `build_shipment_rows`. Do not dynamically expose arbitrary table names or SQL fields.

- [ ] **Step 4: Implement printable HTML**

Generate escaped HTML with `@page { size: A4; margin: 10mm; }`, fixed tables, document title, order metadata, signatures and print timestamp. Never interpolate unescaped user values.

- [ ] **Step 5: Add authenticated routes**

Return in-memory workbook bytes through `StreamingResponse`; return print pages through `HTMLResponse`. Require the same business permission used to edit or manage each document, with `production.manager` accepted for all production documents.

- [ ] **Step 6: Run tests and commit**

Run: `py -3 test_production_workbench.py`

Expected: all document formats and permission checks pass.

Commit:

```bash
git add backend/production_document_service.py backend/production_routes.py backend/test_production_workbench.py
git commit -m "Add production document exports"
```

### Task 5: Frontend Types, APIs and Authenticated Downloads

**Files:**
- Modify: `frontend/src/lib/productionTypes.ts`
- Modify: `frontend/src/lib/productionApi.ts`

- [ ] **Step 1: Add pending task, timeline and filter types**

```ts
export interface PendingProductionTask {
  task_id: string;
  source_revision: string;
  customer: string;
  project: string;
  door_type: string;
  width: number | null;
  height: number | null;
  opening: string;
  approved_at: string;
  approved_by: string;
}

export interface ProductionTimelineItem {
  id: string;
  type: string;
  title: string;
  detail: string;
  operator: string;
  created_at: string;
}
```

- [ ] **Step 2: Add typed query functions**

Add `getPendingProductionTasks`, extended `getProductionOrders`, `getProductionTimeline`, and `downloadProductionDocument` using the shared authenticated Axios instance.

- [ ] **Step 3: Add a print helper that preserves authentication**

Fetch HTML using Axios, create a `Blob` URL, open it in a new window, and revoke the URL after the print window closes. Do not use a naked API URL that loses the Authorization header.

- [ ] **Step 4: Run targeted lint and commit**

Run:

```bash
npx eslint src/lib/productionApi.ts src/lib/productionTypes.ts
```

Expected: no errors.

Commit:

```bash
git add frontend/src/lib/productionApi.ts frontend/src/lib/productionTypes.ts
git commit -m "Add production workbench client APIs"
```

### Task 6: Pending-Release List and Combined Filters

**Files:**
- Create: `frontend/src/components/production/PendingReleaseList.tsx`
- Create: `frontend/src/components/production/ProductionFilters.tsx`
- Modify: `frontend/src/components/production/ProductionReleaseButton.tsx`
- Modify: `frontend/src/components/production/ProductionOrderList.tsx`
- Modify: `frontend/src/app/production/page.tsx`

- [ ] **Step 1: Build the compact pending-release table**

Render the approved task fields in a dense fixed table above formal orders. Show a read-only `待下达` status for all production users and render `ProductionReleaseButton` only for `production.sales`.

- [ ] **Step 2: Make release completion refresh both lists**

Add `onReleased?: () => void` and `compact?: boolean` props to `ProductionReleaseButton`. On success, call `onReleased` after showing the generated production number.

- [ ] **Step 3: Build combined order filters**

Use controlled fields for text, stage, status, owner, shortage, due-from and due-to. Provide explicit “查询” and “清空” commands; do not request on every keystroke.

- [ ] **Step 4: Enrich production-order rows**

Add owner, progress, latest update and due warning. Keep table widths stable with `table-layout: fixed`, ellipsis for long project names and title tooltips for full content.

- [ ] **Step 5: Compose the mixed workbench**

Load pending tasks, dashboard and formal orders together. Place pending release first, filters second, formal list third and selected detail last. Maintain selected order when refreshing unless it no longer exists.

- [ ] **Step 6: Run lint/build and commit**

Run:

```bash
npx eslint src/app/production src/components/production src/lib/productionApi.ts src/lib/productionTypes.ts
npm run build
```

Expected: lint passes and `/production` builds successfully.

Commit:

```bash
git add frontend/src/app/production/page.tsx frontend/src/components/production frontend/src/lib/productionApi.ts frontend/src/lib/productionTypes.ts
git commit -m "Build mixed production order workbench"
```

### Task 7: Expanded Dashboard, Timeline and Document Actions

**Files:**
- Create: `frontend/src/components/production/ProductionTimeline.tsx`
- Create: `frontend/src/components/production/ProductionDocumentActions.tsx`
- Modify: `frontend/src/components/production/ProductionDashboard.tsx`
- Modify: `frontend/src/components/production/ProductionOrderDetail.tsx`

- [ ] **Step 1: Expand dashboard metrics**

Render the eleven approved metrics in responsive groups: pending/alerts first, production stages second, completion last. Use red only for overdue and shortage, amber for near due, green for completed and neutral styling elsewhere.

- [ ] **Step 2: Add timeline tab**

Fetch timeline only when the tab first opens. Render time, action, operator and detail in reverse chronological order with stable row heights.

- [ ] **Step 3: Add document actions per tab**

Place Excel and print icons in BOM, purchase/inventory, cutting, quality and shipment sections. Disable commands until the corresponding record exists, and display backend errors through the existing feedback modal.

- [ ] **Step 4: Add high-risk confirmations**

Use a shared confirmation panel for withdraw, void and shipment outflow. The confirmation text must include the production or shipment number and the operation consequence.

- [ ] **Step 5: Improve operational summaries**

Show BOM item count, purchase arrival ratio, cutting completion ratio, completed operation count, latest quality result and finished-good state in the order overview.

- [ ] **Step 6: Run lint/build and commit**

Run:

```bash
npx eslint src/app/production src/components/production
npm run build
```

Expected: no targeted lint errors and production build succeeds.

Commit:

```bash
git add frontend/src/components/production frontend/src/app/production/page.tsx
git commit -m "Enrich production progress and documents"
```

### Task 8: Full Regression, Deployment Notes and Push

**Files:**
- Modify only files required by failures caused by this feature.

- [ ] **Step 1: Run production and security tests serially**

Run:

```bash
cd backend
py -3 test_production_workbench.py
py -3 test_production_mvp.py
py -3 test_security_phase1.py
```

Expected: all pass. Do not run tests that mutate the shared user fixture concurrently.

- [ ] **Step 2: Run existing functional regressions**

Run CAD, line-art, quote and render tests serially:

```bash
py -3 test_cad_new_options.py
py -3 test_cad_line_art.py
py -3 test_line_art_extraction.py
py -3 test_quote_template_renderer.py
py -3 test_render_background_task.py
py -3 test_render_provider_urls.py
```

Expected: existing passing suites remain green. Record the known legacy `test_data_safety.py` mismatch separately unless this feature changes image persistence.

- [ ] **Step 3: Run frontend verification**

Run:

```bash
cd frontend
npx eslint src/app/production src/components/production src/lib/productionApi.ts src/lib/productionTypes.ts
npm run build
```

Expected: lint passes and `/production` is included in the successful Next.js build.

- [ ] **Step 4: Inspect the final diff**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; user logs, backups and local images remain unstaged.

- [ ] **Step 5: Commit and push both active branches**

```bash
git add backend/main.py backend/production_database.py backend/production_document_service.py backend/production_models.py backend/production_routes.py backend/test_production_workbench.py frontend/src/app/production/page.tsx frontend/src/components/production frontend/src/lib/productionApi.ts frontend/src/lib/productionTypes.ts
git commit -m "Expand production fulfillment workbench"
git push origin HEAD:codex/fix-cloud-quote-exports HEAD:main
```

- [ ] **Step 6: Verify remote refs**

Run:

```bash
git ls-remote --heads origin main codex/fix-cloud-quote-exports
```

Expected: both branches point to the final implementation commit.
