from __future__ import annotations

import argparse
import json
import os
import shutil
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


WORKER_VERSION = "1.0.0"


class WorkerError(RuntimeError):
    def __init__(self, stage: str, message: str, log_tail: str = ""):
        super().__init__(message)
        self.stage = stage
        self.log_tail = log_tail[-8000:]


@dataclass(frozen=True)
class WorkerConfig:
    base_url: str
    token: str
    device_id: str
    autocad_console: str
    poll_seconds: int = 5
    work_dir: str = "work"

    @classmethod
    def from_file(cls, path: str | Path) -> "WorkerConfig":
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))
        token_env = str(data.get("deviceTokenEnv", "CAD_PRINT_DEVICE_TOKEN"))
        token = os.environ.get(token_env, "").strip()
        if not token:
            raise WorkerError("config", f"环境变量 {token_env} 未设置")
        return cls(
            base_url=str(data["baseUrl"]).rstrip("/"),
            token=token,
            device_id=str(data.get("deviceId", "win-main")).strip() or "win-main",
            autocad_console=str(data["autocadConsole"]),
            poll_seconds=max(1, int(data.get("pollSeconds", 5))),
            work_dir=str(data.get("workDir", "work")),
        )


class WorkerApi:
    def __init__(self, config: WorkerConfig):
        self.config = config

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}/{path.lstrip('/')}"

    def _request(
        self,
        method: str,
        path: str,
        stage: str,
        *,
        json_data: dict | None = None,
        body: bytes | None = None,
        content_type: str = "application/json",
        timeout: int = 30,
    ) -> bytes:
        if json_data is not None:
            body = json.dumps(json_data, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self._url(path),
            data=body,
            method=method,
            headers={
                "X-CAD-PRINT-TOKEN": self.config.token,
                "Content-Type": content_type,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(payload).get("detail", payload)
            except json.JSONDecodeError:
                detail = payload
            raise WorkerError(stage, f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise WorkerError(stage, f"网络请求失败：{exc}") from exc

    def heartbeat(self, device_id: str, probe: dict) -> None:
        self._request(
            "POST",
            "cad-print/worker/heartbeat",
            "heartbeat",
            json_data={"deviceId": device_id, "version": WORKER_VERSION, **probe},
            timeout=20,
        )

    def claim(self, device_id: str) -> dict | None:
        payload = self._request(
            "POST",
            "cad-print/worker/claim",
            "claim",
            json_data={"deviceId": device_id},
            timeout=30,
        )
        return json.loads(payload.decode("utf-8")).get("job")

    def download_dxf(self, job_id: str, target: Path) -> None:
        content = self._request(
            "GET",
            f"cad-print/worker/jobs/{job_id}/dxf",
            "download_dxf",
            timeout=60,
        )
        target.write_bytes(content)

    def update_status(self, job_id: str, device_id: str, status: str) -> None:
        self._request(
            "POST",
            f"cad-print/worker/jobs/{job_id}/status",
            "update_status",
            json_data={"deviceId": device_id, "status": status},
            timeout=20,
        )

    def fail(
        self,
        job_id: str,
        device_id: str,
        stage: str,
        message: str,
        log_tail: str,
    ) -> None:
        self._request(
            "POST",
            f"cad-print/worker/jobs/{job_id}/status",
            "report_failure",
            json_data={
                "deviceId": device_id,
                "status": "failed",
                "errorStage": stage,
                "errorMessage": message,
                "logTail": log_tail[-8000:],
            },
            timeout=20,
        )

    def upload_result(self, job_id: str, device_id: str, path: Path) -> None:
        boundary = f"----DoorErpCadPrint{uuid.uuid4().hex}"
        line = b"\r\n"
        body = bytearray()
        body.extend(f"--{boundary}\r\n".encode("ascii"))
        body.extend(b'Content-Disposition: form-data; name="deviceId"\r\n\r\n')
        body.extend(device_id.encode("utf-8"))
        body.extend(line)
        body.extend(f"--{boundary}\r\n".encode("ascii"))
        body.extend(b'Content-Disposition: form-data; name="file"; filename="result.jpg"\r\n')
        body.extend(b"Content-Type: image/jpeg\r\n\r\n")
        body.extend(path.read_bytes())
        body.extend(line)
        body.extend(f"--{boundary}--\r\n".encode("ascii"))
        self._request(
            "POST",
            f"cad-print/worker/jobs/{job_id}/result",
            "upload_result",
            body=bytes(body),
            content_type=f"multipart/form-data; boundary={boundary}",
            timeout=120,
        )


class AutoCadRunner:
    def __init__(self, console_path: str | Path, lisp_path: str | Path | None = None):
        self.console_path = Path(console_path)
        self.lisp_path = Path(lisp_path) if lisp_path else Path(__file__).with_name("autocad_plot.lsp")

    def probe(self) -> dict:
        missing = []
        if not self.console_path.is_file():
            missing.append(f"未找到 AutoCAD Core Console：{self.console_path}")
        if not self.lisp_path.is_file():
            missing.append(f"未找到打印脚本：{self.lisp_path}")
        return {
            "autocadReady": not missing,
            "message": "；".join(missing) if missing else "AutoCAD 原生打印已就绪",
            "version": WORKER_VERSION,
        }

    def print_job(self, job_id: str, dxf_path: Path, output_path: Path) -> Path:
        raise WorkerError("autocad_script", "AutoCAD 原生打印脚本尚未加载")


class CadPrintWorker:
    def __init__(
        self,
        config: WorkerConfig,
        api: Any | None = None,
        runner: Any | None = None,
    ):
        self.config = config
        self.api = api or WorkerApi(config)
        self.runner = runner or AutoCadRunner(config.autocad_console)
        Path(config.work_dir).mkdir(parents=True, exist_ok=True)

    def _pending_marker(self, job_dir: Path) -> Path:
        return job_dir / "pending-upload.json"

    def _retry_pending_upload(self) -> str | None:
        root = Path(self.config.work_dir)
        for marker in root.glob("*/pending-upload.json"):
            job_dir = marker.parent
            data = json.loads(marker.read_text(encoding="utf-8"))
            jpg_path = job_dir / "result.jpg"
            if not jpg_path.is_file():
                marker.unlink(missing_ok=True)
                continue
            try:
                self.api.upload_result(data["jobId"], self.config.device_id, jpg_path)
                shutil.rmtree(job_dir)
                return "completed"
            except WorkerError:
                return "upload_pending"
        return None

    def run_once(self) -> str:
        pending = self._retry_pending_upload()
        if pending:
            return pending

        probe = self.runner.probe()
        self.api.heartbeat(self.config.device_id, probe)
        if not probe["autocadReady"]:
            return "not_ready"

        job = self.api.claim(self.config.device_id)
        if not job:
            return "idle"

        job_dir = Path(self.config.work_dir) / job["id"]
        job_dir.mkdir(parents=True, exist_ok=True)
        dxf_path = job_dir / "source.dxf"
        jpg_path = job_dir / "result.jpg"
        try:
            self.api.download_dxf(job["id"], dxf_path)
            self.api.update_status(job["id"], self.config.device_id, "printing")
            self.runner.print_job(job["id"], dxf_path, jpg_path)
            self.api.update_status(job["id"], self.config.device_id, "uploading")
            try:
                self.api.upload_result(job["id"], self.config.device_id, jpg_path)
            except WorkerError as exc:
                self._pending_marker(job_dir).write_text(
                    json.dumps({"jobId": job["id"]}, ensure_ascii=False),
                    encoding="utf-8",
                )
                self.api.fail(
                    job["id"],
                    self.config.device_id,
                    exc.stage,
                    str(exc),
                    exc.log_tail,
                )
                return "upload_pending"
            shutil.rmtree(job_dir)
            return "completed"
        except WorkerError as exc:
            self.api.fail(
                job["id"],
                self.config.device_id,
                exc.stage,
                str(exc),
                exc.log_tail,
            )
            return "failed"
        except Exception as exc:
            wrapped = WorkerError("worker", f"打印助手异常：{exc}")
            self.api.fail(
                job["id"],
                self.config.device_id,
                wrapped.stage,
                str(wrapped),
                wrapped.log_tail,
            )
            return "failed"

    def run_forever(self) -> None:
        while True:
            try:
                state = self.run_once()
                print(f"[cad-print-worker] {state}", flush=True)
            except WorkerError as exc:
                print(f"[cad-print-worker] connection_error: {exc}", flush=True)
            time.sleep(self.config.poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Door ERP AutoCAD native print worker")
    parser.add_argument("--config", required=True, help="Path to config.json")
    args = parser.parse_args()
    config = WorkerConfig.from_file(args.config)
    CadPrintWorker(config).run_forever()


if __name__ == "__main__":
    main()
