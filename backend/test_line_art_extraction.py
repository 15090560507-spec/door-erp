import io
import os
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from rendering.line_art import extract_uploaded_line_art, recrop_uploaded_line_art


def synthetic_order_sheet() -> bytes:
    image = Image.new("RGB", (1600, 1000), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 1570, 970), outline="black", width=3)
    for left in (380, 920):
        draw.rectangle((left, 230, left + 300, 850), outline="black", width=8)
        draw.line((left + 150, 230, left + 150, 850), fill="black", width=5)
        draw.rectangle((left + 128, 520, left + 145, 610), outline="black", width=4)
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def run():
    extraction = extract_uploaded_line_art(synthetic_order_sheet(), "sheet.png")
    assert extraction["sourceWidth"] == 1600
    assert extraction["sourceHeight"] == 1000
    assert extraction["front"]["url"].endswith(".png")
    assert extraction["back"]["url"].endswith(".png")
    assert extraction["front"]["crop"]["x"] < extraction["back"]["crop"]["x"]
    assert extraction["originalSourcePath"] == extraction["sourcePath"]
    assert os.path.exists(extraction["sourcePath"])
    assert os.path.exists(extraction["front"]["filePath"])
    assert os.path.exists(extraction["back"]["filePath"])

    front = {"x": 350, "y": 200, "width": 360, "height": 680}
    back = {"x": 890, "y": 200, "width": 360, "height": 680}
    updated = recrop_uploaded_line_art(extraction["id"], front, back, 0)
    assert updated["front"]["crop"] == front
    assert updated["back"]["crop"] == back
    assert updated["reviewRequired"] is False

    rotated = recrop_uploaded_line_art(
        extraction["id"],
        {"x": 120, "y": 350, "width": 680, "height": 360},
        {"x": 120, "y": 890, "width": 680, "height": 360},
        90,
    )
    assert rotated["rotation"] == 0
    assert rotated["sourceWidth"] == 1000
    assert rotated["sourceHeight"] == 1600
    assert rotated["sourcePath"] != rotated["originalSourcePath"]

    line_art = cv2.imread(updated["front"]["filePath"], cv2.IMREAD_GRAYSCALE)
    assert line_art is not None
    assert set(np.unique(line_art)).issubset({0, 255})
    print("PASS line-art extraction creates independent lossless front/back PNG files")
    print("PASS line-art extraction supports manual recrop")


if __name__ == "__main__":
    run()
