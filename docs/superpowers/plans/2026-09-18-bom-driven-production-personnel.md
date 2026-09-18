# BOM-Driven Production and Personnel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 取消人工 BOM 核验，把生产进度直接组织到 BOM 部件下，并提供按部门查看人员当前工作的简洁页面。

**Architecture:** 新增纯函数 BOM 就绪校验器，由详情、保存和发布共同调用；保留工作包表作为执行数据，但通过 `component_id` 分组到 BOM 部件下显示；人员页面直接聚合员工档案和未完成工作包，不建立重复人员表。

**Tech Stack:** Python, FastAPI, SQLite, Next.js 16, React 19, TypeScript, existing fulfillment and operations APIs, pytest-compatible backend tests.

---

### Task 1: 建立统一 BOM 自动校验器

**Files:**
- Create: `backend/bom_readiness.py`
- Modify: `backend/bom_routes.py`
- Modify: `backend/bom_generation_service.py`
- Modify: `backend/fulfillment_database.py`
- Modify: `backend/test_bom_api.py`

- [ ] **Step 1: 写入 BOM 就绪规则测试**

测试自制件无需物料档案、外购件必须匹配物料、所有行必须具备名称、分类、数量、单位和取得方式：

```python
def test_bom_readiness_rules():
    assert bom_blockers({
        "id": 1, "name": "门框骨架", "category": "骨架与型材",
        "planned_quantity": 1, "unit": "套", "acquisition_method": "内部加工",
        "procurement_mode": "make", "item_kind": "manufactured_part",
        "material_id": None, "match_status": "无需物料",
    }) == []
    blockers = bom_blockers({
        "id": 2, "name": "标配拉手", "category": "五金与开启机构",
        "planned_quantity": 1, "unit": "件", "acquisition_method": "采购",
        "procurement_mode": "purchase", "item_kind": "material",
        "material_id": None, "match_status": "待匹配",
    })
    assert any(item["field"] == "material_id" for item in blockers)
```

- [ ] **Step 2: 运行测试并确认校验器不存在**

Run: `python -m pytest backend/test_bom_api.py -q`

Expected: 新测试因 `bom_readiness` 或 `bom_blockers` 不存在而失败。

- [ ] **Step 3: 实现纯函数校验器**

`bom_readiness.py` 返回结构化阻断项，并自动给出核验状态：

```python
def bom_blockers(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers = []
    row_id = row.get("id")
    self_made = row.get("procurement_mode") == "make" or row.get("item_kind") in {"assembly", "manufactured_part"}
    for field, label in (("name", "部件名称"), ("category", "分类"), ("unit", "单位"), ("acquisition_method", "取得方式")):
        if not str(row.get(field) or "").strip():
            blockers.append({"id": row_id, "field": field, "message": f"请填写{label}"})
    if float(row.get("planned_quantity") or 0) <= 0:
        blockers.append({"id": row_id, "field": "planned_quantity", "message": "计划用量必须大于0"})
    if not self_made and not row.get("material_id"):
        blockers.append({"id": row_id, "field": "material_id", "message": "请选择物料档案"})
    return blockers

def automatic_verification_status(row: Mapping[str, Any]) -> str:
    return "已核验" if not bom_blockers(row) else "待核验"
```

- [ ] **Step 4: 在生成、保存、详情和发布处复用校验器**

- 生成或保存行后写入自动 `verification_status`。
- `_detail` 为每行附加 `blockers`，并返回扁平 `publish_blockers`。
- `publish_bom` 删除“必须人工核验”的独立判断，只检查统一校验器结果。
- 保留 `/verify` 接口兼容旧客户端，但改为重新计算并返回当前详情，不再作为发布必经步骤。

```python
detail["publish_blockers"] = [
    blocker for row in detail["rows"] for blocker in bom_blockers(row)
]
for row in detail["rows"]:
    row["blockers"] = bom_blockers(row)
    row["verification_status"] = automatic_verification_status(row)
```

- [ ] **Step 5: 验证 BOM API**

Run: `python -m pytest backend/test_bom_api.py backend/test_bom_generation.py backend/test_bom_material_flow.py -q`

Expected: 完整外购行保存后自动成为可发布状态；缺物料或数量的行阻止发布并返回具体字段。

- [ ] **Step 6: 提交自动校验**

```powershell
git add backend/bom_readiness.py backend/bom_routes.py backend/bom_generation_service.py backend/fulfillment_database.py backend/test_bom_api.py
git commit -m "refactor: validate BOM readiness automatically"
```

### Task 2: 精简 BOM 工作台交互

**Files:**
- Modify: `frontend/src/lib/bomTypes.ts`
- Modify: `frontend/src/lib/bomApi.ts`
- Modify: `frontend/src/components/BomWorkbench.tsx`

- [ ] **Step 1: 扩展 BOM 响应类型**

```ts
export interface BomBlocker {
  id?: number;
  field: string;
  message: string;
}

export interface BomRow {
  // existing fields stay unchanged
  blockers?: BomBlocker[];
}

export interface BomDetail {
  // existing fields stay unchanged
  publish_blockers: BomBlocker[];
}
```

