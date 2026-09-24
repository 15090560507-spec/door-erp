"""
分层效果图 / PSD 生成 测试。

覆盖：
- PSD Writer：中文图层名、图层组、透明度、300 DPI 分辨率元数据、层叠顺序、图层裁切。
- 分层渲染：DXF -> PSD + JPG，正反面分组，门板/门框/门套/配件独立成层。
- AI 材质：使用假 Provider 验证 AI 结果按 CAD 蒙版映射到各部件图层；AI 失败时回退默认材质。
"""
import io
import os
import sys
from functools import lru_cache

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import numpy as np
import ezdxf
import pytest
from PIL import Image
from psd_tools import PSDImage
from psd_tools.constants import Resource

from rendering.psd_writer import PsdNode, write_psd
from rendering.layered_render import render_layered_dxf
from rendering.layered_render import DxfGeometryValidationError
from rendering.dxf_geometry import build_geometry_manifest, make_geometry_transform, validate_geometry_manifest
from cad_preview import Primitive
import rendering.layered_render as layered_render
from main import build_cad_params
from models import CADRequest
from drawing import run_integrated_system

PASSED = 0
FAILED = 0


def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"[PASS] {name}")
    else:
        FAILED += 1
        print(f"[FAIL] {name}  {detail}")


@lru_cache(maxsize=2)
def _sample_dxf_text():
    req = CADRequest(door_type="单门", sel_kx="右开", sel_nk="内开", dw=1500, dh=2400,
                     zmls="铝雕圆形拉手", fmls="无", handle_size="150*300", fingerprint_lock="无")
    info, checks, params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, params)
    assert buffer, f"CAD 生成失败: {msg}"
    return buffer.getvalue()


@lru_cache(maxsize=1)
def _a1022_dxf_text():
    req = CADRequest(
        door_type="对开门",
        sel_kx="右开",
        sel_nk="内开",
        dw=1500,
        dh=2400,
        zmls="A1022",
        fmls="无",
        fingerprint_lock="无",
    )
    info, checks, params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, params)
    assert buffer, f"A1022 CAD 生成失败: {msg}"
    return buffer.getvalue()


def _rgba(r, g, b, a=255):
    return Image.new("RGBA", (40, 30), (r, g, b, a))


def _small_rgba(r, g, b, a=255):
    """只在右下角 10x8 区域有内容，其余透明。"""
    img = Image.new("RGBA", (40, 30), (0, 0, 0, 0))
    for x in range(30, 40):
        for y in range(22, 30):
            img.putpixel((x, y), (r, g, b, a))
    return img


def test_psd_writer():
    nodes = [
        PsdNode("01_订货单信息", children=[
            PsdNode("尺寸标注", _small_rgba(10, 10, 10)),
            PsdNode("表格与文字", _small_rgba(20, 20, 20)),
        ]),
        PsdNode("02_正面效果", children=[
            PsdNode("门板", _rgba(180, 120, 40)),
            PsdNode("门框", _rgba(80, 80, 80)),
        ]),
        PsdNode("04_CAD轮廓", _small_rgba(30, 30, 30)),
        PsdNode("07_白色背景", _rgba(255, 255, 255)),
    ]
    data = write_psd(nodes, (200, 150), dpi=300)
    check("psd writer 输出非空", len(data) > 1000, f"len={len(data)}")

    psd = PSDImage.open(io.BytesIO(data))
    check("psd 重新打开尺寸正确", psd.size == (200, 150), str(psd.size))
    names = [c.name for c in psd]
    check("顶层中文图层名保留", "07_白色背景" in names and "02_正面效果" in names, str(names))
    front = next((c for c in psd if c.name == "02_正面效果"), None)
    check("正面效果是图层组", front is not None and front.is_group())
    if front:
        sub = [c.name for c in front]
        check("正面组含门板/门框子层", "门板" in sub and "门框" in sub, str(sub))
    ri = psd.image_resources.get(Resource.RESOLUTION_INFO)
    check("分辨率元数据 300 DPI", ri is not None and getattr(ri.data, "horizontal", 0) == 300, str(ri))

    # 图层裁切：小图层的画布尺寸应远小于整幅画布
    outline = next((c for c in psd if c.name == "04_CAD轮廓"), None)
    check("轮廓层被裁切到内容包围盒", outline is not None and outline.width <= 12 and outline.height <= 10, f"{outline.width}x{outline.height}" if outline else "None")


