# 词表工坊 · vocabulary-tools

词表工坊是 exam-data 的桌面客户端：导入词表 JSON，预览、搜索、筛选和自由选列，生成 Word 表格或 SQL，也可保存 JSON / CSV。数据处理在本机完成，启动时不自动加载词表。

词表数据独立存放在 [NETEMVocabulary](https://github.com/exam-data/NETEMVocabulary)（考研 5530 词）和 [CETVocabulary](https://github.com/exam-data/CETVocabulary)（四六级 5278 词）。

## 启动客户端

源码运行需要 Python 3.10 及以上版本和 [uv](https://docs.astral.sh/uv/)：

```bash
git clone https://github.com/exam-data/vocabulary-tools.git
cd vocabulary-tools
uv sync --frozen
uv run --frozen vocabulary-studio
```

1. 导入自己的 JSON 文件；同一文件包含多个词表时可切换。
2. 搜索或筛选词条，勾选并拖动排列需要的列。
3. 设置每页词数、字体等参数，选择输出格式并生成文件。

Word 表格内建表格样式和释义自动断行。

完整功能、平台依赖和打包方式见 [客户端说明](desktop/README.md)。客户端构建工作流见 [GitHub Actions](https://github.com/exam-data/vocabulary-tools/actions/workflows/desktop.yml)，成功构建的运行可在 Artifacts 下载对应平台的应用包。

## 仓库目录

| 目录 | 内容 |
| --- | --- |
| [desktop/](desktop/) | 客户端界面、数据预览、导出与打包配置 |
| [tools/](tools/) | 导出、格式转换、数据校验、智能重排与拼写变体工具 |
| [docs/](docs/) | 各工具使用说明 |
| [tests/](tests/) | 数据解析、导出和交互测试 |

## 命令行工具

JSON 是数据源，可直接调用客户端共用的脚本：

| 工具 | 用途 | 用法 |
| --- | --- | --- |
| `tools/export_docx.py` | JSON → Word 表格，自动排版及释义断行 | `python3 tools/export_docx.py words.json -o out.docx` |
| `tools/json_to_sql.py` | JSON → MySQL 导入文件 | `python3 tools/json_to_sql.py words.json -o out.sql` |
| `tools/sql_to_json.py` | SQL → JSON | `python3 tools/sql_to_json.py words.sql -o out.json` |
| `tools/check_netem.py` | 校验 NETEM 各版本 JSON / SQL 的词数、序号与字段同步 | [使用说明](docs/how-to-generate-docs.md#数据校验) |
| `tools/check_cet.py` | 校验 CET 四版本、SQL 全字段与超课标重排，可核对 NETEM 同词同步 | `python3 tools/check_cet.py ../CETVocabulary --netem ../NETEMVocabulary` |
| `tools/rerank/` | 综合词频、CEFR、学术及高级词汇智能重排 | [使用说明](docs/how-to-generate-docs.md#智能重排) |
| `tools/spelling-variations/` | 拼写变体词典、规则与数据库批处理入口 | [使用说明](docs/how-to-generate-docs.md#拼写变体) |

各工具的参数见 [使用说明](docs/how-to-generate-docs.md)。

## 许可

数据基于 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)，程序基于 MIT License。客户端所用开源组件及字体许可见 [客户端说明](desktop/README.md#开源组件)。
