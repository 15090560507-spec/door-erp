import base64
import os
import sys

from fastapi.testclient import TestClient

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from auth import create_token
from main import app
from rendering.database import render_db, utc_now_iso
import rendering.routes as render_routes


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
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
