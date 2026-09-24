import base64
import io
import os
import sys

import pytest
from fastapi.testclient import TestClient
from PIL import Image

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from auth import create_token
from main import app
from rendering.database import render_db, utc_now_iso
from rendering.providers import RenderProviderRequest
from rendering.service import execute_precise_render_task
from rendering.layered_render import DxfGeometryValidationError
import rendering.layered_render as layered_render
import rendering.routes as render_routes
import rendering.service as render_service


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _provider_request():
    return RenderProviderRequest(
        config={},
        prompt="test",
        size="original",
        count=1,
        line_art={},
        style_reference=None,
        assets=[],
        temp_assets=[],
    )


def _precise_dxf_task(tmp_path):
    dxf_path = tmp_path / "source.dxf"
    dxf_path.write_text("0\nEOF\n", encoding="ascii")
    return render_db.create_task({
        "renderMode": "precise",
        "sourceType": "dxf",
        "sourceSide": "front",
        "files": [{"role": "source_dxf", "filePath": str(dxf_path)}],
    })


def test_precise_background_task_persists_geometry_metadata(tmp_path, monkeypatch):
    task = _precise_dxf_task(tmp_path)
    validation = {"valid": True, "errors": [], "warnings": []}
    manifest = {"units": "mm", "transform_id": "cad-test", "roles": {}}

    monkeypatch.setattr(layered_render, "render_layered_dxf", lambda *args, **kwargs: {
        "selected_jpg": PNG_1X1,
        "selected_layer_pngs": {"panel": PNG_1X1},
        "material_mode": "flat",
        "material_note": "",
        "geometry_manifest": manifest,
        "geometry_validation": validation,
    })
    try:
        completed = execute_precise_render_task(task["id"], _provider_request())
        assert completed["status"] == "completed"
        assert completed["geometryValidation"] == validation
        assert completed["geometryManifest"]["units"] == "mm"
    finally:
        render_db.delete_task(task["id"])


def test_precise_background_task_passes_selected_side_to_renderer(tmp_path, monkeypatch):
    task = _precise_dxf_task(tmp_path)
    render_db.update_task(task["id"], {"sourceSide": "back"})
    captured = {}

    def fake_render(*args, **kwargs):
        captured.update(kwargs)
        return {
            "selected_side": "back",
            "selected_jpg": PNG_1X1,
            "selected_layer_pngs": {"panel": PNG_1X1},
            "material_mode": "flat",
            "material_note": "",
            "geometry_manifest": {"units": "mm", "roles": {}},
            "geometry_validation": {"valid": True, "errors": [], "warnings": []},
        }

    monkeypatch.setattr(layered_render, "render_layered_dxf", fake_render)
    try:
        completed = execute_precise_render_task(task["id"], _provider_request())
        assert completed["status"] == "completed"
        assert captured["selected_side"] == "back"
    finally:
        render_db.delete_task(task["id"])


def test_precise_background_task_persists_structured_geometry_failure(tmp_path, monkeypatch):
    task = _precise_dxf_task(tmp_path)
    validation = {
        "valid": False,
        "errors": [{"code": "MISSING_FRAME_GEOMETRY", "role": "frame", "message": "门框无有效几何"}],
        "warnings": [],
    }
    manifest = {"units": "mm", "transform_id": "cad-test", "roles": {}}

    def fail(*args, **kwargs):
        raise DxfGeometryValidationError(validation, manifest)

    monkeypatch.setattr(layered_render, "render_layered_dxf", fail)
    try:
        failed = execute_precise_render_task(task["id"], _provider_request())
        assert failed["status"] == "failed"
        assert failed["errorType"] == "dxf_geometry_validation"
        assert failed["geometryValidation"]["errors"][0]["role"] == "frame"
        assert failed["geometryManifest"]["units"] == "mm"
        assert "门框无有效几何" in failed["errorMessage"]
    finally:
        render_db.delete_task(task["id"])


@pytest.mark.parametrize(
    ("mode", "requested", "expected"),
    [
        ("quick", "", "2k"),
        ("quick", "original", "2k"),
        ("precise", "", "4k"),
        ("precise", "original", "4k"),
        ("precise", "2k", "2k"),
    ],
)
def test_resolve_render_size(mode, requested, expected):
    assert render_service._resolve_render_size(mode, requested) == expected


