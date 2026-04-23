"""Per-session lockfile to prevent two instances editing the same session.

The lockfile stores a PID. On startup we reclaim stale locks whose owning
process is no longer alive — this is the usual case after an Inscription
crash.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from inscription.storage.errors import SessionLockedError

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def acquire(lock_path: Path) -> None:
    """Acquire the lock at ``lock_path``.

    A live PID — including this process's own PID — is treated as a
    collision: each repository instance is logically a separate holder, so
    reopening an already-open session within one process must fail too.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        try:
            existing_pid = int(lock_path.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            existing_pid = -1
        if _process_alive(existing_pid):
            msg = (
                f"Session is locked by process {existing_pid}. "
                f"If that process is not actually running, delete "
                f"{lock_path} and retry."
            )
            raise SessionLockedError(msg)
        logger.info("Reclaiming stale lock at %s (previous PID %d)", lock_path, existing_pid)
    lock_path.write_text(str(os.getpid()), encoding="utf-8")


def release(lock_path: Path) -> None:
    """Release the lock if we hold it. Idempotent."""
    try:
        if not lock_path.exists():
            return
        pid = int(lock_path.read_text(encoding="utf-8").strip())
        if pid == os.getpid():
            lock_path.unlink(missing_ok=True)
    except (ValueError, OSError) as exc:
        logger.warning("Failed to release lock %s: %s", lock_path, exc)
