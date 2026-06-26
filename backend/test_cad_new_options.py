import os
import sys
import io
import math
import re

import ezdxf


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from main import build_cad_params, _DEFAULT_DROPDOWN_OPTIONS
from models import CADRequest
from drawing import run_integrated_system
from cad_preview import render_dxf_svg


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
        if entity.dxf.layer == "A-DOOR-PANEL-GEOM"
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


def test_split_handle_uses_directional_blocks():
    req = CADRequest(
        door_type="对开门",
        zmls="分体拉手",
        fmls="分体拉手",
    )

    info, checks, draw_params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("split handle CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    inserts = [entity.dxf.name for entity in doc.modelspace().query("INSERT")]

    baseline_req = req.model_copy(deep=True)
    baseline_req.zmls = "无"
    baseline_req.fmls = "无"
    base_info, base_checks, base_draw_params = build_cad_params(baseline_req)
    _base_msg, base_buffer = run_integrated_system(base_info, base_checks, base_draw_params)
    base_doc = ezdxf.read(io.StringIO(base_buffer.getvalue()))
    base_inserts = [entity.dxf.name for entity in base_doc.modelspace().query("INSERT")]

    y_delta = inserts.count("YFTLS") - base_inserts.count("YFTLS")
    z_delta = inserts.count("ZFTLS") - base_inserts.count("ZFTLS")
    old_delta = inserts.count("FTLS") - base_inserts.count("FTLS")
    check("split handle inserts right directional block", y_delta >= 1, f"YFTLS delta: {y_delta}")
    check("split handle inserts left directional block", z_delta >= 1, f"ZFTLS delta: {z_delta}")
    check("split handle no longer inserts old undirected block", old_delta == 0, f"FTLS delta: {old_delta}")

    for open_dir, expected_block in (("右开", "ZFTLS"), ("左开", "YFTLS")):
        back_req = CADRequest(
            door_type="对开门",
            sel_kx=open_dir,
            zmls="无",
            fmls="分体拉手",
        )
        back_info, back_checks, back_draw_params = build_cad_params(back_req)
        back_msg, back_buffer = run_integrated_system(back_info, back_checks, back_draw_params)
        check(f"back split handle {open_dir} CAD generation returns buffer", back_buffer is not None, back_msg)
        if not back_buffer:
            continue
        back_doc = ezdxf.read(io.StringIO(back_buffer.getvalue()))
        split_inserts = [
            entity for entity in back_doc.modelspace().query("INSERT")
            if entity.dxf.name in {"YFTLS", "ZFTLS"} and float(entity.dxf.insert.x) < 10000
        ]
        check(
            f"back split handle {open_dir} keeps only one handle",
            len(split_inserts) == 1 and split_inserts[0].dxf.name == expected_block,
            [(entity.dxf.name, float(entity.dxf.insert.x)) for entity in split_inserts],
        )


def test_back_a1022_handle_direction_blocks():
    req = CADRequest(
        door_type="对开门",
        zmls="无",
        fmls="A1022",
    )

    info, checks, draw_params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("back A1022 CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    y1022_x = [
        float(entity.dxf.insert.x) for entity in doc.modelspace().query("INSERT")
        if entity.dxf.name == "Y1022"
    ]
    z1022_x = [
        float(entity.dxf.insert.x) for entity in doc.modelspace().query("INSERT")
        if entity.dxf.name == "Z1022"
    ]
    check(
        "back A1022 right leaf uses Y1022 and left leaf uses Z1022",
        bool(y1022_x and z1022_x and min(z1022_x) < max(y1022_x)),
        f"Y1022 x: {y1022_x}, Z1022 x: {z1022_x}",
    )


def test_door_panel_style_lines():
    req = CADRequest(
        door_panel_style="H+型布局",
        panel_lock_offset_x=180,
        panel_hinge_offset_y=100,
        panel_middle_offset_z=180,
        panel_plus_offset_a=350,
        panel_plus_offset_b=100,
    )

    info, checks, draw_params = build_cad_params(req)
    check("panel style passes to info map", info["DOOR_PANEL_STYLE"] == "H+型布局", str(info))
    check("panel style passes to drawing", draw_params["door_panel_style"] == "H+型布局", str(draw_params))
    check("panel lock offset default is 180-compatible", draw_params["panel_lock_offset_x"] == 180, str(draw_params))

    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("panel style CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    panel_lines = [
        entity for entity in doc.modelspace().query("LINE")
        if entity.dxf.layer == "A-DOOR-PANEL"
    ]
    check("H+ panel style draws extra panel lines", len(panel_lines) >= 6, f"line count: {len(panel_lines)}")


def test_disc_panel_style_draws_semicircle():
    req = CADRequest(
        door_panel_style="\u5706\u76d8\u9020\u578b",
        panel_lock_offset_x=180,
        panel_disc_radius=160,
    )

    info, checks, draw_params = build_cad_params(req)
    check("disc panel radius passes to info map", info["PANEL_DISC_RADIUS"] == 160, str(info))
    check("disc panel radius passes to drawing", draw_params["panel_disc_radius"] == 160, str(draw_params))

    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("disc panel CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    panel_arcs = [
        entity for entity in doc.modelspace().query("ARC")
        if entity.dxf.layer == "A-DOOR-PANEL" and abs(float(entity.dxf.radius) - 160) < 0.01
    ]
    panel_lines = [
        entity for entity in doc.modelspace().query("LINE")
        if entity.dxf.layer == "A-DOOR-PANEL"
    ]
    panel_rects = [
        poly_bounds(entity) for entity in doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-PANEL-GEOM"
        and (poly_bounds(entity)[1] - poly_bounds(entity)[0]) > 100
        and (poly_bounds(entity)[3] - poly_bounds(entity)[2]) > 1000
    ]
    check("disc panel style draws semicircle arc", len(panel_arcs) >= 1, f"arcs: {len(panel_arcs)}")
    check(
        "disc panel style draws only body panel edge lines",
        len(panel_lines) <= 4,
        f"panel lines: {len(panel_lines)}",
    )
    check(
        "disc panel arc diameter sits on panel lock edge",
        any(
            abs(float(arc.dxf.center.x) - edge_x) < 0.01
            for arc in panel_arcs
            for rect in panel_rects
            for edge_x in (rect[0], rect[1])
        ),
        f"arcs: {[(float(arc.dxf.center.x), float(arc.dxf.center.y)) for arc in panel_arcs]}, rects: {panel_rects}",
    )


def poly_bounds(entity):
    points = list(entity.get_points("xy"))
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), max(xs), min(ys), max(ys)


