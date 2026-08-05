# 简版生产履约系统实施计划

日期：2026-08-05

设计依据：`docs/superpowers/specs/2026-08-05-production-fulfillment-mvp-design.md`

## 目标

在不修改 CAD 绘图算法、报价计算和效果渲染协议的前提下，增加一套可以从终审图纸下达到发货的简版生产履约流程。

## 任务 1：建立生产模块配置和 SQLite 数据层

文件：

- 新增 `backend/production_database.py`
- 修改 `backend/config.py`
- 新增 `backend/test_production_database.py`

内容：

- 配置 `production.db` 和 `production_files` 路径。
- 初始化生产订单、事件、物料、BOM、采购、库存流水、下料单、排单、工序、质检、成品和发货表。
- 开启外键、事务和行字典读取。
- 实现生产单号、成品编号和发货单号生成。
- 验证数据库重启后数据仍可读取。

## 任务 2：增加多业务权限并保持旧账号兼容

文件：

- 修改 `backend/auth.py`
- 修改 `backend/database.py`
- 修改 `backend/models.py`
- 修改 `backend/main.py`
- 修改 `frontend/src/lib/types.ts`
- 修改 `frontend/src/hooks/useAuth.tsx`
- 修改 `frontend/src/lib/api.ts`
- 修改 `frontend/src/app/dashboard/page.tsx`
- 扩展 `backend/test_auth.py`

内容：

- 用户数据增加可选 `permissions` 数组。
- 没有权限数组的旧账号按原角色映射默认生产权限。
- 增加后端 `require_permissions` 检查。
- 登录和验证响应返回安全的权限数组。
- 后台用户管理支持多选生产权限。
- 超级管理员自动拥有全部生产权限。

## 任务 3：实现生产订单和冻结快照

文件：

- 新增 `backend/production_models.py`
- 新增 `backend/production_routes.py`
- 修改 `backend/main.py`
- 新增 `backend/test_production_api.py`

内容：

- 注册 `/api/production` 路由。
- 终审通过任务可以下达生产，报价可为空。
- 使用现有 CAD 生成函数固化 DXF 副本，不修改绘图算法。
- 保存任务、表单、图片引用和报价信息快照。
- 防止同一终审版本重复下达。
- 支持列表、详情、复制、下料前撤回、暂停、恢复和作废。
- 所有关键动作写操作事件。

## 任务 4：实现生产物料与手工 BOM

文件：

- 修改 `backend/production_database.py`
- 修改 `backend/production_routes.py`
- 修改 `backend/production_models.py`
- 扩展 `backend/test_production_api.py`

内容：

- 生产物料 CRUD 和启用/停用。
- BOM 明细手工新增、修改和删除。
- BOM 从草稿发布。
- BOM 发布前可编辑，发布后用于下料和领料。
- 不实现 BOM 自动生成。

## 任务 5：实现简单采购与库存流水

文件：

- 修改生产后端三个模块。
- 扩展生产 API 测试。

内容：

- 手工采购单及采购明细。
- 草稿、已下单、部分到货和已完成状态。
- 到货入库、生产领料、退料、报废和盘点调整。
- 库存由流水汇总，不允许直接覆盖。
- 生产订单手工维护缺料状态。

## 任务 6：实现综合下料、排单和固定工序

文件：

- 修改生产后端三个模块。
- 扩展生产 API 测试。

内容：

- 已发布 BOM 生成唯一综合下料单。
- 下料单逐项更新实际数量、人员和状态。
- 排单保存计划开始、计划完成、生产人、缺料状态和负责人。
- 初始化固定工序，可将工序标记待开始、进行中、已完成或不适用。
- 主阶段随业务动作更新。

## 任务 7：实现成品质检、入库和发货

文件：

- 修改生产后端三个模块。
- 扩展生产 API 测试。

内容：

- 完成必要工序后提交成品质检。
- 不合格退回指定工序，合格后允许入库。
- 生成唯一成品编号和库存流水。
- 发货单可合并多个已入库生产订单。
- 支持出库、运输中、签收和完成。
- 禁止未入库订单发货和单樘门重复加入有效发货单。

## 任务 8：实现生产前端 API 和类型

文件：

- 新增 `frontend/src/lib/productionTypes.ts`
- 新增 `frontend/src/lib/productionApi.ts`

内容：

- 覆盖总览、订单、物料、BOM、采购库存、下料排单、工序、质检入库和发货接口。
- 沿用现有 Axios 鉴权和统一错误处理。

## 任务 9：实现生产履约页面

文件：

- 新增 `frontend/src/app/production/layout.tsx`
- 新增 `frontend/src/app/production/page.tsx`
- 新增 `frontend/src/components/production/ProductionDashboard.tsx`
- 新增 `frontend/src/components/production/ProductionOrderList.tsx`
- 新增 `frontend/src/components/production/ProductionOrderDetail.tsx`
- 新增 `frontend/src/components/production/ProductionMaterials.tsx`
- 修改 `frontend/src/app/globals.css`（仅在必要时增加打印样式）

内容：

- 单一生产履约页面，使用标签页组织完整流程。
- 总览卡片点击筛选。
- 订单详情中完成 BOM、采购库存、下料排单、工序、质检和发货。
- 所有保存和失败动作给出明确反馈。
- 图片和长表格保持可查看，不重做现有页面设计。

## 任务 10：增加导航和终审下达入口

文件：

- 修改 `frontend/src/lib/types.ts`
- 修改 `frontend/src/components/TopNav.tsx`
- 修改 `frontend/src/middleware.ts`
- 修改 `frontend/src/app/dashboard/page.tsx`

内容：

- 顶部增加“生产履约”，现有订单前期入口保持原样。
- `/production` 加入登录保护。
- 已通过任务显示“下达生产订单”。
- 下达窗口确认客户、项目、交期、备注和是否带入报价。
- 下达成功后可直接打开对应生产订单。

## 任务 11：完整验证和回归

命令：

- `python backend/test_production_database.py`
- `python backend/test_production_api.py`
- `python backend/test_auth.py`
- 运行现有后端测试脚本
- `npm run lint`
- `npm run build`

验证：

- 走通终审下达、手工 BOM、采购入库、下料、排单、全部工序、质检、入库和发货。
- 验证普通账号权限隔离和多权限组合。
- 验证现有图纸、CAD、报价和效果渲染构建及关键测试不回归。
- 检查 Docker 数据卷路径和云端重建后的持久化。

## 提交策略

按可回滚的功能块提交：

1. 生产数据库与权限基础。
2. 生产后端完整流程。
3. 生产前端与下达入口。
4. 测试、文档和收尾。

每次提交只包含本次生产模块文件，不纳入现有未跟踪日志、备份和用户文件。
