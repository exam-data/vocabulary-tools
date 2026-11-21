"""Numeric widths and no-wrap must survive the original Word export pipeline."""
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

from docx import Document
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
TOOL = runpy.run_path(str(ROOT / 'tools/export_docx.py'))


class NumericWidthTests(unittest.TestCase):
    def test_long_numbers_headers_and_null_column_have_room(self):
        rows = [{'序号': 123456789, '词频': 86015, '单词': 'ability', '释义': '能力',
                 '综合得分': 108.62, '真题次数': None}]
        fields = list(rows[0])
        widths = TOOL['compute_widths'](fields, rows)
        for field in ['序号', '词频', '综合得分', '真题次数']:
            self.assertGreaterEqual(widths[fields.index(field)], TOOL['numeric_width'](field, rows))
        self.assertGreater(widths[0], 1000)
        self.assertEqual(sum(widths), TOOL['PAGE_TEXT_TWIPS'])

    def test_text_columns_give_space_without_shrinking_numbers(self):
        rows = [{'序号': 123456789, '原序号': 123456789, '词频': 12345678,
                 '单词': 'ability', '释义': '能力', '分类名称': '分类'}]
        fields = list(rows[0]); widths = TOOL['compute_widths'](fields, rows)
        self.assertLess(widths[-1], 1600)
        self.assertGreaterEqual(widths[-2], 1400)
        for field in ['序号','原序号','词频']:
            self.assertEqual(widths[fields.index(field)], TOOL['numeric_width'](field, rows))
        self.assertEqual(sum(widths), TOOL['PAGE_TEXT_TWIPS'])

    def test_numeric_cells_no_wrap_and_original_style_preserved(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = work/'input.json'; output = work/'out.docx'
            rows = [{'序号': 5530, '词频': 86015, '单词': 'ability', '释义': '能力', '综合得分': 108.62}]
            source.write_text(json.dumps({'词汇表':rows}, ensure_ascii=False))
            subprocess.run([sys.executable,str(ROOT/'tools/export_docx.py'),str(source),'-o',str(output),
                            '--columns',','.join(rows[0])], check=True, capture_output=True)
            doc = Document(output); table = doc.tables[0]
            self.assertEqual(len(table.rows), 19)
            for row in table.rows:
                for i, field in enumerate(rows[0]):
                    self.assertEqual(row.cells[i]._tc.tcPr.find(qn('w:noWrap')) is not None,
                                     field in {'序号','词频','综合得分'})
            self.assertEqual(table.rows[0].cells[0]._tc.tcPr.find(qn('w:shd')).get(qn('w:fill')), '808080')
            run=table.rows[1].cells[0].paragraphs[0].runs[0]
            self.assertEqual(run.font.name, '华文中宋')
            self.assertEqual(run.font.size.pt, 11)
            self.assertEqual(table.rows[1].height.twips, 624)
