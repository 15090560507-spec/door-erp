"""Shared API request and error helpers."""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from door_cad.models import FrameInput, ProjectMeta


class FrameProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputs: FrameInput = Field(default_factory=FrameInput)
    project: ProjectMeta = Field(default_factory=ProjectMeta)


def domain_error(code: str, message: str, field: str | None = None, status_code: int = 422) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "field": field,
            "message": message,
            "severity": "error",
        },
    )
