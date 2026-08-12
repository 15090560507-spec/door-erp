# Door ERP 与 ERPNext 生产集成设计

## 目标

Door ERP 继续作为销售和技术资料系统；ERPNext 作为生产履约的唯一业务系统。销售不离开 Door ERP，技术、采购、仓储、生产和质检人员在 ERPNext 办理标准单据。

## 系统边界

Door ERP 负责图纸录入、CAD、报价、终审、销售确认和生产订单下达。终审通过后，Door ERP 冻结 DXF 和表单参数，并将订单同步到 ERPNext。

ERPNext 负责客户、物料、BOM、请购、采购、库存、工单、领料、完工入库、质检和发货。Door ERP 不再维护第二套 BOM、库存或采购台账。

## 第一阶段闭环

1. 销售在 Door ERP 对终审通过的图纸点击“下达至 ERPNext”。
2. Door ERP 生成本地冻结记录，防止同一终审版本重复下达。
3. 后端使用 ERPNext API 创建或复用客户、订单专用成品物料和销售订单草稿。
4. 后端上传冻结 DXF、门参数 JSON，以及可用的图纸预览；报价快照包含在门参数 JSON 中。
5. Door ERP 展示同步状态、ERPNext 单号、原始错误摘要和“重试同步/进入 ERPNext”入口。
6. 技术人员在 ERPNext 手工建立并审核 BOM；之后使用 ERPNext 原生的物料请购、采购、收货、领料、工单、完工、质检和发货流程。

## 同步与幂等

- Door ERP 每个冻结订单建立一条 `erpnext_syncs` 记录。
- 使用 Door ERP 生产单号写入 ERPNext 销售订单 `po_no`，作为远端幂等标识。
- 再次同步先查本地映射，再按 `po_no` 查询 ERPNext；不会盲目重复创建销售订单。
- 本地订单已冻结但远端失败时保留“同步失败”状态和脱敏错误，可手工重试。
- API Key 和 Secret 仅从后端环境变量读取，不返回浏览器、页面状态或日志。

## ERPNext 主数据策略

- 客户按名称查询；不存在时自动创建公司客户。
- 每樘冻结门创建一个订单专用成品物料，编码为 `DOOR-<Door ERP 生产单号>`，避免不同尺寸、款式共用 BOM。
- 公司、客户组、区域、物料组可由环境变量指定；未设置时后端读取 ERPNext 中第一个可用的标准值。
- 销售订单保持草稿，不自动提交，不自动创建 BOM 或工单。

## 部署与入口

- Door ERP 继续使用 `https://124.223.87.161/`。
- ERPNext 保持已创建的站点名 `erp.124.223.87.161.nip.io`，临时公网入口使用 `https://124.223.87.161:8443/`；Door ERP 后端通过共享 Docker 网络连接代理，避免外部网络对 `nip.io` TLS 握手的重置。
- Door ERP 的生产管理页面仅展示同步订单和状态；“进入 ERPNext 办理”在新标签打开 ERPNext 对应销售订单。
- ERPNext 保持独立 Compose 项目、MariaDB、Redis、卷和备份。Door ERP 与 ERPNext 仅共享 Nginx 反向代理网络。

## 非目标

本阶段不实现单点登录、不迁移旧生产数据、不自动编制 BOM、不实现双向细粒度实时状态映射，也不改动 CAD 绘图或报价逻辑。

## 验收

使用一樘终审通过的门：Door ERP 成功创建 ERPNext 草稿销售订单，ERPNext 中可见 DXF 与参数附件，Door ERP 页面可显示 ERPNext 单号并可打开该订单；网络或凭证错误时，页面能显示失败原因并可重试。
