import base64
import os
import sys

from fastapi.testclient import TestClient

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
        "front_jpg": PNG_1X1,
        "back_jpg": PNG_1X1,
        "front_layer_pngs": {"panel": PNG_1X1},
        "back_layer_pngs": {"panel": PNG_1X1},
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
