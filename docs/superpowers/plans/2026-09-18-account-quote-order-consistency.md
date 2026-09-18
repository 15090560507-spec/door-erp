# Account, Quote, and Order Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复销售小 A 的历史默认密码，统一门框尺寸名称，为同一樘门的报价商品行增加排序，并让订单预览与编辑使用同一套字段。

**Architecture:** 保留现有 JSON 报价存储和销售订单模型。密码通过幂等启动迁移修复；报价排序以门组内数组顺序为准；订单技术字段抽成共享定义，编辑器和摘要组件共同消费。

**Tech Stack:** Python, FastAPI, Pydantic, Next.js 16, React 19, TypeScript, lucide-react, backend script tests, frontend production build.

---

### Task 1: 迁移销售小 A 的历史默认密码

**Files:**
- Modify: `backend/database.py:400-412`
- Modify: `backend/test_data_safety.py:320-365`

- [ ] **Step 1: 写入失败测试**

在临时用户数据库中分别写入 `123`、`123456`、`123654` 和自定义密码，重新初始化 `UserDatabase` 后验证迁移结果：

```python
for old_password in ("123", "123456"):
    payload["users"]["A"]["password"] = hash_password(old_password)
    users_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    migrated = UserDatabase(str(users_path))
    check(f"users: {old_password} 自动迁移", migrated.authenticate("A", "123654") is not None)

payload["users"]["A"]["password"] = hash_password("custom-a-password")
users_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
preserved = UserDatabase(str(users_path))
check("users: 自定义密码保持不变", preserved.authenticate("A", "custom-a-password") is not None)
```

- [ ] **Step 2: 运行测试并确认 `123456` 用例失败**

Run: `python backend/test_data_safety.py`

Expected: `123456 自动迁移` 失败，其余原有数据安全检查保持通过。

- [ ] **Step 3: 实现幂等历史默认密码迁移**

在 `UserDatabase._ensure_defaults` 中仅迁移已知默认值：

```python
sales_a = users.get("A")
if sales_a:
    stored = sales_a.get("password", "")
    if stored and any(verify_password(candidate, stored) for candidate in ("123", "123456")):
        sales_a["password"] = hash_password("123654")
        changed = True
```

不得重置其他密码，不得输出密码哈希。

- [ ] **Step 4: 运行数据安全测试**

Run: `python backend/test_data_safety.py`

Expected: 全部检查通过；再次初始化数据库后 `A / 123654` 仍可登录。

- [ ] **Step 5: 提交密码修复**

```powershell
git add backend/database.py backend/test_data_safety.py
git commit -m "fix: migrate historical sales password defaults"
```

### Task 2: 统一门框宽高显示名称

**Files:**
- Modify: `backend/main.py:244-260`
- Modify: `backend/test_task_summary_search.py`
- Modify: `frontend/src/app/dashboard/page.tsx`
- Modify: `frontend/src/components/production/ProductionOrderDetail.tsx`
- Modify: `frontend/src/components/orders/ApprovedSourcePicker.tsx`

- [ ] **Step 1: 增加门框名称回归测试**

在任务摘要测试中覆盖普通输入和见光输入，两种模式都必须输出 `(门框)`：

```python
normal = create_task({**BASE_PARAMS, "use_light_size": False, "dw": 900, "dh": 2100})
clear = create_task({**BASE_PARAMS, "use_light_size": True, "light_w": 980, "light_h": 2050})
check("normal summary uses frame label", normal["size"].endswith("(门框)"), normal["size"])
check("clear summary uses frame label", clear["size"].endswith("(门框)"), clear["size"])
```

- [ ] **Step 2: 运行测试并确认普通模式仍显示洞口**

Run: `python backend/test_task_summary_search.py`

Expected: 普通尺寸用例因 `(洞口)` 失败。

- [ ] **Step 3: 更正后端摘要和前端文字**

任务摘要统一格式：

```python
size = f"{frame_width:g} x {frame_height:g} (门框)"
```

前端把 `洞口:`、`洞口总宽/高`、`洞口尺寸` 改为 `门框:`、`门框总宽/高`、`门框尺寸`。字段名 `dw/dh` 保持不变，避免破坏存量数据和 CAD 接口。

- [ ] **Step 4: 验证尺寸测试和前端构建**

Run:

```powershell
python backend/test_task_summary_search.py
cd frontend
npm run build
```

Expected: 测试全部通过，Next.js 构建成功。

- [ ] **Step 5: 提交尺寸名称修复**