class _FakeAiProvider:
    """假 Provider：返回一张纯蓝色图，验证 AI 路径与蒙版映射。"""

    def __init__(self):
        self.request = None

    def render(self, request):
        self.request = request
        import base64
        img = Image.new("RGB", (request.line_art and 800 or 1024, 600), (30, 90, 180))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return {"images": [{"type": "b64_json", "src": f"data:image/png;base64,{encoded}"}], "raw": {}}


class _FailingAiProvider:
    def render(self, request):
        from rendering.providers.base import ProviderError
        raise ProviderError("模拟上游失败", status_code=502)


def test_ai_material_and_fallback():
    dxf_text = _sample_dxf_text()
    ai_config = {
        "provider": "openai_compatible",
        "baseUrl": "https://fake.example.com",
        "apiKey": "test-key",
        "model": "test-model",
        "endpoint": "/images/edits",
        "apiType": "openai_images_edits",
        "timeoutSeconds": 60,
    }

    # AI 成功路径
    fake = _FakeAiProvider()
    original_get_provider = layered_render.get_provider
    layered_render.get_provider = lambda name: fake
    try:
        result = render_layered_dxf(dxf_text, dpi=300, target_long_edge=1600, ai_config=ai_config, references=[])
    finally:
        layered_render.get_provider = original_get_provider

    check("AI 路径 material_mode=ai", result["material_mode"] == "ai", result.get("material_mode"))
    check("AI 路径无回退提示", not result.get("material_note"), result.get("material_note"))
    check("AI 请求带上了提示词", "材质" in (fake.request.prompt or ""))
    check("AI 请求使用传入配置", fake.request.config.get("model") == "test-model")

    psd = PSDImage.open(io.BytesIO(result["psd_bytes"]))
    front = next((c for c in psd if c.name == "02_正面效果"), None)
    panel = next((c for c in front if c.name == "门板"), None) if front else None
    check("AI PSD 含门板层", panel is not None)
    if panel:
        composite = panel.composite()
        arr = np.array(composite)
        alpha = arr[..., 3]
        colored = arr[alpha > 0]
        check("AI 门板层有内容", len(colored) > 100, str(len(colored)))
        if len(colored):
            avg = tuple(int(colored[:, i].mean()) for i in range(3))
            check("门板层取到 AI 蓝色材质", abs(avg[0] - 30) < 20 and abs(avg[2] - 180) < 20, str(avg))

    # AI 失败回退路径
    failing = _FailingAiProvider()
    layered_render.get_provider = lambda name: failing
    try:
        fallback = render_layered_dxf(dxf_text, dpi=300, target_long_edge=1600, ai_config=ai_config, references=[])
    finally:
        layered_render.get_provider = original_get_provider
    check("AI 失败回退 flat", fallback["material_mode"] == "flat", fallback.get("material_mode"))
    check("回退带原因提示", "模拟上游失败" in fallback.get("material_note", ""), fallback.get("material_note"))
    check("回退仍输出 PSD", len(fallback["psd_bytes"]) > 1000)


def test_psd_size():
    dxf_text = _sample_dxf_text()
    result = render_layered_dxf(dxf_text, dpi=300, target_long_edge=2600)
    size_mb = len(result["psd_bytes"]) / 1024 / 1024
    print(f"[info] 2600px 长边 PSD 大小: {size_mb:.2f} MB")
    check("默认 2600px 长边 PSD 小于 10MB", size_mb < 10, f"{size_mb:.2f}MB")


