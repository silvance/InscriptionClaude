# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Inscription.

Invoke from the repository root:

    pyinstaller packaging/inscription.spec --noconfirm

Output is written to ``dist/Inscription/``. Copy that folder to the target
workstation and run ``Inscription.exe`` directly. One-folder mode is used in
Phase 0 because it starts faster and is easier to diagnose than one-file; a
proper installer wrapper comes in Phase 5.
"""

from pathlib import Path

ROOT = Path.cwd()
SRC = ROOT / "src"
ENTRY = SRC / "inscription" / "__main__.py"

# Hidden imports — modules that PyInstaller's static analysis can miss
# because they're loaded indirectly. Listing them defensively keeps the
# build robust across PyInstaller versions.
HIDDEN_IMPORTS = [
    # PySide6 sub-modules used directly. The PySide6 hook usually picks
    # them up but listing keeps us safe across PyInstaller upgrades.
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    # Capture stack — pynput dispatches per-OS backends at import time;
    # comtypes underpins pywinauto's UIA bridge on Windows.
    "pynput.mouse",
    "pynput.keyboard",
    "comtypes",
    "comtypes.client",
    "psutil",
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
    excludes=[
        # Trim obviously unused stdlib modules from the bundle.
        "tkinter",
        "unittest",
        "test",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Inscription",
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
    name="Inscription",
)
