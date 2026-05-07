"""Filesystem path resolution for CaseGuide.

Per-user state lives via the shared
:func:`suite_common.paths.default_data_root` helper:

- Windows: ``%LOCALAPPDATA%\\CaseGuide\\``
- Linux / macOS dev fallback: ``~/.local/share/CaseGuide``

CaseGuide itself doesn't manage case files — those belong to
CaseForge — so the data root is intentionally light: just config +
logs + an optional user-playbook overlay directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from suite_common import default_data_root
from suite_common.paths import ensure_dirs as _ensure_dirs

DATA_ROOT: Final = default_data_root("CaseGuide")
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
    _ensure_dirs(DATA_ROOT, LOG_DIR, USER_PLAYBOOKS_DIR)
