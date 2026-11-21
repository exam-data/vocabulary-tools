#!/usr/bin/env python3
"""检查 NETEMVocabulary 中 data/catalog.json 登记的词表及其引用关系，仅使用标准库。

    python3 tools/check_netem.py ../NETEMVocabulary
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "NETEMVocabulary"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check():
    catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    datasets = {}
    for item in catalog["datasets"]:
        name = item["id"]
        require(name not in datasets, f"清单 id 重复：{name}")
        require(Path(item["json"]).stem == Path(item["sql"]).stem == item["table"],
                f"{name}：JSON、SQL 文件名前缀与 SQL 表名不一致")
        document = json.loads((ROOT / item["json"]).read_text(encoding="utf-8"))
        rows = document[item["list_key"]]
        require(len(rows) == item["count"], f"{name}：JSON 词数与清单不符")
        if "总词数" in document:
            require(document["总词数"] == len(rows), f"{name}：顶层总词数不符")
        ids = [row["序号"] for row in rows]
        require(ids == list(range(1, len(rows) + 1)), f"{name}：序号不连续")
        words = [row["单词"] for row in rows]
        require(all(isinstance(w, str) and w.strip() for w in words), f"{name}：有空单词")
        require(len(set(words)) == len(rows), f"{name}：有重复单词")
        require(all(isinstance(r.get("英式音标"), str) and r["英式音标"].startswith("/")
                    and r["英式音标"].endswith("/") for r in rows), f"{name}：有缺失或格式错误的英式音标")
        sql = (ROOT / item["sql"]).read_text(encoding="utf-8")
        table = re.search(r"CREATE TABLE `([^`]+)`", sql)
        require(table is not None and table[1] == item["table"], f"{name}：SQL 表名不符")
        inserts = re.findall(r"^INSERT INTO `([^`]+)` VALUES \((\d+),", sql, re.M)
        require(len(inserts) == len(rows), f"{name}：SQL 行数不符")
        require(all(t == item["table"] for t, _ in inserts), f"{name}：INSERT 表名不符")
        require([int(i) for _, i in inserts] == ids, f"{name}：SQL 序号不符")
        datasets[name] = rows
        print(f"OK {name}: {len(rows)} 词，JSON / SQL 基本检查通过")

    expected = {"full", "reranked", "beyond", "beyond-reranked", "core", "core-reranked"}
    require(set(datasets) == expected, "清单应登记现有 6 份词表")
    full = {row["单词"]: row for row in datasets["full"]}
    by_id = {row["序号"]: row["单词"] for row in datasets["full"]}
    for name, rows in datasets.items():
        require({r["单词"] for r in rows} <= full.keys(), f"{name}：存在主表外的词")
        for row in rows:
            if "原序号" in row:
                require(by_id.get(row["原序号"]) == row["单词"], f"{name}：原序号错配 {row['单词']}")
            for field in ("英式音标", "例句", "例句翻译", "例句来源"):
                require(row.get(field) == full[row["单词"]].get(field), f"{name}：{row['单词']} 的 {field} 未同步")
    require({r["单词"] for r in datasets["reranked"]} == full.keys(), "reranked：完整词表成员不符")
    ranked = [r["单词"] for r in datasets["reranked"]]
    for name in ("core", "beyond"):
        base = {r["单词"]: r for r in datasets[name]}
        reordered = datasets[name + "-reranked"]
        require(set(base) == {r["单词"] for r in reordered}, f"{name}：词频版和重排版成员不同")
        require([r["单词"] for r in reordered] == [w for w in ranked if w in base], f"{name}：重排顺序不符")
        for row in reordered:
            original = base[row["单词"]]
            require({k: v for k, v in row.items() if k != "序号"} ==
                    {k: v for k, v in original.items() if k != "序号"},
                    f"{name}：重排版改变了 {row['单词']} 的原字段")
    for name in ("beyond", "core"):
        origins = [r["原序号"] for r in datasets[name]]
        require(origins == sorted(origins), f"{name}：与主词频顺序不符")
    print("OK 词表成员、顺序、原序号及例句同步检查通过")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="检查 NETEMVocabulary 的 JSON、SQL 及各版本同步情况。")
    parser.add_argument("repository", nargs="?", type=Path, default=ROOT,
                        help="NETEMVocabulary 仓库根目录（默认：同级 NETEMVocabulary）")
    ROOT = parser.parse_args().repository.resolve()
    try:
        check()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        sys.exit(f"检查失败：{exc}")
