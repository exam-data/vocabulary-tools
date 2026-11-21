#!/usr/bin/env python3
"""Validate CET catalog, all row fields, ranked subsets and SQL round trips."""
import argparse
import json
from pathlib import Path
import re
import sys

from sql_to_json import COLUMN_MAP, split_values, parse_value

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "CETVocabulary"
EXPECTED = {"full", "reranked", "beyond", "beyond-reranked"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_sql(path):
    raw = path.read_text(encoding="utf-8")
    match = re.search(r"CREATE TABLE `(\w+)`\s*\((.*?)\) ENGINE", raw, re.S)
    require(match is not None, f"SQL 缺少建表语句：{path}")
    table, block = match.groups()
    columns = [re.match(r"\s*`(\w+)`", line).group(1) for line in block.splitlines() if line.strip().startswith("`")]
    require(len(set(columns)) == len(columns) and all(c in COLUMN_MAP for c in columns), f"SQL 列重复或未知：{path}")
    rows = []
    for line in raw.splitlines():
        if not line.startswith("INSERT INTO"):
            continue
        entry = re.fullmatch(r"INSERT INTO `(\w+)` VALUES \((.*)\);", line)
        require(entry is not None and entry[1] == table, f"SQL INSERT 表名或格式不符：{path}")
        values = split_values(entry[2])
        require(len(values) == len(columns), f"SQL 列数不符：{path}")
        rows.append({COLUMN_MAP[c]: parse_value(v, c) for c, v in zip(columns, values)})
    return table, rows


def check(root=DEFAULT_ROOT, netem=None):
    root = Path(root).resolve()
    catalog = json.loads((root / "data/catalog.json").read_text(encoding="utf-8"))
    items = catalog["datasets"]
    require(len(items) == 4 and {d["id"] for d in items} == EXPECTED, "CET 清单应登记完整/超课标的词频版和重排版，共 4 份；不设核心或兼容版")
    datasets, destinations = {}, set()
    for item in items:
        ident = item["id"]
        paths = [(root / item[field]).resolve() for field in ["json", "sql"]]
        for path in paths:
            require(path.is_relative_to(root) and path not in destinations, f"清单路径越界或重复：{path}")
            destinations.add(path)
        path, sqlpath = paths
        require(path.stem == sqlpath.stem == item["table"], f"{ident}：文件名与 SQL 表名不符")
        data = json.loads(path.read_text(encoding="utf-8")); rows = data[item["list_key"]]
        require(isinstance(rows, list) and rows and len(rows) == item["count"], f"{ident}：清单词数不符")
        if "总词数" in data:
            require(data["总词数"] == len(rows), f"{ident}：顶层总词数不符")
        require([r["序号"] for r in rows] == list(range(1, len(rows) + 1)), f"{ident}：序号不连续")
        words = [r["单词"] for r in rows]
        require(all(isinstance(w, str) and w.strip() for w in words) and len(set(words)) == len(words), f"{ident}：有空单词或重复词条")
        require(all(isinstance(r.get("英式音标"), str) and r["英式音标"].startswith("/") and r["英式音标"].endswith("/") for r in rows), f"{ident}：英式音标缺失或格式错误")
        require(all(r.get("六级") in {None, "★"} for r in rows), f"{ident}：六级标记异常")
        table, recovered = read_sql(sqlpath)
        require(table == item["table"] and recovered == rows, f"{ident}：SQL 逐行字段与 JSON 不一致")
        datasets[ident] = rows
        print(f"OK {ident}: {len(rows)} 词，JSON / SQL 全字段一致")
    full = {r["单词"]: r for r in datasets["full"]}
    for ident, rows in datasets.items():
        for row in rows:
            word = row["单词"]
            require(word in full, f"{ident}：存在主表外词条 {word}")
            source = full[word]
            require({k: v for k, v in row.items() if k not in {"序号", "原序号"}} ==
                    {k: v for k, v in source.items() if k != "序号"}, f"{ident}：{word} 字段与主表不一致")
            if ident != "full":
                require(row.get("原序号") == source["序号"], f"{ident}：{word} 原序号不符")
    require({r["单词"] for r in datasets["reranked"]} == set(full), "完整重排版成员不符")
    beyond = {r["单词"]: r for r in datasets["beyond"]}
    require({r["单词"] for r in datasets["beyond-reranked"]} == set(beyond), "超课标两版本成员不符")
    require([r["原序号"] for r in datasets["beyond"]] == sorted(r["原序号"] for r in datasets["beyond"]), "超课标词频版顺序不符")
    require([r["单词"] for r in datasets["beyond-reranked"]] == [r["单词"] for r in datasets["reranked"] if r["单词"] in beyond], "超课标重排相对顺序不符")
    print("OK 四个版本成员、原序号、字段及超课标相对排序一致")
    if netem:
        other_root = Path(netem).resolve()
        other_catalog = json.loads((other_root / "data/catalog.json").read_text())["datasets"]
        ds = next(d for d in other_catalog if d["id"] == "full")
        other = {r["单词"]: r for r in json.loads((other_root / ds["json"]).read_text())[ds["list_key"]]}
        fields = ("英式音标", "释义", "其他拼写", "分类名称", "CEFR等级", "学术词汇", "高级词汇", "例句", "例句翻译", "例句来源")
        common = full.keys() & other.keys()
        for word in common:
            for field in fields:
                require(full[word].get(field) == other[word].get(field), f"CET / NETEM 同词不同步：{word} / {field}")
        print(f"OK CET / NETEM {len(common)} 个完全同词的释义、音标、例句等字段一致")
    return datasets


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--netem", type=Path, help="额外检查与 NETEM 完全同词的公共字段")
    args = ap.parse_args(argv)
    try:
        check(args.root, args.netem)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"校验失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
