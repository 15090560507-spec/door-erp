# DXF Precise Render Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让精准模式严格读取 DXF 中门扇、门框、门套和五金的实际几何，在同一坐标变换下生成遮罩和合成图，消除部件错位及五金遮罩缺失。

**Architecture:** 在现有 DXF 分层渲染前增加几何清单和校验层，所有部件共享一个 CAD 到像素变换；AI 结果只作为同尺寸纹理源，最终始终用 DXF 遮罩裁切并回贴原坐标。普通图片精准模式继续使用确认后的像素遮罩，不伪造毫米尺寸。

**Tech Stack:** Python, ezdxf, OpenCV, NumPy, Pillow, FastAPI background tasks, React/TypeScript, pytest, existing PSD writer.

---

### Task 1: 建立 DXF 部件几何清单

**Files:**
- Create: `backend/rendering/dxf_geometry.py`
- Modify: `backend/rendering/layered_render.py`
- Modify: `backend/test_layered_render.py`

- [ ] **Step 1: 写入几何清单失败测试**

使用现有 `_sample_dxf_text()`，验证每个部件包含 CAD 边界、来源图层、正反面和同一个变换标识：

```python
result = render_layered_dxf(_sample_dxf_text(), target_long_edge=1600, include_psd=False)
manifest = result["geometry_manifest"]
assert manifest["units"] == "mm"
assert manifest["canvas"]["width"] == result["canvas_size"][0]
assert manifest["canvas"]["height"] == result["canvas_size"][1]
for role in ("panel", "frame", "trim", "hardware"):
    assert role in manifest["roles"]
    assert manifest["roles"][role]["transform_id"] == manifest["transform_id"]
```

- [ ] **Step 2: 运行测试确认清单不存在**

Run: `python -m pytest backend/test_layered_render.py -q`

Expected: 新用例因 `geometry_manifest` 不存在而失败。

- [ ] **Step 3: 实现清单数据结构和坐标转换**

在 `dxf_geometry.py` 定义：

```python
@dataclass(frozen=True)
class GeometryTransform:
    min_x: float
    max_y: float
    scale: float
    width: int
    height: int
    transform_id: str

    def point(self, x: float, y: float) -> tuple[int, int]:
        return (
            int(round((x - self.min_x) * self.scale)),
            int(round((self.max_y - y) * self.scale)),
        )
```

`build_geometry_manifest` 接收已经完成正反面筛选的分类图元，输出：

```python
{
    "units": "mm",
    "transform_id": transform.transform_id,
    "canvas": {"width": transform.width, "height": transform.height},
    "roles": {
        "panel": {"cad_bbox": [...], "pixel_bbox": [...], "layers": [...], "side_bboxes": {...}},
        "frame": {...},
        "trim": {...},
        "hardware": {...},
    },
}
```

- [ ] **Step 4: 让现有 `_Canvas` 暴露同一变换**

`layered_render.py` 不再让清单重复计算缩放。由 `_Canvas` 创建 `GeometryTransform`，绘图、裁切和清单全部使用它。所有角色的 `transform_id` 必须相同。

- [ ] **Step 5: 运行几何测试**

Run: `python -m pytest backend/test_layered_render.py -q`

Expected: 清单、画布尺寸和原有分层渲染测试全部通过。

- [ ] **Step 6: 提交几何清单**

```powershell
git add backend/rendering/dxf_geometry.py backend/rendering/layered_render.py backend/test_layered_render.py
git commit -m "feat: derive render geometry manifest from DXF"
```

### Task 2: 校验图层、轮廓和部件边界

**Files:**
- Modify: `backend/rendering/dxf_geometry.py`
- Modify: `backend/rendering/layered_render.py`
- Modify: `backend/test_layered_render.py`

- [ ] **Step 1: 增加错误图层和空轮廓测试**

构造最小 DXF，把门框放在未知图层并让门扇只有开放线段，验证返回明确错误：

```python
validation = validate_geometry_manifest(manifest, categorized)
codes = {item["code"] for item in validation["errors"]}
assert "MISSING_FRAME_GEOMETRY" in codes or "UNKNOWN_STRUCTURAL_LAYER" in codes
assert "PANEL_CONTOUR_NOT_CLOSED" in codes
```

- [ ] **Step 2: 实现结构校验**

校验结果固定为：

```python
{
    "valid": False,
    "errors": [{"code": "PANEL_CONTOUR_NOT_CLOSED", "role": "panel", "layer": "A-DOOR-PANEL", "message": "门扇轮廓未闭合"}],
    "warnings": [],
}
```