def test_layered_render():
    dxf_text = _sample_dxf_text()
    result = render_layered_dxf(dxf_text, dpi=300, target_long_edge=2000)
    check("渲染返回 PSD 字节", len(result["psd_bytes"]) > 1000, f"len={len(result['psd_bytes'])}")
    check("渲染返回完整 JPG", len(result["complete_jpg"]) > 1000, f"len={len(result['complete_jpg'])}")
    check("渲染返回正面 JPG", len(result["front_jpg"]) > 500, f"len={len(result['front_jpg'])}")
    check("渲染返回反面 JPG", len(result["back_jpg"]) > 500, f"len={len(result['back_jpg'])}")
    check("无 AI 时 material_mode=flat", result.get("material_mode") == "flat")
    check("完整图使用 95 质量输出", result.get("output_quality") == 95, str(result.get("output_quality")))
    check(
        "普通成图使用固定干净图层顺序",
        result.get("visible_layer_order") == ["seam", "trim", "frame", "panel", "glass", "hardware", "lighting"],
        str(result.get("visible_layer_order")),
    )

    psd = PSDImage.open(io.BytesIO(result["psd_bytes"]))
    top_names = [c.name for c in psd]
    for expected in ("01_订货单信息", "02_正面效果", "03_反面效果", "04_CAD轮廓", "05_参考素材", "06_原始CAD底图", "07_白色背景"):
        check(f"PSD 顶层包含 {expected}", expected in top_names, str(top_names))

    # 原始 CAD 底图与参考素材默认隐藏
    raw = next((c for c in psd if c.name == "06_原始CAD底图"), None)
    ref = next((c for c in psd if c.name == "05_参考素材"), None)
    outline = next((c for c in psd if c.name == "04_CAD轮廓"), None)
    info = next((c for c in psd if c.name == "01_订货单信息"), None)
    check("原始CAD底图默认隐藏", raw is not None and not raw.visible)
    check("参考素材默认隐藏", ref is not None and not ref.visible)
    check("CAD轮廓默认隐藏", outline is not None and not outline.visible)
    check("订货单标注默认隐藏", info is not None and not info.visible)

    # 白色背景可单独关闭
    white = next((c for c in psd if c.name == "07_白色背景"), None)
    check("白色背景是独立图层", white is not None and not white.is_group())


def test_dxf_geometry_manifest_uses_one_canvas_transform():
    result = render_layered_dxf(_sample_dxf_text(), target_long_edge=1600, include_psd=False)
    manifest = result["geometry_manifest"]
    assert manifest["units"] == "mm"
    assert manifest["canvas"]["width"] == result["canvas_size"][0]
    assert manifest["canvas"]["height"] == result["canvas_size"][1]
    assert manifest["transform_id"]
    for role in ("panel", "frame", "trim", "glass", "hardware"):
        geometry = manifest["roles"][role]
        assert geometry["transform_id"] == manifest["transform_id"]
        assert set(geometry["side_bboxes"]) == {"front", "back"}
        if role not in {"glass", "hardware"}:
            assert geometry["cad_bbox"]
            assert geometry["pixel_bbox"]
            assert geometry["layers"]


