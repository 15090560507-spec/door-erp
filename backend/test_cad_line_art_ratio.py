import io

import ezdxf

from rendering.cad_line_art import export_dxf_line_art


def _sample_dxf() -> str:
    doc = ezdxf.new("R2013", setup=True)
    for layer in ("A-DOOR-FRAME", "A-DOOR-PANEL"):
        if layer not in doc.layers:
            doc.layers.add(layer)
    msp = doc.modelspace()
    msp.add_text("正面", height=40, dxfattribs={"insert": (500, 2600)})
    msp.add_text("背面", height=40, dxfattribs={"insert": (2500, 2600)})
    for offset in (0, 2000):
        msp.add_lwpolyline(
            [(offset, 0), (offset + 1000, 0), (offset + 1000, 2000), (offset, 2000)],
            close=True,
            dxfattribs={"layer": "A-DOOR-FRAME"},
        )
        msp.add_lwpolyline(
            [(offset + 80, 80), (offset + 920, 80), (offset + 920, 1920), (offset + 80, 1920)],
            close=True,
            dxfattribs={"layer": "A-DOOR-PANEL"},
        )
    msp.add_line((-900, 1000), (-100, 1000))
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue()


def test_line_art_canvas_follows_structural_door_ratio():
    result = export_dxf_line_art(_sample_dxf(), minimum_long_edge=800)

    for side in ("front", "back"):
        geometry = result[side]["geometry"]
        assert abs(geometry["aspectRatio"] - (1100 / 2100)) < 0.001
        assert geometry["pixelWidth"] < geometry["pixelHeight"]
