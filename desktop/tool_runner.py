"""Run an allowlisted original CLI inside its own Python process."""
from pathlib import Path
import runpy
import sys

TOOLS = {'docx': 'export_docx.py', 'sql': 'json_to_sql.py'}


def tools_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'tools'
    source = Path(__file__).resolve().parent.parent / 'tools'
    return source if source.is_dir() else Path(sys.prefix) / 'share/vocabulary-studio/tools'


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in TOOLS:
        raise SystemExit('Unknown original tool')
    path = tools_dir() / TOOLS[sys.argv[1]]
    sys.argv = [str(path), *sys.argv[2:]]
    runpy.run_path(str(path), run_name='__main__')


if __name__ == '__main__':
    main()
