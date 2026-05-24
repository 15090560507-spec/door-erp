# 报价系统重写实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Node.js 报价系统完整重写为 FastAPI + Next.js/TypeScript/Tailwind，作为 ERP 第 6 个功能模块集成。

**Architecture:** 后端新增 `quote_database.py`（配件库/报价单/AI配置的JSON存储层）、`quote_models.py`（Pydantic模型）、`quote_routes.py`（FastAPI路由），前端新增 `/quote` 路由页面 + 6 个组件。完全复用 ERP 现有认证、设计系统、API客户端模式。

**Tech Stack:** Python FastAPI + Pydantic + Next.js 16/TypeScript/Tailwind CSS + React 19

---

## 文件结构映射

```
后端新增:
  backend/quote_models.py          # 报价相关 Pydantic 模型
  backend/quote_database.py        # 配件库 + 报价单 + AI配置 JSON 存储
  backend/quote_routes.py          # 报价相关 API 路由（挂载到 main.py）
  backend/quote_excel.py           # Excel 生成（openpyxl）

后端修改:
  backend/main.py                  # 注册 quote_routes 路由
  backend/config.py                # 新增数据文件路径常量

前端新增:
  src/lib/quoteTypes.ts            # 报价 TypeScript 类型
  src/lib/quoteApi.ts              # 报价 API 调用
  src/app/quote/page.tsx           # 报价系统主页面（左右两栏布局）
  src/app/quote/layout.tsx         # 报价页面布局（复用 DashboardLayout 模式）
  src/components/QuoteItemsTable.tsx   # 8行明细表格
  src/components/QuotePreview.tsx      # 报价单实时预览
  src/components/AccessoryModal.tsx    # 配件库弹窗（CRUD/搜索/导入导出）
  src/components/AiAnalysisPanel.tsx   # AI 图纸识别面板
  src/components/AiConfigModal.tsx     # AI 配置弹窗
  src/components/QuoteHistoryModal.tsx # 报价历史弹窗

前端修改:
  src/lib/types.ts                 # ModuleName 增加 "报价系统", MODULE_OPTIONS 增加选项
  src/middleware.ts                 # PROTECTED_PATHS 增加 "/quote"
  src/components/TopNav.tsx        # 报价系统入口按钮处理
  src/hooks/useAuth.tsx            # ModuleName 类型兼容（TS自动覆盖）
```

---

## Phase 1: 导航入口 + 基础空白页面（当前执行）

### Task 1.1: 扩展 TypeScript 类型定义

**Files:**
- Modify: `frontend/src/lib/types.ts:101-110`

- [ ] **Step 1: 更新 ModuleName 类型和 MODULE_OPTIONS**

在 `types.ts` 第 101-110 行，将 `"后台管理"` 加入联合类型，并添加 `报价系统` 到模块选项：

```typescript
// 第 101 行: ModuleName 类型增加两个值
export type ModuleName = "汇总看板" | "图纸信息录入" | "图纸绘制" | "图纸初审" | "图纸终审" | "报价系统" | "后台管理";

// 第 104-110 行: MODULE_OPTIONS 增加报价系统
export const MODULE_OPTIONS: { title: string; module: ModuleName }[] = [
  { title: "汇总看板", module: "汇总看板" },
  { title: "图纸信息录入", module: "图纸信息录入" },
  { title: "图纸绘制", module: "图纸绘制" },
  { title: "图纸初审", module: "图纸初审" },
  { title: "图纸终审", module: "图纸终审" },
  { title: "报价系统", module: "报价系统" },
];
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `cd "F:/Vibe Coding/door-erp-main/frontend" && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat: add 报价系统 to ModuleName type and MODULE_OPTIONS"
```

---

### Task 1.2: 保护 /quote 路由

**Files:**
- Modify: `frontend/src/middleware.ts:5`

- [ ] **Step 1: 添加 /quote 到受保护路由**

```typescript
const PROTECTED_PATHS = ["/dashboard", "/admin", "/quote"];
```

同时更新 matcher:

```typescript
export const config = {
  matcher: ["/dashboard/:path*", "/admin/:path*", "/quote/:path*"],
};
```

- [ ] **Step 2: 验证 middleware 语法**

Run: `cd "F:/Vibe Coding/door-erp-main/frontend" && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/middleware.ts
git commit -m "feat: protect /quote route in middleware"
```

---

### Task 1.3: 创建报价系统页面 Layout

**Files:**
- Create: `frontend/src/app/quote/layout.tsx`

```typescript
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import TopNav from "@/components/TopNav";

