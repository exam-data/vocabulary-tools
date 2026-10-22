#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用词书生成器：把 exam-data 任一词汇数据 JSON 排成精美的 PDF 词书。

用法：
    # 智能排序版（连续词条流 + 词典式页眉）：
    python3 make_book.py --input ../../NETEMVocabulary/netem_reranked.json \
        --title 考研词汇智能排序词书 --subtitle "5530 词 · 词频 × CEFR × 学术价值 综合排序"
    # 分类记忆版（117 个语义分类横幅 + 类内按序号）：
    python3 make_book.py --input ../../CETVocabulary/cet_reranked.json --mode category \
        --title 四六级词汇分类记忆词书 --subtitle "5278 词 · 117 个语义分类 · 主题归类记忆"

依赖：
    - xelatex（MacTeX/TeX Live）与 Python 标准库
    - 字体：先跑一次 ./fetch_fonts.sh 下载思源宋体到 fonts/；英文用 Georgia（系统自带）；
      标题用 HarmonyOS Sans SC Black（无则回退系统黑体，见 --title-font 参数）

数据字段（全部可选，缺什么就不显示什么）：
    序号 单词 释义 词频 分类名称 CEFR等级 学术词汇 高级词汇 真题次数 例句 例句翻译 例句来源
"""
import argparse, json, os, subprocess, sys
from collections import Counter

BOOK_DIR = os.path.dirname(os.path.abspath(__file__))

def esc(s):
    return (str(s).replace("\\", r"\textbackslash{}").replace("&", r"\&")
             .replace("%", r"\%").replace("#", r"\#").replace("_", r"\_")
             .replace("$", r"\$").replace("^", r"\textasciicircum{}")
             .replace("~", r"\textasciitilde{}"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="词汇数据 JSON")
    ap.add_argument("--mode", choices=["rank", "category"], default="rank",
                    help="rank=连续排序流（默认）；category=按语义分类分节")
    ap.add_argument("--sort", choices=["rank", "score"], default="rank",
                    help="rank=按数据序号（默认）；score=按综合得分降序（学习优先级）")
    ap.add_argument("--title", default="词汇词书")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("-o", "--output", help="输出 PDF 路径（默认 Desktop/<标题>.pdf）")
    ap.add_argument("--fonts-dir", default=f"{BOOK_DIR}/fonts", help="思源宋体所在目录")
    args = ap.parse_args()

    data = json.load(open(args.input, encoding="utf-8"))
    rows = None
    for v in data.values():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            rows = v
            break
    if rows is None:
        sys.exit("JSON 顶层没有找到词条列表")

    has = lambda f: f in rows[0]
    has_exam, has_sent, has_cat = has("真题次数"), has("例句"), has("分类名称")

    entries = []
    for r in rows:
        entries.append({
            "rank": r.get("序号", 0), "word": r["单词"], "mean": r["释义"],
            "cefr": r.get("CEFR等级") or "", "nawl": r.get("学术词汇"), "c1c2": r.get("高级词汇"),
            "freq": r.get("词频"), "exam": r.get("真题次数", 0) or 0,
            "score": r.get("综合得分"),
            "en": r.get("例句") or "", "cn": r.get("例句翻译") or "", "src": r.get("例句来源") or "",
            "cat": r.get("分类名称") or "",
        })
    if args.sort == "score" and any(e.get("score") is not None for e in entries):
        entries.sort(key=lambda e: -(e["score"] or 0))
    else:
        entries.sort(key=lambda e: e["rank"])
    for i, e in enumerate(entries, 1):
        e["disp"] = i

    def meta(e):
        CEFR_TEXT = {"A1": "cefraone", "A2": "cefratwo", "B1": "cefrbone",
                     "B2": "cefrbtwo", "C1": "cefrcone", "C2": "cefrctwo"}
        parts = []
        if e["cefr"]:
            parts.append((e["cefr"], CEFR_TEXT.get(e["cefr"], "metagray")))
        if e["nawl"]:
            parts.append(("学术词汇", "navy"))
        if e["c1c2"]:
            parts.append(("高级词汇", "hipurple"))
        if has_exam and e["exam"]:
            parts.append((f"真题 {e['exam']} 次", "examred"))
        if e["freq"] is not None:
            parts.append((f"词频 {e['freq']}", "metagray"))
        items = []
        for txt, color in parts[:-1]:
            items.append(rf"\mbox{{\textcolor{{{color}}}{{{txt}}}\textcolor{{metagray}}{{ ·}}}}")
        if parts:
            txt, color = parts[-1]
            items.append(rf"\mbox{{\textcolor{{{color}}}{{{txt}}}}}")
        return " ".join(items)

    # 分类顺序
    cat_order = {}
    cat_day = {}
    cats_file = f"{BOOK_DIR}/categories.json"
    if os.path.exists(cats_file):
        for c in json.load(open(cats_file, encoding="utf-8")):
            cat_order[c["name"]] = c["id"]
            if c.get("day"):
                cat_day[c["name"]] = c["day"]

    parts = []
    if args.mode == "category":
        groups = {}
        for e in entries:
            groups.setdefault(e["cat"], []).append(e)
        ordered = sorted(groups, key=lambda c: (c not in cat_order, cat_order.get(c, 999), c))
        parts.append(r"\begin{multicols}{2}")
        for c in ordered:
            es = groups[c]
            name = c if c else "未分类"
            day = cat_day.get(c, "")
            parts.append(rf"\catsec{{{esc(name)}}}{{{len(es)}}}{{{esc(day)}}}")
            for e in es:
                parts.append(rf"\entry{{{e['disp']}}}{{{esc(e['word'])}}}{{{esc(e['mean'])}}}{{{meta(e)}}}{{{esc(e['en'])}}}{{{esc(e['cn'])}}}{{{esc(e['src'])}}}")
        parts.append(r"\end{multicols}")
    else:
        parts.append(r"\begin{multicols}{2}")
        for e in entries:
            parts.append(rf"\entry{{{e['disp']}}}{{{esc(e['word'])}}}{{{esc(e['mean'])}}}{{{meta(e)}}}{{{esc(e['en'])}}}{{{esc(e['cn'])}}}{{{esc(e['src'])}}}")
        parts.append(r"\end{multicols}")
    body = "\n".join(parts)

    n_cat = len(set(e["cat"] for e in entries if e["cat"]))
    n_sent = sum(1 for e in entries if e["en"])
    n_exam = sum(1 for e in entries if e["exam"] > 0)
    stats_rows = [f"收录词汇 & {len(entries)} 个"]
    if n_cat:
        stats_rows.append(f"语义分类 & {n_cat} 个")
    if n_sent:
        stats_rows.append(f"带例句 & {n_sent} 个")
    if n_exam:
        stats_rows.append(f"真题实考词（2005–2023） & {n_exam} 个")
    stats = " \\\\\n".join(stats_rows)   # 行间 LaTeX 换行符 \\

    fonts_ok = os.path.exists(f"{args.fonts_dir}/NotoSerifSC-Regular.ttf")
    if not fonts_ok:
        print("警告：fonts/ 下没有思源宋体，先跑 ./fetch_fonts.sh；本次尝试按系统已安装字体编译")

    cjk_setup = (
        rf"\setCJKmainfont[Path={args.fonts_dir}/, UprightFont={{NotoSerifSC-Regular.ttf}}, BoldFont={{NotoSerifSC-SemiBold.ttf}}]{{NotoSerifSC}}"
        if fonts_ok else
        r"\setCJKmainfont[BoldFont={NotoSerifSC-SemiBold}]{Noto Serif SC}"
    )

    TPL = r"""% !TEX program = xelatex
