"""Per-user filesystem path helpers for the suite apps.

Each app (Inscription / CaseForge / CaseGuide) keeps state under a
per-user data root keyed off the OS convention:

- Windows: ``%LOCALAPPDATA%\\<AppName>\\``
- Linux / macOS / dev fallback: ``~/.local/share/<AppName>/``

Each app's own ``paths.py`` calls :func:`default_data_root` once at
import time and pins app-specific paths under it. This module is the
single source of truth for the layout convention, so a future move
to platformdirs or a different per-OS directory only changes one
function.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def default_data_root(app_name: str) -> Path:
    """Return the per-user data root for ``app_name``.

    Used by every suite app's ``paths.py`` so the LOCALAPPDATA-vs-
    ``~/.local/share`` decision lives in one place. Defensive against
    a missing ``LOCALAPPDATA`` on Windows (rare but possible in
    locked-down forensic-workstation profiles): falls back to
    ``~/.local/share`` so the app stays importable instead of
    crashing on a path lookup at startup.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / app_name
    return Path.home() / ".local" / "share" / app_name


def ensure_dirs(*paths: Path) -> None:
    """``mkdir(parents=True, exist_ok=True)`` over every path.

    Saves each app's ``paths.py`` from rolling its own equivalent.
    """
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
