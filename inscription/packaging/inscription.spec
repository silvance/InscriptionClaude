# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Inscription.

Invoke from the inscription/ directory, or use the repo-root
build.ps1 (Windows) / build.sh (Linux):

    cd inscription
    pyinstaller packaging/inscription.spec --noconfirm

Output lands in dist/Inscription/. Copy that folder to the target
workstation and run the binary inside. One-folder mode is used because
it starts faster and is easier to diagnose than one-file.

Cross-platform: the spec branches on ``sys.platform`` for backend
modules (mss/pynput/psutil pick different submodules per OS) and the
Windows-only ``uac_admin`` manifest flag. The UIA capture path runs
only on Windows; on Linux the app starts fine but the capture buttons
no-op (pywinauto isn't available there).
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR    = Path(SPECPATH).resolve()          # inscription/packaging/
ROOT        = SPEC_DIR.parent                    # inscription/
SRC         = ROOT / "src"
ENTRY       = SRC / "inscription" / "__main__.py"
COMMON_SRC  = ROOT.parent / "suite_common" / "src"

IS_WINDOWS = sys.platform == "win32"

HIDDEN_IMPORTS = [
    # PySide6 — the hook usually picks these up, but listing them
    # keeps the build stable across PyInstaller versions.
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    # Screenshot capture — backend module is per-OS.
    "mss",
    # pynput dispatches per-OS backends at import time.
    "pynput.mouse",
    "pynput.keyboard",
    # System info — psutil's per-OS submodule.
    "psutil",
]

if IS_WINDOWS:
    HIDDEN_IMPORTS += [
        "mss.win32",
        "pynput.mouse._win32",
        "pynput.keyboard._win32",
        # pywinauto UIA bridge — Windows-only.
        "pywinauto",
        "pywinauto.application",
        "pywinauto.backends",
        "pywinauto.backends.uia",
        # comtypes underpins pywinauto on Windows; collect_submodules
        # pulls in the generated COM stubs that static analysis misses.
        "comtypes",
        "comtypes.client",
        *collect_submodules("comtypes"),
        "psutil._pswindows",
    ]
else:
    HIDDEN_IMPORTS += [
        "mss.linux",
        "pynput.mouse._xorg",
        "pynput.keyboard._xorg",
        "psutil._pslinux",
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
    excludes=[
        "tkinter",
        "unittest",
        "test",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

# Windows-only: embed a requireAdministrator manifest so a direct
# double-click on Inscription.exe (skipping start-suite.ps1) still
# gets the UAC prompt. The UIA resolver depends on running at the
# same or higher integrity level as the app it's inspecting -- an
# unelevated Inscription is blind to AXIOM Examine and any other
# forensic tool the operator launched as administrator. On Linux
# there's no UAC equivalent and pywinauto isn't available anyway,
# so the flag is omitted.
exe_kwargs = dict(
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
if IS_WINDOWS:
    exe_kwargs["uac_admin"] = True

exe = EXE(pyz, a.scripts, [], **exe_kwargs)

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
