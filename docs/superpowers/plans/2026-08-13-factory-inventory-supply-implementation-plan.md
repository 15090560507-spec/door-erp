# Door ERP 全厂仓库与供应流程实施计划

**目标：** 将当前依附于门樘订单的供应/仓库功能，替换为全厂公共库存、需求预留、缺口采购、来料检验、生产领退料、外协流转和成品出入库闭环。

**架构：** 保留现有门樘履约中心和 `fulfillment.db`。新增独立的库存、需求、采购和收货 repository/service/router 文件，并允许履约确认事务把同一个 SQLite 连接传给库存服务，保证“冻结技术包 + 生成需求 + 预留库存”原子完成。旧 `production_*` 页面不恢复，只参考其库存计算和测试思路。旧 `fulfillment_supplies` 在迁移期只读，切换完成后停止作为写入入口。

**技术栈：** FastAPI、SQLite、Pydantic、Next.js、React、TypeScript、Axios。

**设计依据：** `docs/superpowers/specs/2026-08-13-factory-inventory-supply-design.md`

---

## 实施原则

1. 每个任务先增加失败测试，再补最小实现，最后运行相关回归。
2. 所有确认操作使用数据库事务；库存余额只由不可变流水汇总或事务内缓存更新。
3. 已确认单据不得直接修改或删除，只能冲销并重建。
4. 新旧库存写入口不得长期并存；迁移核对完成前，新库存模块只读。
5. 普通库存不归属订单，只有需求、预留、领退料和流水可以关联生产编号。
6. 所有接口继续要求登录，第一版不增加新的细粒度权限限制。
7. 每一阶段独立提交，出现问题可以按阶段回退。

## 阶段一：库存底座

### 任务 1：建立库存域数据结构和事务仓储

**文件：**

- 新建 `backend/inventory_database.py`
- 新建 `backend/inventory_models.py`
- 新建 `backend/inventory_service.py`
- 修改 `backend/fulfillment_database.py`
- 新建 `backend/test_inventory_foundation.py`

**步骤：**

1. 增加失败测试，验证默认逻辑仓、物料唯一性、库位唯一性和重复初始化安全性。
2. 在现有 `FULFILLMENT_DB_FILE` 中创建：
   - `inventory_materials`
   - `inventory_warehouses`
   - `inventory_locations`
   - `inventory_transactions`
   - `inventory_balances`
   - `inventory_documents`
   - `inventory_document_items`
   - `inventory_migrations`
3. 为物料编码、仓库编码、仓库库位、流水来源单据建立唯一约束或索引。
4. 初始化原材料仓、配件仓、半成品仓、外协在途仓、成品仓；重复启动不得重复插入。
5. 实现 `InventoryDatabase.transaction()`，并支持接收调用方已有连接，供履约事务复用。
6. 实现不可变流水写入和余额缓存更新；禁止更新、物理删除已确认流水。
7. 运行：`cd backend && python test_inventory_foundation.py`。
8. 提交：`Build shared inventory foundation`。

### 任务 2：实现物料、仓库、库位和库存总览 API

**文件：**

- 新建 `backend/inventory_routes.py`
- 修改 `backend/inventory_models.py`
- 修改 `backend/inventory_service.py`
- 修改 `backend/main.py`
- 修改 `backend/test_inventory_foundation.py`

**接口：**

- `GET /api/inventory/materials`
- `POST /api/inventory/materials`
- `PUT /api/inventory/materials/{id}`
- `GET /api/inventory/warehouses`
- `POST /api/inventory/warehouses`
- `POST /api/inventory/warehouses/{id}/locations`
- `GET /api/inventory/balances`
- `GET /api/inventory/transactions`
- `POST /api/inventory/adjustments`
- `POST /api/inventory/adjustments/{id}/confirm`

**步骤：**

