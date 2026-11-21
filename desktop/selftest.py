"""A packaged smoke test used by all three platform builds, never run at startup."""
import json
from pathlib import Path
import time

from PySide6.QtCore import QSettings
from .data import parse_json
from .exporters import Layout, export_file


def run(app, window, output):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    window.settings=QSettings(str(output/'test-settings.ini'),QSettings.Format.IniFormat)
    assert window.dataset is None and window.stack.currentIndex()==0
    window.show(); app.processEvents()
    window.grab().save(str(output/'empty.png'))
    rows=[{'序号':i,'单词':word,'释义':meaning,'词频':100-i,'例句':"A sentence with <markup> & 中文。",'例句翻译':'这是中文例句。'}
          for i,(word,meaning) in enumerate([
              ('abandon','放弃；舍弃'),('ability','能力；本领'),('accept','接受；认可'),
              ('achieve','达到；取得'),('adapt','适应；改编'),('analyze','分析；研究'),
              ('approach','方法；途径；接近'),('benefit','益处；使受益'),
              ('consider','考虑；认为'),('develop','发展；开发'),('evidence','证据；根据'),
              ('knowledge','知识；学问'),('opportunity','机会；时机'),('research','研究；调查'),
              ('significant','重要的；有意义的'),('underlying','潜在的；根本的'),
          ],1)]
    source=output/'input.json'
    source.write_text(json.dumps({'词汇表':rows,'第二表':[{'word':'test','definition':'测试'}]},ensure_ascii=False),encoding='utf-8')
    errors=[]
    window.job_error=lambda message: (errors.append(message),window.finish_job())
    window.import_file(source)
    deadline=time.monotonic()+30
    while window.busy and time.monotonic()<deadline:
        app.processEvents(); time.sleep(.01)
    assert not errors,errors
    assert not window.busy,'Import timed out'
    assert window.dataset and len(window.dataset.rows)==16
    assert window.selected_columns()==['单词','释义'],window.selected_columns()
    window.columns.reorder_at('单词',window.columns.count())
    assert window.columns.count()==len(window.dataset.fields)
    assert '单词' in window.selected_columns()
    window.columns.reorder_at('单词',0)
    assert window.selected_columns()==['单词','释义']
    window.document_title.setText('考研背诵词表')
    app.processEvents(); window.grab().save(str(output/'loaded.png'))
    window.settings_pages.setCurrentIndex(1)
    app.processEvents();window.grab().save(str(output/'layout.png'))
    window.settings_pages.setCurrentIndex(0)
    # Exercise changing a table and auto-detecting English field names.
    window.table_combo.setCurrentIndex(1); app.processEvents()
    assert window.selected_columns()==['word','definition']
    window.table_combo.setCurrentIndex(0); app.processEvents()
    window.search.setText('abandon'); window.refresh()
    assert len(window.filtered)==1
    window.search.clear(); window.refresh()
    fields=window.selected_columns()
    formats=['json','csv','sql','docx']
    for suffix in formats:
        export_file(output/f'smoke.{suffix}',window.filtered,fields,Layout(title='考研背诵词表'))
        assert (output/f'smoke.{suffix}').stat().st_size>20
    # Exercise the same background export used by the Generate button.
    window.export_to(output/'background.docx')
    deadline=time.monotonic()+30
    while window.busy and time.monotonic()<deadline:
        app.processEvents(); time.sleep(.01)
    assert not errors,errors
    assert (output/'background.docx').exists()
    assert not window.busy
    report={'ok':True,'rows':len(rows),'auto_columns':fields,'formats':formats,'startup':'empty','multiple_tables':True,'background_export':True,'column_reorder':True}
    (output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    window.close(); app.processEvents()