```powershell
git add backend/main.py backend/test_task_summary_search.py frontend/src/app/dashboard/page.tsx frontend/src/components/production/ProductionOrderDetail.tsx frontend/src/components/orders/ApprovedSourcePicker.tsx
git commit -m "fix: label business dimensions as frame size"
```

### Task 3: 同一樘门内拖动报价商品行

**Files:**
- Modify: `frontend/src/components/QuoteItemsTable.tsx`
- Modify: `frontend/src/lib/quoteTypes.ts`
- Modify: `frontend/src/app/quote/page.tsx`
- Modify: `backend/test_quote_multi_door.py`

- [ ] **Step 1: 增加报价顺序持久化测试**

创建一张两樘门报价，把第一樘的商品顺序保存为 `锁具、主门、门套`，验证详情、门组、打印数据都保持该顺序，第二樘不受影响：

```python
first_names = [item["productName"] for item in saved["doorGroups"][0]["items"]]
second_names = [item["productName"] for item in saved["doorGroups"][1]["items"]]
assert first_names == ["锁具", "主门", "门套"]
assert second_names == ["第二樘主门", "第二樘拉手"]
assert [item["rowOrder"] for item in saved["items"]] == list(range(5))
```

- [ ] **Step 2: 运行报价测试确认现有后端顺序契约**

Run: `python -m pytest backend/test_quote_multi_door.py backend/test_quote_template_renderer.py -q`

Expected: 后端按请求数组顺序保存并输出；若测试暴露重新排序行为，先修复 `_build_quote` 再继续前端。

- [ ] **Step 3: 为商品表实现原生行拖拽**

不新增拖拽依赖。使用 `rowId` 作为稳定标识，并把源行移动到目标行：

```tsx
function moveRow(from: number, to: number) {
  if (from === to || from < 0 || to < 0 || from >= items.length || to >= items.length) return;
  const next = [...items];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  onChange(next);
}
```

每行增加 `GripVertical` 图标按钮和 `draggable` 事件。拖动状态只存在于当前 `QuoteItemsTable`，因此天然不能跨门组。

- [ ] **Step 4: 增加上移和下移辅助操作**

行操作菜单提供：

```tsx
<button disabled={index === 0} onClick={() => moveRow(index, index - 1)}>上移</button>
<button disabled={index === items.length - 1} onClick={() => moveRow(index, index + 1)}>下移</button>
```

拖拽、上移、下移都调用同一个 `moveRow`，并由页面现有 `onChange` 标记报价为未保存。

- [ ] **Step 5: 验证保存、预览和构建**

Run:

```powershell
python -m pytest backend/test_quote_multi_door.py backend/test_quote_template_renderer.py -q
cd frontend
npm run build
```

Expected: 报价测试和构建通过；手动调整后预览顺序与编辑顺序一致。

- [ ] **Step 6: 提交报价排序**

```powershell
git add frontend/src/components/QuoteItemsTable.tsx frontend/src/lib/quoteTypes.ts frontend/src/app/quote/page.tsx backend/test_quote_multi_door.py
git commit -m "feat: reorder quote items within each door"
```

### Task 4: 订单预览与编辑共用技术字段

**Files:**
- Create: `frontend/src/components/orders/orderLineFields.ts`
- Create: `frontend/src/components/orders/OrderLineDetails.tsx`
- Create: `frontend/src/components/orders/OrderAttachmentSummary.tsx`
- Modify: `frontend/src/components/orders/OrderLineEditor.tsx`
- Modify: `frontend/src/components/orders/OrderSummary.tsx`
- Modify: `frontend/src/lib/salesOrderTypes.ts`
- Modify: `backend/test_sales_orders.py`

- [ ] **Step 1: 增加订单技术详情保存测试**

创建草稿并保存完整技术字段，重新读取后验证字段未丢失：

```python
technical = {
    "trim_type": "外包套",
    "main_door_style": "铜板压花",
    "lock_type": "指纹锁",
    "handle": "A1022",
    "hinge": "暗合页",
    "material": "0.8mm不锈钢",
    "item_remark": "门框门套分体",
}
assert response.json()["order"]["lines"][0]["technical_details"] == technical
```

- [ ] **Step 2: 建立共享字段定义**

在 `orderLineFields.ts` 中只定义业务键、标签和来源回退键：

