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
