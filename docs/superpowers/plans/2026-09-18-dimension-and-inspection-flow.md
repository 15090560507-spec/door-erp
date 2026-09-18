# Dimension and Inspection Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make clear-opening dimensions propagate consistently into frame, quote, task, and order displays, while making purchase inspection and BOM verification understandable and actionable.

**Architecture:** Add one frontend frame-dimension resolver used by all area and quote calculations, plus an equivalent backend resolver for persisted task summaries. Keep purchase quality inspection separate from BOM data verification, but expose explicit prerequisites and navigation in each UI.

**Tech Stack:** Next.js 16, React 19, TypeScript, FastAPI, Python, SQLite, unittest/pytest-compatible backend tests.

---

### Task 1: Canonical effective frame dimensions

**Files:**
- Modify: `frontend/src/lib/doorAreas.ts`
- Modify: `frontend/src/components/DoorForm.tsx`
- Modify: `frontend/src/app/quote/page.tsx`
- Modify: `backend/main.py`
- Modify: `backend/test_task_summary_search.py`
- Modify: `backend/test_quote_multi_door.py`

- [ ] **Step 1: Write failing backend task-summary tests**

Add checks proving that normal mode uses `dw/dh`, while clear-opening mode derives the displayed frame size from `light_w/light_h` and section widths.

```python
light_params = dict(
    BASE_PARAMS,
    use_light_size=True,
    light_w=980,
    light_h=2050,
    fw_left_str="55/160",
    fw_right_str="55/160",
    fw_top_str="55/195",
    th_str="55/55",
    threshold_type="高低槛",
    sel_nk="内开",
    dw=900,
    dh=2100,
)
resp = client.post("/api/tasks", json={"params": light_params}, headers=HEADERS)
check("clear-opening task uses resolved frame size", resp.json().get("size") == "1300 x 2300 (门框)", resp.text)
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `python backend/test_task_summary_search.py`

Expected: the clear-opening case reports the stale `900 x 2100 (洞口)` value.

- [ ] **Step 3: Add canonical resolvers**

In TypeScript, export a resolver from `doorAreas.ts` and make `calculateDoorAreas` consume it:

```ts
function selectedSection(value: unknown, opening: unknown): number {
  const values = String(value || "0").split("/").map(Number).filter(Number.isFinite);
  const small = values.length ? Math.min(...values) : 0;
  const big = values.length ? Math.max(...values) : 0;
  return String(opening || "").includes("内开") ? big : small;
}

export function resolveFrameDimensions(params: DoorFormData) {
  if (!params.use_light_size) return { width: numeric(params.dw), height: numeric(params.dh) };
  const left = selectedSection(params.fw_left_str, params.sel_nk);
  const right = selectedSection(params.fw_right_str, params.sel_nk);
  const top = selectedSection(params.fw_top_str, params.sel_nk);
  const bottom = params.threshold_type === "吊脚" || params.has_dj ? 0 : selectedSection(params.th_str, params.sel_nk);
  return {
    width: Math.max(300, numeric(params.light_w) + left + right),
    height: Math.max(600, numeric(params.light_h) + top + bottom),
  };
}
```

Add an equivalent `_resolve_frame_dimensions(params)` in `backend/main.py`; `_task_summary_from_params` must format its returned values as `(门框)` in clear-opening mode and `(洞口)` otherwise.

- [ ] **Step 4: Route every consumer through the resolver**

`DoorForm` must display the resolved dimensions, `calculateDoorAreas` must calculate frame/outer/trim areas from them, and quote rows must continue using `calculateDoorAreas` so their dimensions match the task list and order source data.

- [ ] **Step 5: Run focused tests and frontend build**

Run:

```powershell
python backend/test_task_summary_search.py
python -m pytest backend/test_quote_multi_door.py -q
cd frontend
npm run build
```

Expected: all focused tests pass and Next.js build completes without type errors.

- [ ] **Step 6: Commit Task 1**

```powershell
git add frontend/src/lib/doorAreas.ts frontend/src/components/DoorForm.tsx frontend/src/app/quote/page.tsx backend/main.py backend/test_task_summary_search.py backend/test_quote_multi_door.py
git commit -m "fix: unify clear-opening frame dimensions"
```

### Task 2: Actionable purchase inspection

**Files:**
- Modify: `frontend/src/app/inventory/page.tsx`
- Modify: `frontend/src/components/inventory/InventoryWorkspace.tsx`
- Modify: `frontend/src/components/inventory/ReceivingWorkbench.tsx`
- Modify: `backend/test_inventory_purchasing.py`

- [ ] **Step 1: Add backend quantity-conservation coverage**

Add a test that submits quantities whose sum differs from the receipt quantity and expects a validation error; retain the existing successful inspection test for qualified and concession quantities entering inventory.

```python
response = client.post(
    f"/api/inventory/receipt-items/{item_id}/inspect",
    json={
        "qualified_quantity": 14,
        "concession_quantity": 0,
        "rejected_quantity": 0,
        "warehouse_id": warehouse_id,
        "location_id": location_id,
        "remark": "数量不守恒",
    },
    headers=auth_headers,
)
assert response.status_code == 422
```

- [ ] **Step 2: Run the focused purchasing test**

Run: `python backend/test_inventory_purchasing.py`

Expected: existing inspection behavior remains green; add backend validation only if the new case exposes a gap.

- [ ] **Step 3: Make inspection prerequisites visible**

Pass an `openWarehouseSettings` callback from `InventoryPage` through `InventoryWorkspace` to `ReceivingWorkbench`. Replace the silent disabled state with explicit copy:

```tsx
const quantityBalanced = form.qualified + form.concession + form.rejected === item.received_quantity;
const disabledReason = !form.warehouseId
  ? "暂无仓库"
  : !form.locationId
    ? "当前仓库未配置库位"
    : !quantityBalanced
      ? `检验数量合计必须等于 ${item.received_quantity}`
      : "";