\documentclass[10pt,a4paper]{ctexart}
\usepackage[top=20mm,bottom=18mm,left=15mm,right=15mm,columnsep=7mm]{geometry}
\usepackage{multicol}
\usepackage{xcolor}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage{amssymb}
\usepackage{etoolbox}
\usepackage{needspace}
\usepackage[bookmarks=false,hidelinks]{hyperref}

% ---------- 字体 ----------
\setmainfont{Georgia}[Numbers=Lining]
\setsansfont{Helvetica Neue}
__CJK_SETUP__
\newCJKfontfamily\titlecjk{HarmonyOS Sans SC Black}
\newfontfamily\metafont{HarmonyOS Sans SC}
\linespread{1.12}
\setlength{\emergencystretch}{1.5em}

% ---------- 配色 ----------
\definecolor{navy}{RGB}{25,42,86}
\definecolor{lightnavy}{RGB}{90,110,160}
\definecolor{metagray}{RGB}{150,155,165}
\definecolor{examred}{RGB}{176,58,46}
\definecolor{cefraone}{RGB}{138,143,152}
\definecolor{cefratwo}{RGB}{86,156,205}
\definecolor{cefrbone}{RGB}{46,134,193}
\definecolor{cefrbtwo}{RGB}{30,132,73}
\definecolor{cefrcone}{RGB}{211,84,0}
\definecolor{cefrctwo}{RGB}{192,57,43}
\definecolor{hipurple}{RGB}{125,60,152}
\definecolor{rulegray}{RGB}{220,223,228}
\definecolor{darkink}{RGB}{45,50,60}
\definecolor{metadark}{RGB}{104,110,120}

