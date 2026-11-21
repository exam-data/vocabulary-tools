# 词表工坊

词表工坊是本仓库的主要使用入口。客户端负责导入 JSON、解析字段、选择和排列导出列、筛选词条，并把数据及参数交给共用的导出脚本。界面样式与文件输出样式相互独立。

启动时为空白导入页，不内置或自动加载词表。数据处理全部在本机完成。

## 使用

1. 点击「导入 JSON」，或拖入一个 JSON 文件。支持直接词条数组和包含词条数组的对象；同一文件有多个词表时在顶部选择。
2. 自动识别所有词条中的字段，默认选择「单词、释义」。自由勾选并拖动排序，也可以选用字段方案。
3. 按需搜索、筛选分类、调整词条顺序或只取前 N 条。默认保持原数据和顺序。
4. 在「排版设置」里调整导出参数；默认值与命令行工具一致。
5. 选择输出类型，点击「生成词表」。

## 导出

| 类型 | 实际调用 | 默认输出和参数 |
|---|---|---|
| Word 表格 | `tools/export_docx.py` | 华文中宋、11pt、灰色表头、黑边框、居中、行高至少 31.18pt、每页 18 词；释义按列宽自动断行 |
| SQL | `tools/json_to_sql.py` | 字段映射、列类型、建表语句、转义和插入语句 |

Word 不新增标题、统计行、页码或字体嵌入，也不替换字体。Word 字体覆盖、每页词数、释义断行字数及关闭断行均直接对应命令行参数。没有覆盖字体时使用默认的华文中宋；实际显示效果与直接运行命令行工具相同，取决于打开文件的编辑器和其可用字体。

列宽按需调整：数字列按最长数字及表头预留单行宽度，并为数字单元格设置不换行。释义使用剩余宽度；空间仍不足时从后面的文本列适当让出宽度。无法容纳时提示减少列数，不压缩数字或缩小字号。客户端和命令行使用同一套列宽逻辑。

JSON / CSV 导出仅用于保存所选列和筛选结果。导出数据不覆盖输入 JSON。数据预览显示前 200 条，实际导出使用全部筛选结果。

## 环境与运行

桌面包包含 Python、Qt 和 python-docx，导出 Word 和 SQL 不需要额外安装 Python。

开发运行：

```bash
uv sync --frozen --extra build
uv run --frozen --extra build python -m desktop.app
```

## 打包

在目标系统构建对应应用：

```bash
uv run --frozen --extra build python -m PyInstaller --noconfirm --clean desktop/VocabularyStudio.spec
```

macOS 输出 `dist/VocabularyStudio.app`；Windows / Linux 输出 `dist/VocabularyStudio/` 整个目录。架构与构建机器一致。

打包配置直接包含仓库的导出脚本，客户端与命令行使用同一套实现。

三系统工作流见 `.github/workflows/desktop.yml`。Windows / Linux 的实际结果以对应构建和测试为准，不能用 macOS 测试代替。

## 一致性验证

```bash
uv sync --frozen --extra build
uv run --frozen --extra build python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen uv run --frozen --extra build python -m desktop.app --self-test build/smoke
```

测试将相同数据和参数分别交给 Word 命令行工具与客户端，逐项比较 DOCX 包内的所有 XML 和资源，覆盖默认参数、列顺序、每页词数及参数覆盖。SQL 则与命令行工具逐字节比较。另外覆盖字段拖动、损坏偏好恢复、重排词表导入、筛选和导出出错后的文件保护。

`--self-test` 使用隔离偏好，检查空白启动、导入、多词表、选列、拖动和后台导出，测试报告列出实际运行的格式。

## 开源组件

沿用仓库程序许可。Qt / PySide6、Python、python-docx 等保留各自许可证，Qt 采用动态库目录式打包。
