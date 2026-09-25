from typing import Any, Literal

from pydantic import BaseModel, Field


CadPrintStatus = Literal[
    "queued",
    "claimed",
    "printing",
    "uploading",
    "completed",
    "failed",
    "cancelled",
]


class CadPrintCreateRequest(BaseModel):
    params: dict[str, Any]
    sourceTaskId: str = ""


class WorkerDeviceRequest(BaseModel):
    deviceId: str = Field(min_length=1, max_length=80)


class WorkerHeartbeatRequest(WorkerDeviceRequest):
    autocadReady: bool
    message: str = ""
    version: str = ""


class WorkerStatusRequest(WorkerDeviceRequest):
    status: Literal["printing", "uploading", "failed"]
    errorStage: str = ""
    errorMessage: str = ""
    logTail: str = ""

