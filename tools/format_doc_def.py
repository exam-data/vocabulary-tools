#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx 释义换行：把表格中「释义」列按最大字符数断行（移植自旧仓 update_def/format_doc_def.py，
去掉数据库配置依赖，改为命令行参数）。

用法：
    python3 format_doc_def.py in.docx -o out.docx --max-length 20
    （max-length：释义单元格单行可容纳的最大汉字数；在 WPS 里实测后填入）

处理后记得回 WPS 再执行一次 tools/macro.js 美化。
"""
import argparse, sys

def str_add_break_line(zh_str, max_length):
    result = []
    zh_str = zh_str.strip()
    if not zh_str:
        return zh_str
    words = zh_str.split("、")
    current_length = 0
    for word in words:
        if len(word) > max_length:
            result.append(word)
            current_length = len(word) % max_length
            continue
        if current_length + len(word) + 1 <= max_length:
            if current_length > 0:
                result.append("、")
                current_length += 1
            result.append(word)
            current_length += len(word)
        else:
            if result:
                result.append("\n")
            result.append(word)
            current_length = len(word)
    if result and result[-1] == "、":
        result.pop()
    return "".join(result)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="输入 docx（export_docx.py 的产物）")
    ap.add_argument("-o", "--output", required=True, help="输出 docx")
    ap.add_argument("--max-length", type=int, required=True, help="释义单行最大汉字数")
    ap.add_argument("--column", default="释义", help="要处理的列标题（默认：释义）")
    args = ap.parse_args()

    try:
        import docx
    except ImportError:
        sys.exit("缺少依赖：pip install python-docx")

    doc = docx.Document(args.input)
    hit = 0
    for table in doc.tables:
        header = {cell.text.strip(): i for i, cell in enumerate(table.rows[0].cells)}
        if args.column not in header:
            continue
        ci = header[args.column]
        for i, row in enumerate(table.rows):
            if i == 0:
                continue
            cell = row.cells[ci]
            cell.text = str_add_break_line(cell.text, args.max_length)
            hit += 1
    if not hit:
        sys.exit(f"没有找到「{args.column}」列，请检查表头")
    doc.save(args.output)
    print(f"ok: 处理了 {hit} 个单元格 -> {args.output}")
    print("下一步：回 WPS 再执行一次 tools/macro.js")

if __name__ == "__main__":
    main()