def test_pillar_handle_title_and_three_column_panel():
    req = CADRequest(
        door_type="两定两开",
        has_pillar=True,
        pillar_width_str="55/85",
        zmls="自制长拉手",
        fmls="自制长拉手",
        handle_size="40*800",
        door_panel_style="三列式布局",
        back_door_panel_style="H型布局",
        child_door_panel_style="两列式布局",
        panel_three_col_a=120,
        panel_three_col_b=260,
        panel_three_col_c=0,
        back_panel_lock_offset_x=130,
        back_panel_hinge_offset_y=90,
        back_panel_middle_offset_z=160,
        child_panel_lock_offset_x=140,
    )

    info, checks, draw_params = build_cad_params(req)
    check("three-column A width passes to drawing", draw_params["panel_three_col_a"] == 120, str(draw_params))
    check("three-column B width passes to drawing", draw_params["panel_three_col_b"] == 260, str(draw_params))
    check("back panel style passes to drawing", draw_params["back_door_panel_style"] == "H型布局", str(draw_params))
    check("child panel style passes to drawing", draw_params["child_door_panel_style"] == "两列式布局", str(draw_params))
    check("back panel offset passes independently", draw_params["back_panel_lock_offset_x"] == 130, str(draw_params))
    check("child panel offset passes independently", draw_params["child_panel_lock_offset_x"] == 140, str(draw_params))

    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("pillar/handle/three-column CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    panel_polys = [
        entity for entity in doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-PANEL"
    ]
    long_handle_rects = []
    for entity in panel_polys:
        x1, x2, y1, y2 = poly_bounds(entity)
        if abs((x2 - x1) - 40) < 0.01 and abs((y2 - y1) - 800) < 0.01:
            long_handle_rects.append(entity)
    check(
        "front view draws configured sized handle",
        len(long_handle_rects) >= 1,
        f"long handle rectangles: {len(long_handle_rects)}",
    )

    frame_polys = [
        entity for entity in doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-FRAME"
    ]
    pillar_polys = []
    for entity in frame_polys:
        x1, x2, y1, y2 = poly_bounds(entity)
        if abs((x2 - x1) - 85) < 0.01 and abs(y1 - 75) < 0.01 and abs(y2 - 2025) < 0.01:
            pillar_polys.append(entity)
    check(
        "pillars align to frame inner opening not panel gap",
        len(pillar_polys) >= 2,
        f"pillar polys: {len(pillar_polys)}",
    )
    hidden_lines = [
        entity for entity in doc.modelspace().query("LINE")
        if entity.dxf.layer == "A-DOOR-HIDDEN"
    ]
    check(
        "covered panel edges are drawn on hidden dashed layer",
        len(hidden_lines) >= 1 and all(entity.dxf.linetype == "HIDDEN" for entity in hidden_lines),
        [(entity.dxf.layer, entity.dxf.linetype) for entity in hidden_lines[:5]],
    )
    geom_layer = doc.layers.get("A-DOOR-PANEL-GEOM")
    check("panel geometry layer is non-plot helper", geom_layer.dxf.plot == 0, geom_layer.dxf.plot)

    title_texts = [
        entity for entity in doc.modelspace().query("TEXT")
        if entity.dxf.layer == "A-DOOR-mark" and entity.dxf.text in {"正面", "背面"}
    ]
    check(
        "front/back titles are enlarged",
        len(title_texts) >= 2 and all(abs(entity.dxf.height - 128) < 0.01 for entity in title_texts),
        [(entity.dxf.text, entity.dxf.height) for entity in title_texts],
    )

    panel_lines = [
        entity for entity in doc.modelspace().query("LINE")
        if entity.dxf.layer == "A-DOOR-PANEL"
    ]
    check("three-column panel style still draws required panel lines", len(panel_lines) >= 4, f"line count: {len(panel_lines)}")


