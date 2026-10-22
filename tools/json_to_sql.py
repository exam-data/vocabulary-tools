#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON → SQL：把词汇 JSON（仓库唯一真源）转换成 MySQL 导入文件。

用法：
    python3 json_to_sql.py netem_full_list.json              # 输出同名 .sql
    python3 json_to_sql.py cet_full_list.json -o cet.sql     # 指定输出路径
"""
import argparse, json, os, sys

# JSON 中文字段 -> SQL 英文列名（含类型）
FIELD_MAP = {
    "序号":    ("id",         "int"),
    "词频":    ("frequency",  "int"),
    "六级":    ("cet6",       "varchar(32)"),
    "单词":    ("word",       "varchar(255)"),
    "释义":    ("definition", "varchar(255)"),
    "其他拼写": ("variant",    "varchar(255)"),
    "分类名称": ("category",   "varchar(255)"),
}

def quote(v):
    if v is None:
        return "NULL"
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="词汇 JSON 文件")
    ap.add_argument("-o", "--output", help="输出 SQL 路径（默认同名 .sql）")
    args = ap.parse_args()

    data = json.load(open(args.input, encoding="utf-8"))
    table_key = list(data)[0]
    rows = data[table_key]
    table_name = os.path.splitext(os.path.basename(args.input))[0]
    out_path = args.output or os.path.splitext(args.input)[0] + ".sql"

    fields = list(rows[0].keys())
    unknown = [f for f in fields if f not in FIELD_MAP]
    if unknown:
        sys.exit(f"未知字段：{unknown}，请先在 FIELD_MAP 中补充映射")

    col_lines = []
    for f in fields:
        col, typ = FIELD_MAP[f]
        null = "NOT NULL" if col == "id" else "NULL DEFAULT NULL"
        if typ.startswith("varchar"):
            col_lines.append(f"  `{col}` {typ} CHARACTER SET utf8mb4 COLLATE utf8mb4_bin {null}")
        else:
            col_lines.append(f"  `{col}` {typ}(0) {null}")
    if any(FIELD_MAP[f][0] == "id" for f in fields):
        col_lines.append("  PRIMARY KEY (`id`) USING BTREE")

    L = ["SET NAMES utf8mb4;",
         "SET FOREIGN_KEY_CHECKS = 0;",
         "",
         "-- ----------------------------",
         f"-- Table structure for {table_name}",
         "-- ----------------------------",
         f"DROP TABLE IF EXISTS `{table_name}`;",
         f"CREATE TABLE `{table_name}`  (",
         ",\n".join(col_lines),
         ") ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_bin ROW_FORMAT = Dynamic;",
         "",
         "-- ----------------------------",
         f"-- Records of {table_name}",
         "-- ----------------------------",
         ""]
    for r in rows:
        vals = ", ".join(quote(r[f]) for f in fields)
        L.append(f"INSERT INTO `{table_name}` VALUES ({vals});")
        L.append("")
    L.append("SET FOREIGN_KEY_CHECKS = 1;")

    open(out_path, "w", encoding="utf-8").write("\n".join(L))
    print(f"ok: {len(rows)} 行 -> {out_path}")

if __name__ == "__main__":
    main()
