# 门框下料模块设计

## 1. 目标

在现有 Door ERP 中增加独立的“下料”模块，把已确认的门框 DXF 生成规则接入正式系统。模块以订单为单位，一次计算左框、右框、上框、下框及各自骨架和外皮，并由同一个 Geometry JSON 驱动 2D、整套 DXF 和 BOM。

首版以 `Door_Frame_DXF_Generator_v1.4.3_CUT_OUTER_Rebuild.zip` 为生产规则基准。已确认的截面尺寸、槽位、孔位、外皮端部异形和上下框模板不重新设计，只进行结构化适配、校验和系统集成。

## 2. 首版范围

### 2.1 包含

- 顶部导航新增“下料”，位于“图纸终审”和“效果渲染”之间。
- 正式路由为 `/door-cad/frame`。
- 支持关联终审图纸，也支持独立新建下料项目。
- 一套订单同时生成八个零件：左、右、上、下框的骨架和外皮。
- 2D 整套总览。
- 每个零件的折弯截面、展开截面和展开平面三联图。
- 唯一 Geometry JSON。
- 整套集合 DXF。
- BOM 页面和 BOM Excel。
- 项目 JSON 保存、载入、导入和导出。
- 生产校验、明确错误提示和 Docker 部署验证。

### 2.2 不包含

- 3D 模型和 3D 交互。
- 当前零件 DXF 下载。
- 全部单件 DXF ZIP。
- 未确认的旧工艺扩展。
- 门扇、气窗、门套、门头门柱等其他下料模块。

## 3. 接入原则

v1.4.3 不作为独立 Flask 服务运行，也不直接复制旧页面。采用“保留规则、重构接入”的方式：

- 复用 `generator.py` 中的骨架、外皮、槽位、孔位、镜像、端部异形和 DXF 规则。
- 复用 `top_bottom_generator.py` 的独立上下框规则。
- 复用 `all_frames_generator.py` 的整套排版经验。
- 复用 `templates_data/new_lr_process_55_62_template.dxf` 和 `templates_data/top_bottom_double_door_template.dxf`。
- 复用样例 DXF 和测试 JSON 作为回归基准。
- 不复用 Flask `app.py`、旧 HTML 页面、固定输出目录和本地启动脚本。

现有整门 CAD、报价、图纸录入和审核逻辑不被本模块修改。新模块使用独立路由、服务和数据模型，失败时不能影响原有 CAD 生成服务。

## 4. 系统架构

### 4.1 前端

```text
frontend/src/app/door-cad/frame/
frontend/src/components/door-cad/
├── ParameterPanel
├── Overview2D
├── PartDetail2D
├── BomTable
├── ProductionValidation
└── ProjectActions
```

新增模块名“下料”，更新顶部导航、模块类型和中间件保护范围。页面只负责参数输入、状态展示和 Geometry 可视化，不在浏览器中重复计算加工尺寸。

### 4.2 后端

```text
backend/door_cad/
├── api/
│   ├── frame.py
│   ├── dxf.py
│   ├── bom.py
│   └── projects.py
├── models/
│   ├── inputs.py
│   └── geometry.py
├── rules/
│   ├── frame_new_skeleton.py
│   ├── frame_new_skin.py
│   ├── top_frame.py
│   ├── bottom_frame.py
│   └── opening.py
├── geometry/
│   ├── unfold.py
│   ├── fold.py
│   ├── holes.py
│   ├── mirror.py
│   ├── clipping.py
│   └── validation.py
├── exporters/
│   ├── dxf_exporter.py
│   └── bom_excel.py
└── templates/
```

后端沿用项目 FastAPI、认证方式和 Docker 部署，不新增独立服务端口。

## 5. 唯一数据源

数据流固定为：

```text
订单参数
→ v1.4.3 规则适配器
→ Geometry JSON
→ 2D / DXF / BOM
```

禁止 2D、DXF 和 BOM 分别重新计算尺寸。

### 5.1 ProjectGeometry

```text
ProjectGeometry
├── schemaVersion
├── ruleVersion
├── project
├── inputs
├── assembly
├── parts
└── validation
```

`ruleVersion` 首版固定记录为 `frame-new-v1.4.3`，用于追溯生产文件使用的规则版本。

### 5.2 PartGeometry

每个零件至少包含：

- 部件编号、名称、位置和骨架/外皮类型。
- 材质、厚度、长度和数量。
- 展开宽度和连续闭合外轮廓。
- 内孔、工艺切缝、正槽和反槽。
- 展开尺寸链。
- 折弯节点、折弯方向和角度。
- 折弯后截面轮廓。
- 加工标注和 BOM 信息。
- 镜像、裁剪和来源规则信息。

内部计算至少保留 `0.001mm`，界面和 DXF 显示最多一位小数。

## 6. 已确认加工规则

### 6.1 新工艺骨架

- 基准展开宽 `289mm`。
- 板厚 `2.0mm`。
- 正面槽 `126、178`。
- 反面槽 `13、63、113、198、219、276`。
- 展开链 `13/50/50/13/52/20/21/57/13`。
- 固定孔算法：首孔距端 `15mm`，尾孔距端 `15mm`，中间均分且最大间距不超过 `540mm`。
- 合页位置和内部孔规则沿用 v1.4.3。

### 6.2 新工艺外皮

- 基准展开宽 `324.8mm`。
- 板厚 `0.8mm`。
- 正面槽 `139.3、181.9、190.5`。
- 反面槽 `14.5、68.5、126.5、200.3、211.3、247.3、308.3`。
- 展开链 `14.5/54/58/12.8/42.6/8.6/9.8/11/36/61/16.5`。
- 端部异形范围 `x=76～239.8mm`，深度 `47mm`。
- 端部异形属于真实 `L01_OUTER_CUT` 外轮廓，不是内切割线或装饰线。
- 被端部异形切除区域中的报槽线必须裁剪到真实材料边界。

