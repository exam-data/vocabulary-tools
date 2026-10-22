# 如何生成单词列表文档

前置条件：

- Python 3 + `python-docx`（`pip install python-docx`）
- WPS（用于宏美化）

> 与旧流程的区别：**不再需要 MySQL 数据库**，全部直接从 JSON 数据文件生成。

## 步骤

1. 用 `export_docx.py` 从 JSON 生成初版文档：

   ```bash
   python3 tools/export_docx.py netem_full_list.json -o draft.docx --per-page 18
   ```

   可用 `--columns 序号,单词,释义,分类名称` 选择要导出的列，默认全部字段。

2. ~~将 `tools/macro.js` 放入 WPS 宏并执行~~（**已不需要**：新生成器内建了首行灰底、边框、居中、行高等全部美化，`macro.js` 仅作为旧流程备份保留）。

3. 释义列断行**已自动化**：生成器按固定列宽和字号直接算出一行能放几个汉字并按顿号/分号断行，不再需要人工实测。如需手动控制可加 `--max-length N` 覆盖，或 `--no-break-def` 关闭：

   ```bash
   python3 tools/format_doc_def.py draft.docx -o final.docx --max-length <测得的字数>
   ```

4. 对断行后的文档重新执行一次 `macro.js`。

## 拼写变体（其他拼写列）

`tools/spelling-variations/` 是 Node 包，用于按词典和拼写规律批量填充「其他拼写」：

```bash
cd tools/spelling-variations
npm install
node index.js
```

## SQL 互转

数据真源是 JSON。如需 MySQL 导入文件：

```bash
python3 tools/json_to_sql.py netem_full_list.json
```

旧 SQL 文件还原为 JSON：

```bash
python3 tools/sql_to_json.py netem_full_list.sql
```
