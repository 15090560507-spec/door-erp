import copy
import io
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import ezdxf
from ezdxf import bbox
from ezdxf.lldxf.tagwriter import TagCollector

from cad_order_layout import adapt_order_sheet, _template_grid, _proportional_notes, _note_layout
from config import TEMPLATE_PATH
from rendering.cad_sheet_jpg import _order_form_bbox


class OrderLayoutTests(unittest.TestCase):
    def test_note_height_tracks_uniform_sheet_scale(self):
        for width, height, both in ((900, 2100, False), (1400, 2470, True), (5000, 6000, True)):
            with self.subTest(width=width, height=height, both=both):
                doc, _, drawings, notes = self.sample(width, height, both)
                old = _order_form_bbox(doc)
                original_height = notes[0].dxf.char_height
                self.assertIsNone(adapt_order_sheet(doc, drawings, notes))
                new = _order_form_bbox(doc)
                scale = (new[1] - new[0]) / (old[1] - old[0])
                self.assertAlmostEqual(notes[0].dxf.char_height, original_height * scale)

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
        self.assertGreater(notes[0].dxf.char_height, 0)
        self.assertEqual(notes[0].dxf.style, 'Standard')

    def test_original_frame_ratio_and_uniform_grid_scale(self):
        for width, height, both in ((900, 2100, False), (1400, 2470, True),
                                    (7000, 1800, True), (1400, 12000, True)):
            with self.subTest(width=width, height=height, both=both):
                doc, _, drawings, notes = self.sample(width, height, both)
                old_grid = _template_grid(doc.blocks['ORDER_FORM'])[:-1]
                old = _order_form_bbox(doc)
                protected = [TagCollector.dxftags(entity) for entity in drawings]
                self.assertIsNone(adapt_order_sheet(doc, drawings, notes))
                new = _order_form_bbox(doc)
                self.assertAlmostEqual((new[1] - new[0]) / (new[3] - new[2]),
                                       (old[1] - old[0]) / (old[3] - old[2]), places=9)
                scale = (new[1] - new[0]) / (old[1] - old[0])
                new_grid = _template_grid(doc.blocks['ORDER_FORM'])[:-1]
                for before, after in zip(old_grid, new_grid):
                    self.assertAlmostEqual(after, before * scale, places=3)
                self.assertEqual(protected, [TagCollector.dxftags(entity) for entity in drawings])

    def test_late_template_failure_keeps_all_entities_unchanged(self):
        doc, insert, drawings, notes = self.sample()
        block = doc.blocks['ORDER_FORM']
        block.add_point((100, 100))
        before = [TagCollector.dxftags(entity) for entity in block]
        old_insert = TagCollector.dxftags(insert)
        old_note = TagCollector.dxftags(notes[0])
        self.assertIn('Unsupported', adapt_order_sheet(doc, drawings, notes))
        self.assertEqual(before, [TagCollector.dxftags(entity) for entity in block])
        self.assertEqual(old_insert, TagCollector.dxftags(insert))
        self.assertEqual(old_note, TagCollector.dxftags(notes[0]))

    def test_long_notes_wrap_and_reserve_space(self):
        note = 'A manufacturing specification with dimensions 200/180/20/20mm. ' * 20
        doc, _, drawings, notes = self.sample(both=False, note=note)
        self.assertIsNone(adapt_order_sheet(doc, drawings, notes))
        self.assertIn('\\P', notes[0].text)
        self.assertEqual(notes[0].text.replace('\\P', '').replace(' ', ''), note.replace(' ', ''))
        self.assertGreater(notes[0].dxf.insert.y, bbox.extents(drawings, fast=True).extmax.y)

    def test_notes_wrap_at_original_heights_without_text_loss(self):
        examples = [
            ['Handle=200*40mm'],
            ['Trim=160/140/20/20mm\nHandle=200*40mm'],
            ['\u5916\u95e8\u5957\u5bbd/\u538b\u5899/\u5de6\u53f3\u538b\u6846/\u4e0a\u538b\u6846=160/140/20/20mm' * 20],
            ['', 'Front=200mm', 'Back=400mm\nLock=120mm'],
        ]
        for texts in examples:
            with self.subTest(texts=texts):
                lines, used = _proportional_notes(texts, [152] * len(texts), 5000)
                self.assertGreater(used, 0)
                for text, paragraph in zip(texts, lines):
                    self.assertEqual(''.join(paragraph), text.replace('\n', ''))
                    _, _, widest = _note_layout(['\n'.join(paragraph)], 5000, 152)
                    self.assertLessEqual(widest, 5000)

    def test_each_note_preserves_its_original_height_ratio(self):
        doc, _, drawings, notes = self.sample()
        notes.append(doc.modelspace().add_mtext('Workshop note', dxfattribs={
            'char_height': 80, 'width': 6000, 'style': 'Standard'}))
        old = _order_form_bbox(doc)
        self.assertIsNone(adapt_order_sheet(doc, drawings, notes))
        new = _order_form_bbox(doc)
        scale = (new[1] - new[0]) / (old[1] - old[0])
        self.assertAlmostEqual(notes[0].dxf.char_height, 152 * scale)
        self.assertAlmostEqual(notes[1].dxf.char_height, 80 * scale)

    def test_note_region_is_above_door_below_header_and_inside_left_panel(self):
        for text in ('Handle=200*40mm', 'Trim=160/140/20/20mm\nHandle=200*40mm',
                     '\u95e8\u6846\u95e8\u5957\u8bf4\u660e=200/180/20/20mm ' * 12):
            with self.subTest(text=text):
                doc, insert, drawings, notes = self.sample(note=text)
                self.assertIsNone(adapt_order_sheet(doc, drawings, notes))
                _, _, left, _, header, _, _, _ = _template_grid(doc.blocks['ORDER_FORM'])
                _, used, widest = _note_layout([notes[0].plain_text()], notes[0].dxf.width,
                                              notes[0].dxf.char_height)
                top = notes[0].dxf.insert.y
                self.assertLess(top, insert.dxf.insert.y + header)
                self.assertGreater(top - used, bbox.extents(drawings, fast=True).extmax.y)
                self.assertGreater(notes[0].dxf.insert.x, insert.dxf.insert.x)
                self.assertLess(notes[0].dxf.insert.x + widest, insert.dxf.insert.x + left)
                self.assertEqual(notes[0].plain_text().replace('\n', ''), text.replace('\n', ''))

    def test_empty_notes_do_not_change_ratio_or_expand_text_region(self):
        doc, _, drawings, _ = self.sample()
        old = _order_form_bbox(doc)
        self.assertIsNone(adapt_order_sheet(doc, drawings, []))
        new = _order_form_bbox(doc)
        self.assertAlmostEqual((new[1] - new[0]) / (new[3] - new[2]),
                               (old[1] - old[0]) / (old[3] - old[2]), places=9)
        self.assertEqual(_proportional_notes([], [], 500), ([], 0.0))

    def test_notes_that_cannot_fit_warn_without_partial_changes(self):
        doc, insert, drawings, notes = self.sample(note='Text' * 10000)
        before = [TagCollector.dxftags(entity) for entity in doc.blocks['ORDER_FORM']]
        note_before = TagCollector.dxftags(notes[0])
        insert_before = TagCollector.dxftags(insert)
        self.assertIn('proportional height', adapt_order_sheet(doc, drawings, notes))
        self.assertEqual(before, [TagCollector.dxftags(entity) for entity in doc.blocks['ORDER_FORM']])
        self.assertEqual(note_before, TagCollector.dxftags(notes[0]))
        self.assertEqual(insert_before, TagCollector.dxftags(insert))

    def test_long_notes_expand_only_the_uniform_sheet_scale(self):
        text = '\u95e8\u6846\u95e8\u5957\u8bf4\u660e=200/180/20/20mm ' * 20
        short_doc, _, short_drawings, short_notes = self.sample()
        doc, _, drawings, notes = self.sample(note=text)
        original = _order_form_bbox(doc)
        self.assertIsNone(adapt_order_sheet(short_doc, short_drawings, short_notes))
        self.assertIsNone(adapt_order_sheet(doc, drawings, notes))
        short, long = _order_form_bbox(short_doc), _order_form_bbox(doc)
        self.assertGreater(long[1] - long[0], short[1] - short[0])
        self.assertAlmostEqual((long[1] - long[0]) / (long[3] - long[2]),
                               (original[1] - original[0]) / (original[3] - original[2]), places=9)
        self.assertGreaterEqual(notes[0].dxf.char_height, 64)
        self.assertEqual(notes[0].plain_text().replace('\n', ''), text)

    def test_layout_version_invalidates_generated_output_cache(self):
        import main
        from models import CADRequest
        request = CADRequest(dw=1400, dh=2470)
        corrected_key = main._cad_cache_key(request)
        with patch('main.ORDER_LAYOUT_VERSION', 'content-aware-order-sheet-v1'):
            self.assertNotEqual(corrected_key, main._cad_cache_key(request))

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
        from cad_download import editable_sheet_dxf
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
                                     sm='车间生产批注：三元乙丙密封条，靠外装无墙厚。\n合页边开孔位置按确认图复核。',
                                     sel_hys='\u53ef\u62c6\u5378\u5408\u9875', st_val='\u8fde\u4f53\u9501', **variant)
                info, checks, params = build_cad_params(request)
                with patch('drawing.adapt_order_sheet', return_value=None):
                    _, buffer = run_integrated_system(info, checks, copy.deepcopy(params))
                baseline = ezdxf.read(io.StringIO(buffer.getvalue()))
                message, buffer = run_integrated_system(info, checks, copy.deepcopy(params))
                self.assertIsNotNone(buffer, message)
                self.assertNotIn('skipped', message)
                adapted = ezdxf.read(io.StringIO(buffer.getvalue()))
                old_bounds, new_bounds = _order_form_bbox(baseline), _order_form_bbox(adapted)
                self.assertAlmostEqual((new_bounds[1] - new_bounds[0]) / (new_bounds[3] - new_bounds[2]),
                                       (old_bounds[1] - old_bounds[0]) / (old_bounds[3] - old_bounds[2]), places=9)
                sheet_scale = (new_bounds[1] - new_bounds[0]) / (old_bounds[1] - old_bounds[0])
                old_note = next(e for e in baseline.modelspace().query('MTEXT') if '车间生产批注' in e.plain_text())
                new_note = next(e for e in adapted.modelspace().query('MTEXT') if '车间生产批注' in e.plain_text())
                self.assertAlmostEqual(new_note.dxf.char_height, old_note.dxf.char_height * sheet_scale)
                self.assertEqual(new_note.plain_text().replace('\n', ''), old_note.plain_text().replace('\n', ''))

                def protected(doc):
                    return [TagCollector.dxftags(entity) for entity in doc.modelspace()
                            if entity.dxftype() != 'MTEXT'
                            and not (entity.dxftype() == 'INSERT' and entity.dxf.name == 'ORDER_FORM')]

                self.assertEqual(protected(baseline), protected(adapted))
                self.assertFalse(adapted.audit().has_errors)
                download_bytes = editable_sheet_dxf(buffer.getvalue().encode('utf-8'))
                downloaded = ezdxf.read(io.StringIO(download_bytes.decode('utf-8')))
                self.assertIsNone(_order_form_bbox(downloaded))
                for entity in adapted.modelspace():
                    if entity.dxftype() == 'INSERT' and entity.dxf.name == 'ORDER_FORM':
                        continue
                    self.assertEqual(TagCollector.dxftags(entity),
                                     TagCollector.dxftags(downloaded.entitydb[entity.dxf.handle]))
                self.assertFalse(downloaded.audit().has_errors)
                if os.environ.get('CAD_LAYOUT_ARTIFACT_DIR'):
                    from rendering.cad_sheet_jpg import render_dxf_sheet_jpg
                    folder = Path(os.environ['CAD_LAYOUT_ARTIFACT_DIR'])
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / f'adaptive-{index}.dxf').write_bytes(buffer.getvalue().encode('utf-8'))
                    (folder / f'editable-{index}.dxf').write_bytes(download_bytes)
                    for label, doc in (('before', baseline), ('after', adapted)):
                        stream = io.StringIO()
                        doc.write(stream)
                        image = render_dxf_sheet_jpg(stream.getvalue(), output_size=(1782, 1260))
                        (folder / f'{label}-{index}.jpg').write_bytes(image['content'])


if __name__ == '__main__':
    unittest.main()
