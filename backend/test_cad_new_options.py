import os
import sys
import io
import math
import re

import ezdxf


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from main import build_cad_params, _DEFAULT_DROPDOWN_OPTIONS, _resolve_mid_door_width
from models import CADRequest
from drawing import EzdxfDrawer, _build_hatch_library, _hatch_bounds, run_integrated_system
from cad_preview import _collect_entity, render_dxf_svg
from config import CONFIG


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
        and (poly_bounds(entity)[1] - poly_bounds(entity)[0]) > 300
        and (poly_bounds(entity)[3] - poly_bounds(entity)[2]) > 1000
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


def test_rectangular_glass_line_templates():
    def layer_lines(doc):
        return [
            entity for entity in doc.modelspace().query("LINE")
            if entity.dxf.layer == "A-DOOR-PANEL"
        ]

    def duplicate_line_segments(entities):
        counts = {}
        for entity in entities:
            start = (round(float(entity.dxf.start.x), 3), round(float(entity.dxf.start.y), 3))
            end = (round(float(entity.dxf.end.x), 3), round(float(entity.dxf.end.y), 3))
            key = tuple(sorted((start, end)))
            counts[key] = counts.get(key, 0) + 1
        return [key for key, count in counts.items() if count > 1]

    def centers_of_paired_coordinates(values, expected_gap=15):
        ordered = sorted(set(round(float(value), 3) for value in values))
        centers = []
        for first, second in zip(ordered, ordered[1:]):
            if abs((second - first) - expected_gap) < 0.05:
                centers.append((first + second) / 2)
        return centers

    transom_req = CADRequest(
        dw=1800,
        dh=2200,
        sel_qc="玻璃",
        qc_shape="矩形气窗",
        qc_height=400,
        qc_glass_style="六格线条",
        fingerprint_lock="无",
        sel_hys="暗合页",
    )
    transom_info, transom_checks, transom_params = build_cad_params(transom_req)
    check("transom glass style passes to info map", transom_info["QC_GLASS_STYLE"] == "六格线条", transom_info)
    check("transom glass style passes to drawing", transom_params["qc_glass_style"] == "六格线条", transom_params)
    transom_msg, transom_buffer = run_integrated_system(transom_info, transom_checks, transom_params)
    check("horizontal transom glass CAD generation returns buffer", transom_buffer is not None, transom_msg)
    if transom_buffer:
        transom_doc = ezdxf.read(io.StringIO(transom_buffer.getvalue()))
        glass_lines = [
            entity for entity in transom_doc.modelspace().query("LINE")
            if entity.dxf.layer == "A-DOOR-PANEL"
        ]
        horizontal_grid_lines = [
            entity for entity in glass_lines
            if abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) < 0.01
            and abs(float(entity.dxf.start.x) - float(entity.dxf.end.x)) > 1000
        ]
        vertical_grid_lines = [
            entity for entity in glass_lines
            if abs(float(entity.dxf.start.x) - float(entity.dxf.end.x)) < 0.01
            and 250 < abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) < 400
        ]
        check(
            "wide transom six-grid uses 3 columns by 2 rows",
            len(horizontal_grid_lines) >= 2 and len(vertical_grid_lines) >= 4,
            f"horizontal={len(horizontal_grid_lines)}, vertical={len(vertical_grid_lines)}",
        )
        glass_hatches = [
            entity for entity in transom_doc.modelspace().query("HATCH")
            if entity.dxf.layer == "A-DOOR-HATCH"
        ]
        check("transom grid includes glass hatch in both views", len(glass_hatches) >= 2, len(glass_hatches))

        vertical_xs = [
            entity.dxf.start.x for entity in layer_lines(transom_doc)
            if abs(float(entity.dxf.start.x) - float(entity.dxf.end.x)) < 0.01
            and abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) > 200
        ]
        horizontal_ys = [
            entity.dxf.start.y for entity in layer_lines(transom_doc)
            if abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) < 0.01
            and abs(float(entity.dxf.start.x) - float(entity.dxf.end.x)) > 500
        ]
        transom_x_centers = centers_of_paired_coordinates(vertical_xs)
        transom_y_centers = centers_of_paired_coordinates(horizontal_ys)
        check(
            "transom six-grid uses two vertical 15mm divider bands",
            len(transom_x_centers) >= 4,
            transom_x_centers,
        )
        check(
            "transom six-grid uses one horizontal 15mm divider band",
            len(transom_y_centers) >= 1,
            transom_y_centers,
        )
        if len(transom_x_centers) >= 4:
            front_centers = sorted(transom_x_centers)[:2]
            back_centers = sorted(transom_x_centers)[-2:]
            check(
                "transom six-grid divider centers are equally spaced in both views",
                abs((front_centers[1] - front_centers[0]) - (back_centers[1] - back_centers[0])) < 0.05,
                f"front={front_centers}, back={back_centers}",
            )

    panel_req = CADRequest(
        door_panel_style="H+型布局",
        panel_b2_glass_style="八格线条",
        back_door_panel_style="H型布局",
        back_panel_b2_glass_style="单圈外围线(封闭)",
        glass_line_inset=20,
        glass_line_spacing=20,
        fingerprint_lock="无",
        sel_hys="暗合页",
    )
    panel_info, panel_checks, panel_params = build_cad_params(panel_req)
    check("front B2 glass style passes to drawing", panel_params["panel_b2_glass_style"] == "八格线条", panel_params)
    check("back B2 glass style passes independently", panel_params["back_panel_b2_glass_style"] == "单圈外围线(封闭)", panel_params)
    panel_msg, panel_buffer = run_integrated_system(panel_info, panel_checks, panel_params)
    check("H/H+ B2 glass CAD generation returns buffer", panel_buffer is not None, panel_msg)
    if panel_buffer:
        panel_doc = ezdxf.read(io.StringIO(panel_buffer.getvalue()))
        panel_hatches = [
            entity for entity in panel_doc.modelspace().query("HATCH")
            if entity.dxf.layer == "A-DOOR-HATCH"
        ]
        check(
            "closed back B2 stays unfilled while front B2 is hatched",
            len(panel_hatches) == 1,
            len(panel_hatches),
        )
        front_panel_lines = layer_lines(panel_doc)
        long_vertical_xs = [
            entity.dxf.start.x for entity in front_panel_lines
            if abs(float(entity.dxf.start.x) - float(entity.dxf.end.x)) < 0.01
            and abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) > 300
        ]
        panel_band_centers = centers_of_paired_coordinates(long_vertical_xs)
        check(
            "vertical B2 eight-grid uses a centered 15mm divider band in both views",
            len(panel_band_centers) >= 1,
            panel_band_centers,
        )

    for style in ("无线条", "单圈外围线", "单圈外围线(封闭)", "四角回纹", "双边框", "双边框+花件", "六格线条", "八格线条"):
        style_req = CADRequest(
            dw=1800,
            dh=2200,
            sel_qc="玻璃",
            qc_shape="矩形气窗",
            qc_height=400,
            qc_glass_style=style,
            fingerprint_lock="无",
            sel_hys="暗合页",
        )
        style_info, style_checks, style_params = build_cad_params(style_req)
        style_msg, style_buffer = run_integrated_system(style_info, style_checks, style_params)
        check(f"rectangular transom style {style} generates CAD", style_buffer is not None, style_msg)
        if not style_buffer:
            continue
        style_doc = ezdxf.read(io.StringIO(style_buffer.getvalue()))
        style_hatches = [
            entity for entity in style_doc.modelspace().query("HATCH")
            if entity.dxf.layer == "A-DOOR-HATCH"
        ]
        expected_hatches = 0 if style in ("无线条", "单圈外围线(封闭)") else 2
        check(
            f"rectangular transom style {style} uses expected glass fill",
            len(style_hatches) == expected_hatches,
            len(style_hatches),
        )
        if style == "双边框+花件":
            flower_blocks = [
                entity for entity in style_doc.modelspace().query("INSERT")
                if entity.dxf.name == "HJ01"
            ]
            check("glass flower style imports four real HJ01 blocks per view", len(flower_blocks) == 8, len(flower_blocks))
            flower_xs = sorted(round(float(entity.dxf.insert.x), 3) for entity in flower_blocks)
            flower_ys = sorted(round(float(entity.dxf.insert.y), 3) for entity in flower_blocks)
            check(
                "glass flower style places two flowers on each side of both views",
                len(set(flower_xs)) == 4 and len(set(flower_ys)) == 2,
                f"xs={flower_xs}, ys={flower_ys}",
            )
            check(
                "glass flower style mirrors left and right HJ01 blocks",
                len({round(abs(float(entity.dxf.xscale)), 3) for entity in flower_blocks}) == 1
                and all(float(entity.dxf.xscale) > 0 for entity in flower_blocks),
                [float(entity.dxf.xscale) for entity in flower_blocks],
            )

            flower_lines = layer_lines(style_doc)
            diagonal_lines = [
                entity for entity in flower_lines
                if abs(float(entity.dxf.start.x) - float(entity.dxf.end.x)) > 20
                and abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) > 20
            ]
            check(
                "glass flower style draws four X squares per view",
                len(diagonal_lines) >= 16,
                len(diagonal_lines),
            )
            duplicates = duplicate_line_segments(flower_lines)
            check(
                "glass flower style has no coincident line entities",
                not duplicates,
                str(duplicates[:8]),
            )

        if style == "四角回纹":
            return_lines = layer_lines(style_doc)
            diagonal_lines = [
                entity for entity in return_lines
                if abs(float(entity.dxf.start.x) - float(entity.dxf.end.x)) > 5
                and abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) > 5
            ]
            check(
                "four-corner return style keeps only frame miter diagonals",
                len(diagonal_lines) == 16,
                len(diagonal_lines),
            )
            duplicates = duplicate_line_segments(return_lines)
            check(
                "four-corner return style has no coincident line entities",
                not duplicates,
                str(duplicates[:8]),
            )


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
        if entity.dxf.layer == "A-DOOR-PANEL"
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
    wipeouts = [entity for entity in doc.modelspace().query("WIPEOUT")]
    check(
        "panel drawing does not use hidden dashed edges",
        not hidden_lines,
        f"hidden={len(hidden_lines)}, wipeouts={len(wipeouts)}",
    )
    check("hardware masks are isolated on mask layer", all(entity.dxf.layer == "A-DOOR-MASK" for entity in wipeouts), [entity.dxf.layer for entity in wipeouts])
    layer_names = [layer.dxf.name for layer in doc.layers]
    check("panel helper geometry layer is removed", "A-DOOR-PANEL-GEOM" not in doc.layers, layer_names)
    check("hidden dashed panel layer is removed", "A-DOOR-HIDDEN" not in doc.layers, layer_names)

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


