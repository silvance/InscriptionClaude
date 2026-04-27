# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CaseGuide.

Invoke from the caseguide/ directory, or use the repo-root build.ps1:

    cd caseguide
    pyinstaller packaging\\caseguide.spec --noconfirm

Output lands in dist\\CaseGuide\\. Copy that folder to the target
workstation and run CaseGuide.exe.
"""

from pathlib import Path

SPEC_DIR     = Path(__file__).resolve().parent
ROOT         = SPEC_DIR.parent
SRC          = ROOT / "src"
ENTRY        = SRC / "caseguide" / "__main__.py"
PLAYBOOK_DIR = SRC / "caseguide" / "playbook_data"
COMMON_SRC   = ROOT.parent / "suite_common" / "src"

HIDDEN_IMPORTS = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

a = Analysis(
    [str(ENTRY)],
    pathex=[str(SRC), str(COMMON_SRC)],
    binaries=[],
    datas=[
        # Built-in forensic playbooks. paths.py resolves them via
        # Path(__file__).parent / "playbook_data", which lands in
        # the caseguide/ sub-directory inside the bundle's _internal/.
        (str(PLAYBOOK_DIR), "caseguide/playbook_data"),
    ],
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
