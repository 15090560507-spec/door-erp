import copy
import io
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import ezdxf
from ezdxf import bbox
from ezdxf.lldxf.tagwriter import TagCollector

from cad_order_layout import adapt_order_sheet
from config import TEMPLATE_PATH
from rendering.cad_sheet_jpg import _order_form_bbox


class OrderLayoutTests(unittest.TestCase):
    def sample(self, width=1400, height=2470, both=True, note='Trim=160/140/20/20mm\nHandle=200*40mm'):
        doc = ezdxf.readfile(TEMPLATE_PATH)
        ms = doc.modelspace()
        insert = next(entity for entity in ms.query('INSERT') if entity.dxf.name == 'ORDER_FORM')
        for attr in insert.attribs:
            if attr.dxf.tag == 'DHDW':
                attr.dxf.text = 'Customer preserved'
        drawings = [ms.add_lwpolyline([(0, 0), (width, 0), (width, height), (0, height)],
                                      close=True, dxfattribs={'layer': 'A-DOOR-FRAME'})]
        drawings.append(ms.add_text('Front', dxfattribs={'insert': (0, height + 300), 'height': 128}))
        drawings.append(ms.add_line((width + 150, 0), (width + 150, height),
                                    dxfattribs={'layer': 'YQ_DIM'}))
        if both:
            drawings.append(ms.add_lwpolyline([(width + 1200, 0), (width * 2 + 1200, 0),
                                               (width * 2 + 1200, height), (width + 1200, height)], close=True))
        notes = [ms.add_mtext(note, dxfattribs={'insert': (-580, 4900), 'char_height': 152,
                                               'width': 6000, 'style': 'Standard'})]
        return doc, insert, drawings, notes

    def test_compacts_frame_without_touching_door_entities(self):
        doc, insert, drawings, notes = self.sample()
        before = [copy.deepcopy(entity.dxf.all_existing_dxf_attribs()) for entity in drawings]
        points = [list(entity.get_points()) for entity in drawings if entity.dxftype() == 'LWPOLYLINE']
        old = _order_form_bbox(doc)
        self.assertIsNone(adapt_order_sheet(doc, drawings, notes))
        self.assertEqual(before, [entity.dxf.all_existing_dxf_attribs() for entity in drawings])
        self.assertEqual(points, [list(entity.get_points()) for entity in drawings if entity.dxftype() == 'LWPOLYLINE'])
        new = _order_form_bbox(doc)
        self.assertLess(new[1] - new[0], old[1] - old[0])
        self.assertLess(new[3] - new[2], old[3] - old[2])
        self.assertEqual(insert.get_attrib('DHDW').dxf.text, 'Customer preserved')
        extent = bbox.extents(drawings, fast=True)
        self.assertLess(new[0], extent.extmin.x)
        self.assertGreater(new[1], extent.extmax.x)
        self.assertLess(new[2], extent.extmin.y)
        self.assertGreater(new[3], extent.extmax.y)
        self.assertGreater(notes[0].dxf.insert.y, extent.extmax.y)
        self.assertLess(notes[0].dxf.char_height, 152)
        self.assertEqual(notes[0].dxf.style, 'Standard')

    def test_long_notes_wrap_and_reserve_space(self):
        note = 'A manufacturing specification with dimensions 200/180/20/20mm. ' * 20
        doc, _, drawings, notes = self.sample(both=False, note=note)
        self.assertIsNone(adapt_order_sheet(doc, drawings, notes))
        self.assertIn('\\P', notes[0].text)
        self.assertEqual(notes[0].text.replace('\\P', '').replace(' ', ''), note.replace(' ', ''))
        self.assertGreater(notes[0].dxf.insert.y, bbox.extents(drawings, fast=True).extmax.y)

    def test_large_drawing_is_contained_without_scaling(self):
        doc, _, drawings, notes = self.sample(width=5000, height=6000)
        self.assertIsNone(adapt_order_sheet(doc, drawings, notes))
        frame = _order_form_bbox(doc)
        extent = bbox.extents(drawings, fast=True)
        self.assertLess(frame[0], extent.extmin.x)
        self.assertGreater(frame[1], extent.extmax.x)
        self.assertGreater(frame[3], extent.extmax.y)
        self.assertEqual(list(drawings[0].get_points())[1][0], 5000)

    def test_samples_outside_sheet_are_untouched(self):
        doc, _, drawings, notes = self.sample()
        sample = next(entity for entity in doc.modelspace().query('INSERT') if entity.dxf.name == 'hlt')
        before = sample.dxf.all_existing_dxf_attribs().copy()
        adapt_order_sheet(doc, drawings, notes)
        self.assertEqual(before, sample.dxf.all_existing_dxf_attribs())

    def test_legal_remarks_keep_all_text_and_wrap_inside_sheet(self):
        doc, insert, drawings, notes = self.sample()
        block = doc.blocks['ORDER_FORM']
        legal = next(entity for entity in block.query('MTEXT') if entity.dxf.insert.y < 1000)
        old_text = legal.plain_text().replace('\n', '')
        self.assertIsNone(adapt_order_sheet(doc, drawings, notes))
        legal = next(entity for entity in block.query('MTEXT') if entity.dxf.insert.y < 1000)
        self.assertIn('\\P', legal.text)
        self.assertEqual(old_text, legal.plain_text().replace('\n', ''))
        grid = next(line.dxf.start.x for line in block.query('LINE')
                    if abs(line.dxf.start.x - line.dxf.end.x) < 0.1
                    and abs(line.dxf.start.y - line.dxf.end.y) > 3000)
        self.assertLess(legal.dxf.insert.x + legal.dxf.width, grid)

    def test_empty_drawing_preserves_simple_product_sheet(self):
        doc, insert, _, notes = self.sample()
        before = insert.dxf.all_existing_dxf_attribs().copy()
        self.assertIsNone(adapt_order_sheet(doc, [], notes))
        self.assertEqual(before, insert.dxf.all_existing_dxf_attribs())

    def test_unsupported_template_is_not_partially_modified(self):
        doc = ezdxf.new()
        ms = doc.modelspace()
        shape = ms.add_circle((0, 0), 20)
        self.assertTrue(adapt_order_sheet(doc, [shape], []))
        self.assertEqual(shape.dxf.center, (0, 0, 0))

    def test_actual_door_generation_preserves_every_non_sheet_entity(self):
        from drawing import run_integrated_system
        from main import build_cad_params
        from models import CADRequest
        variants = [
            {'dw': 1394, 'dh': 2470, 'door_type': '\u5bf9\u5f00\u95e8'},
            {'dw': 900, 'dh': 2100, 'product_name': '\u5e73\u79fb\u95e8'},
            {'dw': 2400, 'dh': 3250, 'has_outer': False, 'has_outer_portal2': True,
             'sel_qc': '\u73bb\u7483', 'qc_height': 500},
            {'dw': 1600, 'dh': 2700, 'is_arch_door': True, 'arch_spring_height': 2100},
        ]
        for index, variant in enumerate(variants):
            with self.subTest(variant=variant):
                request = CADRequest(dhdw='Layout verification', ys='Test', mshd=80,
                                     sel_nk='\u5185\u5f00', sel_kx='\u53f3\u5f00',
                                     sel_hys='\u53ef\u62c6\u5378\u5408\u9875', st_val='\u8fde\u4f53\u9501', **variant)
                info, checks, params = build_cad_params(request)
                with patch('drawing.adapt_order_sheet', return_value=None):
                    _, buffer = run_integrated_system(info, checks, copy.deepcopy(params))
                baseline = ezdxf.read(io.StringIO(buffer.getvalue()))
                message, buffer = run_integrated_system(info, checks, copy.deepcopy(params))
                self.assertIsNotNone(buffer, message)
                self.assertNotIn('skipped', message)
                adapted = ezdxf.read(io.StringIO(buffer.getvalue()))

                def protected(doc):
                    return [TagCollector.dxftags(entity) for entity in doc.modelspace()
                            if entity.dxftype() != 'MTEXT'
                            and not (entity.dxftype() == 'INSERT' and entity.dxf.name == 'ORDER_FORM')]

                self.assertEqual(protected(baseline), protected(adapted))
                self.assertFalse(adapted.audit().has_errors)
                if os.environ.get('CAD_LAYOUT_ARTIFACT_DIR'):
                    from rendering.cad_sheet_jpg import render_dxf_sheet_jpg
                    folder = Path(os.environ['CAD_LAYOUT_ARTIFACT_DIR'])
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / f'adaptive-{index}.dxf').write_text(buffer.getvalue(), encoding='utf-8')
                    for label, doc in (('before', baseline), ('after', adapted)):
                        stream = io.StringIO()
                        doc.write(stream)
                        image = render_dxf_sheet_jpg(stream.getvalue(), output_size=(1782, 1260))
                        (folder / f'{label}-{index}.jpg').write_bytes(image['content'])


if __name__ == '__main__':
    unittest.main()
