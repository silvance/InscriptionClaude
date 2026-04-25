# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CaseGuide.

Invoke from the caseguide/ directory:

    pyinstaller packaging/caseguide.spec --noconfirm

Output is written to ``dist/CaseGuide/``. Copy that folder to the
target workstation and run ``CaseGuide.exe`` directly.
"""

from pathlib import Path

ROOT = Path.cwd()
SRC = ROOT / "src"
ENTRY = SRC / "caseguide" / "__main__.py"

HIDDEN_IMPORTS = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

a = Analysis(
    [str(ENTRY)],
    pathex=[str(SRC)],
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
    name="CaseGuide",
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
    name="CaseGuide",
)
