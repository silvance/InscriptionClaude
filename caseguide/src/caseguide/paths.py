"""Filesystem path resolution for CaseGuide.

Per-user state lives under ``%LOCALAPPDATA%\\CaseGuide\\`` on Windows;
``~/.local/share/CaseGuide`` elsewhere for development. CaseGuide
itself doesn't manage case files — those belong to CaseForge — so the
data root is intentionally light: just config + logs + an optional
user-playbook overlay directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final


def _default_data_root() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "CaseGuide"
    return Path.home() / ".local" / "share" / "CaseGuide"


DATA_ROOT: Final = _default_data_root()
CONFIG_FILE: Final = DATA_ROOT / "config.ini"
LOG_DIR: Final = DATA_ROOT / "logs"

#: Where built-in playbooks ship — relative to this source file so the
#: PyInstaller bundle finds them via the same path.
BUILTIN_PLAYBOOKS_DIR: Final = Path(__file__).parent / "playbook_data"

#: Optional user-supplied playbooks. Examiners can drop their own
#: JSON files here to extend the built-in library.
USER_PLAYBOOKS_DIR: Final = DATA_ROOT / "playbooks"


def ensure_dirs() -> None:
    """Create the per-user data directories if missing."""
    for path in (DATA_ROOT, LOG_DIR, USER_PLAYBOOKS_DIR):
        path.mkdir(parents=True, exist_ok=True)
