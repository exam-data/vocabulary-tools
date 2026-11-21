"""Resource paths work in both a checkout and a PyInstaller application."""
from pathlib import Path
import sys


def ui_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'ui'
    source = Path(__file__).resolve().parent / 'assets' / 'ui'
    return source if source.is_dir() else Path(sys.prefix) / 'share' / 'vocabulary-studio' / 'ui'