阻断错误包括：门扇或门框无有效几何、边界框为空、需要填充的主要部件没有闭合轮廓、正反面边界无法分离。门套和五金为可选角色，不存在时不阻断；存在但轮廓无效时阻断精准生成。

- [ ] **Step 3: 增加像素遮罩重叠和边界缝隙校验**

把角色遮罩转为布尔数组，统计不同结构角色的异常重叠：

```python
overlap = np.count_nonzero((panel_alpha > 0) & (frame_alpha > 0))
tolerance = max(4, int(0.0005 * panel_alpha.size))
if overlap > tolerance:
    errors.append({
        "code": "ROLE_MASK_OVERLAP",
        "role": "panel/frame",
        "message": f"门扇与门框遮罩异常重叠 {overlap} 像素",
    })
```

正常抗锯齿边缘容差不报错。

对于边界框存在包含关系且按角色规则应相邻的 `panel/frame`、`frame/trim`，分别把二值边缘膨胀 2px；膨胀后仍不接触时返回 `ROLE_BOUNDARY_GAP`。门套不存在时不检查 `frame/trim`，玻璃开孔和 DXF 中明确存在的工艺间隙不作为结构缝隙。

```python
expanded_left = cv2.dilate(left_edge, np.ones((5, 5), np.uint8))
touching = np.any((expanded_left > 0) & (right_edge > 0))
if expected_adjacent and not touching:
    errors.append({"code": "ROLE_BOUNDARY_GAP", "role": f"{left_role}/{right_role}", "message": "相邻部件边界存在异常缝隙"})
```

- [ ] **Step 4: 在精准生成前阻止无效结构**

`render_layered_dxf` 在调用 AI 前完成校验。存在错误时抛出携带 `geometry_validation` 的 `DxfGeometryValidationError`；普通快速 AI 路径不受影响。

- [ ] **Step 5: 运行校验测试**

Run: `python -m pytest backend/test_layered_render.py -q`

Expected: 有效样例通过，错误样例返回精确角色、图层和错误代码。

- [ ] **Step 6: 提交几何校验**

```powershell
git add backend/rendering/dxf_geometry.py backend/rendering/layered_render.py backend/test_layered_render.py
git commit -m "fix: validate DXF component geometry before rendering"
```

### Task 3: 用 DXF 轮廓生成精确部件和五金遮罩

**Files:**
- Modify: `backend/rendering/layered_render.py`
- Modify: `backend/rendering/dxf_geometry.py`
- Modify: `backend/test_layered_render.py`

- [ ] **Step 1: 增加遮罩边界测试**

对每个角色解码 PNG alpha，验证非透明像素边界与清单 `pixel_bbox` 的差值不超过 2px，所有角色层尺寸相同：

```python
for role in ("panel", "frame", "trim", "hardware"):
    layer = cv2.imdecode(np.frombuffer(result["layer_pngs"][role], np.uint8), cv2.IMREAD_UNCHANGED)
    assert layer.shape[:2] == (height, width)
    ys, xs = np.where(layer[..., 3] > 0)
    actual = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    expected = result["geometry_manifest"]["roles"][role]["pixel_bbox"]
    assert max(abs(a - b) for a, b in zip(actual, expected)) <= 2
```

- [ ] **Step 2: 保留闭合图元的真实填充轮廓**

生成遮罩时分别处理闭合多段线、HATCH、圆、弧和块内实体。主要部件只填充闭合轮廓；轮廓线另放 `outline` 层，不用粗描边扩大结构遮罩。

- [ ] **Step 3: 修正五金块遮罩**

对 `INSERT` 先通过 `virtual_entities()` 展开并保留块变换后的实际坐标。五金遮罩合并：

1. 块内闭合轮廓填充；
2. 块内开放线按实际线宽栅格化；
3. 仅在块完全没有可渲染图元时，使用以插入点为中心的小型后备圆，并写入 warning。

不得用连接多个控制点的宽松外包多边形作为默认遮罩。

- [ ] **Step 4: 保证 AI 结果只在原遮罩中出现**

AI 输出先统一缩放到完整画布，再组合原始 alpha：

```python
ai_rgb = np.array(ai_image.resize((canvas.width, canvas.height), Image.LANCZOS), dtype=np.uint8)
alpha = exact_role_mask[..., 3:4]
role_layer = np.concatenate([ai_rgb, alpha], axis=2)
```

最终合成使用所有同尺寸角色层，不对单独角色做二次裁剪或位置补偿。

- [ ] **Step 5: 运行遮罩和 PSD 回归测试**