export default function QuoteLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F2F2F7]">
        <div className="text-center">
          <div className="w-8 h-8 mx-auto mb-3 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin" />
          <p className="text-[#8E8E93] text-sm">加载中...</p>
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="min-h-screen bg-[#F2F2F7]">
      <TopNav />
      <div className="max-w-7xl mx-auto px-6 py-6">
        {children}
      </div>
    </div>
  );
}
```

- [ ] **Step 1: 验证编译**

Run: `cd "F:/Vibe Coding/door-erp-main/frontend" && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/quote/layout.tsx
git commit -m "feat: add quote page layout with auth guard"
```

---

### Task 1.4: 创建报价系统主页面（基础空白版）

**Files:**
- Create: `frontend/src/app/quote/page.tsx`

```typescript
"use client";

export default function QuotePage() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* 左侧：编辑区 */}
      <div className="space-y-4">
        <div className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-6">
          <h2 className="text-[15px] font-semibold text-[#1C1C1E] mb-4">报价明细</h2>
          <p className="text-[13px] text-[#8E8E93]">报价表单开发中...</p>
        </div>

        <div className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-6">
          <h2 className="text-[15px] font-semibold text-[#1C1C1E] mb-4">图纸识别</h2>
          <p className="text-[13px] text-[#8E8E93]">AI 识别面板开发中...</p>
        </div>
      </div>

      {/* 右侧：预览区 */}
      <div className="space-y-4">
        <div className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-6 min-h-[600px]">
          <h2 className="text-[15px] font-semibold text-[#1C1C1E] mb-4">报价单预览</h2>
          <p className="text-[13px] text-[#8E8E93]">预览区域开发中...</p>
        </div>

        <div className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-4">
          <div className="flex gap-2">
            <button
              disabled
              className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#8E8E93]"
            >
              保存
            </button>
            <button
              disabled
              className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#007AFF] text-white opacity-50"
            >
              导出 Excel
            </button>
            <button
              disabled
              className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#8E8E93]"
            >
              导出 JPG
            </button>
            <button
              disabled
              className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#8E8E93]"
            >
              打印
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 1: 验证编译**

Run: `cd "F:/Vibe Coding/door-erp-main/frontend" && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/quote/page.tsx
git commit -m "feat: add quote page with placeholder layout"
```

---

### Task 1.5: 更新 TopNav 支持报价系统路由

**Files:**
- Modify: `frontend/src/components/TopNav.tsx:12-13,31`

当前逻辑：点击模块按钮时，非"后台管理"模块通过 `setModule` 切换（不走路由跳转）。报价系统需要独立路由 `/quote`，类似后台管理的处理方式。

- [ ] **Step 1: 修改 TopNav 点击逻辑**

在 TopNav.tsx 第 31 行，将条件从仅判断"后台管理"扩展为也判断"报价系统"：

```typescript
// 第 12 行: adminItems 保持不变
const adminItems = [...MODULE_OPTIONS, { title: "后台管理", module: "后台管理" as ModuleName }];
const items = user?.role === "超级管理员" ? adminItems : MODULE_OPTIONS;

// 第 31-34 行: 修改 onClick 逻辑
onClick={() => {
  if (item.module === "后台管理") {
    router.push("/admin");
  } else if (item.module === "报价系统") {
    router.push("/quote");
  } else {
    setModule(item.module);
  }
}}
```

- [ ] **Step 2: 验证编译**

Run: `cd "F:/Vibe Coding/door-erp-main/frontend" && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TopNav.tsx
git commit -m "feat: route 报价系统 button to /quote page"
```

---

### Task 1.6: Phase 1 集成测试

- [ ] **Step 1: 启动后端**

```bash
cd "F:/Vibe Coding/door-erp-main/backend" && python main.py
```
Expected: `Uvicorn running on http://0.0.0.0:8000`

