import io

import cv2
import ezdxf
import numpy as np

from rendering.cad_sheet_jpg import render_dxf_sheet_jpg


def _dxf_text(include_order_form: bool = True) -> str:
    doc = ezdxf.new("R2013", setup=True)
    msp = doc.modelspace()
    if include_order_form:
        block = doc.blocks.new("ORDER_FORM")
        block.add_lwpolyline(
            [(0, 0), (2000, 0), (2000, 3000), (0, 3000)],
            close=True,
        )
        block.add_line((0, 300), (2000, 300))
        block.add_attdef("CUSTOMER", insert=(250, 150), height=80)
        order_form = msp.add_blockref("ORDER_FORM", (100, 50))
        order_form.add_auto_attribs({"CUSTOMER": "测试客户"})
    msp.add_lwpolyline(
        [(400, 500), (1000, 500), (1000, 2300), (400, 2300)],
        close=True,
        dxfattribs={"layer": "A-DOOR-FRAME"},
    )
    msp.add_text("正面", height=40, dxfattribs={"insert": (650, 2400)})
    msp.add_line((5000, 5000), (7000, 7000))
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue()


def test_sheet_jpg_uses_order_form_outer_frame():
    result = render_dxf_sheet_jpg(_dxf_text(), minimum_long_edge=600)

    assert result["usedOrderForm"] is True
    assert result["cadBBox"] == [100.0, 2100.0, 50.0, 3050.0]
    image = cv2.imdecode(np.frombuffer(result["content"], dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    assert max(image.shape[:2]) >= 600
    assert abs((image.shape[1] / image.shape[0]) - (2000 / 3000)) < 0.01


def test_sheet_jpg_renders_order_form_attribute_values():
    doc = ezdxf.read(io.StringIO(_dxf_text()))
    insert = next(iter(doc.modelspace().query('INSERT[name=="ORDER_FORM"]')))
    primitives = []
    from cad_preview import _collect_entity

    _collect_entity(insert, primitives)

    assert any(
        primitive.kind == "text" and primitive.data.get("text") == "测试客户"
        for primitive in primitives
    )


def test_sheet_jpg_falls_back_to_visible_geometry_without_order_form():
    result = render_dxf_sheet_jpg(_dxf_text(False), minimum_long_edge=600)

    assert result["usedOrderForm"] is False
    image = cv2.imdecode(np.frombuffer(result["content"], dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    assert np.count_nonzero(image < 240) > 50