Run: `python -m pytest backend/test_layered_render.py backend/test_render_precise_mode.py -q`

Expected: 遮罩边界、AI 裁切、图层尺寸和按需 PSD 测试全部通过。

- [ ] **Step 6: 提交精确遮罩**

```powershell
git add backend/rendering/layered_render.py backend/rendering/dxf_geometry.py backend/test_layered_render.py
git commit -m "fix: preserve exact DXF component masks"
```

### Task 4: 把几何校验结果传到渲染任务和页面

**Files:**
- Modify: `backend/rendering/service.py`
- Modify: `backend/rendering/database.py`
- Modify: `backend/rendering/routes.py`
- Modify: `backend/test_render_background_task.py`
- Modify: `frontend/src/lib/renderApi.ts`
- Modify: `frontend/src/app/render/page.tsx`

- [ ] **Step 1: 增加后台任务结果测试**

成功任务保存几何清单摘要；校验失败任务保存可读错误和结构化问题：

```python
assert completed["geometryValidation"]["valid"] is True
assert completed["geometryManifest"]["units"] == "mm"
assert failed["status"] == "failed"
assert failed["geometryValidation"]["errors"][0]["role"] == "frame"
```

- [ ] **Step 2: 保存任务几何元数据**

`execute_precise_render_task` 从 `render_layered_dxf` 保存：

```python
{
    "geometryManifest": result.get("geometry_manifest"),
    "geometryValidation": result.get("geometry_validation"),
}
```

捕获 `DxfGeometryValidationError` 时仍保留输入文件和参考素材，任务状态为 `failed`，错误文本包含部件名称，结构化详情放在 `geometryValidation`。

- [ ] **Step 3: 扩展前端类型**

```ts
export interface RenderGeometryValidation {
  valid: boolean;
  errors: Array<{ code: string; role: string; layer?: string; message: string }>;
  warnings: Array<{ code: string; role: string; layer?: string; message: string }>;
}
```

- [ ] **Step 4: 在精准生成区域显示结构检查**

上传或关联 DXF 后显示“DXF 结构已读取”；任务失败时逐条显示门扇、门框、门套或五金的图层/轮廓问题。不要把 DXF 毫米尺寸描述为来自预览图。

保留两个按钮：

```tsx
<button onClick={() => void submitTask("quick")}>快速 AI 生成</button>
<button onClick={() => void submitTask("precise")}>精准分区生成</button>
```

PSD 仍只在结果区点击生成，不加入提交任务流程。

- [ ] **Step 5: 验证后台任务和前端构建**

Run:

```powershell
python -m pytest backend/test_render_background_task.py backend/test_render_precise_mode.py -q
cd frontend
npm run build
```

Expected: 测试通过，构建成功。

- [ ] **Step 6: 提交任务反馈**

```powershell
git add backend/rendering/service.py backend/rendering/database.py backend/rendering/routes.py backend/test_render_background_task.py frontend/src/lib/renderApi.ts frontend/src/app/render/page.tsx
git commit -m "feat: expose DXF render geometry validation"
```

### Task 5: 第三阶段视觉与回归验证

**Files:**
- Verify only; no planned source changes.

- [ ] **Step 1: 运行全部渲染测试**

Run:

```powershell
python -m pytest backend/test_layered_render.py backend/test_render_precise_mode.py backend/test_render_background_task.py backend/test_render_provider_urls.py -q
```

Expected: 全部通过。

- [ ] **Step 2: 运行前端生产构建**

Run: `npm run build` from `frontend`.

Expected: 构建成功。

- [ ] **Step 3: 使用固定 DXF 做视觉验证**

1. 生成精准效果图，保存正面结果和各角色 PNG。
2. 检查门扇、门框、门套相邻边界无位移、空白缝或异常覆盖。
3. 检查拉手、锁具遮罩沿实际块轮廓覆盖，外围无明显多遮。
4. 以相同 DXF 分别使用两组材质参考，确认只有材质变化，几何和像素边界保持一致。
5. 点击“生成分层 PSD”后检查图层尺寸和位置；未点击时确认没有 PSD 文件。

- [ ] **Step 4: 使用普通图片做兼容验证**

上传普通线稿，确认页面说明其采用像素遮罩；确认后的精准结果不得显示虚构毫米尺寸。快速 AI 生成仍可独立使用。

- [ ] **Step 5: 单独提交视觉验证缺陷修复**

每个问题先增加固定 DXF 回归断言，再进行最小修复并提交：

```powershell
git commit -m "fix: complete precise render alignment verification"
```
