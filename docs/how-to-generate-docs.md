# 使用说明

## Word 表格

在工具仓库根目录安装依赖，直接从 JSON 导出：

```bash
python3 -m pip install 'python-docx>=1.1,<2'
python3 tools/export_docx.py ../NETEMVocabulary/netem_full_list.json -o out.docx
```

默认导出「序号、词频、单词、释义」，每页 18 词，采用 A4 竖版、灰色表头、黑边框、居中和固定字号。释义按列宽自动断行，导出后即可使用。

可通过参数调整列、每页词数、字体及断行：

```bash
python3 tools/export_docx.py ../NETEMVocabulary/netem_full_list.json \
  -o out.docx --columns 单词,释义 --per-page 18

# 按需覆盖释义单行字数；--no-break-def 可关闭自动断行。
python3 tools/export_docx.py ../NETEMVocabulary/netem_full_list.json \
  -o out.docx --max-length 12
```

推荐使用 [词表工坊客户端](../desktop/README.md) 导入 JSON、预览、选列并导出。源码启动命令见 [仓库首页](../README.md#启动客户端)。

## 数据校验

`tools/check_netem.py` 检查 NETEMVocabulary 中 `data/catalog.json` 登记的 6 份词表，只依赖 Python 标准库：

```bash
python3 tools/check_netem.py ../NETEMVocabulary
```

检查文件、JSON 词数与序号、单词唯一性、英式音标格式、SQL 表名与导入行数，并核对重排版的词条集合与顺序、子集的 `原序号`，以及音标、例句、翻译、出处在各版本间是否一致。修改词表后运行；省略参数时检查同级的 `NETEMVocabulary/`。

CET 提供完整词表和超课标词表，各含词频版与重排版，共四份；没有核心词汇版。目录和清单与 NETEM 采用相同约定，SQL 位于 `data/sql/`：

```bash
python3 tools/check_cet.py ../CETVocabulary
python3 tools/check_cet.py ../CETVocabulary --netem ../NETEMVocabulary
```

CET 校验还会回读全部 SQL 字段，比较原序号、六级标记和所有学习字段，并核对超课标重排顺序。`--netem` 比较两个主表的完全同词释义、音标和例句等公共字段。

## 智能重排

`tools/rerank/rerank_vocab.py` 综合词频、CEFR 难度、学术词汇（NAWL）和高级词汇（C1/C2）重新排序，只依赖 Python 标准库，参考词表在 `tools/rerank/refdata/`：

```bash
python3 tools/rerank/rerank_vocab.py ../NETEMVocabulary/netem_full_list.json
python3 tools/rerank/rerank_vocab.py words.json -o out_prefix
```

在输入文件同目录生成 `<前缀>_reranked.json`：保留原有全部字段，`序号` 改为新排名，并附加 `原序号`、`CEFR等级`、`学术词汇`、`高级词汇`、`综合得分`。

评分为 `ln(词频+1) × 10 + CEFR 难度分 + 学术词汇加分（+30）+ 高级词汇加分（+20）`；词频为 0 时词频分记 5，词频超过 1000 的 NGSL 基础词减 5 分。CEFR 难度分为 A1 0、A2 5、B1 15、B2 25、C1 40、C2 50，未收录记 20。权重在脚本的 `CONFIG` 中调整。

## 拼写变体

`tools/spelling-variations/` 保留拼写变体词典、规则和 Node.js 批处理入口。可在其他程序中导入 `lib/index.js` 使用词典与规则；`index.js` 是 MySQL 数据库批处理入口，需自行准备 `tools/custom_config/js-config.js` 中的数据库连接配置，并核对脚本中的目标表名。

```bash
cd tools/spelling-variations
npm ci
node index.js
```

这部分用于填充「其他拼写」，Word 导出直接读取词表中的现有字段。

## SQL 互转

JSON 是数据源；生成 MySQL 导入文件时，显式指定输出路径：

```bash
python3 tools/json_to_sql.py ../NETEMVocabulary/netem_full_list.json \
  -o ../NETEMVocabulary/data/sql/netem_full_list.sql
```

SQL 文件也可以还原为 JSON：

```bash
python3 tools/sql_to_json.py ../NETEMVocabulary/data/sql/netem_full_list.sql \
  -o restored.json
```

NETEM 的各版本路径、JSON 列表键和 SQL 表名见 [数据清单](https://github.com/exam-data/NETEMVocabulary/blob/master/data/catalog.json)。NETEM 的文件名与 SQL 表名统一使用下划线，重排结果使用 `_reranked` 后缀；转换器按输入文件名生成表名。

CET 同样通过 [数据清单](https://github.com/exam-data/CETVocabulary/blob/master/data/catalog.json) 读取四版本。超课标重排文件为 `cet_beyond_ks3000_reranked.json`；原 `cet_reranked_simple` 重复兼容格式已移除。各 SQL 已迁到 `data/sql/`，文件前缀和表名保持一致。