def test_frame_defaults_and_single_back_mirror():
    default_req = CADRequest()
    check("single right-open default left frame is hinge-wide", default_req.fw_left_str == "55/85", default_req.fw_left_str)
    check("single right-open default right frame is lock-side", default_req.fw_right_str == "55/62", default_req.fw_right_str)
    check("default top and threshold are 55/75", default_req.fw_top_str == "55/75" and default_req.th_str == "55/75", f"{default_req.fw_top_str}/{default_req.th_str}")

    inner_info, inner_checks, inner_draw_params = build_cad_params(CADRequest(sel_nk="内开", fw_left_str="55/85", fw_right_str="55/62", fw_top_str="55/75", th_str="55/75"))
    check(
        "inner-open frame sizes put big values on front/outside",
        inner_draw_params["left_width_front"] == 85
        and inner_draw_params["right_width_front"] == 62
        and inner_draw_params["fw_top_front"] == 75
        and inner_draw_params["th_front"] == 75
        and inner_draw_params["left_width_back"] == 55
        and inner_draw_params["right_width_back"] == 55,
        inner_draw_params,
    )

    outer_info, outer_checks, outer_draw_params = build_cad_params(CADRequest(sel_nk="外开", fw_left_str="55/85", fw_right_str="55/62", fw_top_str="55/75", th_str="55/75"))
    check(
        "outer-open frame sizes put big values on back/inside",
        outer_draw_params["left_width_front"] == 55
        and outer_draw_params["right_width_front"] == 55
        and outer_draw_params["fw_top_front"] == 55
        and outer_draw_params["th_front"] == 55
        and outer_draw_params["left_width_back"] == 85
        and outer_draw_params["right_width_back"] == 62,
        outer_draw_params,
    )

    req = CADRequest(
        door_type="单门",
        fw_left_str="55/62",
        fw_right_str="55/85",
        fw_top_str="55/75",
        th_str="55/75",
    )
    info, checks, draw_params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("single mirror CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    frame_polys = [
        entity for entity in doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-FRAME"
    ]
    back_left_frames = []
    back_right_frames = []
    for entity in frame_polys:
        x1, x2, y1, y2 = poly_bounds(entity)
        if x1 > 1500 and abs(y1) < 0.01 and abs(y2 - req.dh) < 0.01:
            if abs((x2 - x1) - 85) < 0.01:
                back_left_frames.append(entity)
            if abs((x2 - x1) - 62) < 0.01:
                back_right_frames.append(entity)
    check(
        "single back view mirrors front left/right frame widths",
        len(back_left_frames) >= 1 and len(back_right_frames) >= 1,
        f"back 85-width frames: {len(back_left_frames)}, back 62-width frames: {len(back_right_frames)}",
    )