1. 先测试未登录返回 401、物料编码重复返回 409、负库存调整被拒绝。
2. 物料查询支持编码、名称、规格、分类、启用状态筛选。
3. 库存总览返回现存、预留、可用、采购在途、外协在途、最低库存和仓位。
4. 盘盈盘亏先建草稿调整单，确认后一次性写流水；禁止直接传入余额。
5. 错误响应返回中文业务原因，不返回 SQL 或文件路径。
6. 运行库存底座测试和 `backend/test_security_phase1.py`。
7. 提交：`Expose material and warehouse APIs`。

### 任务 3：建设公共仓库前端第一版

**文件：**

- 新建 `frontend/src/lib/inventoryTypes.ts`
- 新建 `frontend/src/lib/inventoryApi.ts`
- 新建 `frontend/src/components/inventory/InventoryOverview.tsx`
- 新建 `frontend/src/components/inventory/MaterialCatalog.tsx`
- 新建 `frontend/src/components/inventory/WarehouseSettings.tsx`
- 新建 `frontend/src/components/inventory/InventoryTransactions.tsx`
- 修改 `frontend/src/app/production/page.tsx`

**步骤：**

1. 把生产管理顶部工作区扩展为“门樘履约、供应需求、采购中心、仓库中心、成品与发货、基础资料”。
2. 仓库中心默认显示全厂库存，不要求选择订单。
3. 使用密集表格呈现物料、规格、仓库、库位、现存、预留、可用和在途。
4. 提供分类、仓库、低库存和关键字筛选。
5. 盘点调整必须弹出确认窗口，并显示成功/失败反馈。
6. 物料档案与仓库设置放入基础资料，不嵌套在门樘卡片中。
7. 运行：`cd frontend && npm run lint && npm run build`。
8. 提交：`Build public warehouse workbench`。

## 阶段二：需求与预留

### 任务 4：建立物料需求和预留模型

**文件：**

- 修改 `backend/inventory_database.py`
- 修改 `backend/inventory_models.py`
- 新建 `backend/requirement_service.py`
- 修改 `backend/fulfillment_database.py`
- 修改 `backend/fulfillment_models.py`
- 新建 `backend/test_inventory_requirements.py`

**步骤：**

1. 增加：
   - `material_requirements`
   - `material_requirement_items`
   - `inventory_reservations`
   - `material_component_links`
2. 给 `fulfillment_components` 增加可空 `material_id`，草稿允许为空，确认技术包前必须完成关联。
3. 技术包确认时，在同一事务内冻结版本、生成当前版本需求、按可用库存预留并计算缺口。
4. 预留顺序为要求交期、需求创建时间、生产编号；同一库存不得被两个订单重复占用。
5. 预留只改变“已预留/可用”，不改变现存。
6. 测试全量库存、部分库存、零库存、两个订单竞争、重复确认幂等和物料未关联。
7. 提交：`Generate and reserve fulfillment material requirements`。

### 任务 5：处理技术变更和需求冻结

**文件：**

- 修改 `backend/requirement_service.py`
- 修改 `backend/fulfillment_database.py`
- 修改 `backend/test_inventory_requirements.py`

**步骤：**

1. 生产变更创建新技术版本时，旧需求标记为冻结。
2. 自动释放未领用、未采购覆盖的旧预留。
3. 对已领料、已下单、部分到货项目生成影响清单，不静默冲销。
4. 新版本确认后建立新需求并重新分配可用库存。
5. 增加测试确保旧版本不能继续领料，新版本不会覆盖历史流水。
6. 提交：`Protect inventory through technical revisions`。

### 任务 6：增加供应需求 API 和前端工作台

**文件：**

- 修改 `backend/inventory_routes.py`
- 修改 `backend/inventory_models.py`
- 修改 `frontend/src/lib/inventoryApi.ts`
- 修改 `frontend/src/lib/inventoryTypes.ts`
- 新建 `frontend/src/components/inventory/SupplyRequirements.tsx`
- 修改 `frontend/src/app/production/page.tsx`

**接口：**

- `GET /api/inventory/requirements`
- `GET /api/inventory/requirements/{id}`
- `POST /api/inventory/requirements/{id}/reallocate`
- `POST /api/inventory/requirement-items/{id}/supplement`