- [ ] **Step 2: 启动前端**

```bash
cd "F:/Vibe Coding/door-erp-main/frontend" && npm run dev
```
Expected: `ready started server on http://localhost:3000`

- [ ] **Step 3: 人工验证清单**

1. 浏览器访问 `http://localhost:3000`，用 admin/admin888 登录
2. 登录后应在 TopNav 看到 `报价系统` 按钮
3. 点击 `报价系统`，应跳转到 `/quote` 页面
4. `/quote` 页面显示左右两栏布局，含占位文本和 disabled 按钮
5. 刷新页面后仍保持在 `/quote`（cookie 认证生效）
6. 直接清除 cookie 后访问 `/quote`，应被重定向到 `/` 登录页
7. 点击其他模块按钮（如汇总看板），应正常切换回 Dashboard

- [ ] **Step 4: Commit checkpoint**

```bash
git add -A
git commit -m "feat: complete Phase 1 - quote system navigation entry and blank page"
```

---

## Phase 2: 后端 — 数据层与 API（后续实施）

### Task 2.1: 新增配置路径常量

**Files:**
- Modify: `backend/config.py`
- 在 `TASKS_BACKUP_DIR` 之后新增：

```python
ACCESSORIES_DB_FILE = os.path.join(DATA_DIR, 'accessories_database.json')
QUOTES_DB_FILE = os.path.join(DATA_DIR, 'quotes_database.json')
AI_CONFIG_FILE = os.path.join(DATA_DIR, 'ai_config.json')
ACCESSORIES_BACKUP_DIR = os.path.join(BACKUP_DIR, 'accessories')
QUOTES_BACKUP_DIR = os.path.join(BACKUP_DIR, 'quotes')

for _d in (ACCESSORIES_BACKUP_DIR, QUOTES_BACKUP_DIR):
    os.makedirs(_d, exist_ok=True)
```

### Task 2.2: 创建报价 Pydantic 模型

**Files:**
- Create: `backend/quote_models.py`

包含模型：`AccessoryBase`, `AccessoryCreate`, `AccessoryResponse`, `QuoteItem`, `QuoteCreate`, `QuoteResponse`, `QuoteListResponse`, `AiConfigUpdate`, `AiConfigResponse`, `DrawingAnalysisRequest`

### Task 2.3: 创建报价数据库层

**Files:**
- Create: `backend/quote_database.py`

三个类：
- `AccessoryDatabaseManager` — 配件 CRUD + 搜索 + 导出/导入
- `QuoteDatabaseManager` — 报价单 CRUD，字段结构与原 Node.js 版对齐
- `AiConfigManager` — AI 配置读写

完全复用 `database.py` 的原子写入 + 备份模式。

### Task 2.4: 创建报价 API 路由

**Files:**
- Create: `backend/quote_routes.py`

端点：
- `GET /api/accessories` — 配件列表+搜索
- `POST /api/accessories` — 新增配件
- `DELETE /api/accessories/{id}` — 软删除配件
- `GET /api/accessories/export` — 导出配件库 JSON
- `POST /api/accessories/import` — 导入配件库 JSON
- `GET /api/quotes` — 报价单列表
- `POST /api/quotes` — 创建报价单
- `GET /api/quotes/{id}` — 报价单详情
- `DELETE /api/quotes/{id}` — 删除报价单
- `GET /api/quotes/{id}/export.xlsx` — 导出 Excel
- `GET /api/quotes/{id}/export.jpg` — 导出 JPG
- `GET /api/quotes/{id}/export.pdf` — 导出 PDF（打印用）
- `GET /api/ai-config` — 获取 AI 配置
- `POST /api/ai-config` — 保存 AI 配置
- `POST /api/drawings/analyze` — 上传图纸 AI 识别

### Task 2.5: 在 main.py 注册报价路由

**Files:**
- Modify: `backend/main.py`

```python
from quote_routes import quote_router
app.include_router(quote_router)
```

---

## Phase 3: 前端 — 组件开发（后续实施）

### Task 3.1: 创建报价 TypeScript 类型

**Files:**
- Create: `frontend/src/lib/quoteTypes.ts`

定义 `QuoteItem`, `QuoteFormData`, `Accessory`, `AiConfig`, `AnalysisResult` 等类型。

