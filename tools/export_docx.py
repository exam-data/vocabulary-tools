#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON → docx：直接从词汇 JSON 生成 Word 初版文档（每页一个表格，首行是字段名）。
替代旧流程的 generate_doc_from_sql.py —— 不再需要 MySQL。

依赖：pip install python-docx

用法：
    python3 export_docx.py netem_full_list.json -o out.docx
    python3 export_docx.py cet_full_list.json -o out.docx --per-page 18 --columns 序号,单词,释义,分类名称

生成后：把 macro.js 放进 WPS 宏执行美化；需要释义换行再用 format_doc_def.py。
"""
import argparse, json, os, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="词汇 JSON 文件")
    ap.add_argument("-o", "--output", default="updated_doc.docx", help="输出 docx（默认 updated_doc.docx）")
    ap.add_argument("--per-page", type=int, default=18, help="每页单词数（默认 18）")
    ap.add_argument("--columns", help="要导出的字段，逗号分隔（默认全部字段）")
    args = ap.parse_args()

    try:
        from docx import Document
    except ImportError:
        sys.exit("缺少依赖：pip install python-docx")

    data = json.load(open(args.input, encoding="utf-8"))
    rows = data[list(data)[0]]
    fields = list(rows[0].keys())
    if args.columns:
        fields = [f.strip() for f in args.columns.split(",")]
        bad = [f for f in fields if f not in rows[0]]
        if bad:
            sys.exit(f"字段不存在：{bad}；可用字段：{list(rows[0].keys())}")

    per_num, total = args.per_page, len(rows)
    page_num = total // per_num + (1 if total % per_num else 0)

    doc = Document()
    idx = 0
    for _ in range(page_num):
        table = doc.add_table(rows=per_num + 1, cols=len(fields))
        for ci, name in enumerate(fields):
            table.rows[0].cells[ci].text = name
        for ri in range(1, per_num + 1):
            if idx >= total:
                break
            r = rows[idx]
            for ci, f in enumerate(fields):
                v = r[f]
                table.rows[ri].cells[ci].text = "" if v is None else str(v)
            idx += 1
        doc.add_page_break()
        if idx >= total:
            break

    doc.save(args.output)
    print(f"ok: {total} 词 / {page_num} 页 -> {args.output}")
    print("下一步：在 WPS 中打开，执行 tools/macro.js 美化")

if __name__ == "__main__":
    main()
