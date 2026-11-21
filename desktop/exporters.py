"""GUI adapters for the repository's command-line export tools."""
from __future__ import annotations
from dataclasses import dataclass
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .data import display, project


@dataclass(frozen=True)
class Layout:
    title: str = '词汇词书'
    rows_per_page: int = 18
    font: str = ''  # Empty delegates to the original tool's 华文中宋 default.
    max_length: int = 0
    break_def: bool = True

    def validate(self):
        if not 1 <= self.rows_per_page <= 100:
            raise ValueError('每页词数须在 1–100 之间。')
        if not 0 <= self.max_length <= 200:
            raise ValueError('释义断行字数须在 0–200 之间，0 表示自动计算。')


def run_tool(name: str, arguments: list[str]):
    from .tool_runner import tools_dir
    if getattr(sys, 'frozen', False):
        command = [sys.executable, '--run-tool', name, *arguments]
    else:
        command = [sys.executable, str(Path(__file__).with_name('tool_runner.py')), name, *arguments]
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
    result = subprocess.run(command, cwd=str(tools_dir().parent), env=env,
                            capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=1200, **options)
    if result.returncode:
        message = (result.stdout + '\n' + result.stderr).strip()
        raise ValueError(message[-6000:] or '导出工具运行失败。')
    return result.stdout


def export_file(path: Path, source_rows: list[dict], fields: list[str], layout: Layout) -> None:
    """Only project data and pass original CLI parameters; atomically save success."""
    path = Path(path).resolve()
    layout.validate()
    rows = project(source_rows, fields)
    suffix = path.suffix.lower()
    if suffix not in {'.docx', '.json', '.csv', '.sql'}:
        raise ValueError('支持 Word、JSON、CSV 和 SQL。')
    if any(',' in field for field in fields) and suffix == '.docx':
        raise ValueError('Word 导出以逗号分隔列名，不能处理字段名本身包含逗号的情况。')
    with tempfile.TemporaryDirectory(dir=path.parent, prefix='.vocabulary-export-') as work:
        work = Path(work)
        # The original SQL converter derives its table name from the input stem.
        source = work / (path.stem + '.json')
        source.write_text(json.dumps({layout.title: rows}, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        target = work / path.name
        if suffix == '.docx':
            args = [str(source), '-o', str(target), '--columns', ','.join(fields),
                    '--per-page', str(layout.rows_per_page)]
            if layout.font:
                args += ['--font', layout.font]
            if layout.max_length:
                args += ['--max-length', str(layout.max_length)]
            if not layout.break_def:
                args += ['--no-break-def']
            run_tool('docx', args)
        elif suffix == '.sql':
            run_tool('sql', [str(source), '-o', str(target)])
        elif suffix == '.json':
            # Source already contains exactly the projected values and order.
            target = source
        else:
            with target.open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows({f: display(row[f]) for f in fields} for row in rows)
        target.replace(path)
