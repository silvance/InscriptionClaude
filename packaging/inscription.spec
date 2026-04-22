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

block_cipher = None

ROOT = Path.cwd()
SRC = ROOT / "src"
ENTRY = SRC / "inscription" / "__main__.py"

a = Analysis(
    [str(ENTRY)],
    pathex=[str(SRC)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim obviously unused stdlib modules from the bundle.
        "tkinter",
        "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
