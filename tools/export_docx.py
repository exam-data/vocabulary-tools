#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON → docx：直接从词汇 JSON 生成 Word 文档（每页一个表格，首行是字段名）。
替代旧流程的 generate_doc_from_sql.py —— 不再需要 MySQL；
且美化已内建（等效旧 macro.js：首行灰底、0.5pt 黑边框、华文中宋、
行高至少 31.18pt、水平+垂直居中、零间距），生成即成品，无需再跑 WPS 宏。

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
from docx.shared import Pt

HEADER_FILL = "808080"      # 首行灰底（等同 wdColorGray50）
ROW_HEIGHT = Pt(31.18)
FONT = "华文中宋"

def shade(cell, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shd)

def style_cell(cell, text, header=False):
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    if header:
        shade(cell, HEADER_FILL)
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    run = p.add_run(text)
    run.bold = header
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="词汇 JSON 文件")
    ap.add_argument("-o", "--output", default="updated_doc.docx", help="输出 docx（默认 updated_doc.docx）")
    ap.add_argument("--per-page", type=int, default=18, help="每页单词数（默认 18）")
    ap.add_argument("--columns", help="要导出的字段，逗号分隔（默认全部字段）")
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

    per_num, total = args.per_page, len(rows)
    page_num = total // per_num + (1 if total % per_num else 0)

    doc = Document()
    # 全局默认字体
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

    idx = 0
    for _ in range(page_num):
        table = doc.add_table(rows=per_num + 1, cols=len(fields))
        table.style = "Table Grid"          # 0.5pt 全黑边框
        for row in table.rows:
            row.height = ROW_HEIGHT
            row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        for ci, name in enumerate(fields):
            style_cell(table.rows[0].cells[ci], name, header=True)
        for ri in range(1, per_num + 1):
            if idx >= total:
                break
            r = rows[idx]
            for ci, f in enumerate(fields):
                v = r[f]
                style_cell(table.rows[ri].cells[ci], "" if v is None else str(v))
            idx += 1
        doc.add_page_break()
        if idx >= total:
            break

    doc.save(args.output)
    print(f"ok: {total} 词 / {page_num} 页 -> {args.output}（已内建美化，打开即是成品）")

if __name__ == "__main__":
    main()