**步骤：**

1. 列表显示生产编号、物料、需求、预留、缺口、在途、已领料和交期。
2. 提供待关联物料、部分缺料、全部缺料、待领料筛选。
3. 门樘详情只保留本门樘供应摘要和相关单据链接，不提供直接入库按钮。
4. 补料必须建立补料记录，不修改冻结版本原需求数量。
5. 运行后端需求测试和前端构建。
6. 提交：`Build supply requirement workbench`。

## 阶段三：采购与来料

### 任务 7：实现缺口池、合并采购和需求分配

**文件：**

- 修改 `backend/inventory_database.py`
- 修改 `backend/inventory_models.py`
- 新建 `backend/purchasing_service.py`
- 修改 `backend/inventory_routes.py`
- 新建 `backend/test_inventory_purchasing.py`

**步骤：**

1. 增加：
   - `purchase_demands`
   - `purchase_orders`
   - `purchase_order_items`
   - `purchase_allocations`
2. 缺口池只包含“需求量 - 已预留 - 有效采购分配量”大于零的项目。
3. 允许选择多个订单的同物料缺口合并采购，但每条采购明细保存分配来源。
4. 数量、单位、供应商、预计到货日和单价在采购单确认前可修改。
5. 采购单确认后只允许关闭、取消余量或冲销，不能覆盖历史数量。
6. 测试跨订单合并、部分采购、超额采购、取消和重复提交幂等。
7. 提交：`Build merged purchasing with demand allocation`。

### 任务 8：实现到货、来料检验和公共库存入库

**文件：**

- 修改 `backend/inventory_database.py`
- 修改 `backend/inventory_models.py`
- 新建 `backend/receiving_service.py`
- 修改 `backend/inventory_routes.py`
- 修改 `backend/test_inventory_purchasing.py`

**步骤：**

1. 增加 `receipts`、`receipt_items`、`incoming_inspections`。
2. 采购到货先登记数量和来源采购行，状态进入待检。
3. 结果支持合格、让步接收、不合格；不合格不得入可用库存。
4. 确认入库必须在同一事务内完成：写入库流水、更新余额、更新到货量、按分配补足预留。
5. 超过原需求分配的合格数量进入公共可用库存。
6. 测试部分到货、分批检验、拒收、让步接收、重复入库和超收。
7. 提交：`Connect purchasing receipts to inspected inventory`。

### 任务 9：建设采购中心和待检工作台

**文件：**

- 新建 `frontend/src/components/inventory/PurchasingCenter.tsx`
- 新建 `frontend/src/components/inventory/ReceivingWorkbench.tsx`
- 修改 `frontend/src/lib/inventoryApi.ts`
- 修改 `frontend/src/lib/inventoryTypes.ts`
- 修改 `frontend/src/app/production/page.tsx`

**步骤：**

1. 采购中心分为缺口池、采购单、到货进度三个标签。
2. 合并采购时可展开查看每个生产编号的分配数量。
3. 仓库中心增加待检、待入库列表，逐项录入合格/让步/不合格数量。
4. 所有写操作有加载状态、成功弹窗和原始业务错误信息。
5. 删除当前 `FulfillmentSupplyWorkbench` 中直接把供应事项改为已入库的操作入口。
6. 运行前端 lint/build 和后端采购测试。
7. 提交：`Build purchasing and receiving workbenches`。

## 阶段四：生产流转

### 任务 10：实现领料、退料、补料、调拨和报废

**文件：**

- 修改 `backend/inventory_database.py`
- 修改 `backend/inventory_models.py`
- 新建 `backend/material_flow_service.py`
- 修改 `backend/inventory_routes.py`
- 新建 `backend/test_inventory_material_flow.py`

**步骤：**

