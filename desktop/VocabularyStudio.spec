# Build on each target OS; Python and Qt are bundled.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent
datas = [(str(root / 'desktop' / 'assets' / 'licenses'), 'licenses')]
datas += [(str(root / 'desktop' / 'assets' / 'ui'), 'ui')]
datas += [(str(root / 'tools' / 'export_docx.py'), 'tools'),
          (str(root / 'tools' / 'json_to_sql.py'), 'tools')]
for package in ['PySide6-Essentials', 'shiboken6', 'python-docx', 'lxml']:
    datas += copy_metadata(package)
# python-docx uses paths containing "parts/../templates"; preserving the
# source directory as well as its XML templates makes those paths resolvable.
datas += collect_data_files('docx', include_py_files=True)
a = Analysis(
    [str(root / 'desktop' / 'launch.py')],
    pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=['desktop.selftest', 'docx'],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'tkinter', 'matplotlib', 'numpy'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='VocabularyStudio',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=str(root / 'desktop' / 'assets' / 'ui' / 'app-icon.ico') if sys.platform=='win32' else None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='VocabularyStudio')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='VocabularyStudio.app', icon=str(root / 'desktop' / 'assets' / 'ui' / 'app-icon.icns'),
                 bundle_identifier='org.examdata.vocabularystudio',
                 info_plist={'NSHighResolutionCapable': True, 'CFBundleDisplayName': '词表工坊',
                             'CFBundleShortVersionString': '0.2.2'})
