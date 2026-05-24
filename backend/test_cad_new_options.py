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
        sel_hys="三位可调合页",
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


if __name__ == "__main__":
    test_cad_new_options_flow()
    print(f"\nPASS: {PASSED}")
    print(f"FAIL: {FAILED}")
    if FAILED:
        sys.exit(1)