def test_clean_product_prompt_removes_visible_drafting_artifacts():
    prompt = render_service._effective_prompt("铜色门", "quick")

    assert "不显示线稿" in prompt
    assert "尺寸线" in prompt
    assert "真实" in prompt


def test_component_recomposition_ignores_outline_and_keeps_hardware_on_top(tmp_path, monkeypatch):
    panel_path = tmp_path / "panel.png"
    hardware_path = tmp_path / "hardware.png"
    outline_path = tmp_path / "outline.png"
    Image.new("RGBA", (40, 50), (210, 30, 30, 255)).save(panel_path)
    hardware = Image.new("RGBA", (40, 50), (0, 0, 0, 0))
    for x in range(15, 25):
        for y in range(20, 30):
            hardware.putpixel((x, y), (20, 190, 50, 255))
    hardware.save(hardware_path)
    Image.new("RGBA", (40, 50), (0, 0, 0, 255)).save(outline_path)

    def version(path):
        return {"currentVersion": 1, "versions": [{"version": 1, "filePath": str(path)}]}

    captured = {}

    def fake_save_bytes(data, filename, _subdir):
        captured["data"] = data
        return {"url": "/result.jpg", "filePath": str(tmp_path / filename), "originalName": filename}

    monkeypatch.setattr(render_service, "save_bytes", fake_save_bytes)
    render_service._compose_component_layers(
        "task-1",
        {
            "panel": version(panel_path),
            "hardware": version(hardware_path),
            "outline": version(outline_path),
        },
    )

    image = Image.open(io.BytesIO(captured["data"])).convert("RGB")
    assert image.getpixel((5, 5))[0] > 150
    center = image.getpixel((20, 25))
    assert center[1] > center[0] * 3


def test_component_recomposition_rejects_mismatched_canvas(tmp_path, monkeypatch):
    panel_path = tmp_path / "panel.png"
    frame_path = tmp_path / "frame.png"
    Image.new("RGBA", (40, 50), (210, 30, 30, 255)).save(panel_path)
    Image.new("RGBA", (41, 50), (90, 90, 90, 255)).save(frame_path)

    def version(path):
        return {"currentVersion": 1, "versions": [{"version": 1, "filePath": str(path)}]}

    with pytest.raises(ValueError, match="frame|panel"):
        render_service._compose_component_layers(
            "task-2",
            {"panel": version(panel_path), "frame": version(frame_path)},
        )


def main():
    client = TestClient(app)
    config = render_db.create_model_config({
        "name": "background-test",
        "provider": "image2_proxy",
        "baseUrl": "https://example.test",
        "apiKey": "sk-test",
        "model": "gpt-image-2",
        "endpoint": "/images/edits",
        "apiType": "openai_images_edits",
    })
    original_execute = render_routes.execute_render_task

    def fake_execute(task_id, provider_request):
        return render_db.update_task(task_id, {
            "status": "completed",
            "images": [{"id": f"{task_id}-1", "type": "url", "src": "https://example.test/result.png", "filePath": ""}],
            "finishedAt": utc_now_iso(),
        })

    try:
        render_routes.execute_render_task = fake_execute
        headers = {"Authorization": f"Bearer {create_token('admin')}"}
        response = client.post(
            "/api/render/tasks",
            data={
                "modelConfigId": config["id"],
                "prompt": "test",
                "size": "original",
                "count": "1",
                "selectedAssetIds": "[]",
            },
            files={
                "lineArt": ("line.png", PNG_1X1, "image/png"),
                "styleReference": ("style.png", PNG_1X1, "image/png"),
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        task = response.json()["task"]
        assert task["status"] == "pending", task
        task_response = client.get(f"/api/render/tasks/{task['id']}", headers=headers)
        assert task_response.status_code == 200, task_response.text
        refreshed = task_response.json()["task"]
        assert refreshed["status"] == "completed", refreshed
        assert refreshed["images"], refreshed
        print("PASS render task returns immediately and completes in background")
    finally:
        render_routes.execute_render_task = original_execute
        render_db.delete_task(response.json()["task"]["id"]) if "response" in locals() and response.status_code == 200 else None
        render_db.update_model_config(config["id"], {"enabled": False})


if __name__ == "__main__":
    main()
