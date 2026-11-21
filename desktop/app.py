"""Native Qt client. Data processing and exports stay entirely in Python."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import traceback

from PySide6.QtCore import QAbstractTableModel, QMimeData, QModelIndex, QObject, QPointF, QRectF, QRunnable, QSettings, QSize, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QDrag, QFont, QFontDatabase, QIcon, QImage, QKeySequence, QPalette, QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QStackedWidget, QTableView,
    QVBoxLayout, QWidget, QAbstractItemView,
)

from .data import PRESETS, Dataset, column_state, display, find_field, load_json, recommended_fields, select_rows
from .exporters import Layout, export_file
from .resources import ui_dir


def line_icon(kind, color='#636366', size=20):
    pixmap=QPixmap(size*2,size*2)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(2)
    painter=QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size/24,size/24)
    pen=QPen(QColor(color),1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    if kind in {'file','document'}:
        painter.drawRoundedRect(QRectF(5,3,14,18),3,3)
        for y in [9,13,17]:
            painter.drawLine(QPointF(9,y),QPointF(15,y))
    elif kind=='search':
        painter.drawEllipse(QRectF(4,4,12,12))
        painter.drawLine(QPointF(14,14),QPointF(20,20))
    elif kind=='preview':
        path=QPainterPath(QPointF(2,12))
        path.cubicTo(7,4,17,4,22,12)
        path.cubicTo(17,20,7,20,2,12)
        painter.drawPath(path);painter.drawEllipse(QRectF(9,9,6,6))
    elif kind in {'up','down','export'}:
        if kind=='export':
            painter.drawLine(QPointF(12,3),QPointF(12,15))
            painter.drawLine(QPointF(8,7),QPointF(12,3));painter.drawLine(QPointF(16,7),QPointF(12,3))
            path=QPainterPath(QPointF(5,12));path.lineTo(5,20);path.lineTo(19,20);path.lineTo(19,12);painter.drawPath(path)
        else:
            y1,y2=(15,9) if kind=='up' else (9,15)
            painter.drawLine(QPointF(7,y1),QPointF(12,y2));painter.drawLine(QPointF(12,y2),QPointF(17,y1))
    painter.end()
    return QIcon(pixmap)


class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Job(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = Signals()

    def run(self):
        try:
            self.signals.done.emit(self.fn())
        except Exception as exc:
            traceback.print_exc()
            self.signals.failed.emit(str(exc))


class PreviewModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.rows, self.fields = [], []

    def update(self, rows, fields):
        self.beginResetModel()
        self.rows, self.fields = rows, fields
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.fields)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return display(self.rows[index.row()].get(self.fields[index.column()]))
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return self.fields[section] if orientation == Qt.Orientation.Horizontal else str(section+1)
        return None


class ColumnList(QListWidget):
    """Reorder field names without Qt's item-transfer/removal machinery."""
    reorder_requested = Signal(int, int)
    MIME = 'application/x-vocabulary-column'

    def __init__(self):
        super().__init__()
        self.drop_row = None
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def startDrag(self, actions):
        if self.currentItem() is None:
            return
        mime = QMimeData()
        mime.setData(self.MIME, self.currentItem().text().encode('utf-8'))
        drag = QDrag(self)
        drag.setMimeData(mime)
        # The drop handler performs one reorder; the source must never delete
        # an item as a second step after Qt considers a drag complete.
        drag.exec(Qt.DropAction.CopyAction)
        self.drop_row = None
        self.viewport().update()

    def dragEnterEvent(self, event):
        if event.source() is self and event.mimeData().hasFormat(self.MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def insertion_row(self, point):
        item = self.itemAt(point)
        if item is None:
            return self.count()
        rect = self.visualItemRect(item)
        return self.row(item) + (1 if point.y() > rect.center().y() else 0)

    def dragMoveEvent(self, event):
        if event.source() is self and event.mimeData().hasFormat(self.MIME):
            self.drop_row = self.insertion_row(event.position().toPoint())
            self.viewport().update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_row = None
        self.viewport().update()
        event.accept()

    def reorder_at(self, field, insertion):
        source = next((i for i in range(self.count()) if self.item(i).text() == field), None)
        if source is not None:
            target = max(0, min(insertion, self.count()))
            self.reorder_requested.emit(source, target - (1 if target > source else 0))

    def dropEvent(self, event):
        if event.source() is self and event.mimeData().hasFormat(self.MIME):
            field = bytes(event.mimeData().data(self.MIME)).decode('utf-8')
            self.reorder_at(field, self.insertion_row(event.position().toPoint()))
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()
        self.drop_row = None
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.drop_row is not None and self.count():
            rect = self.visualItemRect(self.item(min(self.drop_row, self.count()-1)))
            y = rect.bottom() if self.drop_row == self.count() else rect.top()
            painter = QPainter(self.viewport())
            painter.setPen(QPen(QColor('#225ee5'), 2))
            painter.drawLine(0, y, self.viewport().width(), y)
            painter.end()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("词表工坊 · Vocabulary Studio")
        self.resize(1240, 850)
        self.setMinimumSize(1000, 700)
        self.setAcceptDrops(True)
        self.settings = QSettings("exam-data", "VocabularyStudio")
        self.tables = []
        self.dataset = None
        self.source_path = None
        self.filtered = []
        self.output_path = None
        self.busy = False
        self.updating = False
        self.thread_pool = QThreadPool(self)
        self.temp = tempfile.TemporaryDirectory(prefix="vocabulary-studio-")
        self.filter_timer = QTimer(self)
        self.filter_timer.setSingleShot(True)
        self.filter_timer.setInterval(180)
        self.filter_timer.timeout.connect(self.refresh)
        self.build_ui()

    def build_ui(self):
        outer = QWidget()
        self.setCentralWidget(outer)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(28, 22, 28, 14)
        outer_layout.setSpacing(20)

        top = QHBoxLayout()
        title = QLabel("词表工坊")
        title.setObjectName("AppTitle")
        top.addWidget(title)
        caption = QLabel("你的本地词汇工作台")
        caption.setObjectName("Muted")
        top.addSpacing(12)
        top.addWidget(caption)
        top.addStretch()
        offline = QLabel("●  本机处理")
        offline.setObjectName("OfflineBadge")
        top.addWidget(offline)
        top.addSpacing(10)
        self.open_button = QPushButton("导入 JSON")
        self.open_button.setIcon(line_icon('file'))
        self.open_button.setShortcut(QKeySequence.StandardKey.Open)
        self.open_button.clicked.connect(self.choose_file)
        top.addWidget(self.open_button)
        outer_layout.addLayout(top)

        self.stack = QStackedWidget()
        outer_layout.addWidget(self.stack, 1)
        empty = QFrame()
        empty.setObjectName("EmptyPane")
        empty_layout = QVBoxLayout(empty)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(18)
        hero = QLabel()
        hero.setObjectName("HeroIcon")
        hero.setFixedSize(84, 84)
        hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.setPixmap(line_icon('document', '#007aff', 46).pixmap(QSize(46, 46)))
        empty_layout.addWidget(hero, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addSpacing(6)
        label = QLabel("从一份 JSON 开始")
        label.setObjectName("EmptyTitle")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(label)
        note = QLabel("导入你的词汇文件，选好需要的列。\n预览排版，生成适合自己的背诵词表。")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setObjectName("HeroDescription")
        empty_layout.addWidget(note)
        empty_layout.addSpacing(8)
        choose = QPushButton("选择 JSON 文件")
        choose.setObjectName("Primary")
        choose.setFixedWidth(186)
        choose.setMinimumHeight(42)
        choose.clicked.connect(self.choose_file)
        empty_layout.addWidget(choose, 0, Qt.AlignmentFlag.AlignHCenter)
        drag_note = QLabel("也可以将文件拖放到这里")
        drag_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drag_note.setObjectName("Muted")
        empty_layout.addWidget(drag_note)
        empty_layout.addSpacing(28)
        badges = QHBoxLayout()
        badges.setSpacing(10)
        badges.addStretch()
        for text in ["自动识别字段", "自由编排列", "Word / SQL"]:
            badge = QLabel(text)
            badge.setObjectName("FeatureBadge")
            badges.addWidget(badge)
        badges.addStretch()
        empty_layout.addLayout(badges)
        self.stack.addWidget(empty)

        self.editor = QWidget()
        self.stack.addWidget(self.editor)
        edit_layout = QVBoxLayout(self.editor)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(16)
        source_layout = QHBoxLayout()
        source_icon = QLabel()
        source_icon.setPixmap(line_icon('file', '#007aff', 24).pixmap(QSize(24, 24)))
        source_layout.addWidget(source_icon)
        source_layout.addSpacing(4)
        self.source_label = QLabel()
        self.source_label.setObjectName("FileName")
        self.source_label.setWordWrap(True)
        source_layout.addWidget(self.source_label, 1)
        self.table_combo = QComboBox()
        self.table_combo.setMinimumWidth(245)
        self.table_combo.currentIndexChanged.connect(self.activate_table)
        source_layout.addWidget(self.table_combo)
        edit_layout.addLayout(source_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        edit_layout.addWidget(splitter, 1)
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(290)
        sidebar.setMaximumWidth(380)
        left = QVBoxLayout(sidebar)
        left.setContentsMargins(18, 18, 18, 16)
        left.setSpacing(16)
        segmented = QFrame()
        segmented.setObjectName("Segmented")
        segment_layout = QHBoxLayout(segmented)
        segment_layout.setContentsMargins(3, 3, 3, 3)
        segment_layout.setSpacing(2)
        group = QButtonGroup(self)
        group.setExclusive(True)
        self.settings_pages = QStackedWidget()
        for index, text in enumerate(["导出列", "排版设置"]):
            button = QPushButton(text)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setChecked(index == 0)
            group.addButton(button, index)
            segment_layout.addWidget(button)
        group.idClicked.connect(self.settings_pages.setCurrentIndex)
        self.settings_pages.currentChanged.connect(lambda index: group.button(index).setChecked(True))
        left.addWidget(segmented)
        left.addWidget(self.settings_pages, 1)

        columns_page = QWidget()
        column_layout = QVBoxLayout(columns_page)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(12)
        column_layout.addWidget(self.section_label("词表方案"))
        self.preset = QComboBox()
        self.preset.addItems(PRESETS)
        self.preset.currentTextChanged.connect(self.apply_preset)
        column_layout.addWidget(self.preset)
        heading = QHBoxLayout()
        heading.addWidget(self.section_label("包含的字段"))
        heading.addStretch()
        for text, callback in [("全选", lambda: self.set_all_columns(True)), ("清空", lambda: self.set_all_columns(False))]:
            button = QPushButton(text)
            button.setObjectName("TextButton")
            button.clicked.connect(callback)
            heading.addWidget(button)
        column_layout.addLayout(heading)
        self.columns = ColumnList()
        self.columns.setMinimumHeight(170)
        self.columns.setSpacing(2)
        self.columns.itemChanged.connect(self.columns_changed)
        self.columns.reorder_requested.connect(self.move_column_to)
        column_layout.addWidget(self.columns, 1)
        column_actions = QHBoxLayout()
        hint = QLabel("拖动字段调整顺序")
        hint.setObjectName("Muted")
        column_actions.addWidget(hint)
        column_actions.addStretch()
        for icon, delta, tooltip in [('up', -1, '上移所选字段'), ('down', 1, '下移所选字段')]:
            button = QPushButton()
            button.setObjectName("IconButton")
            button.setIcon(line_icon(icon))
            button.setFixedSize(28, 28)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda checked=False, d=delta: self.move_column(d))
            column_actions.addWidget(button)
        column_layout.addLayout(column_actions)
        self.remember = QCheckBox("记住选列与顺序")
        self.remember.setChecked(self.settings.value("remember", True, type=bool))
        self.remember.toggled.connect(self.remember_changed)
        column_layout.addWidget(self.remember)
        self.settings_pages.addWidget(columns_page)

        layout_scroll = QScrollArea()
        layout_scroll.setWidgetResizable(True)
        layout_scroll.viewport().setStyleSheet('background: #efeff3;')
        layout_page = QWidget()
        layout_page.setObjectName('LayoutPage')
        layout_box = QVBoxLayout(layout_page)
        layout_box.setContentsMargins(0, 0, 4, 0)
        layout_box.setSpacing(14)
        layout_box.addWidget(self.section_label("Word 表格"))
        form = QFormLayout()
        form.setVerticalSpacing(14)
        self.per_page = QSpinBox()
        self.per_page.setRange(1,100)
        self.per_page.setValue(18)
        form.addRow("每页词数",self.per_page)
        self.word_font = QLineEdit()
        self.word_font.setPlaceholderText("华文中宋（默认字体）")
        form.addRow("字体覆盖",self.word_font)
        self.max_length = QSpinBox()
        self.max_length.setRange(0,200)
        self.max_length.setSpecialValueText("按列宽自动计算")
        form.addRow("释义断行字数",self.max_length)
        layout_box.addLayout(form)
        self.break_def = QCheckBox("自动断行释义")
        self.break_def.setChecked(True)
        layout_box.addWidget(self.break_def)
        word_note = QLabel("数字列优先留足单行宽度，空间不足时适当收窄后面的文本列。")
        word_note.setWordWrap(True)
        word_note.setObjectName("Muted")
        layout_box.addWidget(word_note)
        layout_box.addSpacing(12)
        layout_box.addWidget(self.section_label("词表名称"))
        self.document_title = QLineEdit("词汇词书")
        self.document_title.setMaxLength(120)
        layout_box.addWidget(self.document_title)
        layout_box.addStretch()
        layout_scroll.setWidget(layout_page)
        self.settings_pages.addWidget(layout_scroll)
        splitter.addWidget(sidebar)

        right = QFrame()
        right.setObjectName("PreviewPane")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(22, 18, 22, 18)
        right_layout.setSpacing(14)
        preview_heading = QHBoxLayout()
        heading = QLabel("词表预览")
        heading.setObjectName("PaneTitle")
        preview_heading.addWidget(heading)
        preview_heading.addStretch()
        right_layout.addLayout(preview_heading)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        self.search = QLineEdit()
        self.search.setObjectName("SearchField")
        self.search.setPlaceholderText("搜索单词或释义")
        self.search.addAction(line_icon('search', '#8e8e93', 18), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda: self.filter_timer.start())
        filter_row.addWidget(self.search, 1)
        self.category = QComboBox()
        self.category.setMaximumWidth(180)
        self.category.currentIndexChanged.connect(self.refresh)
        filter_row.addWidget(self.category)
        right_layout.addLayout(filter_row)
        options = QHBoxLayout()
        options.setSpacing(10)
        self.sort = QComboBox()
        self.sort.addItems(["原始顺序", "单词字母顺序", "词频从高到低"])
        self.sort.setMaximumWidth(166)
        self.sort.currentIndexChanged.connect(self.refresh)
        options.addWidget(self.sort)
        prefix = QLabel("词数")
        prefix.setObjectName("Muted")
        options.addWidget(prefix)
        self.limit = QSpinBox()
        self.limit.setRange(0, 10000000)
        self.limit.setSpecialValueText("全部")
        self.limit.setMaximumWidth(105)
        self.limit.valueChanged.connect(self.refresh)
        options.addWidget(self.limit)
        self.renumber = QCheckBox("重新编号")
        self.renumber.toggled.connect(self.refresh)
        options.addWidget(self.renumber)
        options.addStretch()
        right_layout.addLayout(options)
        self.count_label = QLabel()
        self.count_label.setObjectName("PreviewCaption")
        right_layout.addWidget(self.count_label)
        self.preview_model = PreviewModel()
        self.preview = QTableView()
        self.preview.setModel(self.preview_model)
        self.preview.setShowGrid(False)
        self.preview.setAlternatingRowColors(True)
        self.preview.setWordWrap(False)
        self.preview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.preview.horizontalHeader().setStretchLastSection(True)
        self.preview.verticalHeader().setDefaultSectionSize(42)
        right_layout.addWidget(self.preview, 1)
        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        right_layout.addWidget(divider)
        exports = QHBoxLayout()
        export_label = QLabel("导出为")
        export_label.setObjectName("Muted")
        exports.addWidget(export_label)
        self.format = QComboBox()
        self.format.addItems(["Word 表格 (.docx)", "JSON (.json)", "CSV (.csv)", "SQL (.sql)"])
        self.format.setMinimumWidth(145)
        exports.addWidget(self.format)
        exports.addStretch()
        self.export_button = QPushButton("生成词表")
        self.export_button.setObjectName("Primary")
        self.export_button.setIcon(line_icon('export', '#ffffff'))
        self.export_button.setMinimumWidth(128)
        self.export_button.clicked.connect(self.save_file)
        exports.addWidget(self.export_button)
        right_layout.addLayout(exports)
        splitter.addWidget(right)
        splitter.setSizes([300, 850])

        bottom = QHBoxLayout()
        self.status = QLabel("文件始终留在本机")
        self.status.setObjectName("StatusText")
        bottom.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(150)
        self.progress.hide()
        bottom.addWidget(self.progress)
        self.open_output = QPushButton("打开生成文件")
        self.open_output.setObjectName("TextButton")
        self.open_output.clicked.connect(self.open_generated)
        self.open_output.hide()
        bottom.addWidget(self.open_output)
        outer_layout.addLayout(bottom)

    @staticmethod
    def section_label(text):
        label=QLabel(text); label.setObjectName("SectionTitle"); return label

    def choose_file(self):
        path,_=QFileDialog.getOpenFileName(self,"导入词表 JSON",self.settings.value("import_directory",""),"JSON 文件 (*.json)")
        if path:
            self.import_file(Path(path))

    def import_file(self,path):
        if self.busy:
            return
        path=Path(path)
        def done(tables):
            self.tables=tables; self.source_path=path
            self.settings.setValue("import_directory",str(path.parent))
            self.table_combo.blockSignals(True); self.table_combo.clear()
            for table in tables:
                self.table_combo.addItem(f"{table.name} · {len(table.rows)} 条")
            self.table_combo.blockSignals(False)
            self.table_combo.setVisible(len(tables)>1)
            self.source_label.setText(path.name)
            self.source_label.setToolTip(str(path))
            self.stack.setCurrentIndex(1)
            self.activate_table(0)
            self.status.setText(f"已解析 {len(tables)} 个词表 · 文件保留在本机")
        self.run_job(lambda:load_json(path),done,"正在解析 JSON…")

    def schema_key(self):
        schema=json.dumps(sorted(self.dataset.fields),ensure_ascii=False)
        return "columns/"+hashlib.sha256(schema.encode()).hexdigest()

    def activate_table(self,index):
        if index<0 or index>=len(self.tables):
            return
        self.updating=True
        self.dataset=self.tables[index]
        fields=self.dataset.fields
        self.search.clear(); self.limit.setValue(0); self.sort.setCurrentIndex(0); self.renumber.setChecked(False)
        self.category.clear(); self.category.addItem("全部分类","")
        category_field=find_field(fields,"分类名称")
        if category_field:
            for value in sorted({display(r.get(category_field)) for r in self.dataset.rows if r.get(category_field)}):
                self.category.addItem(value,value)
        self.category.setEnabled(bool(category_field))
        self.document_title.setText("词汇词书")
        self.columns.clear()
        saved=None
        if self.remember.isChecked():
            try:
                saved=json.loads(self.settings.value(self.schema_key(),"null"))
            except (ValueError,TypeError):
                pass
        ordered,selected=column_state(fields,self.preset.currentText(),saved)
        for field in ordered:
            item=QListWidgetItem(field)
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsDragEnabled)
            item.setCheckState(Qt.CheckState.Checked if field in selected else Qt.CheckState.Unchecked)
            self.columns.addItem(item)
        self.updating=False
        self.columns_changed()

    def selected_columns(self):
        return [self.columns.item(i).text() for i in range(self.columns.count()) if self.columns.item(i).checkState()==Qt.CheckState.Checked]

    def remember_changed(self):
        self.settings.setValue("remember",self.remember.isChecked())
        if self.remember.isChecked():
            self.columns_changed()

    def columns_changed(self,*args):
        if self.updating or not self.dataset:
            return
        present=[self.columns.item(i).text() for i in range(self.columns.count())]
        if len(present)!=len(self.dataset.fields) or set(present)!=set(self.dataset.fields):
            ordered,selected=column_state(self.dataset.fields,self.preset.currentText(),{
                'order':present,'selected':self.selected_columns()})
            self.updating=True
            self.columns.clear()
            for field in ordered:
                item=QListWidgetItem(field)
                item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if field in selected else Qt.CheckState.Unchecked)
                self.columns.addItem(item)
            self.updating=False
        if self.remember.isChecked():
            self.settings.setValue(self.schema_key(),json.dumps({
                "order":[self.columns.item(i).text() for i in range(self.columns.count())],
                "selected":self.selected_columns()},ensure_ascii=False))
        self.refresh()

    def apply_preset(self,name):
        if not self.dataset:
            return
        selected=recommended_fields(self.dataset.fields,name)
        self.updating=True
        # A preset has a useful column order, followed by unchecked remaining fields.
        fields=selected+[f for f in self.dataset.fields if f not in selected]
        self.columns.clear()
        for field in fields:
            item=QListWidgetItem(field)
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if field in selected else Qt.CheckState.Unchecked)
            self.columns.addItem(item)
        self.updating=False; self.columns_changed()

    def set_all_columns(self,on):
        self.updating=True
        for i in range(self.columns.count()):
            self.columns.item(i).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        self.updating=False; self.columns_changed()

    def move_column(self,delta):
        row=self.columns.currentRow(); target=row+delta
        self.move_column_to(row,target)

    def move_column_to(self,row,target):
        if row<0 or not 0<=target<self.columns.count():
            return
        self.updating=True
        item=self.columns.takeItem(row); self.columns.insertItem(target,item); self.columns.setCurrentRow(target)
        self.updating=False; self.columns_changed()

    def refresh(self,*args):
        if self.updating or not self.dataset:
            return
        self.filtered=select_rows(self.dataset,search=self.search.text(),category=self.category.currentData() or "",
                                  sort=self.sort.currentText(),limit=self.limit.value(),renumber=self.renumber.isChecked())
        fields=self.selected_columns()
        # Content preview is bounded; exports always use the complete filtered set.
        self.preview_model.update(self.filtered[:200],fields)
        self.count_label.setText(f"{len(self.filtered):,} / {len(self.dataset.rows):,} 个词条    ·    {len(fields)} 列    ·    显示前 {min(200,len(self.filtered))} 条")
        for i,field in enumerate(fields):
            self.preview.setColumnWidth(i,260 if field in {"释义","例句","例句翻译","definition","meaning"} else 150)
        enabled=bool(fields and self.filtered)
        self.export_button.setEnabled(enabled)

    def layout_options(self):
        return Layout(title=self.document_title.text().strip() or "词汇词书",
                      rows_per_page=self.per_page.value(),font=self.word_font.text().strip(),
                      max_length=self.max_length.value(),break_def=self.break_def.isChecked())

    def save_file(self):
        self.filter_timer.stop(); self.refresh()
        if not self.filtered or not self.selected_columns():
            return
        suffix=["docx","json","csv","sql"][self.format.currentIndex()]
        base=self.source_path.stem if self.source_path else "vocabulary"
        folder=self.settings.value("export_directory",str(Path.home()/"Documents"))
        target, selected_filter=QFileDialog.getSaveFileName(self,"保存词表",str(Path(folder)/(base+"-词表."+suffix)),f"{suffix.upper()} 文件 (*.{suffix})")
        if not target:
            return
        path=Path(target)
        if path.suffix.lower()!="."+suffix:
            path=Path(str(path)+"."+suffix)
            if path.exists() and QMessageBox.question(self,"覆盖文件",f"{path.name} 已存在，是否覆盖？")!=QMessageBox.StandardButton.Yes:
                return
        self.settings.setValue("export_directory",str(path.parent))
        self.export_to(path)

    def export_to(self,path):
        self.filter_timer.stop(); self.refresh()
        rows=list(self.filtered); fields=self.selected_columns(); layout=self.layout_options()
        def done(_):
            self.output_path=Path(path); self.open_output.show()
            self.status.setText(f"已生成 {len(rows):,} 条 · {Path(path).name}")
        self.run_job(lambda:export_file(Path(path),rows,fields,layout),done,"正在生成词表…")

    def run_job(self,fn,done,message):
        if self.busy:
            return
        self.busy=True; self.editor.setEnabled(False); self.open_button.setEnabled(False)
        self.progress.show(); self.status.setText(message)
        job=Job(fn)
        def completed(value):
            self.finish_job(); done(value)
        job.signals.done.connect(completed)
        job.signals.failed.connect(self.job_error)
        self.active_job=job
        self.thread_pool.start(job)

    def finish_job(self):
        self.busy=False; self.editor.setEnabled(True); self.open_button.setEnabled(True); self.progress.hide()
        self.refresh()

    def job_error(self,message):
        self.finish_job(); self.status.setText("操作未完成，请检查文件或设置")
        box=QMessageBox(self); box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("无法完成操作"); box.setTextFormat(Qt.TextFormat.PlainText); box.setText(message); box.exec()

    def open_generated(self):
        if self.output_path and self.output_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_path)))

    def dragEnterEvent(self,event):
        urls=event.mimeData().urls()
        if not self.busy and len(urls)==1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower()==".json":
            event.acceptProposedAction()

    def dropEvent(self,event):
        urls=event.mimeData().urls()
        if len(urls)==1 and urls[0].isLocalFile():
            self.import_file(Path(urls[0].toLocalFile())); event.acceptProposedAction()

    def closeEvent(self,event):
        if self.busy:
            self.status.setText("正在处理文件，请完成后再关闭窗口。")
            event.ignore(); return
        self.temp.cleanup()
        super().closeEvent(event)


