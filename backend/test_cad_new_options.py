import io
import os
import sys

import ezdxf


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from main import build_cad_params
from models import CADRequest
from drawing import run_integrated_system


PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name} -- {detail}")


def test_cad_new_options_flow():
    req = CADRequest(
        dhdw="测试客户",
        gdmc="测试项目",
        ddh="CAD-NEW-001",
        sel_hys="三维可调合页",
        threshold_type="吊脚",
        has_dj=True,
        dj_height=20,
        has_outer=True,
        trim_front_in=160,
        trim_style_outer="平包套",
        overlap_front=25,
        has_inner=True,
        trim_back_in=140,
        trim_style_inner="平包套",
        overlap_back=35,
        zmls="自制长拉手",
        fmls="标配拉手",
        handle_size="40*800",
        fingerprint_lock="安志杰AF-12",
        mark_light_size=True,
    )

    info, checks, draw_params = build_cad_params(req)
    check("DJ attr is checked", info["DJ"] == "√", str(info.get("DJ")))
    check("DJG attr uses height", info["DJG"] == "20", str(info.get("DJG")))
    check("fingerprint lock maps to ZWS", info["ZWS"] == "安志杰AF-12", str(info.get("ZWS")))
    check("front overlap is independent", draw_params["overlap_front"] == 25, str(draw_params))
    check("back overlap is independent", draw_params["overlap_back"] == 35, str(draw_params))
    check("self-made long handle note is formatted", "自制长拉手尺寸为：40mm*800mm" in info["BZ"], info["BZ"])
    check("hanging threshold removes front sill", draw_params["th_front"] == 0, str(draw_params))
    check("hanging threshold removes back sill", draw_params["th_back"] == 0, str(draw_params))
    check("hanging threshold carries panel gap", draw_params["dj_height"] == 20, str(draw_params))
    check("mark light size passes to drawing", draw_params["mark_light_size"] is True, str(draw_params))

    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    inserts = [entity.dxf.name for entity in doc.modelspace().query("INSERT")]
    check("PBT block inserted", "PBT" in inserts, str(inserts[:20]))
    check("AZJ block inserted", "AZJ" in inserts, str(inserts[:20]))

    baseline_req = req.model_copy(deep=True)
    baseline_req.zmls = "无"
    baseline_req.fmls = "无"
    baseline_req.handle_size = ""
    baseline_req.fingerprint_lock = "无"
    base_info, base_checks, base_draw_params = build_cad_params(baseline_req)
    _base_msg, base_buffer = run_integrated_system(base_info, base_checks, base_draw_params)
    base_doc = ezdxf.read(io.StringIO(base_buffer.getvalue()))
    base_inserts = [entity.dxf.name for entity in base_doc.modelspace().query("INSERT")]
    check(
        "front sized handle does not add backpack blocks",
        inserts.count("BBLS") == base_inserts.count("BBLS"),
        f"BBLS: {base_inserts.count('BBLS')} -> {inserts.count('BBLS')}",
    )
    standard_handle_delta = (
        inserts.count("ZBPLS") + inserts.count("YBPLS")
        - base_inserts.count("ZBPLS") - base_inserts.count("YBPLS")
    )
    check(
        "back handle style still draws when front handle size is provided",
        standard_handle_delta == 1,
        f"standard handle delta: {standard_handle_delta}",
    )

    panel_polys = [
        entity for entity in doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-PANEL"
    ]
    min_panel_y = min(point[1] for entity in panel_polys for point in entity.get_points("xy"))
    check("hanging door panel starts at 20mm above bottom", abs(min_panel_y - 20) < 0.01, str(min_panel_y))


def test_a1022_handle_backpack_handle_and_adjustable_hinge():
    req = CADRequest(
        sel_hys="\u4e09\u7ef4\u53ef\u8c03\u5408\u9875",
        zmls="A1022",
        fmls="\u80cc\u5305\u62c9\u624b",
    )

    info, checks, draw_params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("A1022 CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    inserts = [entity.dxf.name for entity in doc.modelspace().query("INSERT")]

    baseline_req = req.model_copy(deep=True)
    baseline_req.zmls = "\u65e0"
    baseline_req.fmls = "\u65e0"
    baseline_req.sel_hys = "\u5317\u4eac\u6697\u5408\u9875"
    base_info, base_checks, base_draw_params = build_cad_params(baseline_req)
    _base_msg, base_buffer = run_integrated_system(base_info, base_checks, base_draw_params)
    base_doc = ezdxf.read(io.StringIO(base_buffer.getvalue()))
    base_inserts = [entity.dxf.name for entity in base_doc.modelspace().query("INSERT")]

    a1022_count = inserts.count("Z1022") + inserts.count("Y1022")
    base_a1022_count = base_inserts.count("Z1022") + base_inserts.count("Y1022")
    check(
        "A1022 handle inserts mapped block",
        a1022_count > base_a1022_count,
        f"A1022 mapped blocks: {base_a1022_count} -> {a1022_count}",
    )
    check(
        "backpack handle uses BBLS block",
        inserts.count("BBLS") > base_inserts.count("BBLS"),
        f"BBLS: {base_inserts.count('BBLS')} -> {inserts.count('BBLS')}",
    )
    check(
        "three-way adjustable hinge uses kcx block",
        inserts.count("kcx") > base_inserts.count("kcx"),
        f"kcx: {base_inserts.count('kcx')} -> {inserts.count('kcx')}",
    )


if __name__ == "__main__":
    test_cad_new_options_flow()
    test_a1022_handle_backpack_handle_and_adjustable_hinge()
    print(f"\nPASS: {PASSED}")
    print(f"FAIL: {FAILED}")
    if FAILED:
        sys.exit(1)
