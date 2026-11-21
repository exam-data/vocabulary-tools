import csv
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

from desktop.data import Dataset, load_json, parse_json, project, recommended_fields, select_rows
from desktop.exporters import Layout, export_file

ROOT=Path(__file__).resolve().parents[1]


class DataTests(unittest.TestCase):
    def test_detect_tables_and_union_optional_fields(self):
        tables=parse_json('\ufeff'+json.dumps({'说明':'说明','tags':['a'],'第一表':[{'单词':'a'},{'单词':'b','例句':'Later'}],'第二表':[{'word':'c'}]},ensure_ascii=False))
        self.assertEqual(len(tables),2)
        self.assertEqual(tables[0].fields,['单词','例句'])
        self.assertEqual(recommended_fields(['frequency','word','meaning','example']),['word','meaning'])
        self.assertEqual(recommended_fields(['释义','单词','词频']),['单词','释义'])
        self.assertEqual(project(tables[0].rows,['例句']),[{'例句':None},{'例句':'Later'}])

    def test_bad_and_empty_input(self):
        for text in ['{','null','[]','{"rows":[]}','{"rows":[{},{}]}','[{"单词":"a"},3]','[{"词频":NaN}]']:
            with self.subTest(text=text),self.assertRaises(ValueError):parse_json(text)
        with self.assertRaises(ValueError):project([{'word':'a'}],[])
        with self.assertRaises(ValueError):project([],['word'])

    def test_filter_sort_limit_renumber_without_mutation(self):
        dataset=Dataset('x',[{'序号':4,'单词':'Book','词频':2,'分类名称':'A'},
                             {'序号':8,'单词':'apple','词频':20,'分类名称':'B'},
                             {'序号':9,'单词':'able','词频':None,'分类名称':'A'}])
        out=select_rows(dataset,category='A',sort='单词字母顺序',limit=1,renumber=True)
        self.assertEqual(out,[{'序号':1,'单词':'able','词频':None,'分类名称':'A'}])
        self.assertEqual(dataset.rows[2]['序号'],9)
        self.assertEqual(select_rows(dataset,search='BOOK')[0]['单词'],'Book')
        self.assertEqual(select_rows(dataset,sort='词频从高到低')[0]['单词'],'apple')


class OriginalToolParityTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.root=Path(self.directory.name)
        self.rows=[{'序号':i,'词频':100-i,'单词':word,'释义':'研究、分析；带有相同断行规则的释义','其他拼写':None,'学术词汇':False}
                   for i,word in enumerate(['word','example','research','analysis','ability','abandon','test']*3,1)]

    def tearDown(self):self.directory.cleanup()

    def original(self,script,args):
        subprocess.run([sys.executable,str(ROOT/'tools'/script),*map(str,args)],check=True,capture_output=True)

    def test_docx_matches_every_original_archive_member(self):
        # Compare every OOXML part, not merely word count or visible text.
        cases=[(['序号','词频','单词','释义'],Layout(),[]),
               (['单词','释义'],Layout(rows_per_page=13),['--per-page','13']),
               (['释义','单词'],Layout(rows_per_page=5,font='Songti SC',max_length=8,break_def=False),
                ['--per-page','5','--font','Songti SC','--max-length','8','--no-break-def'])]
        for fields,layout,args in cases:
            with self.subTest(fields=fields,args=args):
                source=self.root/'source.json';source.write_text(json.dumps({'词汇表':self.rows},ensure_ascii=False))
                direct=self.root/'original.docx';client=self.root/'client.docx'
                self.original('export_docx.py',[source,'-o',direct,'--columns',','.join(fields),*args])
                export_file(client,self.rows,fields,layout)
                with ZipFile(direct) as expected,ZipFile(client) as actual:
                    self.assertEqual(set(expected.namelist()),set(actual.namelist()))
                    for member in expected.namelist():
                        self.assertEqual(expected.read(member),actual.read(member),member)

    def test_sql_matches_original_byte_for_byte(self):
        fields=list(self.rows[0]);source=self.root/'vocabulary.json'
        source.write_text(json.dumps({'词汇表':self.rows},ensure_ascii=False))
        direct=self.root/'direct.sql';client=self.root/'vocabulary.sql'
        self.original('json_to_sql.py',[source,'-o',direct])
        export_file(client,self.rows,fields,Layout())
        self.assertEqual(direct.read_bytes(),client.read_bytes())

    def test_data_exports_and_failure_preserve_source(self):
        for suffix in ['json','csv']:
            path=self.root/f'out.{suffix}'
            export_file(path,self.rows,['单词','释义'],Layout())
            if suffix=='json':self.assertEqual(load_json(path)[0].rows,project(self.rows,['单词','释义']))
            else:
                with path.open(encoding='utf-8-sig',newline='') as f:self.assertEqual(list(csv.DictReader(f)),project(self.rows,['单词','释义']))
        path=self.root/'safe.json';path.write_text('existing')
        with self.assertRaises(ValueError):export_file(path,[{'单词':float('nan')}],['单词'],Layout())
        self.assertEqual(path.read_text(),'existing')

    def test_original_errors_do_not_trigger_substitute_layout(self):
        path=self.root/'safe.docx';path.write_text('existing')
        fields=['序号','词频','单词','其他拼写','学术词汇','原序号','综合得分','释义','分类名称','CEFR等级','高级词汇','例句','例句翻译']
        rows=[{**self.rows[0],'原序号':1,'综合得分':100,'分类名称':'分类','CEFR等级':'C2','高级词汇':True,'例句':'test','例句翻译':'测试'}]
        with self.assertRaisesRegex(ValueError,'列太多'):export_file(path,rows,fields,Layout())
        self.assertEqual(path.read_text(),'existing')
        with self.assertRaisesRegex(ValueError,'支持'):export_file(self.root/'x.pdf',self.rows,['单词'],Layout())


if __name__=='__main__':unittest.main()
