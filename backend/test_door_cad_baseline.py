import hashlib
import json
import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from door_cad.baseline import BASELINE_DIR, FIXTURE_DIR, load_json_fixture


def test_v143_cut_outer_fixture_is_frozen():
    expected = load_json_fixture("v143_cut_outer_expected.json")
    assert expected["version"] == "1.4.3"
    assert expected["outer_width"] == 324.8
    assert expected["left_notch"] == {"x1": 76.0, "x2": 239.8, "depth": 47.0}
    assert len(expected["cut_outer_vertex_order_left"]) == 12


def test_v143_template_checksums_match_files():
    checksums = load_json_fixture("v143_template_checksums.json")
    for filename, expected in checksums.items():
        path = BASELINE_DIR / filename
        assert path.exists(), f"missing baseline template: {filename}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected


def test_baseline_contains_only_confirmed_templates():
    names = sorted(path.name for path in BASELINE_DIR.glob("*.dxf"))
    assert names == [
        "new_lr_process_55_62_template.dxf",
        "top_bottom_double_door_template.dxf",
    ]