- [ ] **Step 2: 删除人工选择核验状态**

从 `BomWorkbench` 删除 `selectedRows`、`selectedVerifiable`、`verifySelected` 和“核验选中”按钮。发布按钮只依赖：

```tsx
const blockers = detail?.publish_blockers || [];
const canPublish = Boolean(detail?.rows.length) && blockers.length === 0;
```

仍保留 BOM 行勾选框用于未来批量编辑时，必须改名为“选择行”，不得再承担核验语义；如果当前没有其他批量操作则直接删除勾选框。

- [ ] **Step 3: 把阻断原因放到对应输入项下方**

```tsx
const blockersFor = (row: BomRow, field: string) =>
  (row.blockers || []).filter((item) => item.field === field);

{blockersFor(row, "material_id").map((item) => (
  <small key={item.message} className="bom-row-error">{item.message}</small>
))}
```

顶部显示 `还有 N 项发布前问题`，点击问题时使用行 ID 滚动并聚焦到对应字段。

- [ ] **Step 4: 更新状态名称**

工作台指标把“待核验”改为“待补齐”，但 API 为兼容旧数据仍可接受 `待核验` 筛选值。自制件显示“自制资料完整”，外购件显示“外购资料完整”或具体缺项。

- [ ] **Step 5: 运行前端构建**

Run: `npm run build` from `frontend`.

Expected: 构建成功，组件中不再引用 `verifyDoorBomRows`。

- [ ] **Step 6: 提交 BOM 工作台精简**

```powershell
git add frontend/src/lib/bomTypes.ts frontend/src/lib/bomApi.ts frontend/src/components/BomWorkbench.tsx
git commit -m "feat: show automatic BOM publication blockers"
```

### Task 3: 按 BOM 部件组织工序进度

**Files:**
- Create: `frontend/src/components/production/ComponentProcessTable.tsx`
- Modify: `frontend/src/app/production/page.tsx`
- Modify: `frontend/src/lib/fulfillmentTypes.ts`
- Modify: `backend/work_package_service.py`
- Modify: `backend/fulfillment_database.py`
- Modify: `backend/test_work_package_dependencies.py`
- Modify: `backend/test_fulfillment_workflow.py`

- [ ] **Step 1: 增加工作包与 BOM 部件关联测试**

发布 BOM 后验证每个非装配工作包都有 `component_id`，同一部件可拥有多个顺序工序，装配工序关联装配总成：

```python
packages = db.fetch_all(
    "SELECT component_id, operation_code, sequence_no FROM fulfillment_work_packages WHERE door_unit_id=? ORDER BY sequence_no",
    (door_id,),
)
assert packages
assert all(row["component_id"] for row in packages)
frame_skin = [row["operation_code"] for row in packages if row["component_id"] == frame_skin_id]
assert frame_skin == ["PREPARE", "SHEAR", "BEND", "SURFACE"]
```

- [ ] **Step 2: 运行关联测试**

Run: `python -m pytest backend/test_work_package_dependencies.py backend/test_fulfillment_workflow.py -q`

Expected: 现有唯一关联通过；多工序顺序用例若失败，进入下一步补齐。

- [ ] **Step 3: 让工艺路线生成稳定的部件子工序**

在工作包生成服务中，先按 `component_id` 分组，再按模板工序创建工作包。每条工作包保存：

```python
{
    "component_id": component["id"],
    "operation_code": operation["code"],
    "name": operation["name"],
    "route": " → ".join(item["name"] for item in route_operations),
    "sequence_no": component_sequence * 100 + operation_index,
}
```

外购件不创建制造工作包，其采购、到货、备齐状态继续来自物料需求和库存记录。

- [ ] **Step 4: 统一五阶段导航并保留算料入口**

`BomWorkbench` 的三步说明和生产页阶段导航统一为：

```ts
const PRODUCTION_STAGES = [
  "生产准备",
  "算料与下料准备",
  "部件生产与装配",
  "质检入库",
  "发货完成",
] as const;
```

“算料与下料准备”继续打开现有 `CalculationWorkbench`，显示所依据的 BOM 版本和当前状态。本轮不增加算料公式；没有算料记录时显示“尚未建立算料清单”，不能跳过为已完成。

- [ ] **Step 5: 建立部件主表组件**

`ComponentProcessTable` 按技术包部件依次渲染：

- 部件父行：名称、规格、计划数量、取得方式、材料状态、总体状态；
- 子行：该 `component_id` 的工序、执行人员、当前状态和操作；
- 外购件子区域：库存已有、采购中、已到货、已备齐；
- 没有工作包的自制件：明确显示“未生成工序”，不伪装成生产中。

```ts
const worksByComponent = new Map<number, FulfillmentWorkPackage[]>();
for (const work of door.work_packages) {
  if (!work.component_id) continue;
  worksByComponent.set(work.component_id, [...(worksByComponent.get(work.component_id) || []), work]);
}
```

- [ ] **Step 6: 合并重复生产展示**

在生产页用 `ComponentProcessTable` 替换独立的“BOM部件生产表”和“工序调度”两张表。批量开始、完成、提交质检和跳过继续操作选中的子工序。拼装人员面板固定放在全部部件之后，标题统一为“拼装人员”。

