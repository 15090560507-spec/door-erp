from __future__ import annotations

import tempfile
from pathlib import Path

import ezdxf
from PIL import Image, ImageStat

from generate_section_proof import generate_section_proof


REQUIRED_LAYERS = {
    "REF-WALL",
    "SKIN",
    "SKELETON",
    "CUT",
    "BEND",
    "WELD",
    "CENTER",
    "DIM",
    "TEXT",
}

PART_IDS = {
    "TRIM-SKIN-01",
    "TRIM-SKELETON-01",
    "FRAME-SKIN-01",
    "FRAME-SKELETON-01",
    "LEAF-SKIN-FRONT-01",
    "LEAF-SKIN-BACK-01",
    "LEAF-TUBE-01",
}


def _all_text(doc: ezdxf.document.Drawing) -> str:
    values: list[str] = []
    for entity in doc.modelspace().query("TEXT MTEXT"):
        if entity.dxftype() == "MTEXT":
            values.append(entity.plain_text())
        else:
            values.append(str(entity.dxf.text))
    return "\n".join(values)


def test_generate_section_proof() -> None:
    with tempfile.TemporaryDirectory(prefix="section-proof-") as temporary_directory:
        output_directory = Path(temporary_directory)
        dxf_path, png_path = generate_section_proof(output_directory)

        assert dxf_path.is_file()
        assert png_path.is_file()
        assert (output_directory / "parametric-section-assembly.png").is_file()
        assert (output_directory / "parametric-section-parts-upper.png").is_file()
        assert (output_directory / "parametric-section-parts-lower.png").is_file()

        doc = ezdxf.readfile(dxf_path)
        assert doc.units == ezdxf.units.MM
        assert not doc.audit().errors
        assert REQUIRED_LAYERS.issubset({layer.dxf.name for layer in doc.layers})

        text = _all_text(doc)
        assert "概念验证，非生产依据" in text
        assert "HINGE-01" in text
        assert "250 / 1050 / 1850" in text
        assert "方管下料图" in text
        assert "LEAF-TUBE-01 板材展开图" not in text
        for part_id in PART_IDS:
            assert part_id in text

        assert len(doc.modelspace().query('LINE[layer=="BEND"]')) >= 8
        assert len(doc.modelspace().query('LWPOLYLINE[layer=="CUT"]')) >= 12

        with Image.open(png_path) as image:
            assert image.width >= 2400
            assert image.height >= 1600
            assert ImageStat.Stat(image.convert("L")).extrema[0][0] < 245


if __name__ == "__main__":
    test_generate_section_proof()
    print("section proof: PASS")