def test_optional_dxf_glass_uses_shared_geometry_and_renders_above_panel():
    doc = ezdxf.new()
    modelspace = doc.modelspace()
    modelspace.add_text("正面", dxfattribs={"layer": "A-DOOR-mark", "height": 20}).set_placement((0, 350))
    modelspace.add_text("背面", dxfattribs={"layer": "A-DOOR-mark", "height": 20}).set_placement((1000, 350))
    for offset in (0, 1000):
        modelspace.add_lwpolyline(
            [(offset + 100, 0), (offset + 300, 0), (offset + 300, 260), (offset + 100, 260)],
            close=True,
            dxfattribs={"layer": "A-DOOR-PANEL"},
        )
        modelspace.add_lwpolyline(
            [(offset + 50, -40), (offset + 350, -40), (offset + 350, 300), (offset + 50, 300)],
            close=True,
            dxfattribs={"layer": "A-DOOR-FRAME"},
        )
        modelspace.add_lwpolyline(
            [(offset + 145, 90), (offset + 255, 90), (offset + 255, 220), (offset + 145, 220)],
            close=True,
            dxfattribs={"layer": "A-DOOR-GLASS"},
        )

    stream = io.StringIO()
    doc.write(stream)
    result = render_layered_dxf(stream.getvalue(), target_long_edge=800, include_psd=False)

    glass_geometry = result["geometry_manifest"]["roles"]["glass"]
    assert glass_geometry["transform_id"] == result["geometry_manifest"]["transform_id"]
    assert glass_geometry["layers"] == ["A-DOOR-GLASS"]
    glass = np.array(Image.open(io.BytesIO(result["layer_pngs"]["glass"])).convert("RGBA"))
    assert np.count_nonzero(glass[..., 3]) > 0
    assert result["visible_layer_order"].index("glass") > result["visible_layer_order"].index("panel")


def test_geometry_validation_reports_missing_frame_unknown_layer_and_open_panel():
    transform = make_geometry_transform(min_x=0, max_y=100, scale=1, width=200, height=100)
    panel = Primitive("polyline", "A-DOOR-PANEL", [(10, 10), (80, 10), (80, 90)], {"closed": False})
    unknown = Primitive("line", "A-DOOR-STRUCTURE-UNKNOWN", [(0, 0), (10, 10)], {})
    categorized = {"panel": [panel], "frame": [], "trim": [], "accessory": [], "outline": [unknown]}
    manifest = build_geometry_manifest(
        categorized,
        {"panel": [panel], "frame": [], "trim": [], "accessory": []},
        {"panel": [], "frame": [], "trim": [], "accessory": []},
        transform,
    )

    validation = validate_geometry_manifest(manifest, categorized)

    codes = {item["code"] for item in validation["errors"]}
    assert "MISSING_FRAME_GEOMETRY" in codes
    assert "UNKNOWN_STRUCTURAL_LAYER" in codes
    assert "PANEL_CONTOUR_NOT_CLOSED" in codes


def test_geometry_validation_reports_clear_mask_overlap_and_gap():
    transform = make_geometry_transform(min_x=0, max_y=100, scale=1, width=200, height=100)
    panel = Primitive("polyline", "A-DOOR-PANEL", [(10, 10), (100, 10), (100, 90), (10, 90)], {"closed": True})
    frame = Primitive("polyline", "A-DOOR-FRAME", [(90, 0), (180, 0), (180, 100), (90, 100)], {"closed": True})
    categorized = {"panel": [panel], "frame": [frame], "trim": [], "accessory": [], "outline": []}
    manifest = build_geometry_manifest(categorized, categorized, categorized, transform)
    panel_mask = np.zeros((100, 200, 4), dtype=np.uint8)
    frame_mask = np.zeros_like(panel_mask)
    panel_mask[10:90, 10:100, 3] = 255
    frame_mask[:, 90:180, 3] = 255

    overlap_validation = validate_geometry_manifest(
        manifest,
        categorized,
        {"panel": panel_mask, "frame": frame_mask},
    )
    assert "ROLE_MASK_OVERLAP" in {item["code"] for item in overlap_validation["errors"]}

    adjacent_frame = Primitive("polyline", "A-DOOR-FRAME", [(101, 0), (180, 0), (180, 100), (101, 100)], {"closed": True})
    adjacent = {**categorized, "frame": [adjacent_frame]}
    adjacent_manifest = build_geometry_manifest(adjacent, adjacent, adjacent, transform)
    separated_frame_mask = np.zeros_like(panel_mask)
    separated_frame_mask[:, 110:180, 3] = 255
    gap_validation = validate_geometry_manifest(
        adjacent_manifest,
        adjacent,
        {"panel": panel_mask, "frame": separated_frame_mask},
    )
    assert "ROLE_BOUNDARY_GAP" in {item["code"] for item in gap_validation["errors"]}