1. 增加 `material_issue_orders`、`material_return_orders`、`stock_transfer_orders` 和对应明细表。
2. 发料只能基于有效需求和预留，确认后扣减现存、释放预留、累计已领料。
3. 仓库按清单逐项确认数量；不要求领料人二次确认。
4. 退料上限不得超过该生产编号净领料数量，退回后恢复公共库存。
5. 报废写负向库存流水且不恢复可用量；补料生成独立补料需求。
6. 仓库/库位调拨必须在一个事务内生成成对流水。
7. 测试超领、重复发料、超退、部分退料、调拨回滚和负库存。
8. 提交：`Build production issue return and transfer flow`。

### 任务 11：实现外协在途闭环

**文件：**

- 修改 `backend/inventory_database.py`
- 修改 `backend/inventory_models.py`
- 修改 `backend/material_flow_service.py`
- 修改 `backend/receiving_service.py`
- 修改 `backend/inventory_routes.py`
- 修改 `backend/test_inventory_material_flow.py`

**步骤：**

1. 外协发出从当前仓位扣减并进入外协在途仓，记录供应商、工作包和预计返回日。
2. 外协返回必须登记到货并执行来料检验。
3. 合格件进入半成品仓；需要立即生产时仍先完成入库，再创建发料单。
4. 列表显示供应商、已发、已回、待回、不合格和逾期数量。
5. 测试部分返回、超量返回、不合格、重复返回和供应商追溯。
6. 提交：`Track subcontracted materials through inventory`。

### 任务 12：建设仓库作业台并调整门樘供应摘要

**文件：**

- 新建 `frontend/src/components/inventory/MaterialIssueWorkbench.tsx`
- 新建 `frontend/src/components/inventory/InventoryTransferWorkbench.tsx`
- 新建 `frontend/src/components/inventory/SubcontractWorkbench.tsx`
- 修改 `frontend/src/app/production/page.tsx`
- 修改 `frontend/src/lib/inventoryApi.ts`
- 修改 `frontend/src/lib/inventoryTypes.ts`

**步骤：**

1. 仓库中心增加待发料、领退料、调拨、外协在途和库存流水。
2. 待发料按交期和生产编号排序，逐项确认仓位及数量。
3. 门樘“供应与仓储”改为摘要视图：需求、预留、缺料、在途、到货、已领和退料。
4. 摘要只跳转到公共工作台对应筛选结果，不直接改库存状态。
5. 运行前端构建和物料流测试。
6. 提交：`Build warehouse operations workbench`。

## 阶段五：成品闭环与迁移切换

### 任务 13：实现成品逐樘入库和发货出库

**文件：**

- 修改 `backend/inventory_database.py`
- 修改 `backend/inventory_models.py`
- 新建 `backend/finished_goods_service.py`
- 修改 `backend/inventory_routes.py`
- 修改 `backend/fulfillment_database.py`
- 新建 `backend/test_finished_goods_inventory.py`

**步骤：**

1. 增加 `finished_goods`，以生产编号作为唯一追踪标识。
2. 只有当前版本成品质检合格的门樘才能入成品仓。
3. 成品入库必须关联成品仓和库位，并写库存流水与门樘事件。
4. 发货前校验成品已入库及财务放行；特殊放行继续保留授权记录。
5. 发货确认后按生产编号出库；重复出库返回 409。
6. 测试逐樘入库、分批发货、未质检入库、未入库发货和重复发货。
7. 提交：`Close finished goods inventory and shipment flow`。

### 任务 14：迁移现有供应和库存数据

**文件：**

- 新建 `backend/migrate_fulfillment_inventory.py`
- 新建 `backend/test_inventory_migration.py`
- 修改 `backend/inventory_database.py`
- 修改 `backend/fulfillment_database.py`
- 修改 `deploy/README.md` 或现有部署说明文件

**步骤：**

