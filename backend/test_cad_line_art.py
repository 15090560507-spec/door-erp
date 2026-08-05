import io
import os
import sys

import cv2
import numpy as np


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from drawing import run_integrated_system
from main import build_cad_params
from models import CADRequest
from rendering.cad_line_art import export_dxf_line_art


def run():
    request = CADRequest(
        door_type="对开门",
        zmls="A1022",
        fmls="背包拉手",
        has_outer=True,
        has_inner=True,
        enable_occlusion=True,
    )
    info, checks, params = build_cad_params(request)
    message, buffer = run_integrated_system(info, checks, params)
    assert buffer is not None, message
    result = export_dxf_line_art(buffer.getvalue(), minimum_long_edge=1200)
    assert result["front"]["filePath"] != result["back"]["filePath"]
    for side in ("front", "back"):
        image = cv2.imread(result[side]["filePath"])
        assert image is not None
        assert max(image.shape[:2]) >= 1200
        assert np.count_nonzero(image < 180) > 100
    print("PASS linked CAD exports independent clean front/back PNG line art")


if __name__ == "__main__":
    run()