def test_precise_render_blocks_invalid_open_panel_geometry():
    doc = ezdxf.new()
    modelspace = doc.modelspace()
    modelspace.add_text("正面", dxfattribs={"layer": "A-DOOR-mark", "height": 20}).set_placement((0, 300))
    modelspace.add_text("背面", dxfattribs={"layer": "A-DOOR-mark", "height": 20}).set_placement((1000, 300))
    for offset in (0, 1000):
        modelspace.add_lwpolyline([(offset, 0), (offset + 300, 0), (offset + 300, 220)], dxfattribs={"layer": "A-DOOR-PANEL"})
        modelspace.add_lwpolyline([(offset - 30, -30), (offset + 330, -30), (offset + 330, 250), (offset - 30, 250)], close=True, dxfattribs={"layer": "A-DOOR-FRAME"})
    stream = io.StringIO()
    doc.write(stream)

    with pytest.raises(DxfGeometryValidationError) as captured:
        render_layered_dxf(stream.getvalue(), target_long_edge=600, include_psd=False)

    assert "PANEL_CONTOUR_NOT_CLOSED" in {item["code"] for item in captured.value.geometry_validation["errors"]}


def test_exact_role_masks_follow_manifest_bounds_including_open_hardware_lines():
    doc = ezdxf.new()
    modelspace = doc.modelspace()
    modelspace.add_text("正面", dxfattribs={"layer": "A-DOOR-mark", "height": 20}).set_placement((0, 350))
    modelspace.add_text("背面", dxfattribs={"layer": "A-DOOR-mark", "height": 20}).set_placement((1000, 350))

    handle = doc.blocks.new("A1022_TEST")
    handle.add_lwpolyline([(0, 0), (20, 0), (20, 100), (0, 100)], close=True)
    handle.add_line((20, 50), (60, 50))

    for offset in (0, 1000):
        modelspace.add_lwpolyline(
            [(offset + 100, 0), (offset + 300, 0), (offset + 300, 200), (offset + 100, 200)],
            close=True,
            dxfattribs={"layer": "A-DOOR-PANEL"},
        )
        modelspace.add_lwpolyline(
            [(offset + 50, -50), (offset + 350, -50), (offset + 350, 250), (offset + 50, 250)],
            close=True,
            dxfattribs={"layer": "A-DOOR-FRAME"},
        )
        modelspace.add_lwpolyline(
            [(offset, -100), (offset + 400, -100), (offset + 400, 300), (offset, 300)],
            close=True,
            dxfattribs={"layer": "A-DOOR-TRIM"},
        )
        modelspace.add_blockref("A1022_TEST", (offset + 180, 50), dxfattribs={"layer": "A-DOOR-PANEL"})

    stream = io.StringIO()
    doc.write(stream)
    ai_config = {
        "provider": "openai_compatible",
        "baseUrl": "https://fake.example.com",
        "apiKey": "test-key",
        "model": "test-model",
        "endpoint": "/images/edits",
        "apiType": "openai_images_edits",
    }
    original_get_provider = layered_render.get_provider
    layered_render.get_provider = lambda name: _FakeAiProvider()
    try:
        result = render_layered_dxf(
            stream.getvalue(),
            target_long_edge=800,
            ai_config=ai_config,
            references=[],
            include_psd=False,
        )
    finally:
        layered_render.get_provider = original_get_provider
    width, height = result["canvas_size"]

    for role in ("panel", "frame", "trim", "hardware"):
        layer = np.array(Image.open(io.BytesIO(result["layer_pngs"][role])).convert("RGBA"))
        assert layer.shape[:2] == (height, width)
        ys, xs = np.where(layer[..., 3] > 0)
        assert len(xs) > 0, role
        actual = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
        expected = result["geometry_manifest"]["roles"][role]["pixel_bbox"]
        assert max(abs(a - b) for a, b in zip(actual, expected)) <= 2, (role, actual, expected)


