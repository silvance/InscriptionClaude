# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CaseForge.

Invoke from the caseforge/ directory, or use the repo-root build.ps1:

    cd caseforge
    pyinstaller packaging\\caseforge.spec --noconfirm

Output lands in dist\\CaseForge\\. Copy that folder to the target
workstation and run CaseForge.exe.
"""

from pathlib import Path

SPEC_DIR    = Path(__file__).resolve().parent
ROOT        = SPEC_DIR.parent
SRC         = ROOT / "src"
ENTRY       = SRC / "caseforge" / "__main__.py"
COMMON_SRC  = ROOT.parent / "suite_common" / "src"

HIDDEN_IMPORTS = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    # Optional report dependencies — bundled so the report export
    # menu works without a separate pip install.
    "docxtpl",
    "docx",
    "jinja2",
    "jinja2.ext",
    "lxml",
    "lxml.etree",
]

a = Analysis(
    [str(ENTRY)],
    pathex=[str(SRC), str(COMMON_SRC)],
    binaries=[],
    datas=[],
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "test"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CaseForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CaseForge",
)
