from pathlib import Path

from tools.cad_print_worker.worker import CadPrintWorker, WorkerConfig, WorkerError


class FakeApi:
    def __init__(self, root: Path):
        self.root = root
        self.claimed = False
        self.uploaded: list[str] = []
        self.status_updates: list[dict] = []
        self.heartbeats: list[dict] = []

    def heartbeat(self, device_id: str, probe: dict) -> None:
        self.heartbeats.append({"deviceId": device_id, **probe})

    def claim(self, device_id: str):
        if self.claimed:
            return None
        self.claimed = True
        return {"id": "job-1", "dxfUrl": "/cad-print/worker/jobs/job-1/dxf"}

    def download_dxf(self, job_id: str, target: Path) -> None:
        target.write_text("0\nSECTION\n0\nEOF\n", encoding="ascii")

    def update_status(self, job_id: str, device_id: str, status: str) -> None:
        self.status_updates.append({"jobId": job_id, "deviceId": device_id, "status": status})

    def upload_result(self, job_id: str, device_id: str, path: Path) -> None:
        assert path.is_file()
        self.uploaded.append(job_id)

    def fail(self, job_id: str, device_id: str, stage: str, message: str, log_tail: str) -> None:
        self.status_updates.append({
            "jobId": job_id,
            "deviceId": device_id,
            "status": "failed",
            "errorStage": stage,
            "errorMessage": message,
            "logTail": log_tail,
        })


class FakeRunner:
    def __init__(self, failure: WorkerError | None = None):
        self.failure = failure
        self.calls: list[str] = []

    def probe(self):
        return {"autocadReady": True, "message": "ready", "version": "test"}

    def print_job(self, job_id: str, dxf_path: Path, output_path: Path) -> Path:
        self.calls.append(job_id)
        if self.failure:
            raise self.failure
        output_path.write_bytes(b"jpeg")
        return output_path


def _config(tmp_path: Path) -> WorkerConfig:
    return WorkerConfig(
        base_url="https://example.test/api",
        token="secret",
        device_id="win-main",
        autocad_console=r"D:\Desin all\CAD2022\AutoCAD 2022\accoreconsole.exe",
        poll_seconds=1,
        work_dir=str(tmp_path / "work"),
    )


def test_worker_claims_prints_and_uploads(tmp_path):
    api = FakeApi(tmp_path)
    runner = FakeRunner()
    worker = CadPrintWorker(_config(tmp_path), api=api, runner=runner)

    assert worker.run_once() == "completed"
    assert runner.calls == ["job-1"]
    assert api.uploaded == ["job-1"]
    assert [item["status"] for item in api.status_updates] == ["printing", "uploading"]
    assert not (Path(worker.config.work_dir) / "job-1").exists()


def test_worker_reports_autocad_failure(tmp_path):
    api = FakeApi(tmp_path)
    runner = FakeRunner(WorkerError("autocad_plot", "AutoCAD 原生打印失败", "fatal log"))
    worker = CadPrintWorker(_config(tmp_path), api=api, runner=runner)

    assert worker.run_once() == "failed"
    assert api.status_updates[-1]["status"] == "failed"
    assert api.status_updates[-1]["errorStage"] == "autocad_plot"
    assert api.status_updates[-1]["logTail"] == "fatal log"


def test_worker_stays_idle_when_autocad_is_not_ready(tmp_path):
    api = FakeApi(tmp_path)
    runner = FakeRunner()
    runner.probe = lambda: {"autocadReady": False, "message": "missing", "version": ""}
    worker = CadPrintWorker(_config(tmp_path), api=api, runner=runner)

    assert worker.run_once() == "not_ready"
    assert api.claimed is False
