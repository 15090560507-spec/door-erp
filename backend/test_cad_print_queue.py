import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from auth import create_token
from cad_printing.database import CadPrintDatabase


def test_claim_is_single_and_expired_lease_returns_to_queue(tmp_path):
    db = CadPrintDatabase(
        tmp_path / "jobs.json",
        tmp_path / "nodes.json",
        lease_seconds=30,
    )
    job = db.create_job(
        source_task_id="task-1",
        fingerprint="abc",
        dxf_path="a/source.dxf",
        created_by="A",
    )

    claimed = db.claim_next("win-main", now="2026-09-25T10:00:00Z")
    assert claimed is not None
    assert claimed["id"] == job["id"]
    assert claimed["status"] == "claimed"
    assert db.claim_next("win-other", now="2026-09-25T10:00:10Z") is None

    reclaimed = db.claim_next("win-main", now="2026-09-25T10:00:31Z")
    assert reclaimed is not None
    assert reclaimed["id"] == job["id"]
    assert reclaimed["attempts"] == 2


def test_node_online_uses_last_heartbeat(tmp_path):
    db = CadPrintDatabase(
        tmp_path / "jobs.json",
        tmp_path / "nodes.json",
        offline_seconds=45,
    )
    db.heartbeat(
        "win-main",
        {"autocadReady": True, "message": "ready"},
        now="2026-09-25T10:00:00Z",
    )

    online = db.node_status("win-main", now="2026-09-25T10:00:40Z")
    offline = db.node_status("win-main", now="2026-09-25T10:00:46Z")

    assert online["online"] is True
    assert online["autocadReady"] is True
    assert offline["online"] is False


def test_completed_fingerprint_is_reused(tmp_path):
    db = CadPrintDatabase(tmp_path / "jobs.json", tmp_path / "nodes.json")
    job = db.create_job(
        source_task_id="task-1",
        fingerprint="same-params",
        dxf_path="a/source.dxf",
        created_by="A",
    )
    db.claim_next("win-main", now="2026-09-25T10:00:00Z")
    db.complete_job(
        job["id"],
        "win-main",
        result_path="a/result.jpg",
        width=5940,
        height=4200,
        now="2026-09-25T10:00:05Z",
    )

    reused = db.find_completed("same-params")
    assert reused is not None
    assert reused["id"] == job["id"]
    assert reused["status"] == "completed"


@pytest.fixture()
def print_api(tmp_path, monkeypatch):
    import cad_printing.routes as routes
    import cad_printing.storage as storage
    from main import app

    database = CadPrintDatabase(
        tmp_path / "jobs.json",
        tmp_path / "nodes.json",
        lease_seconds=30,
        offline_seconds=45,
    )
    routes.configure_cad_print_database(database)
    routes.configure_cad_generator(lambda params: ("fingerprint-1", b"0\nSECTION\n0\nEOF\n"))
    monkeypatch.setattr(storage, "CAD_PRINT_DIR", tmp_path / "files")
    monkeypatch.setenv("CAD_PRINT_DEVICE_TOKEN", "worker-secret")
    monkeypatch.setenv("CAD_PRINT_DEVICE_ID", "win-main")
    yield TestClient(app), database


def _employee_headers():
    return {"Authorization": f"Bearer {create_token('A')}"}


def _worker_headers():
    return {"X-CAD-PRINT-TOKEN": "worker-secret"}


def _jpeg(width: int, height: int) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(output, "JPEG", quality=80)
    return output.getvalue()


def test_worker_endpoints_require_device_token(print_api):
    client, _ = print_api
    created = client.post(
        "/api/cad-print/jobs",
        json={"params": {"dhdw": "测试"}, "sourceTaskId": "task-1"},
        headers=_employee_headers(),
    )
    assert created.status_code == 200, created.text

    denied = client.post(
        "/api/cad-print/worker/claim",
        json={"deviceId": "win-main"},
    )
    assert denied.status_code == 401


def test_worker_can_claim_download_and_upload_native_jpg(print_api):
    client, _ = print_api
    job = client.post(
        "/api/cad-print/jobs",
        json={"params": {"dhdw": "测试"}, "sourceTaskId": "task-1"},
        headers=_employee_headers(),
    ).json()["job"]

    heartbeat = client.post(
        "/api/cad-print/worker/heartbeat",
        json={"deviceId": "win-main", "autocadReady": True, "message": "ready"},
        headers=_worker_headers(),
    )
    assert heartbeat.status_code == 200, heartbeat.text

    claimed = client.post(
        "/api/cad-print/worker/claim",
        json={"deviceId": "win-main"},
        headers=_worker_headers(),
    ).json()["job"]
    assert claimed["id"] == job["id"]

    downloaded = client.get(
        f"/api/cad-print/worker/jobs/{job['id']}/dxf",
        headers=_worker_headers(),
    )
    assert downloaded.content.startswith(b"0\nSECTION")

    uploaded = client.post(
        f"/api/cad-print/worker/jobs/{job['id']}/result",
        data={"deviceId": "win-main"},
        files={"file": ("result.jpg", _jpeg(5940, 4200), "image/jpeg")},
        headers=_worker_headers(),
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["job"]["status"] == "completed"

    result = client.get(
        f"/api/cad-print/jobs/{job['id']}/result",
        headers=_employee_headers(),
    )
    assert result.status_code == 200
    assert result.headers["content-type"].startswith("image/jpeg")


def test_upload_rejects_wrong_jpg_size(print_api):
    client, _ = print_api
    job = client.post(
        "/api/cad-print/jobs",
        json={"params": {"dhdw": "测试"}},
        headers=_employee_headers(),
    ).json()["job"]
    client.post(
        "/api/cad-print/worker/claim",
        json={"deviceId": "win-main"},
        headers=_worker_headers(),
    )

    uploaded = client.post(
        f"/api/cad-print/worker/jobs/{job['id']}/result",
        data={"deviceId": "win-main"},
        files={"file": ("wrong.jpg", _jpeg(100, 100), "image/jpeg")},
        headers=_worker_headers(),
    )
    assert uploaded.status_code == 422
    assert "5940x4200" in uploaded.text