- [ ] **Step 7: 验证生产流程**

Run:

```powershell
python -m pytest backend/test_work_package_dependencies.py backend/test_fulfillment_workflow.py backend/test_fulfillment_center.py -q
cd frontend
npm run build
```

Expected: 测试通过；前端只保留一张以 BOM 部件为主线的进度表。

- [ ] **Step 8: 提交部件生产表**

```powershell
git add frontend/src/components/production/ComponentProcessTable.tsx frontend/src/components/BomWorkbench.tsx frontend/src/app/production/page.tsx frontend/src/lib/fulfillmentTypes.ts backend/work_package_service.py backend/fulfillment_database.py backend/test_work_package_dependencies.py backend/test_fulfillment_workflow.py
git commit -m "feat: organize production progress by BOM component"
```

### Task 4: 精简人员与当前工作页面

**Files:**
- Modify: `backend/operations_routes.py`
- Modify: `backend/operations_models.py`
- Create: `backend/test_personnel_work.py`
- Modify: `frontend/src/lib/operationsApi.ts`
- Modify: `frontend/src/lib/operationsTypes.ts`
- Create: `frontend/src/components/production/PersonnelWorkBoard.tsx`
- Modify: `frontend/src/app/production/page.tsx`

- [ ] **Step 1: 写入人员当前工作聚合测试**

建立两个部门、三名员工和两个未完成工作包，验证返回按部门分组、每人最多显示一个当前工作，已完成工作不作为当前工作：

```python
response = client.get("/api/operations/personnel-work", headers=headers)
assert response.status_code == 200
departments = response.json()["departments"]
assert [item["name"] for item in departments] == ["下料组", "装配组"]
worker = departments[0]["employees"][0]
assert set(worker) >= {"id", "employee_no", "name", "status", "current_work"}
assert worker["current_work"]["production_no"] == "TM260001-01"
```

- [ ] **Step 2: 实现只读聚合接口**

新增 `GET /api/operations/personnel-work`。查询在职员工，并左连接状态不为 `已完成/已取消` 的工作包及门樘；优先级按 `进行中、待质检、已排单、待排单` 排序。

```python
return {
    "departments": [
        {
            "name": team or "未分部门",
            "employees": [{
                "id": row["id"],
                "employee_no": row["employee_no"],
                "name": row["name"],
                "status": "工作中" if row.get("work_id") else "空闲",
                "current_work": current_work_or_none,
            }],
        }
    ]
}
```

接口不返回下一任务、预计交期、今日完成量、负荷或工资字段。

- [ ] **Step 3: 建立前端类型和 API**

```ts
export interface PersonnelWorkEmployee {
  id: number;
  employee_no: string;
  name: string;
  status: "工作中" | "空闲";
  current_work: null | { work_package_id: number; production_no: string; operation_name: string; status: string };
}
```

- [ ] **Step 4: 增加简洁人员页面**

`PersonnelWorkBoard` 使用部门折叠区，每人一行只显示姓名、当前工作和状态。点击当前工作调用生产页已有门樘选择回调，直接打开对应 TM 门樘和工序。

- [ ] **Step 5: 运行人员测试和构建**

Run:

```powershell
python -m pytest backend/test_personnel_work.py backend/test_fulfillment_center.py -q
cd frontend
npm run build
```

Expected: 聚合测试通过，前端构建成功。

- [ ] **Step 6: 提交人员当前工作页面**

```powershell
git add backend/operations_routes.py backend/operations_models.py backend/test_personnel_work.py frontend/src/lib/operationsApi.ts frontend/src/lib/operationsTypes.ts frontend/src/components/production/PersonnelWorkBoard.tsx frontend/src/app/production/page.tsx
git commit -m "feat: add simplified personnel work view"
```

### Task 5: 第二阶段综合验证

**Files:**
- Verify only; no planned source changes.

- [ ] **Step 1: 运行 BOM 与生产回归集**

Run:

```powershell
python -m pytest backend/test_bom_api.py backend/test_bom_generation.py backend/test_bom_material_flow.py backend/test_work_package_dependencies.py backend/test_fulfillment_workflow.py backend/test_fulfillment_center.py backend/test_personnel_work.py -q
```

Expected: 全部通过。

- [ ] **Step 2: 运行前端构建**

Run: `npm run build` from `frontend`.

Expected: 构建成功。

- [ ] **Step 3: 浏览器验证生产主线**

1. 生成 BOM，缺少资料的行直接显示字段原因。
2. 补齐资料后发布按钮自动可用，无“核验选中”步骤。
3. 发布后生产页逐条对应 BOM 部件，每个自制部件下显示实际工序。
4. 外购件只显示库存和采购状态。
5. 部件全部完成后在表格末尾分配拼装人员，再进入质检和成品入库。
6. 人员页面按部门显示姓名、当前工作和状态。

- [ ] **Step 4: 单独提交验证缺陷修复**

先添加失败测试再修复，提交信息使用：

```powershell
git commit -m "fix: complete BOM production personnel verification"
```