STYLE = """
QWidget { color: #1d1d1f; font-size: 13px; }
QMainWindow, QDialog { background: #f5f5f7; }
QLabel#AppTitle { font-size: 25px; font-weight: 700; }
QLabel#PaneTitle { font-size: 18px; font-weight: 600; }
QLabel#FileName { font-size: 14px; font-weight: 600; }
QLabel#EmptyTitle { font-size: 30px; font-weight: 700; }
QLabel#HeroDescription { font-size: 15px; color: #86868b; line-height: 1.6; }
QLabel#HeroIcon { background: #edf5ff; border: 1px solid #e2edfc; border-radius: 22px; }
QLabel#Muted { color: #86868b; font-size: 12px; }
QLabel#PreviewCaption { color: #86868b; font-size: 12px; padding: 3px 0; }
QLabel#SectionTitle { font-size: 12px; color: #6e6e73; font-weight: 600; }
QLabel#StatusText { color: #98989d; font-size: 11px; }
QLabel#FeatureBadge { color: #6e6e73; background: #f5f5f7; border-radius: 12px; padding: 7px 12px; font-size: 12px; }
QLabel#OfflineBadge { color: #438765; background: #edf5ef; border-radius: 12px; padding: 6px 11px; font-size: 11px; }
QFrame#EmptyPane { background: white; border: 1px solid #e8e8ed; border-radius: 18px; }
QFrame#Sidebar { background: #efeff3; border: 1px solid #e8e8ed; border-radius: 16px; }
QWidget#LayoutPage { background: #efeff3; }
QFrame#PreviewPane { background: white; border: 1px solid #e8e8ed; border-radius: 16px; }
QFrame#Segmented { background: #e3e3e9; border-radius: 9px; }
QFrame#Divider { background: #ededf0; border: none; }
QPushButton { background: white; border: 1px solid #dedee3; border-radius: 8px; padding: 8px 13px; font-weight: 500; }
QPushButton:hover { background: #f8f8fa; border-color: #c9c9cf; }
QPushButton:pressed { background: #ededf0; }
QPushButton#Primary { background: #007aff; color: white; border: 1px solid #007aff; padding: 9px 16px; font-weight: 600; }
QPushButton#Primary:hover { background: #006be0; border-color: #006be0; }
QPushButton#Primary:pressed { background: #005fc7; }
QPushButton#TextButton { background: transparent; color: #007aff; border: none; padding: 2px 5px; font-size: 12px; }
QPushButton#TextButton:hover { color: #005fc7; }
QPushButton#IconButton { padding: 3px; border-radius: 7px; }
QPushButton#SegmentButton { background: transparent; border: 1px solid transparent; border-radius: 7px; padding: 6px 12px; color: #6e6e73; }
QPushButton#SegmentButton:checked { background: white; border: 1px solid #d7d7de; color: #1d1d1f; }
QPushButton:disabled { color: #b2b2b8; background: #f2f2f5; border-color: #e8e8ed; }
QLineEdit, QComboBox, QSpinBox { background: white; border: 1px solid #dedee5; border-radius: 8px; padding: 7px 10px; min-height: 20px; selection-background-color: #cfe5ff; selection-color: #1d1d1f; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #78b5ff; }
QLineEdit#SearchField { background: #f5f5f7; border: 1px solid #f5f5f7; }
QLineEdit#SearchField:focus { background: white; border-color: #78b5ff; }
QLineEdit:disabled, QComboBox:disabled { color: #aeaeb3; background: #f5f5f7; }
QComboBox { padding-right: 27px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 25px; border: none; }
QComboBox::down-arrow { image: url('@ASSETS@/chevron-down.svg'); width: 14px; height: 14px; }
QComboBox QAbstractItemView { background: white; border: 1px solid #dedee3; padding: 4px; selection-background-color: #e8f2ff; selection-color: #1d1d1f; }
QSpinBox { padding-right: 24px; }
QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 22px; border: none; }
QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 22px; border: none; }
QSpinBox::up-arrow { image: url('@ASSETS@/chevron-up.svg'); width: 12px; height: 12px; }
QSpinBox::down-arrow { image: url('@ASSETS@/chevron-down.svg'); width: 12px; height: 12px; }
QListWidget { border: none; background: transparent; outline: none; }
QListWidget::item { padding: 7px 8px; border-radius: 7px; }
QListWidget::item:hover { background: #e7e7ec; }
QListWidget::item:selected { background: #dfe6f0; color: #1d1d1f; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator, QListWidget::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #c4c4cb; background: white; }
QCheckBox::indicator:checked, QListWidget::indicator:checked { border-color: #007aff; background: #007aff; image: url('@ASSETS@/check.svg'); }
QTableView { border: none; background: white; alternate-background-color: #f8f9fb; selection-background-color: #e5f0ff; selection-color: #1d1d1f; outline: none; }
QHeaderView::section { background: #f7f7f9; border: none; border-bottom: 1px solid #ededf0; padding: 10px 12px; color: #86868b; font-size: 12px; font-weight: 500; }
QTableCornerButton::section { background: #f7f7f9; border: none; }
QTableView::item { padding: 0 9px; }
QScrollArea { border: none; background: transparent; }
QSplitter::handle { background: transparent; width: 16px; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px 0; }
QScrollBar::handle:vertical { background: #c7c7ce; min-height: 28px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0 2px; }
QScrollBar::handle:horizontal { background: #c7c7ce; min-width: 28px; border-radius: 4px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
QProgressBar { border: none; background: #e4e4e9; border-radius: 3px; max-height: 5px; }
QProgressBar::chunk { background: #007aff; border-radius: 3px; }
"""


