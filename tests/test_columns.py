"""Regression coverage for rerank import and column drag losing a field."""
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt
from desktop.app import ColumnList, Window, create_application
from desktop.data import column_state, parse_json
from desktop.exporters import Layout, export_file


class ColumnStateTests(unittest.TestCase):
    def test_repair_saved_state_that_lost_headword(self):
        fields=['序号','原序号','词频','单词','释义']
        order,selected=column_state(fields,'背诵词表',{
            'order':['序号','释义','原序号','词频'],
            'selected':['序号','释义','词频']})
        self.assertEqual(order,['序号','单词','释义','原序号','词频'])
        self.assertEqual(selected,['序号','单词','释义','词频'])

    def test_intentionally_unchecked_headword_stays_available(self):
        fields=['单词','释义','词频']
        order,selected=column_state(fields,'背诵词表',{'order':fields,'selected':['释义']})
        self.assertEqual(order,fields)
        self.assertEqual(selected,['释义'])


class ColumnWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=create_application()

    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.window=Window()
        self.window.settings=QSettings(str(Path(self.directory.name)/'settings.ini'),QSettings.Format.IniFormat)
        self.window.remember.setChecked(True)
        data={'说明':'rerank','总词数':2,'词汇表':[
            {'序号':1,'原序号':9,'词频':14916,'单词':'that','释义':'那'},
            {'序号':2,'原序号':43,'词频':3200,'单词':'research','释义':'研究'}]}
        self.window.tables=parse_json(json.dumps(data,ensure_ascii=False))
        self.window.activate_table(0)
        self.window.show(); self.app.processEvents()

    def tearDown(self):
        self.window.close();self.app.processEvents();self.directory.cleanup()

    def assert_all_fields(self):
        names=[self.window.columns.item(i).text() for i in range(self.window.columns.count())]
        self.assertEqual(len(names),len(self.window.dataset.fields))
        self.assertEqual(set(names),set(self.window.dataset.fields))
        self.assertEqual(set(self.window.selected_columns()),{'单词','释义'})
        self.assertIn('that',[self.window.preview_model.data(self.window.preview_model.index(0,i)) for i in range(self.window.preview_model.columnCount())])

    def test_drag_drop_onto_other_row_preserves_fields_and_export(self):
        columns=self.window.columns
        mime=QMimeData();mime.setData(ColumnList.MIME,'单词'.encode())
        rect=columns.visualItemRect(columns.item(1))
        class Drop:
            action=None
            accepted=False
            def source(self):return columns
            def mimeData(self):return mime
            def position(self):return QPointF(rect.center().x(),rect.bottom()-1)
            def setDropAction(self,action):self.action=action
            def accept(self):self.accepted=True
        event=Drop();columns.dropEvent(event)
        self.assertTrue(event.accepted)
        self.assertEqual(event.action,Qt.DropAction.CopyAction)
        self.assertEqual(self.window.selected_columns(),['释义','单词'])
        self.assert_all_fields()
        for field in self.window.dataset.fields:
            columns.reorder_at(field,columns.count())
            self.assert_all_fields()
            columns.reorder_at(field,0)
            self.assert_all_fields()
        self.window.activate_table(0)
        self.assert_all_fields()
        path=Path(self.directory.name)/'rerank.json'
        export_file(path,self.window.filtered,self.window.selected_columns(),Layout())
        rows=next(iter(json.loads(path.read_text()).values()))
        self.assertEqual([row['单词'] for row in rows],['that','research'])

    def test_reimport_repairs_old_missing_column_preferences(self):
        self.window.settings.setValue(self.window.schema_key(),json.dumps({
            'order':['序号','释义','原序号','词频'],'selected':['序号','释义','词频']}))
        self.window.activate_table(0)
        names=[self.window.columns.item(i).text() for i in range(self.window.columns.count())]
        self.assertIn('单词',names)
        self.assertIn('单词',self.window.selected_columns())
        saved=json.loads(self.window.settings.value(self.window.schema_key()))
        self.assertIn('单词',saved['order']);self.assertIn('单词',saved['selected'])


if __name__=='__main__':
    unittest.main()
