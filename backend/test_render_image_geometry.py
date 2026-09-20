import io
import os
import sys

import numpy as np
import pytest
from PIL import Image

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from rendering.image_geometry import (
    build_structural_seam,
    encode_jpeg,
    normalize_rgb_cover,
    seam_rgba,
    validate_layer_canvases,
)


def test_normalize_rgb_cover_keeps_aspect_ratio_and_center_crops():
    source = np.zeros((100, 200, 3), dtype=np.uint8)
    source[:, :100] = (255, 0, 0)
    source[:, 100:] = (0, 0, 255)

    result = normalize_rgb_cover(source, (100, 100))

    assert result.shape == (100, 100, 3)
    assert tuple(result[50, 5]) == (255, 0, 0)
    assert tuple(result[50, 95]) == (0, 0, 255)


def test_validate_layer_canvases_names_the_invalid_role():
    layers = {
        "panel": np.zeros((100, 80, 4), dtype=np.uint8),
        "hardware": np.zeros((90, 80, 4), dtype=np.uint8),
    }

    with pytest.raises(ValueError, match="hardware"):
        validate_layer_canvases(layers, (80, 100))


def test_structural_seam_only_appears_between_adjacent_parts():
    frame = np.zeros((60, 80), dtype=np.uint8)
    panel = np.zeros_like(frame)
    frame[10:50, 8:35] = 255
    panel[10:50, 37:72] = 255

    seam = build_structural_seam({"frame": frame, "panel": panel}, width_px=2)

    assert seam[30, 35] > 0 or seam[30, 36] > 0
    assert seam[5, 5] == 0
    assert seam[30, 75] == 0


def test_seam_rgba_is_black_and_uses_mask_as_alpha():
    mask = np.zeros((12, 14), dtype=np.uint8)
    mask[4:8, 5:9] = 255

    layer = seam_rgba(mask)

    assert layer.shape == (12, 14, 4)
    assert np.all(layer[..., :3] == 0)
    assert np.array_equal(layer[..., 3], mask)


def test_jpeg_encoder_uses_high_quality_rgb_output():
    rgba = np.full((40, 50, 4), 255, dtype=np.uint8)
    rgba[10:30, 15:35, :3] = (20, 80, 160)

    data = encode_jpeg(rgba)
    decoded = Image.open(io.BytesIO(data))

    assert decoded.mode == "RGB"
    assert decoded.size == (50, 40)
    assert len(data) > 300
