#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON → docx：直接从词汇 JSON 生成排版完善的 Word 文档，导出即成品。

相比旧流程（generate_doc_from_sql.py + 两次 macro.js + 手工测字数断行）：
- 不再需要 MySQL；美化内建（等效旧 macro.js：首行灰底、0.5pt 黑边框、华文中宋、
  行高至少 31.18pt、水平+垂直居中、零间距）
- 固定列宽布局：释义列自动计算单行最大汉字数，按顿号优雅断行，无需人工实测
  （字号 11pt 全角字宽 220 twips，列宽减边距后整除即得）
- 可用 --max-length 覆盖自动值，--no-break-def 关闭断行

依赖：pip install python-docx

用法：
    python3 export_docx.py netem_full_list.json -o out.docx
    python3 export_docx.py cet_full_list.json -o out.docx --per-page 18 --columns 序号,单词,释义,分类名称
"""
import argparse, json, sys

from docx import Document
from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Twips

HEADER_FILL = "808080"      # 首行灰底（等同 wdColorGray50）
ROW_HEIGHT = Pt(31.18)
FONT = "华文中宋"
FONT_SIZE_PT = 11           # 显式固定，保证断行计算确定
CHAR_TWIPS = FONT_SIZE_PT * 20
PAGE_TEXT_TWIPS = 9026      # A4 (11906) - 默认左右页边距 (1440*2)
CELL_MARGIN_TWIPS = 216     # 单元格左右内边距 (108*2)

# 各字段列宽（twips）；释义为弹性列，吃掉剩余宽度
FIELD_WIDTH = {
    "序号": 650, "原序号": 650, "词频": 750, "六级": 450,
    "单词": 1600, "其他拼写": 1100, "分类名称": 1100,
    "CEFR等级": 650, "学术词汇": 750, "高级词汇": 750, "综合得分": 750,
}
DEF_FIELD = "释义"

import re

def str_add_break_line(zh_str, max_length, seps="、；"):
    """按义项分隔符（顿号/分号）断行：贪心装行，超长义项独占一行。
    兼容考研数据（、分隔）与四六级数据（；分隔）两种释义风格。"""
    zh_str = zh_str.strip()
    if not zh_str:
        return zh_str
    parts = re.split(f"([{seps}])", zh_str)   # [词, 分隔符, 词, ...]
    items = []
    i = 0
    while i < len(parts):
        word = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        if word:
            items.append(word + sep)
        i += 2
    lines, cur, curlen = [], [], 0
    for item in items:
        add = len(item) if not cur else len(item)  # 分隔符已随词计入
        if cur and curlen + add > max_length:
            lines.append("".join(cur))
            cur, curlen = [], 0
        cur.append(item)
        curlen += add
        if len(item) > max_length:      # 超长义项：独占，后续换新行
            lines.append("".join(cur))
            cur, curlen = [], 0
    if cur:
        lines.append("".join(cur))
    return "\n".join(l.rstrip("、；") for l in lines)

def shade(cell, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shd)

def write_cell(cell, text, header=False):
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    if header:
        shade(cell, HEADER_FILL)
    p = cell.paragraphs[0]
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    segs = text.split("\n")
    for i, seg in enumerate(segs):
        run = p.add_run(seg)
        run.bold = header
        run.font.name = FONT
        run.font.size = Pt(FONT_SIZE_PT)
        run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        if i < len(segs) - 1:
            run.add_break()

def compute_widths(fields):
    fixed = sum(FIELD_WIDTH.get(f, 1100) for f in fields if f != DEF_FIELD)
    widths = []
    for f in fields:
        if f == DEF_FIELD:
            widths.append(max(PAGE_TEXT_TWIPS - fixed, 1200))
        else:
            widths.append(FIELD_WIDTH.get(f, 1100))
    return widths

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="词汇 JSON 文件")
    ap.add_argument("-o", "--output", default="updated_doc.docx", help="输出 docx（默认 updated_doc.docx）")
    ap.add_argument("--per-page", type=int, default=18, help="每页单词数（默认 18）")
    ap.add_argument("--columns", help="要导出的字段，逗号分隔（默认全部字段）")
    ap.add_argument("--max-length", type=int, help="释义单行最大汉字数（默认按列宽自动计算）")
    ap.add_argument("--no-break-def", action="store_true", help="关闭释义断行")
    args = ap.parse_args()

    data = json.load(open(args.input, encoding="utf-8"))
    rows = None
    for v in data.values():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            rows = v
            break
    if rows is None:
        sys.exit("JSON 顶层没有找到词条列表")
    fields = list(rows[0].keys())
    if args.columns:
        fields = [f.strip() for f in args.columns.split(",")]
        bad = [f for f in fields if f not in rows[0]]
        if bad:
            sys.exit(f"字段不存在：{bad}；可用字段：{list(rows[0].keys())}")

    widths = compute_widths(fields)
    break_def = not args.no_break_def and DEF_FIELD in fields
    max_length = None
    if break_def:
        def_w = widths[fields.index(DEF_FIELD)]
        max_length = args.max_length or max(1, (def_w - CELL_MARGIN_TWIPS) // CHAR_TWIPS)
        print(f"释义列宽 {def_w} twips → 单行最大 {max_length} 字（{'手动指定' if args.max_length else '自动计算'}）")

    per_num, total = args.per_page, len(rows)
    page_num = total // per_num + (1 if total % per_num else 0)

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(FONT_SIZE_PT)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

    idx = 0
    for _ in range(page_num):
        table = doc.add_table(rows=per_num + 1, cols=len(fields))
        table.style = "Table Grid"          # 0.5pt 全黑边框
        table.autofit = False               # 固定列宽
        tblPr = table._tbl.tblPr
        layout = OxmlElement("w:tblLayout")
        layout.set(qn("w:type"), "fixed")
        tblPr.append(layout)
        for ci, w in enumerate(widths):
            for cell in table.columns[ci].cells:
                cell.width = Twips(w)
        for row in table.rows:
            row.height = ROW_HEIGHT
            row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        for ci, name in enumerate(fields):
            write_cell(table.rows[0].cells[ci], name, header=True)
        for ri in range(1, per_num + 1):
            if idx >= total:
                break
            r = rows[idx]
            for ci, f in enumerate(fields):
                v = r[f]
                text = "" if v is None else str(v)
                if break_def and f == DEF_FIELD and text:
                    text = str_add_break_line(text, max_length)
                write_cell(table.rows[ri].cells[ci], text)
            idx += 1
        doc.add_page_break()
        if idx >= total:
            break

    doc.save(args.output)
    print(f"ok: {total} 词 / {page_num} 页 -> {args.output}（美化+断行已内建，打开即是成品）")

if __name__ == "__main__":
    main()