% ---------- 页眉页脚（词典式：左=本页首词，右=本页末词） ----------
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0.3pt}
\renewcommand{\headrule}{\color{rulegray}\hrule width\headwidth height\headrulewidth}
\fancyhead[L]{\footnotesize\color{metagray}\rightmark}
\fancyhead[R]{\footnotesize\color{metagray}\leftmark}
\fancyfoot[C]{\footnotesize\color{metagray}\thepage}

% ---------- 组件 ----------
\newcommand{\entry}[7]{%
  \par\vspace{1.5pt}\noindent\begin{minipage}{\linewidth}
  {\hangindent=1.6em
  {\footnotesize\color{lightnavy}\sffamily #1}\hspace{0.45em}%
  {\large\bfseries #2}\hspace{0.6em}{\color{darkink}#3}\hspace{0.6em}{\scriptsize\metafont #4}\par}%
  \ifstrempty{#5}{}{\par\vspace{1.5pt}{\leftskip=1.6em\small\itshape #5\hspace{0.6em}{\tiny\metafont\color{metagray}\mbox{#7}}\par}}%
  \ifstrempty{#6}{}{{\leftskip=1.6em\small\color{metadark}#6\par}}%
  \par\vspace{2.5pt}{\color{rulegray}\rule{\linewidth}{0.3pt}}%
  \end{minipage}\markboth{#2}{#2}\par\vspace{2.2pt}}
\newcommand{\catsec}[3]{%
  \par\needspace{7\baselineskip}\vspace{7pt}%
  \noindent{\color{navy}\rule[-2.5pt]{2.5pt}{13pt}\hspace{5pt}%
  {\large\titlecjk\color{navy}#1}\hfill
  {\scriptsize\metafont\color{metagray}#2 词\ifstrempty{#3}{}{ · #3}}}%
  \par\vspace{1.5pt}\noindent{\color{navy!35}\rule{\linewidth}{0.6pt}}\vspace{3.5pt}}

\titleformat{\section}{\LARGE\titlecjk\color{navy}}{}{0pt}{}
\titlespacing*{\section}{0pt}{0pt}{10pt}
\setlength{\columnseprule}{0.2pt}
\renewcommand{\columnseprulecolor}{\color{rulegray}}
\setlength{\parindent}{0pt}

\begin{document}

\begin{titlepage}
\pagecolor{navy}\color{white}
\vspace*{38mm}
\begin{center}
{\fontsize{34}{44}\selectfont\titlecjk\ziju{0.14}__TITLE__\par}
\vspace{6mm}
{\color{rulegray}\rule{0.55\textwidth}{0.6pt}\par}
\vspace{8mm}
{\Large __SUBTITLE__\par}
\vspace{16mm}
{\normalsize
\begin{tabular}{r@{\hspace{1em}}l}
__STATS__
\end{tabular}\par}
\vfill
{\small 数据：github.com/exam-data · \today\par}
\end{center}
\end{titlepage}
\pagecolor{white}\color{black}

\thispagestyle{fancy}
\section*{使用说明}
\vspace{2mm}
{\small
\textbf{词条格式}\quad 卡片式结构：加粗单词＋释义（紧跟其后）$\to$ 英文例句（斜体，行尾小字为来源）$\to$ 例句中文。
单词行尾的小字为元信息标记：CEFR 等级、学术词汇 / 高级词汇字样、真题 N 次（真题词表中出现次数）、词频 N，
不同类别以颜色区分。

\vspace{3mm}
\textbf{来源标注}\quad 例句行尾的灰色小字为出处：「真题 2005·T1」表示 2005 年真题阅读 Text 1；
「DeepSeek」表示 AI 生成短句；其余为语料库名称。

\vspace{3mm}
\textbf{生成方式}\quad 本书由 exam-data/vocabulary-tools 仓库的 tools/book/make\_book.py 自动排版生成。
}
\clearpage

__BODY__

\end{document}
"""
    tex = (TPL.replace("__BODY__", body)
              .replace("__CJK_SETUP__", cjk_setup)
              .replace("__TITLE__", esc(args.title))
              .replace("__SUBTITLE__", esc(args.subtitle))
              .replace("__STATS__", stats))

    work = "/tmp/book_generic"
    os.makedirs(work, exist_ok=True)
    open(f"{work}/book.tex", "w", encoding="utf-8").write(tex)

    for i in range(2):
        p = subprocess.run(["/Library/TeX/texbin/xelatex", "-interaction=nonstopmode", "book.tex"],
                           cwd=work, capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            print("\n".join((p.stdout + p.stderr).splitlines()[-20:]))
            sys.exit(1)
    out = args.output or os.path.expanduser(f"~/Desktop/{args.title}.pdf")
    subprocess.run(["cp", f"{work}/book.pdf", out], check=True)
    print(f"PDF -> {out} ({os.path.getsize(out)} bytes, {len(entries)} 词, 模式 {args.mode})")

if __name__ == "__main__":
    main()