def create_application():
    app=QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("VocabularyStudio")
    app.setOrganizationName("exam-data")
    app.setStyle("Fusion")
    palette=QPalette(); palette.setColor(QPalette.ColorRole.Window,QColor("#f5f5f7")); palette.setColor(QPalette.ColorRole.WindowText,QColor("#1d1d1f"))
    palette.setColor(QPalette.ColorRole.Base,QColor("white")); palette.setColor(QPalette.ColorRole.Text,QColor("#1d1d1f")); palette.setColor(QPalette.ColorRole.ButtonText,QColor("#1d1d1f"))
    app.setPalette(palette)
    font=QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    if font.family()=='Sans Serif':
        families=set(QFontDatabase.families())
        for name in ['Helvetica Neue','Segoe UI','Noto Sans','DejaVu Sans','Arial']:
            if name in families:
                font=QFont(name)
                break
    font.setPointSize(13)
    app.setFont(font)
    app.setWindowIcon(QIcon(str(ui_dir()/'app-icon.png')))
    app.setStyleSheet(STYLE.replace("@ASSETS@",ui_dir().as_posix()))
    return app


def main():
    app=create_application()
    window=Window()
    if len(sys.argv)==3 and sys.argv[1]=="--self-test":
        from .selftest import run
        run(app,window,sys.argv[2])
        return
    window.show()
    sys.exit(app.exec())


if __name__=="__main__":
    main()
