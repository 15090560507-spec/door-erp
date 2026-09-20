import io
import json
import os
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image
from psd_tools import PSDImage

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from rendering.precise_render import ROLE_ORDER, render_precise_image
import rendering.precise_render as precise_render
from rendering.segmentation import _infer_masks
import rendering.legacy_cleanup as legacy_cleanup
import rendering.service as render_service
from rendering.service import _normalize_reference_bindings


def test_inferred_masks_are_separate_and_cover_the_main_door_regions():
    image = np.full((720, 480, 3), 255, dtype=np.uint8)
    for inset in (24, 55, 88):
        cv2.rectangle(image, (inset, inset), (479 - inset, 719 - inset), (20, 20, 20), 3)

    masks, confidence, warnings = _infer_masks(image)

    assert confidence >= 0.8
    assert not warnings
    assert np.count_nonzero(masks["panel"]) > 0
    assert np.count_nonzero(masks["frame"]) > 0
    assert np.count_nonzero(masks["trim"]) > 0
    assert not np.any((masks["panel"] > 0) & (masks["frame"] > 0))
    assert not np.any((masks["frame"] > 0) & (masks["trim"] > 0))


def test_precise_bitmap_layers_stay_inside_confirmed_masks():
    width, height = 240, 360
    source = Image.new("RGB", (width, height), "white")
    masks = {}
    expected_masks = {}

    with tempfile.TemporaryDirectory() as folder:
        source_path = os.path.join(folder, "line-art.png")
        source.save(source_path)
        rectangles = {
            "trim": (8, 20, 42, 340),
            "frame": (48, 20, 82, 340),
            "panel": (88, 20, 150, 340),
            "glass": (156, 20, 196, 340),
            "hardware": (202, 20, 232, 340),
        }
        for role in ROLE_ORDER:
            x1, y1, x2, y2 = rectangles[role]
            current_array = np.zeros((height, width), dtype=np.uint8)
            current_array[y1:y2, x1:x2] = 255
            mask_path = os.path.join(folder, f"{role}.png")
            Image.fromarray(current_array, "L").save(mask_path)
            masks[role] = {"filePath": mask_path}
            expected_masks[role] = current_array.copy()

        result = render_precise_image(source_path, masks, {}, {})

    assert result["canvas_size"] == (width, height)
    assert set(ROLE_ORDER).issubset(result["layer_pngs"])
    for role in ROLE_ORDER:
        layer = cv2.imdecode(np.frombuffer(result["layer_pngs"][role], dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        assert layer is not None
        assert layer.shape == (height, width, 4)
        assert np.array_equal(layer[..., 3] > 0, expected_masks[role] > 0)


def test_precise_bitmap_result_is_clean_and_keeps_foreground_order(monkeypatch, tmp_path):
    width, height = 120, 160
    source = np.full((height, width, 3), 255, dtype=np.uint8)
    source[:, 50:52] = 0
    source[110:112, :] = 0
    source_path = tmp_path / "line-art.png"
    Image.fromarray(source, "RGB").save(source_path)

    rectangles = {
        "trim": (2, 2, 118, 158),
        "frame": (10, 10, 110, 150),
        "panel": (20, 20, 100, 140),
        "glass": (40, 40, 80, 80),
        "hardware": (55, 60, 65, 100),
    }
    masks = {}
    for role, (x1, y1, x2, y2) in rectangles.items():
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[y1:y2, x1:x2] = 255
        path = tmp_path / f"{role}.png"
        Image.fromarray(mask, "L").save(path)
        masks[role] = {"filePath": str(path)}

    colors = {
        "门扇": (210, 30, 30),
        "门套": (130, 80, 30),
        "门框": (90, 90, 90),
        "玻璃": (20, 90, 210),
        "拉手": (20, 190, 50),
    }

    def fake_material(rgb, _config, _references, prompt):
        color = next(value for label, value in colors.items() if label in prompt)
        result = np.empty_like(rgb)
        result[...] = color
        return result

    monkeypatch.setattr(precise_render, "_apply_ai_material", fake_material)
    references = {role: [{"filePath": "reference.png"}] for role in ROLE_ORDER}

    result = render_precise_image(str(source_path), masks, {"provider": "fake"}, references)
    image = np.array(Image.open(io.BytesIO(result["image_bytes"])).convert("RGB"))

    # Hardware is above glass and panel.
    assert image[70, 60, 1] > 150
    assert image[70, 60, 1] > image[70, 60, 0] * 3
    # The black source line inside the panel is not composited into the final result.
    assert image[120, 50, 0] > 150
    assert result["visible_layer_order"] == [
        "seam",
        "trim",
        "frame",
        "panel",
        "glass",
        "hardware",
        "lighting",
    ]
    assert result["output_quality"] == 95
    assert "outline" not in result["visible_layer_order"]


def test_reference_bindings_keep_component_roles_separate():
    bindings = _normalize_reference_bindings(
        {
            "panel": {"assetIds": ["panel-1", "panel-1"]},
            "trim": {"assetIds": ["trim-1"]},
        },
        ["panel-1", "legacy-hardware"],
    )

    assert bindings["panel"]["assetIds"] == ["panel-1"]
    assert bindings["trim"]["assetIds"] == ["trim-1"]
    assert bindings["frame"]["assetIds"] == []
    assert bindings["hardware"]["assetIds"] == ["legacy-hardware"]


def test_psd_is_built_on_demand_from_existing_component_layers(monkeypatch, tmp_path):
    layer_path = tmp_path / "panel.png"
    Image.new("RGBA", (80, 120), (120, 80, 40, 255)).save(layer_path)
    task = {
        "id": "precise-task",
        "status": "completed",
        "renderMode": "precise",
        "files": [],
        "componentLayers": {
            "panel": {
                "currentVersion": 1,
                "versions": [{"version": 1, "filePath": str(layer_path)}],
            },
        },
    }
    saved_psd = {}

    class FakeDatabase:
        def get_task(self, _task_id):
            return task

        def update_task(self, _task_id, patch):
            task.update(patch)
            return task

    def fake_save_bytes(data, filename, _subdir):
        saved_psd["bytes"] = data
        saved_psd["filename"] = filename
        return {"url": "/test/result.psd", "filePath": str(tmp_path / "result.psd"), "originalName": filename}

    monkeypatch.setattr(render_service, "render_db", FakeDatabase())
    monkeypatch.setattr(render_service, "save_bytes", fake_save_bytes)

    result = render_service.generate_task_psd("precise-task")
    psd = PSDImage.open(io.BytesIO(saved_psd["bytes"]))

    assert result["psdStatus"] == "completed"
    assert saved_psd["filename"].endswith(".psd")
    assert set(layer.name for layer in psd) == {
        "01_原始线稿",
        "02_门套与门头门柱",
        "03_门框",
        "04_门扇",
        "05_玻璃",
        "06_拉手与锁具",
        "07_其他五金",
        "08_阴影与高光",
        "09_背景",
    }


def test_legacy_layered_cleanup_only_deletes_recorded_files(monkeypatch, tmp_path):
    files_root = tmp_path / "files"
    results = files_root / "results"
    results.mkdir(parents=True)
    recorded = results / "old.psd"
    unrelated = results / "keep.jpg"
    recorded.write_bytes(b"old")
    unrelated.write_bytes(b"keep")
    records_path = tmp_path / "layered_render_records.json"
    records_path.write_text(json.dumps([{"files": {"psd": {"url": "/api/render/files/results/old.psd"}}}]), encoding="utf-8")
    marker_path = tmp_path / "render" / "cleanup.done"

    monkeypatch.setattr(legacy_cleanup, "RENDER_FILES_DIR", str(files_root))
    monkeypatch.setattr(legacy_cleanup, "LEGACY_RECORDS_PATH", str(records_path))
    monkeypatch.setattr(legacy_cleanup, "CLEANUP_MARKER_PATH", str(marker_path))

    legacy_cleanup.cleanup_legacy_layered_outputs()
    legacy_cleanup.cleanup_legacy_layered_outputs()

    assert not recorded.exists()
    assert unrelated.exists()
    assert not records_path.exists()
    assert marker_path.exists()