### 6.3 左右框

- 右框由左框完整几何镜像生成。
- 外轮廓、孔、槽、切缝和标注测量点均镜像。
- 文字不得镜像。
- 合页内部上下语义保持不变。

### 6.4 上下框

- 上框和下框是独立规则模块，禁止由侧框旋转得到。
- 首版以 `top_bottom_double_door_template.dxf` 为标准模板来源。
- 模板轮廓读取后转为参数化 Geometry，再交给 2D、DXF 和 BOM 使用。
- 上下框分别保存孔位、插销孔、锁点、开启方向和装配语义。

## 7. 页面设计

```text
顶部：项目名称｜关联终审图纸｜保存｜导入JSON｜导出JSON｜导出DXF
左侧：订单参数、框规格、工艺、板厚、组件开关
右侧：[整套总览] [单件详图] [BOM]
```

### 7.1 整套总览

默认显示八个零件缩略加工图。使用可缩放 SVG 展示，支持滚轮缩放、拖动、适应窗口和点击零件。点击零件进入单件详图。

### 7.2 单件详图

固定顺序：

```text
上：折弯截面图
中：展开截面图
下：展开平面图
```

三张图只消费同一个 PartGeometry。允许按图层隐藏和高亮加工线，但不改变真实 Geometry。

### 7.3 参数重算

参数修改后短延迟调用后端重算。页面显示“未保存修改”“计算中”“校验通过”“校验失败”。计算失败时保留上一次有效结果，并弹窗显示具体字段和错误原因。

## 8. API

```text
POST /api/door-cad/frame/calculate
POST /api/door-cad/frame/export-dxf
POST /api/door-cad/frame/export-bom
POST /api/door-cad/frame/projects
GET  /api/door-cad/frame/projects/{id}
PUT  /api/door-cad/frame/projects/{id}
```

`calculate` 返回完整 Geometry JSON。DXF 和 BOM 接口接收项目参数或已保存项目编号，在服务端重新核对规则版本和生产校验状态。

## 9. DXF

首版只提供整套集合 DXF。文件包含八个零件的三联加工图，并按固定间距排版。

必须满足：

- 使用 `ezdxf`，禁止字符串拼接 DXF。
- 使用既定 CAD 图层标准。
- 外轮廓是连续闭合轮廓。
- 正槽、反槽、切缝和切割线严格分层。
- 加工尺寸为真实 `DIMENSION`。
- 中文为真实 `TEXT/MTEXT`。
- 镜像零件文字方向正确。
- 保存后重新读取并运行 `doc.audit()`。
- 审计存在 error 时禁止下载。

默认文件名：`订单号-项目名称-门框下料图.dxf`。

## 10. BOM

BOM 页面和 Excel 包含：

- 部件编号。
- 部件名称。
- 位置。
- 骨架/外皮。
- 材质。
- 厚度。
- 展开宽度。
- 长度。
- 数量。
- 工艺。
- 备注。

默认八行。未启用某组件时不生成对应行。所有尺寸直接读取 PartGeometry。

## 11. 生产校验

### 11.1 禁止导出的错误

- 输入尺寸无效。
- 展开尺寸链与展开宽度不一致。
- 外轮廓不闭合或自交。
- 槽位、孔或切缝越界。
- 端部切除区域仍残留槽线。
- 左右镜像后孔位语义错误。
- 上下框模板缺失或无法读取。
- DXF 图层、文字样式或标注样式缺失。
- DXF 审计存在 error。
- BOM 数量与 Geometry 零件数量不一致。

### 11.2 警告

警告不直接阻止导出，但用户必须确认并留下记录。首版警告包括非标准规格、模板版本变化和缺少项目名称等非几何问题。

### 11.3 状态

```text
ERROR   禁止生产导出
WARNING 需要确认后导出
PASSED  生产校验通过
```

## 12. 测试和验收

自动测试至少覆盖：

1. v1.4.3 标准尺寸回归。
2. 非标准门高的固定孔均布。
3. 左右框完整镜像。
4. 外皮端部异形轮廓和槽线裁剪。
5. 上框、下框独立生成。
6. 八个零件全部存在且编号唯一。
7. 真实 DIMENSION 实体检查。
8. DXF 审计零错误。
9. Geometry、2D、DXF 和 BOM 尺寸一致。
10. JSON 保存和重新载入后 Geometry 完全一致。
11. 未登录访问返回 401，业务权限沿用现有系统规则。
12. Docker 环境下计算、预览和下载成功。
13. Playwright 检查桌面和窄屏下无重叠、文字可读、SVG 非空。

验收时必须使用 v1.4.3 自带参考 DXF、样例 DXF 和测试 JSON 做回归比较。未经 AutoCAD/WPS CAD 实际打开确认的文件，不标记为生产可用。

## 13. 实施边界

- 不改现有整门 CAD 算法。
- 不改报价计算逻辑。
- 不把门框规则写入前端组件。
- 不增加独立 Flask 服务和公开端口。
- 不在首版加入 3D、单件 DXF、DXF ZIP 或其他下料品类。
- 对未经确认的新工艺数据不做猜测；后续规则必须独立版本化。

## 14. 完成定义

用户能够从“下料”入口打开门框模块，输入或关联订单参数，同时查看八个零件总览，进入任一零件查看三联图，查看并导出 BOM，保存和恢复项目，并在生产校验通过后下载一份包含完整门框的集合 DXF。2D、DXF 和 BOM 对同一尺寸的结果必须一致。
