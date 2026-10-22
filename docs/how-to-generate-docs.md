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

2. 将 `tools/macro.js` 放入 WPS 宏并执行，对初版文档进行美化（首行底色、边框、跨页表头等）。

3. 如需释义列按宽度断行：先测试单元格单行可容纳的最大汉字数，然后：

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