def test_dimension_spacing_and_trim_width_text():
    req = CADRequest(
        has_outer=True,
        trim_front_in=160,
        trim_style_outer="\u5e73\u5305\u5957",
        mark_light_size=True,
    )

    info, checks, draw_params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("dimension spacing CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    dims = list(doc.modelspace().query("DIMENSION"))
    dim_texts = [entity.dxf.text for entity in dims]
    check("trim width dimension has no leading blank", "160" in dim_texts and " 160" not in dim_texts, dim_texts)

    front_horizontal_y = sorted(
        round(float(entity.dxf.defpoint2.y), 2)
        for entity in dims
        if abs(float(entity.dxf.angle)) < 0.01 and float(entity.dxf.defpoint2.x) < 1000
    )
    check(
        "front horizontal dimension layers add 40mm cumulatively",
        front_horizontal_y == [-520.0, -380.0, -240.0, -240.0],
        front_horizontal_y,
    )

    front_vertical_x = sorted(
        round(float(entity.dxf.defpoint2.x), 2)
        for entity in dims
        if abs(float(entity.dxf.angle) - 90) < 0.01 and float(entity.dxf.defpoint2.x) < 1000
    )
    check(
        "front vertical dimension layers add 40mm cumulatively",
        front_vertical_x == [570.0, 810.0, 950.0],
        front_vertical_x,
    )


def test_middle_door_dimension_text_and_transom_light_height():
    middle_req = CADRequest(door_type="\u6298\u53e0\u56db\u5f00\u95e8")
    middle_info, middle_checks, middle_draw_params = build_cad_params(middle_req)
    middle_msg, middle_buffer = run_integrated_system(middle_info, middle_checks, middle_draw_params)
    check("middle door dimension CAD generation returns buffer", middle_buffer is not None, middle_msg)
    if middle_buffer:
        middle_doc = ezdxf.read(io.StringIO(middle_buffer.getvalue()))
        middle_texts = [entity.dxf.text for entity in middle_doc.modelspace().query("DIMENSION")]
        check(
            "middle door dimension text names inner clear width",
            "\u4e2d\u95e8\u5185\u7a7a\u5bbd <>" in middle_texts,
            middle_texts,
        )

    fixed_req = CADRequest(door_type="\u4e24\u5b9a\u4e24\u5f00")
    fixed_info, fixed_checks, fixed_draw_params = build_cad_params(fixed_req)
    fixed_msg, fixed_buffer = run_integrated_system(fixed_info, fixed_checks, fixed_draw_params)
    check("fixed-and-open door middle dimension CAD generation returns buffer", fixed_buffer is not None, fixed_msg)
    if fixed_buffer:
        fixed_doc = ezdxf.read(io.StringIO(fixed_buffer.getvalue()))
        fixed_texts = [entity.dxf.text for entity in fixed_doc.modelspace().query("DIMENSION")]
        check(
            "fixed-and-open middle door dimension text names inner clear width",
            "\u4e2d\u95e8\u5185\u7a7a\u5bbd <>" in fixed_texts,
            fixed_texts,
        )

    transom_req = CADRequest(
        sel_qc="\u73bb\u7483",
        qc_height=400,
        mark_light_size=True,
    )
    transom_info, transom_checks, transom_draw_params = build_cad_params(transom_req)
    transom_msg, transom_buffer = run_integrated_system(transom_info, transom_checks, transom_draw_params)
    check("transom light-height CAD generation returns buffer", transom_buffer is not None, transom_msg)
    if not transom_buffer:
        return

    transom_doc = ezdxf.read(io.StringIO(transom_buffer.getvalue()))
    transom_frame_max_y = max(
        poly_bounds(entity)[3]
        for entity in transom_doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-FRAME"
    )
    check(
        "transom adds above door height instead of compressing door",
        abs(transom_frame_max_y - 2500) < 0.01,
        transom_frame_max_y,
    )
    light_height_dims = [
        entity for entity in transom_doc.modelspace().query("DIMENSION")
        if entity.dxf.text.startswith("\u89c1\u5149\u9ad8") and abs(float(entity.dxf.angle) - 90) < 0.01
    ]
    check("transom drawing has one light-height dimension", len(light_height_dims) == 1, len(light_height_dims))
    if not light_height_dims:
        return

    dim = light_height_dims[0]
    y1 = round(float(dim.dxf.defpoint2.y), 2)
    y2 = round(float(dim.dxf.defpoint3.y), 2)
    check(
        "transom light height dimensions from middle rail underside to threshold top",
        (y1, y2) == (75.0, 2025.0),
        (y1, y2),
    )


def test_transom_pillar_lintel_label_and_view_gap():
    req = CADRequest(
        has_outer=True,
        has_inner=True,
        trim_front_in=160,
        trim_back_in=140,
        trim_style_outer="\u5e73\u5305\u5957",
        trim_style_inner="\u5e73\u5305\u5957",
        has_mm=True,
        mm_height=260,
        sel_qc="\u73bb\u7483",
        qc_height=400,
        door_type="\u4e24\u5b9a\u4e24\u5f00",
        has_pillar=True,
        pillar_width_str="55/85",
    )

    info, checks, draw_params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("transom pillar/lintel/view-gap CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    dim_texts = [entity.dxf.text for entity in doc.modelspace().query("DIMENSION")]
    check("lintel height dimension uses numeric text only", "260" in dim_texts and "\u95e8\u6963\u9ad8\u5ea6 260" not in dim_texts, dim_texts)

    frame_polys = [
        entity for entity in doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-FRAME"
    ]
    pillar_polys = []
    for entity in frame_polys:
        x1, x2, y1, y2 = poly_bounds(entity)
        if abs((x2 - x1) - 85) < 0.01 and abs(y1 - 75) < 0.01 and abs(y2 - 2025) < 0.01:
            pillar_polys.append(entity)
    check(
        "transom pillars stay between middle rail and threshold",
        len(pillar_polys) >= 2,
        f"pillar polys: {len(pillar_polys)}",
    )

    trim_polys = [
        entity for entity in doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-TRIM"
    ]
    trim_bounds = [poly_bounds(entity) for entity in trim_polys]
    front_bounds = [bounds for bounds in trim_bounds if bounds[1] < 1500]
    back_bounds = [bounds for bounds in trim_bounds if bounds[0] > 1500]
    if not front_bounds or not back_bounds:
        check("front and back trim bounds exist", False, trim_bounds)
        return

    front_right = max(bounds[1] for bounds in front_bounds)
    back_left = min(bounds[0] for bounds in back_bounds)
    check(
        "front and back trim edges are 1200mm apart",
        abs((back_left - front_right) - 1200) < 0.01,
        f"front right {front_right}, back left {back_left}, gap {back_left - front_right}",
    )


def test_light_width_uses_pillar_inner_edges():
    req = CADRequest(
        door_type="\u4e24\u5b9a\u4e24\u5f00",
        has_pillar=True,
        pillar_width_str="55/85",
        mark_light_size=True,
    )

    info, checks, draw_params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("pillar light-width CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    light_width_dims = [
        entity for entity in doc.modelspace().query("DIMENSION")
        if entity.dxf.text.startswith("\u89c1\u5149\u5bbd") and abs(float(entity.dxf.angle)) < 0.01
    ]
    check("pillar drawing has one light-width dimension", len(light_width_dims) == 1, len(light_width_dims))
    if not light_width_dims:
        return

    dim = light_width_dims[0]
    x1 = round(float(dim.dxf.defpoint2.x), 2)
    x2 = round(float(dim.dxf.defpoint3.x), 2)
    check(
        "pillar light width dimensions between pillar inner edges",
        (x1, x2) == (-549.0, 227.0),
        (x1, x2),
    )


def test_new_defaults_fingerprint_and_transom_shape():
    default_req = CADRequest()
    check("default top gap is 3mm", default_req.top_gap == 3, default_req.top_gap)
    check("default bottom gap is 5mm", default_req.bottom_gap == 5, default_req.bottom_gap)
    check("default middle gap is 2mm", default_req.middle_gap == 2, default_req.middle_gap)
    check("fingerprint lock defaults blank", default_req.fingerprint_lock == "", default_req.fingerprint_lock)
    fingerprint_options = _DEFAULT_DROPDOWN_OPTIONS["FINGERPRINT_LOCKS"]
    check(
        "fingerprint options include blank/no/Q3/T5 and renamed customer-provided option",
        "" in fingerprint_options
        and "\u65e0" in fingerprint_options
        and "\u5b89\u5fd7\u6770AF-12" in fingerprint_options
        and "Q3\u6307\u7eb9\u9501" in fingerprint_options
        and "T5\u6307\u7eb9\u9501" in fingerprint_options
        and "\u5ba2\u5907\u6307\u7eb9\u9501" in fingerprint_options
        and "\u5ba2\u5907" not in fingerprint_options,
        fingerprint_options,
    )

    for lock_name in ("\u5b89\u5fd7\u6770AF-12", "Q3\u6307\u7eb9\u9501", "T5\u6307\u7eb9\u9501"):
        req = CADRequest(fingerprint_lock=lock_name)
        info, checks, draw_params = build_cad_params(req)
        msg, buffer = run_integrated_system(info, checks, draw_params)
        check(f"{lock_name} CAD generation returns buffer", buffer is not None, msg)
        if not buffer:
            continue
        doc = ezdxf.read(io.StringIO(buffer.getvalue()))
        inserts = [entity.dxf.name for entity in doc.modelspace().query("INSERT")]
        check(f"{lock_name} uses AZJ block", "AZJ" in inserts, inserts[:20])

    arch_req = CADRequest(
        dh=2880,
        fw_top_str="55/70",
        has_outer=True,
        trim_front_in=160,
        trim_style_outer="\u0030\u0031\u6b3e\u5305\u5957",
        sel_qc="\u73bb\u7483",
        qc_height=400,
        qc_shape="\u5f27\u5f62\u6c14\u7a97",
    )
    arch_info, arch_checks, arch_draw_params = build_cad_params(arch_req)
    arch_msg, arch_buffer = run_integrated_system(arch_info, arch_checks, arch_draw_params)
    check("arched transom CAD generation returns buffer", arch_buffer is not None, arch_msg)
    if not arch_buffer:
        return
    arch_doc = ezdxf.read(io.StringIO(arch_buffer.getvalue()))
    check("generated dimensions are associative", arch_doc.header.get("$DIMASSOC") == 2, arch_doc.header.get("$DIMASSOC"))
    frame_arcs = [entity for entity in arch_doc.modelspace().query("ARC") if entity.dxf.layer == "A-DOOR-FRAME"]
    trim_arcs = [entity for entity in arch_doc.modelspace().query("ARC") if entity.dxf.layer == "A-DOOR-TRIM"]
    check("arched transom draws inner and outer frame arcs", len(frame_arcs) >= 4, len(frame_arcs))
    check("arched transom draws trim and trim-style arcs when trim exists", len(trim_arcs) >= 6, len(trim_arcs))
    arch_frame_lines = [
        entity for entity in arch_doc.modelspace().query("LINE")
        if entity.dxf.layer == "A-DOOR-FRAME"
    ]
    diagonal_lines = []
    for entity in arch_frame_lines:
        y1 = round(float(entity.dxf.start.y), 2)
        y2 = round(float(entity.dxf.end.y), 2)
        if 2880.0 in (y1, y2) and y1 != y2:
            diagonal_lines.append(entity)
    check("arched transom corners use diagonal frame joins", len(diagonal_lines) >= 4, len(diagonal_lines))

    def arc_endpoints(arc):
        start = math.radians(float(arc.dxf.start_angle))
        end = math.radians(float(arc.dxf.end_angle))
        return (
            (
                round(float(arc.dxf.center.x) + float(arc.dxf.radius) * math.cos(end), 2),
                round(float(arc.dxf.center.y) + float(arc.dxf.radius) * math.sin(end), 2),
            ),
            (
                round(float(arc.dxf.center.x) + float(arc.dxf.radius) * math.cos(start), 2),
                round(float(arc.dxf.center.y) + float(arc.dxf.radius) * math.sin(start), 2),
            ),
        )

    arc_endpoint_pairs = [arc_endpoints(arc) for arc in frame_arcs]
    check(
        "arched transom outer arc endpoints shift sideways as well as upward",
        any((right[0] - left[0]) > 760 for left, right in arc_endpoint_pairs),
        arc_endpoint_pairs,
    )
    check(
        "arched transom outer frame arc extends to side frame outer edges",
        any(abs((right[0] - left[0]) - arch_draw_params["dw"]) < 0.01 for left, right in arc_endpoint_pairs),
        arc_endpoint_pairs,
    )

    trim_endpoint_pairs = [arc_endpoints(arc) for arc in trim_arcs]
    check(
        "arched transom trim outer arc extends to trim outer edges",
        any((right[0] - left[0]) > 1080 for left, right in trim_endpoint_pairs),
        trim_endpoint_pairs,
    )

    arch_frame_polys = [
        entity for entity in arch_doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-FRAME"
    ]
    arch_frame_bounds = [poly_bounds(entity) for entity in arch_frame_polys]
    check(
        "arched transom omits rectangular transom range line",
        not any(
            len(list(entity.get_points("xy"))) == 4
            and abs(poly_bounds(entity)[2] - 2880) < 0.01
            and abs(poly_bounds(entity)[3] - 3210) < 0.01
            and (poly_bounds(entity)[1] - poly_bounds(entity)[0]) > 500
            for entity in arch_frame_polys
        ),
        arch_frame_bounds,
    )
    check(
        "arched transom inner opening is a selectable closed polyline",
        any(
            len(list(entity.get_points("xy"))) > 16
            and abs(poly_bounds(entity)[2] - 2880) < 0.01
            and abs(poly_bounds(entity)[3] - 3210) < 0.01
            for entity in arch_frame_polys
        ),
        arch_frame_bounds,
    )

    panel_bounds = [
        poly_bounds(entity)
        for entity in arch_doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-PANEL-GEOM"
    ]
    panel_heights = sorted({
        round(float(y2 - y1), 2)
        for x1, x2, y1, y2 in panel_bounds
        if (x2 - x1) > 300 and (y2 - y1) > 1000
    })
    check("front and back door panels have the same height", len(panel_heights) == 1, panel_heights)

    arch_dim_texts = [entity.dxf.text for entity in arch_doc.modelspace().query("DIMENSION")]
    check("arched transom door-height dimension omits label", "\u95e8\u9ad8 <>" not in arch_dim_texts, arch_dim_texts)


def test_integrated_door_sections_and_dimensions():
    req = CADRequest(
        is_integrated_door=True,
        integrated_panel_height=300,
        integrated_press_top_rail=20,
        integrated_glass_bottom_rail=20,
        integrated_glass_height=500,
    )

    info, checks, draw_params = build_cad_params(req)
    check("integrated door flag passes to drawing", draw_params["is_integrated_door"] is True, draw_params)
    check("integrated seal panel height passes to drawing", draw_params["integrated_panel_height"] == 300, draw_params)
    check("integrated glass height passes to drawing", draw_params["integrated_glass_height"] == 500, draw_params)

    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("integrated door CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    frame_max_y = max(
        poly_bounds(entity)[3]
        for entity in doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-FRAME"
    )
    check("integrated door total height stacks above lower door", abs(frame_max_y - 2900) < 0.01, frame_max_y)
    frame_polys = [
        entity for entity in doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-FRAME"
    ]
    front_window_bottom_frames = []
    back_window_bottom_frames = []
    front_full_side_frames = []
    back_seal_side_frames = []
    door_top_frames = []
    for entity in frame_polys:
        x1, x2, y1, y2 = poly_bounds(entity)
        if abs(y1 - 2400) < 0.01 and abs(y2 - 2475) < 0.01 and (x2 - x1) > 500:
            if x1 < 1000:
                front_window_bottom_frames.append(entity)
            else:
                back_window_bottom_frames.append(entity)
        if abs(y1 - 2025) < 0.01 and abs(y2 - 2100) < 0.01 and (x2 - x1) > 500:
            door_top_frames.append(entity)
        if abs(y1) < 0.01 and abs(y2 - 2900) < 0.01 and (x2 - x1) < 120 and x1 < 1000:
            front_full_side_frames.append(entity)
        if abs(y1 - 2080) < 0.01 and abs(y2 - 2420) < 0.01 and (x2 - x1) < 120:
            if x1 >= 1000:
                back_seal_side_frames.append(entity)
    check("integrated front view keeps window bottom frame", len(front_window_bottom_frames) >= 1, len(front_window_bottom_frames))
    check("integrated back view keeps window bottom frame", len(back_window_bottom_frames) >= 1, len(back_window_bottom_frames))
    check("integrated door top frame uses configured top frame width", len(door_top_frames) >= 2, len(door_top_frames))
    check("integrated front side frames are single continuous frames", len(front_full_side_frames) >= 2, len(front_full_side_frames))
    check("integrated back seal panel has no side frames", len(back_seal_side_frames) == 0, len(back_seal_side_frames))
    panel_polys = [
        entity for entity in doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-PANEL"
    ]
    seal_panels = []
    for entity in panel_polys:
        x1, x2, y1, y2 = poly_bounds(entity)
        if abs(y1 - 2080) < 0.01 and abs(y2 - 2420) < 0.01:
            seal_panels.append(entity)
    check("integrated door draws middle seal panel", len(seal_panels) >= 1, f"seal panels: {len(seal_panels)}")

    dim_texts = [entity.dxf.text for entity in doc.modelspace().query("DIMENSION")]
    check(
        "integrated door section dimensions use numeric text only",
        "\u4e0a\u65b9\u73bb\u7483\u9ad8 <>" not in dim_texts
        and "\u4e2d\u95f4\u5c01\u677f\u9ad8 <>" not in dim_texts
        and "\u4e0b\u65b9\u95e8\u9ad8 <>" not in dim_texts
        and "500" in dim_texts
        and "340" in dim_texts
        and "300" in dim_texts
        and "2100" in dim_texts
        and "\u8fde\u4f53\u603b\u9ad8 <>" not in dim_texts,
        dim_texts,
    )
    section_dims = [
        entity for entity in doc.modelspace().query("DIMENSION")
        if entity.dxf.text in {"500", "340", "300", "2100"} and abs(float(entity.dxf.angle) - 90) < 0.01
    ]
    section_dim_groups = {}
    for entity in section_dims:
        section_dim_groups.setdefault(round(float(entity.dxf.defpoint.x), 2), set()).add(entity.dxf.text)
    check(
        "integrated section dimensions share one vertical dimension line",
        section_dim_groups
        and {"500", "340", "2100"} in section_dim_groups.values()
        and {"500", "300", "2100"} in section_dim_groups.values(),
        section_dim_groups,
    )
    back_titles = [
        entity for entity in doc.modelspace().query("TEXT")
        if entity.dxf.text == "\u80cc\u9762" and float(entity.dxf.insert.x) > 1000
    ]
    check(
        "integrated back title stays above back window",
        bool(back_titles and max(float(entity.dxf.insert.y) for entity in back_titles) > 2900),
        [(float(entity.dxf.insert.x), float(entity.dxf.insert.y)) for entity in back_titles],
    )


def test_double_door_sized_handles_draw_on_front_only():
    def sized_handle_rects(front_handle: str, back_handle: str):
        req = CADRequest(
            door_type="对开门",
            zmls=front_handle,
            fmls=back_handle,
            handle_size="40*800",
        )

        info, checks, draw_params = build_cad_params(req)
        msg, buffer = run_integrated_system(info, checks, draw_params)
        check(f"double door sized-handle CAD generation returns buffer {front_handle}/{back_handle}", buffer is not None, msg)
        if not buffer:
            return [], []

        doc = ezdxf.read(io.StringIO(buffer.getvalue()))
        panel_polys = [
            entity for entity in doc.modelspace().query("LWPOLYLINE")
            if entity.dxf.layer == "A-DOOR-PANEL"
        ]
        long_handle_rects = []
        for entity in panel_polys:
            x1, x2, y1, y2 = poly_bounds(entity)
            if abs((x2 - x1) - 40) < 0.01 and abs((y2 - y1) - 800) < 0.01:
                long_handle_rects.append((x1, x2, y1, y2))
        front_rects = [bounds for bounds in long_handle_rects if bounds[1] < 1000]
        back_rects = [bounds for bounds in long_handle_rects if bounds[0] > 1000]
        return front_rects, back_rects

    front_rects, back_rects = sized_handle_rects("铝雕拉手", "标配拉手")
    front_centers = sorted(round((x1 + x2) / 2, 2) for x1, x2, _y1, _y2 in front_rects)
    check(
        "double door draws sized handles on both front leaves",
        len(front_rects) >= 2,
        f"front long handle rectangles: {front_rects}",
    )
    check(
        "double door front sized handles are split across two leaves",
        len(set(front_centers)) >= 2 and (front_centers[-1] - front_centers[0]) > 200,
        f"front long handle centers: {front_centers}",
    )
    check(
        "sized handle does not auto-copy to back view",
        len(back_rects) == 0,
        f"back long handle rectangles: {back_rects}",
    )
    front_rects_both, back_rects_both = sized_handle_rects("铝雕拉手", "铝雕拉手")
    back_centers_both = sorted(round((x1 + x2) / 2, 2) for x1, x2, _y1, _y2 in back_rects_both)
    check(
        "double door draws sized handles on both back leaves when back handle is sized",
        len(back_rects_both) >= 2,
        f"back long handle rectangles: {back_rects_both}",
    )
    check(
        "double door back sized handles are split across two leaves",
        len(set(back_centers_both)) >= 2 and (back_centers_both[-1] - back_centers_both[0]) > 200,
        f"back long handle centers: {back_centers_both}",
    )


def test_back_backpack_handle_stays_near_lock_edge():
    def bbls_x_for(open_dir: str, door_type: str = "单门"):
        req = CADRequest(
            door_type=door_type,
            sel_kx=open_dir,
            zmls="无",
            fmls="背包拉手",
        )
        info, checks, draw_params = build_cad_params(req)
        msg, buffer = run_integrated_system(info, checks, draw_params)
        check(f"back backpack {door_type} {open_dir} CAD generation returns buffer", buffer is not None, msg)
        if not buffer:
            return None
        doc = ezdxf.read(io.StringIO(buffer.getvalue()))
        bbls = [
            entity for entity in doc.modelspace().query("INSERT")
            if entity.dxf.name == "BBLS" and entity.dxf.layer == "A-DOOR-PANEL"
        ]
        frame_polys = [
            entity for entity in doc.modelspace().query("LWPOLYLINE")
            if entity.dxf.layer == "A-DOOR-FRAME"
        ]
        back_bounds = [
            poly_bounds(entity) for entity in frame_polys
            if poly_bounds(entity)[0] > 1000
        ]
        if not bbls or not back_bounds:
            return None
        back_min_x = min(bounds[0] for bounds in back_bounds)
        back_max_x = max(bounds[1] for bounds in back_bounds)
        return float(bbls[0].dxf.insert.x), (back_min_x + back_max_x) / 2

    right_result = bbls_x_for("右开")
    left_result = bbls_x_for("左开")
    double_right_result = bbls_x_for("右开", "对开门")
    double_left_result = bbls_x_for("左开", "对开门")
    check(
        "right-open single back backpack handle is on lock side",
        bool(right_result and right_result[0] < right_result[1]),
        str(right_result),
    )
    check(
        "left-open single back backpack handle is on lock side",
        bool(left_result and left_result[0] > left_result[1]),
        str(left_result),
    )
    check(
        "right-open double back backpack handle is near center lock edge",
        bool(double_right_result and double_right_result[0] < double_right_result[1] and abs(double_right_result[0] - double_right_result[1]) < 120),
        str(double_right_result),
    )
    check(
        "left-open double back backpack handle is near center lock edge",
        bool(double_left_result and double_left_result[0] > double_left_result[1] and abs(double_left_result[0] - double_left_result[1]) < 120),
        str(double_left_result),
    )


def test_cad_preview_svg_renders():
    req = CADRequest(dhdw="preview", gdmc="preview", sel_hys="暗合页", fingerprint_lock="无")
    info, checks, draw_params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("preview CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    svg = render_dxf_svg(buffer.getvalue())
    check("preview SVG starts with svg element", svg.startswith("<svg"), svg[:80])
    check("preview SVG contains drawing geometry", "<path" in svg or "<line" in svg, svg[:200])
    view_box = re.search(r'viewBox="([^"]+)"', svg)
    view_width = float(view_box.group(1).split()[2]) if view_box else 0
    check("preview SVG crops to front and back views", 0 < view_width < 7000, view_box.group(1) if view_box else svg[:120])


if __name__ == "__main__":
    test_cad_new_options_flow()
    test_a1022_handle_backpack_handle_and_adjustable_hinge()
    test_split_handle_uses_directional_blocks()
    test_back_a1022_handle_direction_blocks()
    test_door_panel_style_lines()
    test_disc_panel_style_draws_semicircle()
    test_pillar_handle_title_and_three_column_panel()
    test_double_door_sized_handles_draw_on_front_only()
    test_back_backpack_handle_stays_near_lock_edge()
    test_frame_defaults_and_single_back_mirror()
    test_dimension_spacing_and_trim_width_text()
    test_middle_door_dimension_text_and_transom_light_height()
    test_transom_pillar_lintel_label_and_view_gap()
    test_light_width_uses_pillar_inner_edges()
    test_new_defaults_fingerprint_and_transom_shape()
    test_integrated_door_sections_and_dimensions()
    test_cad_preview_svg_renders()
    print(f"\nPASS: {PASSED}")
    print(f"FAIL: {FAILED}")
    if FAILED:
        sys.exit(1)
