import ezdxf
import fulfillment_routes

from door_cad.exporters import build_combined_dxf, combined_dxf_filename
from door_cad.exporters.dxf_exporter import _renderer_parameters
from door_cad.models import FrameInput, ProjectMeta
from door_cad.services import calculate_frame_project
from fulfillment_database import FulfillmentDatabase
from test_bom_generation import create_door
from test_door_cad_api import _client, _request


def test_combined_dxf_contains_all_parts_layers_dimensions_and_audits_cleanly(tmp_path):
    geometry = calculate_frame_project(
        FrameInput(),
        ProjectMeta(orderNo="DD20260829001", projectName="标准门框"),
    )
    payload = build_combined_dxf(geometry)
    path = tmp_path / "combined.dxf"
    path.write_bytes(payload)
    document = ezdxf.readfile(path)
    modelspace = document.modelspace()

    expected_layers = {
        "L00_AUX", "L01_OUTER_CUT", "L02_INNER_CUT",
        "L10_GROOVE_FRONT", "L11_GROOVE_BACK",
        "L20_FACE_OUTER", "L21_GROOVE_OUTER", "L22_GROOVE_INNER", "L23_FACE_INNER",
        "L30_DIM", "L31_NOTE_CN", "L32_PART_ID", "L33_CENTER_MARK",
    }
    assert expected_layers.issubset({layer.dxf.name for layer in document.layers})
    assert {style.dxf.name for style in document.styles}.issuperset({"CN_TEXT", "NUM_TEXT"})
    assert {style.dxf.name for style in document.dimstyles}.issuperset(
        {"DIM_PLAN", "DIM_SECTION", "DIM_DETAIL"}
    )
    assert len(modelspace.query("DIMENSION")) >= 250

    cut_outer = list(modelspace.query('LWPOLYLINE[layer=="L01_OUTER_CUT"]'))
    assert len(cut_outer) == 4
    for entity in cut_outer:
        points = list(entity.get_points("xy"))
        assert points[0] == points[-1]

    outer_skin_paths = [entity for entity in cut_outer if len(list(entity.get_points("xy"))) == 13]
    assert len(outer_skin_paths) == 2
    for entity in outer_skin_paths:
        points = list(entity.get_points("xy"))
        ys = [point[1] for point in points]
        assert min(ys) + 47.0 in ys
        assert max(ys) - 47.0 in ys
        min_x, max_x = min(point[0] for point in points), max(point[0] for point in points)
        clipped_grooves = [
            line
            for layer in ("L10_GROOVE_FRONT", "L11_GROOVE_BACK")
            for line in modelspace.query(f'LINE[layer=="{layer}"]')
            if min_x < line.dxf.start.x < max_x
            and line.dxf.start.y == min(ys) + 47.0
            and line.dxf.end.y == max(ys) - 47.0
        ]
        assert clipped_grooves

    notes = "\n".join(entity.plain_text() for entity in modelspace.query("MTEXT"))
    assert "DD20260829001" in notes
    assert "标准门框" in notes
    assert "统一三行标注" in notes
    assert not document.audit().errors


def test_combined_dxf_supports_partial_part_selection(tmp_path):
    variants = (
        FrameInput(includeTop=False, includeBottom=False),
        FrameInput(includeLeft=False, includeRight=False),
        FrameInput(includeRight=False, includeBottom=False),
    )
    for index, inputs in enumerate(variants):
        geometry = calculate_frame_project(inputs, ProjectMeta(projectName=f"局部导出{index}"))
        path = tmp_path / f"partial-{index}.dxf"
        path.write_bytes(build_combined_dxf(geometry))
        document = ezdxf.readfile(path)
        assert document.modelspace().query("DIMENSION")
        assert not document.audit().errors


def test_v143_renderer_keeps_dynamic_hinge_datum_for_nonstandard_side_widths():
    geometry = calculate_frame_project(
        FrameInput(outerSideShort=60, outerSideLong=70),
        ProjectMeta(projectName="非标框宽"),
    )
    parameters = _renderer_parameters(geometry)
    assert parameters["skeleton_params"]["hinge_center_override"] == 102.0
    assert parameters["outer_params"]["hinge_center_override"] == 103.5


def test_combined_dxf_filename_is_windows_safe():
    geometry = calculate_frame_project(
        FrameInput(),
        ProjectMeta(orderNo="DD:01", projectName="测试/项目"),
    )
    assert combined_dxf_filename(geometry) == "DD_01-测试_项目-门框下料图.dxf"


def test_combined_dxf_endpoint_returns_authenticated_download(tmp_path):
    client = _client(tmp_path)
    payload = _request()
    payload["acknowledgeWarnings"] = True
    response = client.post("/api/door-cad/frame/export-dxf", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/dxf")
    assert "门框下料图.dxf" in response.headers["content-disposition"] or "%E9%97%A8%E6%A1%86" in response.headers["content-disposition"]
    path = tmp_path / "api.dxf"
    path.write_bytes(response.content)
    assert not ezdxf.readfile(path).audit().errors


def test_combined_dxf_endpoint_uses_frozen_door_unit_geometry(tmp_path):
    database = FulfillmentDatabase(tmp_path / "fulfillment.db", tmp_path / "files")
    door_id = create_door(database, {
        "product_name": "不锈钢镀铜门",
        "door_type": "单门",
        "frame_process": "新工艺",
        "dw": 1000,
        "dh": 2200,
        "fw_left_str": "55/75",
        "fw_right_str": "55/75",
        "fw_top_str": "85/100",
        "threshold_type": "高低槛",
        "th_str": "45/60",
        "sel_hys": "半钢暗合页",
        "hysl": "3个/扇",
    }, sales_order_id=91)
    original_database = fulfillment_routes.fulfillment_db
    fulfillment_routes.fulfillment_db = database
    try:
        response = _client(tmp_path).post(
            "/api/door-cad/frame/export-dxf",
            json={"doorUnitId": door_id, "acknowledgeWarnings": True},
        )
    finally:
        fulfillment_routes.fulfillment_db = original_database

    assert response.status_code == 200
    path = tmp_path / "door-unit.dxf"
    path.write_bytes(response.content)
    document = ezdxf.readfile(path)
    notes = "\n".join(entity.plain_text() for entity in document.modelspace().query("MTEXT"))
    assert "SO0091" in notes
    assert not document.audit().errors
