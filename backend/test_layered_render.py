"""
分层效果图 / PSD 生成 测试。

覆盖：
- PSD Writer：中文图层名、图层组、透明度、300 DPI 分辨率元数据、层叠顺序。
- 分层渲染：DXF -> PSD + JPG，正反面分组，门板/门框/门套/配件独立成层。
"""
import io
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from PIL import Image
from psd_tools import PSDImage
from psd_tools.constants import Resource

from rendering.psd_writer import PsdNode, write_psd
from rendering.layered_render import render_layered_dxf
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


def test_psd_writer():
    nodes = [
        PsdNode("01_订货单信息", children=[
            PsdNode("尺寸标注", _rgba(10, 10, 10)),
            PsdNode("表格与文字", _rgba(20, 20, 20)),
        ]),
        PsdNode("02_正面效果", children=[
            PsdNode("门板", _rgba(180, 120, 40)),
            PsdNode("门框", _rgba(80, 80, 80)),
        ]),
        PsdNode("04_CAD轮廓", _rgba(30, 30, 30)),
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


def test_layered_render():
    dxf_text = _sample_dxf_text()
    result = render_layered_dxf(dxf_text, dpi=300, target_long_edge=2000)
    check("渲染返回 PSD 字节", len(result["psd_bytes"]) > 1000, f"len={len(result['psd_bytes'])}")
    check("渲染返回完整 JPG", len(result["complete_jpg"]) > 1000, f"len={len(result['complete_jpg'])}")
    check("渲染返回正面 JPG", len(result["front_jpg"]) > 500, f"len={len(result['front_jpg'])}")
    check("渲染返回反面 JPG", len(result["back_jpg"]) > 500, f"len={len(result['back_jpg'])}")

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
    print(f"\n{PASSED} PASS / {FAILED} FAIL")
    sys.exit(1 if FAILED else 0)
