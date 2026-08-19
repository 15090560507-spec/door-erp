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

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import numpy as np
from PIL import Image
from psd_tools import PSDImage
from psd_tools.constants import Resource

from rendering.psd_writer import PsdNode, write_psd
from rendering.layered_render import render_layered_dxf
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


def _sample_dxf_text():
    req = CADRequest(door_type="单门", sel_kx="右开", sel_nk="内开", dw=1500, dh=2400,
                     zmls="铝雕圆形拉手", fmls="无", handle_size="150*300", fingerprint_lock="无")
    info, checks, params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, params)
    assert buffer, f"CAD 生成失败: {msg}"
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

    psd = PSDImage.open(io.BytesIO(result["psd_bytes"]))
    top_names = [c.name for c in psd]
    for expected in ("01_订货单信息", "02_正面效果", "03_反面效果", "04_CAD轮廓", "05_参考素材", "06_原始CAD底图", "07_白色背景"):
        check(f"PSD 顶层包含 {expected}", expected in top_names, str(top_names))

    # 原始 CAD 底图与参考素材默认隐藏
    raw = next((c for c in psd if c.name == "06_原始CAD底图"), None)
    ref = next((c for c in psd if c.name == "05_参考素材"), None)
    check("原始CAD底图默认隐藏", raw is not None and not raw.visible)
    check("参考素材默认隐藏", ref is not None and not ref.visible)

    # 白色背景可单独关闭
    white = next((c for c in psd if c.name == "07_白色背景"), None)
    check("白色背景是独立图层", white is not None and not white.is_group())


if __name__ == "__main__":
    test_psd_writer()
    test_layered_render()
    test_psd_size()
    test_ai_material_and_fallback()
    print(f"\n{PASSED} PASS / {FAILED} FAIL")
    sys.exit(1 if FAILED else 0)
