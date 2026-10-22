#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用词汇智能重排器：词频 × CEFR 难度 × 学术词汇（NAWL）× 高级词汇（C1/C2）
适用于 exam-data 任意词汇数据 JSON（考研/四六级或未来的数据集）。

用法：
    python3 rerank_vocab.py cet_full_list.json
    python3 rerank_vocab.py netem_full_list.json -o out_prefix

产出（与输入同目录）：
    <前缀>_reranked.json        完整版：原字段全部保留，序号变为新排名，
                                附加 原序号/CEFR等级/学术词汇/高级词汇/综合得分
    <前缀>_reranked_simple.json  兼容版：字段与输入完全对齐，仅序号变为新排名
算法权重见下方 CONFIG，可自行调整。
"""
import argparse, csv, json, math, os
from pathlib import Path

CONFIG = {
    "cefr_scores": {"A1": 0, "A2": 5, "B1": 15, "B2": 25, "C1": 40, "C2": 50},
    "cefr_default": 20,
    "nawl_bonus": 30,
    "c1c2_bonus": 20,
    "ngsl_penalty": -5,
    "freq_weight": 10,
    "zero_freq_base": 5,
}
REFDATA = Path(__file__).parent / "refdata"

def load_cefr(path):
    ranks = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
    out = {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            cefr = row["CEFR"].strip().upper()
            for w in row["headword"].strip().lower().split("/"):
                w = w.strip()
                if w and cefr and (w not in out or ranks.get(cefr, 0) > ranks.get(out[w], 0)):
                    out[w] = cefr
    return out

def load_headword_csv(path, column="headword"):
    """只取指定列（DictReader），避免 pos/notes 列里的语法词造成误判"""
    words = set()
    with open(path, encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            w = (row.get(column) or "").strip().lower()
            if w:
                words.add(w)
    return words

def load_word_set(path, header=True):
    words = set()
    with open(path, encoding="utf-8", errors="ignore") as f:
        if header:
            f.readline()
        for line in f:
            if line.startswith("#"):
                continue
            for part in line.split(","):
                w = part.strip().lower()
                if w:
                    words.add(w)
    return words

def normalize(word):
    v = [word.lower().strip()]
    if "-" in v[0]:
        v += [v[0].replace("-", ""), v[0].replace("-", " ")]
    return v

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="词汇 JSON（顶层含词条列表）")
    ap.add_argument("-o", "--out-prefix", help="输出文件名前缀（默认取输入文件名）")
    args = ap.parse_args()

    data = json.load(open(args.input, encoding="utf-8"))
    title, rows = None, None
    for k, v in data.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            title, rows = k, v
            break
    if rows is None:
        raise SystemExit("JSON 顶层没有找到词条列表")
    base_fields = list(rows[0].keys())
    print(f"词条 {len(rows)}，字段 {base_fields}")

    cefr = load_cefr(REFDATA / "cefrj-vocabulary-profile-1.5.csv")
    nawl = load_word_set(REFDATA / "NAWL_1.2_lemmatized_for_research.csv", header=False)
    ngsl = load_word_set(REFDATA / "NGSL_1.2_lemmatized_for_research.csv", header=False)
    c1c2 = load_headword_csv(REFDATA / "octanove-vocabulary-profile-c1c2-1.0.csv")

    C = CONFIG
    scored = []
    for entry in rows:
        freq = entry.get("词频") or 0
        freq_score = math.log(freq + 1) * C["freq_weight"] if freq > 0 else C["zero_freq_base"]
        variants = normalize(entry["单词"])
        level = next((cefr[v] for v in variants if v in cefr), None)
        cefr_score = C["cefr_scores"].get(level, C["cefr_default"]) if level else C["cefr_default"]
        is_nawl = any(v in nawl for v in variants)
        is_c1 = any(v in c1c2 for v in variants)
        penalty = C["ngsl_penalty"] if (freq > 1000 and any(v in ngsl for v in variants)) else 0
        score = freq_score + cefr_score + C["nawl_bonus"] * is_nawl + C["c1c2_bonus"] * is_c1 + penalty
        scored.append((score, entry, level, is_nawl, is_c1))

    scored.sort(key=lambda x: x[0], reverse=True)

    prefix = args.out_prefix or os.path.splitext(args.input)[0]
    full, simple = [], []
    for i, (score, entry, level, is_nawl, is_c1) in enumerate(scored, 1):
        full.append({"序号": i, "原序号": entry["序号"],
                     **{k: v for k, v in entry.items() if k != "序号"},
                     "CEFR等级": level, "学术词汇": is_nawl, "高级词汇": is_c1,
                     "综合得分": round(score, 2)})
        simple.append({"序号": i, **{k: v for k, v in entry.items() if k != "序号"}})

    json.dump({"说明": f"{title} - 智能重排（词频×CEFR×学术×高级）",
               "排序算法": "score = log(词频+1)*10 + CEFR难度分 + 学术加分(+30) + 高级加分(+20)",
               "总词数": len(full), "词汇表": full},
              open(f"{prefix}_reranked.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump({title.replace("排序表", "智能排序表")
               if "排序表" in title else title + "智能排序": simple},
              open(f"{prefix}_reranked_simple.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"ok: {prefix}_reranked.json / {prefix}_reranked_simple.json（{len(full)} 词）")
    print("top5:", [e["单词"] for e in full[:5]])

if __name__ == "__main__":
    main()
