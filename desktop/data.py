"""JSON parsing and transformations, independent of the desktop interface."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

PRESETS = {
    "背诵词表": ["单词", "释义"],
    "词频学习": ["序号", "词频", "单词", "释义"],
    "例句学习": ["单词", "释义", "例句", "例句翻译"],
    "分类记忆": ["单词", "释义", "分类名称"],
    "全部字段": None,
}
# Common English field names are recognized without changing imported data.
ALIASES = {
    "单词": ["word", "headword", "lemma", "vocabulary"],
    "释义": ["definition", "meaning", "translation", "释意", "中文释义"],
    "序号": ["id", "rank", "index"],
    "词频": ["frequency", "freq"],
    "例句": ["sentence", "example"],
    "例句翻译": ["sentence_cn", "example_translation"],
    "分类名称": ["category", "分类"],
}


@dataclass
class Dataset:
    name: str
    rows: list[dict]

    @property
    def fields(self) -> list[str]:
        # A union across every row: optional fields need not appear in row one.
        return list(dict.fromkeys(k for row in self.rows for k in row))


def parse_json(content: str, name: str = "词表") -> list[Dataset]:
    try:
        def invalid_constant(value):
            raise ValueError(f"JSON 不能包含 {value}，请使用 null 或有限数字。")
        data = json.loads(content.lstrip("\ufeff"), parse_constant=invalid_constant)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 格式错误：第 {exc.lineno} 行，第 {exc.colno} 列。{exc.msg}") from exc
    candidates = [(name, data)] if isinstance(data, list) else (
        [(key, value) for key, value in data.items() if isinstance(value, list)]
        if isinstance(data, dict) else []
    )
    tables = []
    for title, rows in candidates:
        if not rows:
            continue
        # Skip metadata string arrays but reject mixed record arrays.
        if not any(isinstance(row, dict) for row in rows):
            continue
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError(f"「{title}」中的词条必须都是对象，不能混入字符串或数字。")
        if not any(rows):
            continue
        if any(not isinstance(key, str) or not key for row in rows for key in row):
            raise ValueError("字段名必须是非空字符串。")
        tables.append(Dataset(str(title), rows))
    if not tables:
        raise ValueError('未找到词条。支持 [{"单词": "word", "释义": "词"}] 或 {"词汇表": [...]}。')
    return tables


def load_json(path: Path) -> list[Dataset]:
    try:
        return parse_json(path.read_text(encoding="utf-8-sig"), path.stem)
    except UnicodeDecodeError as exc:
        raise ValueError("文件不是 UTF-8 编码，请将 JSON 另存为 UTF-8 后重试。") from exc


def find_field(fields: list[str], canonical: str) -> str | None:
    if canonical in fields:
        return canonical
    lookup = {field.casefold(): field for field in fields}
    return next((lookup[alias.casefold()] for alias in ALIASES.get(canonical, []) if alias.casefold() in lookup), None)


def recommended_fields(fields: list[str], preset: str = "背诵词表") -> list[str]:
    wanted = PRESETS[preset]
    if wanted is None:
        return fields[:]
    selected = list(dict.fromkeys(f for key in wanted if (f := find_field(fields, key))))
    return selected or fields[:min(2, len(fields))]


def column_state(fields: list[str], preset: str, saved=None) -> tuple[list[str], list[str]]:
    """Restore preferences while ensuring every imported field stays available."""
    defaults = recommended_fields(fields, preset)
    if not isinstance(saved, dict) or not all(isinstance(saved.get(k), list) for k in ('order', 'selected')):
        return defaults + [f for f in fields if f not in defaults], defaults
    order = list(dict.fromkeys(f for f in saved['order'] if isinstance(f, str) and f in fields))
    selected = [f for f in order if f in saved['selected']]
    for field in fields:
        if field in order:
            continue
        # An older drag operation could remove a field from the widget itself.
        # Recover missing default fields beside their related default columns.
        following = next((f for f in defaults[defaults.index(field)+1:] if f in order), None) if field in defaults else None
        order.insert(order.index(following) if following else len(order), field)
        if field in defaults:
            selected.append(field)
    return order, [f for f in order if f in selected]


def display(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def select_rows(dataset: Dataset, search: str = "", category: str = "", sort: str = "原始顺序",
                limit: int = 0, renumber: bool = False) -> list[dict]:
    fields = dataset.fields
    query = search.strip().casefold()
    category_field = find_field(fields, "分类名称")
    rows = [row for row in dataset.rows
            if (not query or any(query in display(v).casefold() for v in row.values()))
            and (not category or (category_field and display(row.get(category_field)) == category))]
    if sort == "单词字母顺序":
        field = find_field(fields, "单词")
        if field:
            rows.sort(key=lambda r: display(r.get(field)).casefold())
    elif sort == "词频从高到低":
        field = find_field(fields, "词频")
        if field:
            def numeric(row):
                try:
                    value = float(row.get(field) or 0)
                    return value if value == value else 0
                except (TypeError, ValueError):
                    return 0
            rows.sort(key=numeric, reverse=True)
    if limit:
        rows = rows[:limit]
    id_field = find_field(fields, "序号")
    if renumber and id_field:
        rows = [{**row, id_field: i} for i, row in enumerate(rows, 1)]
    return rows


def project(rows: list[dict], fields: list[str]) -> list[dict]:
    if not rows:
        raise ValueError("当前筛选没有词条，请调整筛选条件。")
    if not fields:
        raise ValueError("请至少选择一个导出列。")
    return [{field: row.get(field) for field in fields} for row in rows]