1. 迁移脚本启动前复制 `data/fulfillment.db` 到带时间戳的备份文件。
2. 从 `fulfillment_supplies` 生成可追溯的历史需求来源，不将其状态直接当作库存余额。
3. 从 `fulfillment_inventory_movements` 迁移可识别物料流水；无法匹配的记录输出迁移异常清单。
4. 从已有成品入库流水迁移 `finished_goods`，生产编号重复时停止迁移并报告。
5. 使用 `inventory_migrations` 记录来源表和来源 ID，保证脚本重复执行不重复入账。
6. 增加核对报告：旧入库/出库数量、新流水数量、余额差异、未映射物料。
7. 核对通过前，新库存页面只读；通过显式切换标记后才开放写入。
8. 提交：`Migrate fulfillment inventory safely`。

### 任务 15：完成前端切换并移除旧写入口

**文件：**

- 修改 `frontend/src/app/production/page.tsx`
- 删除 `frontend/src/components/FulfillmentSupplyWorkbench.tsx`
- 修改 `frontend/src/lib/fulfillmentApi.ts`
- 修改 `frontend/src/lib/fulfillmentTypes.ts`
- 修改 `backend/fulfillment_routes.py`
- 修改 `backend/fulfillment_database.py`
- 修改 `backend/test_fulfillment_center.py`

**步骤：**

1. 删除采购/仓库对 `fulfillment_supplies` 的直接写入 UI。
2. 将旧 `PUT /api/fulfillment/supplies/{id}` 改为 410，并给出迁移到新接口的中文提示。
3. 保留旧供应记录的只读查询，用于历史门樘追溯。
4. 门樘详情改为读取新需求、采购、领退料和库存摘要。
5. 新仓库中心成为唯一库存写入口。
6. 更新履约测试，确保旧入口不可绕过来料检验和库存流水。
7. 提交：`Switch fulfillment to shared inventory domain`。

### 任务 16：端到端验证、部署文档和发布

**文件：**

- 修改 `backend/test_fulfillment_center.py`
- 新建 `backend/test_inventory_end_to_end.py`
- 修改部署说明文档
- 仅在必要时修改 `docker-compose.yml`

**端到端场景：**

1. 两个门樘确认技术包，同时需要同一物料。
2. 公共库存只够一部分，系统按交期预留且不重复占用。
3. 剩余缺口合并采购，保留两个生产编号分配。
4. 分批到货、来料检验、入库后自动补足预留。
5. 仓库逐项发料，生产退料，外协发出和返回。
6. 工作包完成、成品质检、逐樘入库、财务放行和发货出库。
7. 每一步可从库存流水追溯来源单据、生产编号、操作人和时间。

**验证命令：**

```powershell
cd backend
python test_inventory_foundation.py
python test_inventory_requirements.py
python test_inventory_purchasing.py
python test_inventory_material_flow.py
python test_finished_goods_inventory.py
python test_inventory_migration.py
python test_inventory_end_to_end.py
python test_fulfillment_center.py
python test_security_phase1.py
python test_api.py
python test_cad_new_options.py
python test_quote_multi_door.py
python test_render_background_task.py

cd ../frontend
npm run lint
npm run build
```

**发布步骤：**

1. 执行 `git diff --check`，确认只包含库存供应相关文件。
2. 备份服务器 `data/fulfillment.db` 和 JSON 数据文件。
3. 先部署只读库存底座并执行迁移核对。
4. 核对报告无余额差异后开启新库存写入。
5. 验证 Door ERP 主页、门樘履约、公共仓库、采购、CAD、报价和效果渲染。
6. 提交最终文档：`Document shared inventory deployment`。
7. 推送 `codex/fix-cloud-quote-exports`，确认后合并到 `main`。

## 完成标准

- 仓库无需选择订单即可维护全厂物料和库存。
- 技术包确认自动形成需求、预留和缺口，不重复占用库存。
- 采购可跨订单合并，但每个数量可追溯到生产编号。
- 来料未经检验不能入公共库存。
- 仓库发料才扣减现存，退料恢复库存。
- 外协、半成品、成品均有明确仓位和不可变流水。
- 门樘详情只展示摘要，不再绕过公共库存直接改状态。
- 新旧库存余额迁移核对一致，原有 CAD、报价、效果渲染和审核流程保持可用。
