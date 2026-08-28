"""Frozen v1.4.3 fixtures and templates used for regression checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(__file__).resolve().parent
BASELINE_DIR = PACKAGE_DIR / "templates"
FIXTURE_DIR = PACKAGE_DIR / "fixtures"


def load_json_fixture(filename: str) -> Any:
    """Load a UTF-8 JSON fixture from the frozen baseline directory."""

    path = FIXTURE_DIR / filename
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