```

When `disabledReason` is a missing location, show a `配置仓库与库位` button. Keep the submit button enabled only when all prerequisites pass.

- [ ] **Step 4: Verify build and purchase tests**

Run:

```powershell
python backend/test_inventory_purchasing.py
python backend/test_inventory_api.py
cd frontend
npm run build
```

Expected: tests pass and the frontend builds.

- [ ] **Step 5: Commit Task 2**

```powershell
git add frontend/src/app/inventory/page.tsx frontend/src/components/inventory/InventoryWorkspace.tsx frontend/src/components/inventory/ReceivingWorkbench.tsx backend/test_inventory_purchasing.py
git commit -m "fix: expose purchase inspection prerequisites"
```

### Task 3: Clarify BOM verification

**Files:**
- Modify: `frontend/src/components/BomWorkbench.tsx`
- Modify: `backend/test_bom_api.py`

- [ ] **Step 1: Preserve BOM verification rules with focused tests**

Confirm self-made rows are automatically `已核验`, unmatched purchased rows cannot be verified, and matched purchased rows with positive quantity can be verified.

```python
assert self_made["verification_status"] == "已核验"
assert unmatched_verify.status_code == 422
assert matched_verify.json()["bom"]["rows"][0]["verification_status"] == "已核验"
```

- [ ] **Step 2: Replace ambiguous UI wording**

Keep `待核验/已核验` as the BOM data state, but add a visible explanation near the action bar: “核验仅确认物料档案、取得方式和计划数量，不是质量检验。” For non-verifiable rows, show the concrete missing prerequisite instead of a generic waiting state.

```tsx
const verificationHint = row.procurement_mode === "make"
  ? "自制件无需物料档案"
  : !row.material_id
    ? "请先选择物料档案"
    : row.planned_quantity <= 0
      ? "计划用量必须大于 0"
      : "可勾选后核验";
```

- [ ] **Step 3: Run BOM tests and frontend build**

Run:

```powershell
python -m pytest backend/test_bom_api.py backend/test_bom_generation.py -q
cd frontend
npm run build
```

Expected: BOM tests pass and the UI compiles.

- [ ] **Step 4: Commit Task 3**

```powershell
git add frontend/src/components/BomWorkbench.tsx backend/test_bom_api.py
git commit -m "fix: clarify BOM verification workflow"
```

### Task 4: Integrated regression verification

**Files:**
- Verify only; no planned source changes.

- [ ] **Step 1: Run the combined backend regression set**

Run:

```powershell
python backend/test_task_summary_search.py
python -m pytest backend/test_quote_multi_door.py backend/test_bom_api.py backend/test_bom_generation.py -q
python backend/test_inventory_purchasing.py
python backend/test_inventory_api.py
```

Expected: all selected tests pass.

- [ ] **Step 2: Run the production frontend build**

Run: `npm run build` from `frontend`.

Expected: build exits successfully.

- [ ] **Step 3: Verify the three user workflows in the browser**

1. Enter clear-opening dimensions and confirm DoorForm, task list, quote row, and order source show the same resolved frame size.
2. Open `库存管理 → 采购待检`; confirm a configured location enables inspection, while a warehouse without locations shows the exact reason and settings action.
3. Open BOM preparation; confirm self-made rows say `自制确认`, purchased rows explain missing prerequisites, and “核验” is explicitly distinguished from quality inspection.

- [ ] **Step 4: Commit any verification-only fixes separately**

If browser verification reveals a defect, add a focused regression test, make the smallest fix, rerun the affected checks, and commit only those files with `fix: complete dimension and inspection verification`.
