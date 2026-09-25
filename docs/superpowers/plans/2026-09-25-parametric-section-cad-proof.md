# 参数化生产剖面 CAD 概念验证实施计划

**目标：** 生成经 DXF 审计的概念验证图和实际 DXF 渲染 PNG，展示总装剖面、折弯成品截面、板材展开、方管下料、零件立面及合页联动孔。

**架构：** 使用独立 Python 生成器创建毫米制 R2010 DXF。几何和工艺元数据由小型数据类定义，绘图辅助函数只负责语义图层、标注和布局。PNG 必须从保存后的 DXF 重新读取并渲染，避免预览与 CAD 内容不一致。

## 任务 1：建立验收测试

文件：

- 新建 `tools/section_proof/test_generate_section_proof.py`

测试内容：

- DXF 单位为毫米，审计无错误。
- 必需图层、7 个零件编号和“概念验证，非生产依据”文字存在。
- `HINGE-01`、三个孔中心高度和对齐说明存在。
- 折弯板件包含 `BEND` 图元。
- 方管零件包含下料说明，但不标记为板材展开。
- PNG 存在且具有有效尺寸和非空像素。

## 任务 2：实现 DXF 基础与绘图辅助函数

文件：

- 新建 `tools/section_proof/generate_section_proof.py`

实现内容：

- 创建 R2010 毫米制文档与语义图层。
- 提供标题、矩形、折线、剖面填充、中心线、折弯线、焊缝和尺寸辅助函数。
- 使用 ASCII 图层名和零件编号；中文说明使用 DXF 文本并配置中文字体样式。

## 任务 3：绘制总装剖面与零件图组

文件：

- 修改 `tools/section_proof/generate_section_proof.py`

实现内容：

- 绘制墙体、门套外皮/折弯骨架、门框外皮/折弯骨架、门扇前后外皮/方管骨架。
- 为 6 个板件绘制成品截面、展开图和立面图。
- 为方管骨架绘制成品截面、方管下料图和立面图。
- 展开图标注分段尺寸、总展开宽、折弯线、方向和顺序。

## 任务 4：加入合页联动孔和参数表

文件：

- 修改 `tools/section_proof/generate_section_proof.py`

实现内容：

- 在剖面和立面图中表达 `HINGE-01` 穿透构件与三个垂直孔位。
- 标记门框侧与门扇侧同轴联动。
- 列出演示板厚、截面尺寸、装配间隙和非厂规警示。

## 任务 5：从 DXF 渲染 PNG 并校验

文件：

- 修改 `tools/section_proof/generate_section_proof.py`
- 生成 `docs/samples/parametric-section-proof/parametric-section-proof.dxf`
- 生成 `docs/samples/parametric-section-proof/parametric-section-proof.png`
- 生成 `docs/samples/parametric-section-proof/README.md`

实现内容：

- 保存 DXF 后重新读取。
- 使用 ezdxf Matplotlib 后端按模型空间范围渲染 PNG。
- 执行 DXF 审计、自动测试和 PNG 像素检查。
- 人工查看 PNG，确认文字、布局、线条和零件图没有重叠。

## 验证命令

```powershell
python tools/section_proof/test_generate_section_proof.py
python tools/section_proof/generate_section_proof.py
python tools/section_proof/test_generate_section_proof.py
```