### Task 3.2: 创建报价 API 客户端

**Files:**
- Create: `frontend/src/lib/quoteApi.ts`

复用 `api.ts` 的 Axios 实例，封装所有报价相关 API 调用。

### Task 3.3: 创建 QuoteItemsTable 组件

**Files:**
- Create: `frontend/src/components/QuoteItemsTable.tsx`

8 行可编辑明细表格，支持：
- 品名型号输入 + 配件搜索建议下拉
- 宽/高/开启方向/单位/单价输入
- 选中配件自动带出单位、单价
- 开启方向自动标准化（复用原 app.js 的 normalizeOpenDirection 逻辑）

### Task 3.4: 创建 QuotePreview 组件

**Files:**
- Create: `frontend/src/components/QuotePreview.tsx`

报价单实时预览，格式参照原 index.html 的预览模板：
- 公司名称标题
- 客户/项目/日期元数据
- 8 行明细表格（序号、品名、规格、方向、单位、数量、单价、总金额）
- 合计金额 + 中文大写金额
- 底部条款文字

### Task 3.5: 创建 AccessoryModal 组件

**Files:**
- Create: `frontend/src/components/AccessoryModal.tsx`

全屏 Modal，内容包含：
- 新增配件表单（名称、类别、型号、关键词、单位、单价）
- 搜索框（实时过滤）
- 配件列表（每行含删除按钮）
- 导出/导入按钮

### Task 3.6: 创建 AiConfigModal 组件

**Files:**
- Create: `frontend/src/components/AiConfigModal.tsx`

配置 AI 接口的 Modal：
- Base URL、Endpoint Path、API Key、模型名
- 识别提示词 textarea

### Task 3.7: 创建 AiAnalysisPanel 组件

**Files:**
- Create: `frontend/src/components/AiAnalysisPanel.tsx`

图纸识别面板：
- 文件上传（JPG/PNG）
- 上传并识别按钮
- 识别结果显示（客户/项目/尺寸/明细数）
- 应用识别结果按钮（回填到表单）
- JSON 原始输出

### Task 3.8: 创建 QuoteHistoryModal 组件

**Files:**
- Create: `frontend/src/components/QuoteHistoryModal.tsx`

报价记录列表 Modal：
- 按时间倒序排列
- 点击载入表单
- 右侧删除按钮

### Task 3.9: 组装报价主页面

**Files:**
- Modify: `frontend/src/app/quote/page.tsx`

替换 Phase 1 占位内容为真实组件，完整左右两栏布局：
- 左侧：报价表单 + AI 图纸识别面板
- 右侧：预览面板 + 操作按钮行（保存/导出Excel/导出JPG/打印）

### Task 3.10: 实现中文大写金额工具函数

**Files:**
- Create: `frontend/src/lib/toChineseAmount.ts`

将原 app.js 的 `toChineseAmount` 函数移植为 TypeScript 版本。

---

## Phase 4: 导出功能（后续实施）

### Task 4.1: Excel 生成后端

**Files:**
- Create: `backend/quote_excel.py`

使用 openpyxl 复现原 generate_quote.py 逻辑：
- 读取 template.xlsx
- 填入客户/项目/日期/8行明细
- 导出为 .xlsx 文件

### Task 4.2: JPG/PDF 导出后端

**Files:**
- 扩展: `backend/quote_routes.py`

添加 JPG/PDF 导出端点。策略：
- 服务端用 Playwright 渲染 HTML 为 PDF
- Python Pillow/pdf2image 转 JPG
- 或使用 WeasyPrint 直接生成 PDF

---

## 自检清单

- [ ] 计划是否覆盖了所有 spec 要求？ 是 — 包含全部功能（报价录入、配件库、AI识别、导出Excel/PDF/JPG、打印）
- [ ] 是否有占位符/TODO？ 无
- [ ] 类型一致性？ TypeScript ModuleName 与 Python 模型字段对齐
- [ ] 是否遵循现有代码模式？ 是 — JSON Store + 原子写入 / Axios 拦截器 / Dashboard Layout 模式
- [ ] Phase 1 是否可以独立交付？ 是 — 导航入口 + 空白页面可独立验证
