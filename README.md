# vocabulary-tools

exam-data 词汇数据的**统一工具箱与可视化入口**。数据本身存放在数据仓库（[NETEMVocabulary](https://github.com/exam-data/NETEMVocabulary) 考研 5530 词、[CETVocabulary](https://github.com/exam-data/CETVocabulary) 四六级 5278 词），本仓库提供：

- **`index.html`（数据浏览）**：纯静态词汇数据浏览器——搜索、分类筛选、词频/字母排序、六级星标过滤，打开网页即用，**不需要任何本地环境**。数据实时取自两个数据仓的 master 分支。
- **`tools.html`（工具网页版）**：生成 Word 单词文档、JSON⇄SQL 互转，**全部在浏览器本地完成**，无需 Python；可直接载入线上数据，免去上传。
- **`tools/`**：命令行工具。JSON 是唯一数据真源，SQL 由 JSON 生成，**不再需要 MySQL**。
- **`docs/`**：流程文档。

## 可视化浏览器

本仓库开启 GitHub Pages 后即可在线访问（Settings → Pages → Source 选 `master` 根目录）：

```
https://exam-data.github.io/vocabulary-tools/
```

本地预览也可以直接双击 `index.html`，或：

```bash
python3 -m http.server 8000   # 然后访问 http://localhost:8000
```

## 工具一览

| 工具 | 用途 | 用法 |
|---|---|---|
| `tools/export_docx.py` | JSON → Word 初版（每页一表） | `python3 tools/export_docx.py netem_full_list.json -o out.docx` |
| `tools/macro.js` | WPS 宏：美化 Word 表格（**旧流程遗留**；新生成器已内建美化，无需再用） | 在 WPS 宏编辑器中执行 |
| `tools/format_doc_def.py` | Word 释义列按宽度断行 | `python3 tools/format_doc_def.py in.docx -o out.docx --max-length 20` |
| `tools/json_to_sql.py` | JSON → MySQL 导入文件 | `python3 tools/json_to_sql.py netem_full_list.json` |
| `tools/sql_to_json.py` | SQL → JSON（兼容旧数据） | `python3 tools/sql_to_json.py netem_full_list.sql` |
| `tools/spelling-variations/` | Node 包：填充「其他拼写」 | 见 `docs/how-to-generate-docs.md` |
| `tools/rerank/` | 通用智能重排器（词频×CEFR×学术×高级） | `python3 tools/rerank/rerank_vocab.py <词汇.json>` |
| `tools/book/` | 词书 PDF 模板（rank/category 双模式，xelatex） | 见 `tools/book/README.md` |

## 生成单词文档的完整流程

```bash
pip install python-docx          # 唯一依赖
python3 tools/export_docx.py netem_full_list.json -o draft.docx   # 美化+释义断行已内建，打开即成品
# （可选）python3 tools/format_doc_def.py draft.docx -o final.docx --max-length 20
```

也可以直接用网页版 [tools.html](https://exam-data.github.io/vocabulary-tools/tools.html)，浏览器里点一下就导出美化好的 Word。

详见 [docs/how-to-generate-docs.md](docs/how-to-generate-docs.md)。

## 许可

数据基于 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)，程序基于 MIT License。
