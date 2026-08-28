import ezdxf

from door_cad.exporters import build_combined_dxf, combined_dxf_filename
from door_cad.models import FrameInput, ProjectMeta
from door_cad.services import calculate_frame_project
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
        "L01_OUTER_CUT", "L02_INNER_CUT", "L03_GROOVE_INNER",
        "L04_GROOVE_OUTER", "L05_FOLD", "L06_DIM", "L07_NOTE", "L08_SECTION",
    }
    assert expected_layers.issubset({layer.dxf.name for layer in document.layers})
    assert len(modelspace.query('LWPOLYLINE[layer=="L01_OUTER_CUT"]')) == 8
    assert all(entity.closed for entity in modelspace.query('LWPOLYLINE[layer=="L01_OUTER_CUT"]'))
    assert len(modelspace.query("DIMENSION")) >= 16

    texts = [entity.dxf.text for entity in modelspace.query("TEXT")]
    for part in geometry.parts:
        assert part.partId in texts
    assert not any(entity.dxf.get("text_generation_flag", 0) & 2 for entity in modelspace.query("TEXT"))
    assert not document.audit().errors


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