def test_real_a1022_block_uses_its_transformed_dxf_geometry_as_mask():
    result = render_layered_dxf(_a1022_dxf_text(), target_long_edge=1000, include_psd=False)
    hardware_geometry = result["geometry_manifest"]["roles"]["hardware"]
    assert hardware_geometry["cad_bbox"]

    layer = np.array(Image.open(io.BytesIO(result["layer_pngs"]["hardware"])).convert("RGBA"))
    ys, xs = np.where(layer[..., 3] > 0)
    assert len(xs) > 0
    actual = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    expected = hardware_geometry["pixel_bbox"]
    assert max(abs(a - b) for a, b in zip(actual, expected)) <= 2, (actual, expected)


def test_selected_face_canvas_ignores_far_accessory_helpers_and_stays_shared(monkeypatch):
    doc = ezdxf.new()
    modelspace = doc.modelspace()
    modelspace.add_text("正面", dxfattribs={"layer": "A-DOOR-mark", "height": 20}).set_placement((200, 420))
    modelspace.add_text("背面", dxfattribs={"layer": "A-DOOR-mark", "height": 20}).set_placement((1200, 420))

    helper = doc.blocks.new("HANDLE_WITH_HELPER")
    helper.add_lwpolyline([(0, 0), (20, 0), (20, 80), (0, 80)], close=True)
    helper.add_line((-900, 40), (0, 40))

    for offset in (0, 1000):
        modelspace.add_lwpolyline(
            [(offset + 100, 0), (offset + 300, 0), (offset + 300, 360), (offset + 100, 360)],
            close=True,
            dxfattribs={"layer": "A-DOOR-PANEL"},
        )
        modelspace.add_lwpolyline(
            [(offset + 70, -30), (offset + 330, -30), (offset + 330, 390), (offset + 70, 390)],
            close=True,
            dxfattribs={"layer": "A-DOOR-FRAME"},
        )
        modelspace.add_lwpolyline(
            [(offset + 40, -60), (offset + 360, -60), (offset + 360, 420), (offset + 40, 420)],
            close=True,
            dxfattribs={"layer": "A-DOOR-TRIM"},
        )
        modelspace.add_blockref("HANDLE_WITH_HELPER", (offset + 240, 140), dxfattribs={"layer": "A-DOOR-PANEL"})

    stream = io.StringIO()
    doc.write(stream)
    submitted_shapes = []

    def fake_material(rgb, _config, _references, _prompt):
        submitted_shapes.append(rgb.shape)
        return rgb.copy()

    monkeypatch.setattr(layered_render, "_apply_ai_material", fake_material)
    references = {role: [{"filePath": f"{role}.png"}] for role in ("panel", "trim", "frame", "glass", "hardware")}
    result = render_layered_dxf(
        stream.getvalue(),
        target_long_edge=900,
        ai_config={"provider": "fake"},
        reference_bindings=references,
        include_psd=False,
        selected_side="front",
    )

    width, height = result["canvas_size"]
    assert result["selected_side"] == "front"
    assert result["front_size"] == (width, height)
    assert submitted_shapes
    assert all(shape[:2] == (height, width) for shape in submitted_shapes)
    assert height == 900
    assert 450 <= width <= 700
    selected = Image.open(io.BytesIO(result["selected_jpg"]))
    assert selected.size == (width, height)
    for content in result["selected_layer_pngs"].values():
        assert Image.open(io.BytesIO(content)).size == (width, height)


if __name__ == "__main__":
    test_psd_writer()
    test_layered_render()
    test_psd_size()
    test_ai_material_and_fallback()
    print(f"\n{PASSED} PASS / {FAILED} FAIL")
    sys.exit(1 if FAILED else 0)
