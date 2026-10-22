#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL → JSON：把旧流程的 MySQL 导入文件还原为词汇 JSON（与 json_to_sql.py 互逆）。

用法：
    python3 sql_to_json.py netem_full_list.sql                      # 输出同名 .json
    python3 sql_to_json.py cet_full_list.sql -t 四六级词汇词频排序表   # 指定 JSON 顶层标题
"""
import argparse, os, re, sys

COLUMN_MAP = {  # SQL 列名 -> JSON 中文字段
    "id": "序号", "frequency": "词频", "cet6": "六级",
    "word": "单词", "definition": "释义", "variant": "其他拼写", "category": "分类名称",
    "orig_id": "原序号", "cefr": "CEFR等级", "nawl": "学术词汇", "c1c2": "高级词汇",
    "score": "综合得分",
    "sentence": "例句", "sentence_cn": "例句翻译", "sentence_src": "例句来源",
}
TITLE_MAP = {
    "netem_full_list": "5530考研词汇词频排序表",
    "cet_full_list": "四六级词汇词频排序表",
}

def split_values(s):
    """按顶层逗号拆分 VALUES 内容，兼容引号与转义"""
    vals, cur, inq, i = [], [], False, 0
    while i < len(s):
        c = s[i]
        if inq:
            if c == "\\" and i + 1 < len(s):
                cur.append(s[i + 1]); i += 2; continue
            if c == "'":
                inq = False
            else:
                cur.append(c)
        else:
            if c == "'":
                inq = True
            elif c == ",":
                vals.append("".join(cur).strip()); cur = []
            else:
                cur.append(c)
        i += 1
    tail = "".join(cur).strip()
    if tail:
        vals.append(tail)
    return vals

def parse_value(v, col):
    if v == "NULL":
        return None
    if col in ("id", "frequency", "orig_id"):
        return int(v)
    if col == "score":
        return float(v)
    if col in ("nawl", "c1c2"):
        return v == "1"
    return v

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="SQL 文件")
    ap.add_argument("-o", "--output", help="输出 JSON 路径（默认同名 .json）")
    ap.add_argument("-t", "--title", help="JSON 顶层标题（默认按文件名推断）")
    args = ap.parse_args()

    text = open(args.input, encoding="utf-8").read()
    m = re.search(r"CREATE TABLE `(\w+)`\s*\((.*?)\) ENGINE", text, re.S)
    if not m:
        sys.exit("未找到 CREATE TABLE 语句")
    table_name, col_block = m.group(1), m.group(2)
    cols = [re.match(r"\s*`(\w+)`", l).group(1)
            for l in col_block.splitlines() if l.strip().startswith("`")]

    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("INSERT INTO"):
            continue
        vm = re.search(r"VALUES \((.*)\);$", line)
        if not vm:
            continue
        vals = split_values(vm.group(1))
        if len(vals) != len(cols):
            sys.exit(f"列数与值数不符：{line[:120]}")
        row = {}
        for col, val in zip(cols, vals):
            row[COLUMN_MAP.get(col, col)] = parse_value(val, col)
        rows.append(row)

    title = args.title or TITLE_MAP.get(table_name, table_name)
    out_path = args.output or os.path.splitext(args.input)[0] + ".json"
    import json
    json.dump({title: rows}, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"ok: {len(rows)} 行 -> {out_path}")

if __name__ == "__main__":
    main()