def test_panel_hatch_presets_and_masks():
    req = CADRequest(
        panel_preset="\u7d2b\u8346\u82b1\u6b3e",
        panel_fill_a="\u94b1\u5e01\u6b3e",
        fmks="",
        zmls="\u6807\u914d\u62c9\u624b",
        fingerprint_lock="\u5b89\u5fd7\u6770AF-12",
        sel_hys="\u6697\u5408\u9875",
    )
    info, checks, draw_params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("panel hatch preset CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return
    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    panel_hatches = [
        entity for entity in doc.modelspace().query("HATCH")
        if entity.dxf.layer == "A-DOOR-HATCH"
    ]
    patterns = [entity.dxf.pattern_name for entity in panel_hatches]
    check("zijinghua preset adds template hatch", "ZIJINGHUA" in patterns, patterns)
    check("fixed panel preset overrides stale custom fill", "QIANBI" not in patterns, patterns)
    check("preset adds vertical stripe hatch", "ANSI31" in patterns, patterns)
    pattern_line_counts = {
        entity.dxf.pattern_name: len(entity.pattern.lines)
        for entity in panel_hatches
    }
    check(
        "custom hatch keeps complete template definition",
        pattern_line_counts.get("ZIJINGHUA", 0) > 1000,
        str(pattern_line_counts),
    )
    check(
        "ANSI31 keeps a valid pattern definition",
        pattern_line_counts.get("ANSI31", 0) >= 1,
        str(pattern_line_counts),
    )
    wipeouts = [entity for entity in doc.modelspace().query("WIPEOUT") if entity.dxf.layer == "A-DOOR-MASK"]
    check("hardware mask wipeouts are generated above hatches", len(wipeouts) >= 2, len(wipeouts))

    for preset_name in ("紫荆花款", "钱币款", "竖条款", "流星雨款", "四方纳福款"):
        preset_req = CADRequest(
            panel_preset=preset_name,
            door_type="单门",
            sel_hys="暗合页",
            fingerprint_lock="无",
        )
        preset_info, preset_checks, preset_draw_params = build_cad_params(preset_req)
        preset_msg, preset_buffer = run_integrated_system(preset_info, preset_checks, preset_draw_params)
        check(f"{preset_name} CAD generation returns buffer", preset_buffer is not None, preset_msg)
        if not preset_buffer:
            continue

        preset_doc = ezdxf.read(io.StringIO(preset_buffer.getvalue()))
        panel_bounds = [
            poly_bounds(entity)
            for entity in preset_doc.modelspace().query("LWPOLYLINE")
            if entity.dxf.layer == "A-DOOR-PANEL" and entity.closed
        ]
        back_stripe_matches = []
        for hatch in preset_doc.modelspace().query("HATCH"):
            if hatch.dxf.layer != "A-DOOR-HATCH" or hatch.dxf.pattern_name != "ANSI31":
                continue
            bounds = _hatch_bounds(hatch)
            if not bounds:
                continue
            hatch_left, hatch_bottom, hatch_right, hatch_top = bounds
            if abs((hatch_right - hatch_left) - 100) > 0.01:
                continue
            containers = [
                panel
                for panel in panel_bounds
                if panel[0] <= hatch_left + 0.01
                and panel[1] >= hatch_right - 0.01
                and abs(panel[2] - hatch_bottom) < 0.01
                and abs(panel[3] - hatch_top) < 0.01
            ]
            if any(abs(panel[1] - hatch_right - 180) < 0.01 for panel in containers):
                back_stripe_matches.append(bounds)
        check(
            f"{preset_name} back panel keeps 180mm blank then 100mm vertical stripe",
            len(back_stripe_matches) == 1,
            str(back_stripe_matches),
        )

    polygon_doc = ezdxf.new("R2018")
    polygon_block = polygon_doc.blocks.new("POLYGON_MASK_TEST")
    polygon_block.add_lwpolyline(
        [(0, 0), (40, 0), (60, 20), (40, 40), (0, 40), (-20, 20)],
        close=True,
    )
    polygon_ms = polygon_doc.modelspace()
    polygon_drawer = EzdxfDrawer(polygon_doc, polygon_ms, "HINGE_TEST")
    mask_created = polygon_drawer.draw_wipeout_for_block("POLYGON_MASK_TEST", (100, 100))
    polygon_wipeout = next(iter(polygon_ms.query("WIPEOUT")), None)
    polygon_vertices = polygon_wipeout.boundary_path_wcs() if polygon_wipeout is not None else []
    check(
        "hardware mask follows a non-rectangular closed block outline",
        mask_created and len(polygon_vertices) > 4,
        str([(round(point.x, 2), round(point.y, 2)) for point in polygon_vertices]),
    )


def test_all_panel_hatch_definitions_survive_roundtrip():
    template_path = os.path.join(os.path.dirname(BACKEND_DIR), "template.dxf")
    template_doc = ezdxf.readfile(template_path)
    library = _build_hatch_library(template_doc)
    expected = {
        "\u7d2b\u8346\u82b1": ("ZIJINGHUA", 1000),
        "\u94b1\u5e01\u6b3e": ("QIANBI", 10),
        "\u6d41\u661f\u96e8": ("LIUXINGYU", 10),
        "\u56db\u65b9\u7eb3\u798f": ("EARTH", 2),
        "\u7ad6\u6761": ("ANSI31", 1),
        "\u659c\u5b9e\u865a": ("ANSI33", 2),
        "\u6b63\u5b9e\u865a": ("ANSI33", 2),
    }

    output_doc = ezdxf.new("R2018")
    output_ms = output_doc.modelspace()
    drawer = EzdxfDrawer(output_doc, output_ms, "HINGE_TEST")
    for index, sample_name in enumerate(expected):
        drawer.draw_hatch_rect(index * 120, 0, index * 120 + 100, 200, library[sample_name])

    stream = io.StringIO()
    output_doc.write(stream)
    roundtrip_doc = ezdxf.read(io.StringIO(stream.getvalue()))
    hatches = list(roundtrip_doc.modelspace().query("HATCH"))
    for hatch, (sample_name, (pattern_name, minimum_lines)) in zip(hatches, expected.items()):
        line_count = len(hatch.pattern.lines) if hatch.pattern is not None else 0
        check(
            f"hatch {sample_name} survives DXF roundtrip",
            hatch.dxf.pattern_name == pattern_name and line_count >= minimum_lines,
            f"pattern={hatch.dxf.pattern_name}, lines={line_count}",
        )
    check("DXF keeps fill display enabled", roundtrip_doc.header.get("$FILLMODE") == 1)
    check("DXF requests regeneration", roundtrip_doc.header.get("$REGENMODE") == 1)


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
        fw_left_str="50/62",
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
            if abs((x2 - x1) - 55) < 0.01:
                back_left_frames.append(entity)
            if abs((x2 - x1) - 50) < 0.01:
                back_right_frames.append(entity)
    check(
        "single back view mirrors back-side left/right frame widths",
        len(back_left_frames) >= 1 and len(back_right_frames) >= 1,
        f"back 55-width frames: {len(back_left_frames)}, back 50-width frames: {len(back_right_frames)}",
    )


def test_single_door_front_back_panel_consistent_and_frame_overlap():
    """单门正反面门板大小必须一致；宽框一侧左右框必须压住门板（门框遮挡门板）。"""
    DW = 900

    def view_geometry(nk: str):
        req = CADRequest(
            door_type="单门",
            sel_nk=nk,
            fw_left_str="55/85",
            fw_right_str="55/62",
            fw_top_str="55/75",
            th_str="55/75",
            zmls="无",
            fmls="无",
        )
        info, checks, draw_params = build_cad_params(req)
        msg, buffer = run_integrated_system(info, checks, draw_params)
        check(f"single {nk} panel CAD generation returns buffer", buffer is not None, msg)
        if not buffer:
            return None
        doc = ezdxf.read(io.StringIO(buffer.getvalue()))
        panels = [
            poly_bounds(entity) for entity in doc.modelspace().query("LWPOLYLINE")
            if entity.dxf.layer == "A-DOOR-PANEL" and poly_bounds(entity)[3] - poly_bounds(entity)[2] > 1500
        ]
        frames = [
            poly_bounds(entity) for entity in doc.modelspace().query("LWPOLYLINE")
            if entity.dxf.layer == "A-DOOR-FRAME"
        ]
        geometry = {}
        for label, min_x, max_x in (("front", -10 ** 9, 1500), ("back", 1500, 10 ** 9)):
            view_frames = [b for b in frames if min_x <= b[0] < max_x]
            view_panels = [b for b in panels if min_x <= b[0] < max_x]
            if not view_frames or not view_panels:
                geometry[label] = None
                continue
            origin = min(b[0] for b in view_frames)
            side_frames = [
                b for b in view_frames
                if (b[1] - b[0]) < 300 and (b[3] - b[2]) > 1500
            ]
            left_frame = min(
                (b for b in side_frames if abs(b[0] - origin) < 0.5),
                key=lambda b: b[0],
                default=None,
            )
            right_frame = min(
                (b for b in side_frames if abs(b[1] - (origin + DW)) < 0.5),
                key=lambda b: b[0],
                default=None,
            )
            panel = max(view_panels, key=lambda b: b[1] - b[0])
            geometry[label] = {
                "panel": (panel[0] - origin, panel[1] - origin),
                "left_frame_width": (left_frame[1] - left_frame[0]) if left_frame else None,
                "right_frame_width": (right_frame[1] - right_frame[0]) if right_frame else None,
            }
        return geometry

    outer_geom = view_geometry("外开")
    inner_geom = view_geometry("内开")

    for label, geom in (("outer-open", outer_geom), ("inner-open", inner_geom)):
        ok = bool(geom and geom["front"] and geom["back"] and geom["front"]["panel"] and geom["back"]["panel"])
        if ok:
            front_width = geom["front"]["panel"][1] - geom["front"]["panel"][0]
            back_width = geom["back"]["panel"][1] - geom["back"]["panel"][0]
            ok = abs(front_width - back_width) < 0.01
        check(
            f"{label} single door front/back panels have identical width",
            ok,
            str(geom),
        )

    # 宽框一侧（外开→背面，内开→正面）必须压住门板；小框一侧保持门缝间隙。
    if outer_geom and outer_geom["back"] and outer_geom["back"]["left_frame_width"] is not None:
        px1, px2 = outer_geom["back"]["panel"]
        check(
            "outer-open single back big frame overlaps panel on both sides",
            px1 < outer_geom["back"]["left_frame_width"]
            and px2 > DW - outer_geom["back"]["right_frame_width"],
            str(outer_geom["back"]),
        )
    else:
        check("outer-open single back big frame overlaps panel on both sides", False, str(outer_geom))
    if outer_geom and outer_geom["front"] and outer_geom["front"]["left_frame_width"] is not None:
        px1, px2 = outer_geom["front"]["panel"]
        check(
            "outer-open single front small frame keeps panel gap",
            px1 > outer_geom["front"]["left_frame_width"]
            and px2 < DW - outer_geom["front"]["right_frame_width"],
            str(outer_geom["front"]),
        )
    else:
        check("outer-open single front small frame keeps panel gap", False, str(outer_geom))

    if inner_geom and inner_geom["front"] and inner_geom["front"]["left_frame_width"] is not None:
        px1, px2 = inner_geom["front"]["panel"]
        check(
            "inner-open single front big frame overlaps panel on both sides",
            px1 < inner_geom["front"]["left_frame_width"]
            and px2 > DW - inner_geom["front"]["right_frame_width"],
            str(inner_geom["front"]),
        )
    else:
        check("inner-open single front big frame overlaps panel on both sides", False, str(inner_geom))
    if inner_geom and inner_geom["back"] and inner_geom["back"]["left_frame_width"] is not None:
        px1, px2 = inner_geom["back"]["panel"]
        check(
            "inner-open single back small frame keeps panel gap",
            px1 > inner_geom["back"]["left_frame_width"]
            and px2 < DW - inner_geom["back"]["right_frame_width"],
            str(inner_geom["back"]),
        )
    else:
        check("inner-open single back small frame keeps panel gap", False, str(inner_geom))


def test_large_board_horizontal_panels_and_outer_portal2():
    large_req = CADRequest(
        door_panel_style="大板布局",
        panel_fill_a="竖条",
        back_door_panel_style="大板布局",
        back_panel_fill_a="钱币款",
        fingerprint_lock="无",
        zmls="无",
        fmls="无",
    )
    large_info, large_checks, large_params = build_cad_params(large_req)
    large_msg, large_buffer = run_integrated_system(large_info, large_checks, large_params)
    check("large-board panel CAD generation returns buffer", large_buffer is not None, large_msg)
    if large_buffer:
        large_doc = ezdxf.read(io.StringIO(large_buffer.getvalue()))
        panel_hatches = [
            entity for entity in large_doc.modelspace().query("HATCH")
            if entity.dxf.layer == "A-DOOR-HATCH"
        ]
        check("large-board panel fills the full panel in both views", len(panel_hatches) >= 2, len(panel_hatches))

    horizontal_req = CADRequest(
        dh=2400,
        door_panel_style="三横式",
        panel_horizontal_a_height=1000,
        panel_horizontal_b_height=300,
        panel_fill_a="竖条",
        panel_fill_b="钱币款",
        panel_fill_c="四方纳福",
        fingerprint_lock="无",
        zmls="无",
        fmls="无",
    )
    horizontal_info, horizontal_checks, horizontal_params = build_cad_params(horizontal_req)
    check(
        "horizontal panel heights pass to drawing",
        horizontal_params["panel_horizontal_a_height"] == 1000
        and horizontal_params["panel_horizontal_b_height"] == 300,
        horizontal_params,
    )
    horizontal_msg, horizontal_buffer = run_integrated_system(horizontal_info, horizontal_checks, horizontal_params)
    check("three-horizontal panel CAD generation returns buffer", horizontal_buffer is not None, horizontal_msg)

    invalid_req = horizontal_req.model_copy(update={
        "panel_horizontal_a_height": 2000,
        "panel_horizontal_b_height": 500,
    })
    invalid_info, invalid_checks, invalid_params = build_cad_params(invalid_req)
    invalid_msg, invalid_buffer = run_integrated_system(invalid_info, invalid_checks, invalid_params)
    check(
        "invalid horizontal panel heights block CAD generation with a clear message",
        invalid_buffer is None and "分区高度无效" in invalid_msg,
        invalid_msg,
    )

    portal_req = CADRequest(
        has_outer=False,
        has_outer_portal=False,
        has_outer_landscape=False,
        has_outer_portal2=True,
        outer_portal2_pillar_width=180,
        outer_portal2_header_height=260,
        outer_portal2_lr_overlap=25,
        outer_portal2_top_overlap=30,
        fingerprint_lock="无",
    )
    portal_info, portal_checks, portal_params = build_cad_params(portal_req)
    check("outer portal2 is marked as a portal", portal_checks["OUTER_PORTAL"] == "√", portal_checks)
    check(
        "outer portal2 preserves independent geometry settings",
        portal_params["has_outer_portal2"] is True
        and portal_params["trim_front"] == 180
        and portal_params["trim_front_right"] == 180
        and portal_params["trim_front_top"] == 260
        and portal_params["outer_portal2_lr_overlap"] == 25
        and portal_params["outer_portal2_top_overlap"] == 30,
        portal_params,
    )
    check(
        "outer portal2 note hides the form-only number suffix",
        "外门头门柱：" in portal_info["BZ"] and "外门头门柱2" not in portal_info["BZ"],
        portal_info["BZ"],
    )
    portal_msg, portal_buffer = run_integrated_system(portal_info, portal_checks, portal_params)
    check("outer portal2 CAD generation returns buffer", portal_buffer is not None, portal_msg)


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
    trim_width_dims = [
        entity for entity in dims
        if abs(float(entity.dxf.angle)) < 0.01
        and abs(abs(float(entity.dxf.defpoint3.x) - float(entity.dxf.defpoint2.x)) - 160) < 0.01
    ]
    check(
        "trim width dimension uses dynamic measured text",
        any(entity.dxf.text == "<>" for entity in trim_width_dims) and " 160" not in dim_texts,
        dim_texts,
    )

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


def test_outer_portal_draws_separate_rectangles_and_header_dimension():
    req = CADRequest(
        has_outer=False,
        has_outer_portal=True,
        has_inner=False,
        outer_portal_pillar_width=180,
        outer_portal_header_height=260,
        trim_style_outer="03款包套",
    )

    info, checks, draw_params = build_cad_params(req)
    msg, buffer = run_integrated_system(info, checks, draw_params)
    check("outer portal CAD generation returns buffer", buffer is not None, msg)
    if not buffer:
        return

    doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    front_trim_polys = []
    for entity in doc.modelspace().query("LWPOLYLINE"):
        if entity.dxf.layer != "A-DOOR-TRIM":
            continue
        x1, x2, y1, y2 = poly_bounds(entity)
        if x2 < 1000 and y2 > 1000:
            front_trim_polys.append(entity)

    check(
        "outer portal uses two pillars and one header rectangle",
        len(front_trim_polys) == 3 and all(entity.closed and len(list(entity.get_points("xy"))) == 4 for entity in front_trim_polys),
        [poly_bounds(entity) for entity in front_trim_polys],
    )

    header_dims = [
        entity for entity in doc.modelspace().query("DIMENSION")
        if abs(float(entity.dxf.angle) - 90) < 0.01
        and abs(abs(float(entity.dxf.defpoint3.y) - float(entity.dxf.defpoint2.y)) - 260) < 0.01
    ]
    check("outer portal header height dimension is dynamic", any(entity.dxf.text == "<>" for entity in header_dims), [entity.dxf.text for entity in header_dims])

    pillar_dims = [
        entity for entity in doc.modelspace().query("DIMENSION")
        if abs(float(entity.dxf.angle)) < 0.01
        and abs(abs(float(entity.dxf.defpoint3.x) - float(entity.dxf.defpoint2.x)) - 180) < 0.01
    ]
    check("outer portal pillar width dimension is dynamic", any(entity.dxf.text == "<>" for entity in pillar_dims), [entity.dxf.text for entity in pillar_dims])

    front_door_height_dims = [
        entity for entity in doc.modelspace().query("DIMENSION")
        if abs(float(entity.dxf.angle) - 90) < 0.01
        and float(entity.dxf.defpoint2.x) < 1500
        and abs(abs(float(entity.dxf.defpoint3.y) - float(entity.dxf.defpoint2.y)) - req.dh) < 0.01
    ]
    check("outer portal front view has one door height dimension", len(front_door_height_dims) == 1, [entity.dxf.text for entity in front_door_height_dims])


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

    middle_width_dims = [
        entity for entity in doc.modelspace().query("DIMENSION")
        if entity.dxf.text == "中门内空宽 <>" and abs(float(entity.dxf.angle)) < 0.01
    ]
    check("pillar drawing has one middle clear-width dimension", len(middle_width_dims) == 1, len(middle_width_dims))
    if middle_width_dims:
        middle_dim = middle_width_dims[0]
        middle_x1 = round(float(middle_dim.dxf.defpoint2.x), 2)
        middle_x2 = round(float(middle_dim.dxf.defpoint3.x), 2)
        check(
            "middle clear width dimensions between pillar inner edges",
            (middle_x1, middle_x2) == (x1, x2),
            ((middle_x1, middle_x2), (x1, x2)),
        )

    four_req = CADRequest(
        door_type="四开门",
        has_pillar=True,
        pillar_width_str="55/85",
        mark_light_size=True,
    )
    four_info, four_checks, four_draw_params = build_cad_params(four_req)
    four_msg, four_buffer = run_integrated_system(four_info, four_checks, four_draw_params)
    check("four-door pillar clear-width CAD generation returns buffer", four_buffer is not None, four_msg)
    if four_buffer:
        four_doc = ezdxf.read(io.StringIO(four_buffer.getvalue()))
        four_light_dims = [
            entity for entity in four_doc.modelspace().query("DIMENSION")
            if entity.dxf.text.startswith("见光宽") and abs(float(entity.dxf.angle)) < 0.01
        ]
        four_middle_dims = [
            entity for entity in four_doc.modelspace().query("DIMENSION")
            if entity.dxf.text == "中门内空宽 <>" and abs(float(entity.dxf.angle)) < 0.01
        ]
        check(
            "four-door middle and light dimensions use the same pillar inner edges",
            len(four_light_dims) == 1
            and len(four_middle_dims) == 1
            and round(float(four_light_dims[0].dxf.defpoint2.x), 2) == round(float(four_middle_dims[0].dxf.defpoint2.x), 2)
            and round(float(four_light_dims[0].dxf.defpoint3.x), 2) == round(float(four_middle_dims[0].dxf.defpoint3.x), 2),
            (len(four_light_dims), len(four_middle_dims)),
        )


def test_middle_clear_width_input_and_new_hidden_hinges():
    no_pillar_req = CADRequest(
        door_type="四开门",
        dw=2400,
        middle_gap=4,
        mid_clear_width=1000,
        has_pillar=False,
    )
    check(
        "no-pillar middle clear width resolves leaf width",
        _resolve_mid_door_width(no_pillar_req, "四开门") == 498,
        _resolve_mid_door_width(no_pillar_req, "四开门"),
    )
    info, checks, params = build_cad_params(no_pillar_req)
    check("resolved no-pillar leaf width reaches CAD params", params["mid_door_width"] == 498, params)
    message, buffer = run_integrated_system(info, checks, params)
    check("no-pillar middle clear-width CAD generation returns buffer", buffer is not None, message)
    if buffer:
        doc = ezdxf.read(io.StringIO(buffer.getvalue()))
        dims = [
            entity for entity in doc.modelspace().query("DIMENSION")
            if entity.dxf.text == "中门内空宽 <>" and abs(float(entity.dxf.angle)) < 0.01
        ]
        measured = abs(float(dims[0].dxf.defpoint3.x) - float(dims[0].dxf.defpoint2.x)) if dims else 0
        check("no-pillar middle clear dimension equals input", len(dims) == 1 and abs(measured - 1000) < 0.01, measured)

    two_fixed_req = CADRequest(
        door_type="两定两开",
        dw=2400,
        middle_gap=4,
        mid_clear_width=820,
        has_pillar=False,
    )
    check(
        "two-fixed middle clear width resolves leaf width",
        _resolve_mid_door_width(two_fixed_req, "两定两开") == 408,
        _resolve_mid_door_width(two_fixed_req, "两定两开"),
    )
    _, _, two_fixed_params = build_cad_params(two_fixed_req)
    check("resolved two-fixed leaf width reaches CAD params", two_fixed_params["mid_door_width"] == 408, two_fixed_params)

    pillar_req = CADRequest(
        door_type="四开门",
        dw=2400,
        middle_gap=2,
        mid_clear_width=900,
        has_pillar=True,
        pillar_width_str="55/85",
        sel_nk="内开",
    )
    check(
        "pillar middle clear width resolves leaf width",
        _resolve_mid_door_width(pillar_req, "四开门") == 462,
        _resolve_mid_door_width(pillar_req, "四开门"),
    )
    info, checks, params = build_cad_params(pillar_req)
    message, buffer = run_integrated_system(info, checks, params)
    check("pillar middle clear-width CAD generation returns buffer", buffer is not None, message)
    if buffer:
        doc = ezdxf.read(io.StringIO(buffer.getvalue()))
        dims = [
            entity for entity in doc.modelspace().query("DIMENSION")
            if entity.dxf.text == "中门内空宽 <>" and abs(float(entity.dxf.angle)) < 0.01
        ]
        measured = abs(float(dims[0].dxf.defpoint3.x) - float(dims[0].dxf.defpoint2.x)) if dims else 0
        check("pillar middle clear dimension equals input", len(dims) == 1 and abs(measured - 900) < 0.01, measured)

    hinge_options = _DEFAULT_DROPDOWN_OPTIONS["HINGES"]
    for hinge_name in ("半钢暗合页", "全钢暗合页"):
        check(f"{hinge_name} is a default hinge option", hinge_name in hinge_options, hinge_options)
        check(f"{hinge_name} maps to hidden hinge block", CONFIG.HINGE_TYPES.get(hinge_name) == "暗合页块", CONFIG.HINGE_TYPES)


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
        "arched transom uses real arc entities instead of a segmented range polyline",
        not any(len(list(entity.get_points("xy"))) > 16 for entity in arch_frame_polys),
        arch_frame_bounds,
    )

    panel_bounds = [
        poly_bounds(entity)
        for entity in arch_doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "A-DOOR-PANEL"
    ]
    panel_heights = sorted({
        round(float(y2 - y1), 2)
        for x1, x2, y1, y2 in panel_bounds
        if (x2 - x1) > 300 and (y2 - y1) > 1000
    })
    check("front and back door panels have the same height", len(panel_heights) == 1, panel_heights)

    arch_dim_texts = [entity.dxf.text for entity in arch_doc.modelspace().query("DIMENSION")]
    check("arched transom door-height dimension omits label", "\u95e8\u9ad8 <>" not in arch_dim_texts, arch_dim_texts)

    arch_door_req = CADRequest(
        dh=2880,
        fw_top_str="55/70",
        sel_qc="\u65e0",
        is_arch_door=True,
        arch_spring_height=2400,
        has_outer=True,
        trim_front_in=160,
        trim_style_outer="\u0030\u0031\u6b3e\u5305\u5957",
    )
    door_info, door_checks, door_draw_params = build_cad_params(arch_door_req)
    check("arched door flag passes to drawing", door_draw_params["is_arch_door"] is True, door_draw_params)
    check("arched door spring height passes to drawing", door_draw_params["arch_spring_height"] == 2400, door_draw_params)
    door_msg, door_buffer = run_integrated_system(door_info, door_checks, door_draw_params)
    check("arched door CAD generation returns buffer", door_buffer is not None, door_msg)
    if door_buffer:
        door_doc = ezdxf.read(io.StringIO(door_buffer.getvalue()))
        door_frame_arcs = [entity for entity in door_doc.modelspace().query("ARC") if entity.dxf.layer == "A-DOOR-FRAME"]
        door_trim_arcs = [entity for entity in door_doc.modelspace().query("ARC") if entity.dxf.layer == "A-DOOR-TRIM"]
        check("arched door draws frame arcs", len(door_frame_arcs) >= 4, len(door_frame_arcs))
        check("arched door draws trim arcs", len(door_trim_arcs) >= 4, len(door_trim_arcs))
        arch_panel_polys = [
            entity for entity in door_doc.modelspace().query("LWPOLYLINE")
            if entity.dxf.layer == "A-DOOR-PANEL"
            and len(list(entity.get_points("xyseb"))) == 4
            and any(abs(point[4]) > 0.001 for point in entity.get_points("xyseb"))
        ]
        check("arched door panel top uses a real bulged arc segment", len(arch_panel_polys) >= 2, len(arch_panel_polys))
        door_dim_texts = [entity.dxf.text for entity in door_doc.modelspace().query("DIMENSION")]
        check("arched door spring height dimension is drawn", "2400" in door_dim_texts, door_dim_texts)


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
        "right-open single back backpack handle is on lock side (mirrored back view: lock edge on view right)",
        bool(right_result and right_result[0] > right_result[1]),
        str(right_result),
    )
    check(
        "left-open single back backpack handle is on lock side (mirrored back view: lock edge on view left)",
        bool(left_result and left_result[0] < left_result[1]),
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

    mirrored_req = CADRequest(
        door_type="四开门",
        sel_kx="左开",
        sel_nk="内开",
        dw=1800,
        mid_door_width=500,
        fingerprint_lock="安志杰AF-12",
        zmls="无",
        fmls="无",
    )
    mirrored_info, mirrored_checks, mirrored_params = build_cad_params(mirrored_req)
    mirrored_msg, mirrored_buffer = run_integrated_system(mirrored_info, mirrored_checks, mirrored_params)
    check("left-opening four-door preview CAD generation returns buffer", mirrored_buffer is not None, mirrored_msg)
    if mirrored_buffer:
        mirrored_doc = ezdxf.read(io.StringIO(mirrored_buffer.getvalue()))
        fingerprint_inserts = [
            entity for entity in mirrored_doc.modelspace().query('INSERT[name=="AZJ"]')
            if abs(float(entity.dxf.insert.x)) < 1000
        ]
        primitives = []
        if fingerprint_inserts:
            _collect_entity(fingerprint_inserts[0], primitives)
        preview_x_values = [x for primitive in primitives for x, _y in primitive.points]
        check(
            "mirrored fingerprint preview stays around its DXF insertion point",
            bool(fingerprint_inserts and preview_x_values)
            and max(abs(x - float(fingerprint_inserts[0].dxf.insert.x)) for x in preview_x_values) < 200,
            (float(fingerprint_inserts[0].dxf.insert.x) if fingerprint_inserts else None, preview_x_values[:8]),
        )


def test_optional_structural_occlusion_keeps_source_geometry():
    base_req = CADRequest(
        door_type="对开门",
        has_outer=True,
        has_inner=True,
        zmls="A1022",
        fmls="背包拉手",
        fingerprint_lock="安志杰AF-12",
        enable_occlusion=False,
    )
    enabled_req = base_req.model_copy(update={"enable_occlusion": True})

    base_info, base_checks, base_params = build_cad_params(base_req)
    enabled_info, enabled_checks, enabled_params = build_cad_params(enabled_req)
    _base_msg, base_buffer = run_integrated_system(base_info, base_checks, base_params)
    enabled_msg, enabled_buffer = run_integrated_system(enabled_info, enabled_checks, enabled_params)
    check("occlusion CAD generation returns buffer", enabled_buffer is not None, enabled_msg)
    if not base_buffer or not enabled_buffer:
        return

    base_doc = ezdxf.read(io.StringIO(base_buffer.getvalue()))
    enabled_doc = ezdxf.read(io.StringIO(enabled_buffer.getvalue()))
    base_ms = base_doc.modelspace()
    enabled_ms = enabled_doc.modelspace()

    base_masks = [entity for entity in base_ms.query("WIPEOUT") if entity.dxf.layer == "A-DOOR-OCCLUSION"]
    enabled_masks = [entity for entity in enabled_ms.query("WIPEOUT") if entity.dxf.layer == "A-DOOR-OCCLUSION"]
    check("occlusion is disabled by default", len(base_masks) == 0, str(len(base_masks)))
    check("occlusion creates structural masks when enabled", len(enabled_masks) > 0, str(len(enabled_masks)))

    for layer in ("A-DOOR-PANEL", "A-DOOR-FRAME", "A-DOOR-TRIM"):
        base_count = len([entity for entity in base_ms if entity.dxf.layer == layer and entity.dxftype() != "WIPEOUT"])
        enabled_count = len([entity for entity in enabled_ms if entity.dxf.layer == layer and entity.dxftype() != "WIPEOUT"])
        check(
            f"occlusion keeps original {layer} geometry",
            enabled_count == base_count,
            f"{base_count} -> {enabled_count}",
        )

    ordered = list(enabled_ms.entities_in_redraw_order())
    mask_indexes = [index for index, entity in enumerate(ordered) if entity.dxf.layer == "A-DOOR-OCCLUSION"]
    foreground_indexes = [
        index for index, entity in enumerate(ordered)
        if entity.dxftype() in {"DIMENSION", "TEXT", "MTEXT", "INSERT"}
        and entity.dxf.layer != "ORDER_FORM"
    ]
    check(
        "hardware text and dimensions stay above structural masks",
        bool(mask_indexes and foreground_indexes and min(foreground_indexes) > min(mask_indexes)),
        f"masks={mask_indexes[:3]}, foreground={foreground_indexes[:3]}",
    )

    enabled_svg = render_dxf_svg(enabled_buffer.getvalue())
    check(
        "CAD preview renders structural wipeouts",
        'class="cad-wipeout" data-layer="A-DOOR-OCCLUSION"' in enabled_svg,
        enabled_svg[:240],
    )


def test_outer_landscape_trim_with_occlusion():
    req = CADRequest(
        dhdw="一门一景测试",
        st_val="连体锁",
        sel_hys="暗合页",
        fingerprint_lock="无",
        has_outer=False,
        has_outer_portal=False,
        has_outer_landscape=True,
        outer_landscape_left_width=150,
        outer_landscape_right_width=180,
        outer_landscape_top_height=160,
        outer_landscape_left_overlap=20,
        outer_landscape_right_overlap=25,
        outer_landscape_top_overlap=30,
        enable_occlusion=True,
    )
    info, checks, draw_params = build_cad_params(req)
    check("one-scene trim is marked as outer trim", checks["OUTER"] == "√", str(checks))
    check("one-scene trim preserves three independent overlap values", (
        draw_params["outer_landscape_left_overlap"],
        draw_params["outer_landscape_right_overlap"],
        draw_params["outer_landscape_top_overlap"],
    ) == (20, 25, 30), str(draw_params))
    message, buffer = run_integrated_system(info, checks, draw_params)
    check("one-scene CAD generation supports occlusion", buffer is not None, message)
    if not buffer:
        return
    landscape_doc = ezdxf.read(io.StringIO(buffer.getvalue()))
    landscape_width_dims = sorted(
        round(abs(float(entity.dxf.defpoint3.x) - float(entity.dxf.defpoint2.x)), 2)
        for entity in landscape_doc.modelspace().query("DIMENSION")
        if abs(float(entity.dxf.angle)) < 0.01
        and round(abs(float(entity.dxf.defpoint3.x) - float(entity.dxf.defpoint2.x)), 2) in {150.0, 180.0}
    )
    check(
        "one-scene left and right width dimensions use independent inputs",
        landscape_width_dims[:2] == [150.0, 180.0],
        landscape_width_dims,
    )
    svg = render_dxf_svg(buffer.getvalue())
    check("one-scene CAD preview supports occlusion", svg.startswith("<svg") and "cad-wipeout" in svg, svg[:180])


def test_order_title_product_name_and_simple_products():
    req = CADRequest(
        order_title="杭州兰庭新贵门业",
        material="0.8mm",
        product_name="不锈钢镀铜门",
        st_val="连体锁",
    )
    info, _checks, params = build_cad_params(req)
    check("order title maps to TT", info["TT"] == "杭州兰庭新贵门业", info)
    check("material and product name map to CPMC", info["CPMC"] == "0.8mm的不锈钢镀铜门", info)
    check("legacy ZZCL keeps the same visible product name", info["ZZCL"] == info["CPMC"], info)
    check("normal product keeps door drawing", params["simple_product"] is False, params)
    message, buffer = run_integrated_system(info, _checks, params)
    check("normal product CAD generation returns buffer", buffer is not None, message)
    if buffer:
        product_doc = ezdxf.read(io.StringIO(buffer.getvalue()))
        order_form = product_doc.blocks.get("ORDER_FORM")
        block_cpmc = [entity.dxf.text for entity in order_form.query("ATTDEF") if entity.dxf.tag == "CPMC"]
        block_title = [entity.dxf.text for entity in order_form.query("ATTDEF") if entity.dxf.tag == "TT"]
        check("current template CPMC attribute is filled", block_cpmc == ["0.8mm的不锈钢镀铜门"], block_cpmc)
        check("current template TT attribute is filled", block_title == ["杭州兰庭新贵门业"], block_title)

    simple_info, _simple_checks, simple_params = build_cad_params(CADRequest(
        product_name="牌匾",
        material="1.0mm",
        ys="黑色",
    ))
    check("plaque uses simple-product drawing mode", simple_params["simple_product"] is True, simple_params)
    check("plaque uses slash placeholders", simple_info["ST"] == "/" and simple_info["ZMLS"] == "/", simple_info)
    message, buffer = run_integrated_system(simple_info, _simple_checks, simple_params)
    check("plaque CAD generation returns buffer", buffer is not None, message)

    canopy_info, _canopy_checks, canopy_params = build_cad_params(CADRequest(
        product_name="雨棚",
        material="1.2mm",
        ys="2号色",
        dw=1800,
        dh=600,
    ))
    check("canopy uses simple-product drawing mode", canopy_params["simple_product"] is True, canopy_params)
    check("canopy uses slash placeholders", canopy_info["ST"] == "/" and canopy_info["ZMLS"] == "/", canopy_info)


if __name__ == "__main__":
    test_cad_new_options_flow()
    test_a1022_handle_backpack_handle_and_adjustable_hinge()
    test_split_handle_uses_directional_blocks()
    test_back_a1022_handle_direction_blocks()
    test_door_panel_style_lines()
    test_rectangular_glass_line_templates()
    test_disc_panel_style_draws_semicircle()
    test_pillar_handle_title_and_three_column_panel()
    test_panel_hatch_presets_and_masks()
    test_all_panel_hatch_definitions_survive_roundtrip()
    test_double_door_sized_handles_draw_on_front_only()
    test_back_backpack_handle_stays_near_lock_edge()
    test_frame_defaults_and_single_back_mirror()
    test_single_door_front_back_panel_consistent_and_frame_overlap()
    test_large_board_horizontal_panels_and_outer_portal2()
    test_dimension_spacing_and_trim_width_text()
    test_outer_portal_draws_separate_rectangles_and_header_dimension()
    test_middle_door_dimension_text_and_transom_light_height()
    test_transom_pillar_lintel_label_and_view_gap()
    test_light_width_uses_pillar_inner_edges()
    test_middle_clear_width_input_and_new_hidden_hinges()
    test_new_defaults_fingerprint_and_transom_shape()
    test_integrated_door_sections_and_dimensions()
    test_cad_preview_svg_renders()
    test_optional_structural_occlusion_keeps_source_geometry()
    test_outer_landscape_trim_with_occlusion()
    test_order_title_product_name_and_simple_products()
    print(f"\nPASS: {PASSED}")
    print(f"FAIL: {FAILED}")
    if FAILED:
        sys.exit(1)
