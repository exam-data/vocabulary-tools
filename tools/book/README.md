# 词书生成模板

把 exam-data 任一词汇数据 JSON 排成精美的 A4 双栏 PDF 词书。两种模式：

| 模式 | 效果 |
|---|---|
| `rank`（默认） | 按序号连续的词条流，词典式页眉（本页首词…末词） |
| `category` | 按 117 个语义分类分节（分类横幅 + 词数 + 建议背诵日），类内按序号 |

## 用法

```bash
# 0. 准备字体（只需一次）：下载思源宋体到 fonts/
./fetch_fonts.sh

# 1. 智能排序版（输入用重排后的数据，词条顺序即学习优先级）
python3 make_book.py --input ../../../NETEMVocabulary/netem_reranked.json \
    --title 考研词汇智能排序词书 --subtitle "5530 词 · 词频 × CEFR × 学术价值 综合排序"

# 2. 分类记忆版
python3 make_book.py --input ../../../CETVocabulary/cet_reranked.json --mode category \
    --title 四六级词汇分类记忆词书 --subtitle "5278 词 · 117 个语义分类 · 主题归类记忆"
```

输出默认到 `~/Desktop/<标题>.pdf`，可用 `-o` 指定。

## 依赖

- `xelatex`（MacTeX / TeX Live 全套）
- Python 3 标准库（无第三方依赖）
- 字体：思源宋体（`fetch_fonts.sh` 下载，OFL 协议）；英文用 Georgia（macOS 自带）；
  标题用 HarmonyOS Sans SC Black（无则会编译报错，把 `make_book.py` 里 `\titlecjk` 换成系统黑体即可）

## 词条卡片

加粗单词 → 释义（紧随其后）→ 元信息（CEFR 按等级分色 / 学术词汇 / 高级词汇 / 真题 N 次 / 词频 N）
→ 斜体例句＋来源小字 → 例句中文。词条块不跨栏，来源标注随句。

数据字段全部是可选的：数据里有什么就显示什么，没有就不显示。

`categories.json` 为 117 个语义分类的顺序与建议背诵日（category 模式使用）。