```ts
export const ORDER_LINE_TECHNICAL_FIELDS = [
  { key: "trim_type", label: "门套类型", sourceKeys: ["trim_type", "trim_style_outer", "sel_bz"] },
  { key: "main_door_style", label: "主门款式", sourceKeys: ["main_door_style", "zmks"] },
  { key: "lock_type", label: "锁具", sourceKeys: ["lock_type", "fingerprint_lock", "st_val"] },
  { key: "handle", label: "拉手", sourceKeys: ["handle", "zmls"] },
  { key: "hinge", label: "铰链", sourceKeys: ["hinge", "sel_hys"] },
  { key: "material", label: "材质", sourceKeys: ["material", "zzcl"] },
  { key: "item_remark", label: "商品行备注", sourceKeys: ["item_remark"] },
] as const;
```

- [ ] **Step 3: 建立统一只读详情组件**

`OrderLineDetails` 接收订单行和 `drawing_snapshot.params`，统一渲染门型、门框宽高、开向、颜色及共享技术字段。值解析顺序为 `technical_details`、订单行顶层字段、图纸快照回退值。

```ts
export function resolveOrderLineField(line: SalesOrderLine, key: string, sourceKeys: readonly string[]) {
  const sources = [line.technical_details || {}, line as unknown as Record<string, unknown>, line.drawing_snapshot?.params || {}];
  for (const source of sources) for (const candidate of [key, ...sourceKeys]) {
    const value = source[candidate];
    if (value !== undefined && value !== null && String(value).trim()) return String(value);
  }
  return "-";
}
```

- [ ] **Step 4: 让编辑器和摘要共同消费字段定义**

`OrderLineEditor` 用 `ORDER_LINE_TECHNICAL_FIELDS.map` 生成输入框；`OrderSummary` 用 `OrderLineDetails` 展示相同顺序和相同值。删除摘要中单独维护的 `value(params, ...)` 技术字段列表。

- [ ] **Step 5: 补齐订单级信息和附件摘要**

`OrderSummary` 的基本信息增加联系电话、商品类别，并在门樘明细后增加只读附件区。附件按现有分类展示，不复制上传逻辑：

```tsx
<div><Phone size={17} /><span>联系电话</span><strong>{order.customer_phone || "未填写"}</strong></div>
<div><Tags size={17} /><span>商品类别</span><strong>{order.product_category || "未填写"}</strong></div>
<OrderAttachmentSummary attachments={order.attachments || []} />
```

`SalesOrder` 已有 `attachments: SalesOrderAttachment[]`。`OrderAttachmentSummary` 按 `drawing_classification`、`customer_signed`、`quote_signed`、`split_drawing` 四类分组，只提供文件查看或下载；编辑页继续使用 `OrderAttachmentPanel` 上传和删除。

- [ ] **Step 6: 运行订单测试和前端构建**

Run:

```powershell
python -m pytest backend/test_sales_orders.py backend/test_sales_order_fulfillment_bridge.py -q
cd frontend
npm run build
```

Expected: 订单字段往返测试通过，前端构建成功。

- [ ] **Step 7: 提交订单字段统一**

```powershell
git add frontend/src/components/orders/orderLineFields.ts frontend/src/components/orders/OrderLineDetails.tsx frontend/src/components/orders/OrderAttachmentSummary.tsx frontend/src/components/orders/OrderLineEditor.tsx frontend/src/components/orders/OrderSummary.tsx frontend/src/lib/salesOrderTypes.ts backend/test_sales_orders.py
git commit -m "fix: align order preview and edit fields"
```

### Task 5: 第一阶段综合验证

**Files:**
- Verify only; no planned source changes.

- [ ] **Step 1: 运行后端回归集**

Run:

```powershell
python backend/test_data_safety.py
python backend/test_task_summary_search.py
python -m pytest backend/test_quote_multi_door.py backend/test_quote_template_renderer.py backend/test_sales_orders.py backend/test_sales_order_fulfillment_bridge.py -q
```

Expected: 全部通过。

- [ ] **Step 2: 运行前端生产构建**

Run: `npm run build` from `frontend`.

Expected: 构建成功且无 TypeScript 错误。

- [ ] **Step 3: 浏览器验证核心流程**

1. 用历史密码数据启动后，以 `A / 123654` 登录。
2. 普通和见光输入的任务、报价、订单都显示门框宽高。
3. 在第一樘门内把商品行拖动排序，确认第二樘门不变化。
4. 保存并重新打开报价，确认编辑、预览和导出顺序一致。
5. 打开订单预览和编辑，逐项对比技术字段和值。

- [ ] **Step 4: 把验证发现的缺陷单独提交**

先增加最小回归测试，再修复并提交：

```powershell
git commit -m "fix: complete account quote order verification"
```
