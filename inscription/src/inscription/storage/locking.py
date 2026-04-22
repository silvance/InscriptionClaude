"""Per-case lockfile to prevent two instances editing the same case.

The lockfile stores a PID. On startup we reclaim stale locks whose owning
process is no longer alive — this is the usual case after an Inscription
crash.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from inscription.storage.errors import CaseLockedError

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def _process_alive(pid: int) -> bool:
    """Return True if a process with ``pid`` appears to be running.

    Uses ``os.kill(pid, 0)`` which posts no signal but raises ``ProcessLookup``
    if the PID is dead. Works on Linux and Windows.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # PID exists but belongs to another user. Treat as alive.
        return True
    except OSError:
        return False
    return True


def acquire(lock_path: Path) -> None:
    """Acquire the lock at ``lock_path``.

    If a stale lock exists (PID no longer alive), it is reclaimed. A live
    PID — including this process's own PID — is treated as a collision:
    each ``CaseRepository`` instance is logically a separate holder, so
    reopening an already-open case within one process must fail too.

    Raises:
        CaseLockedError: If a live process already holds the lock.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        try:
            existing_pid = int(lock_path.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            existing_pid = -1
        if _process_alive(existing_pid):
            msg = (
                f"Case is locked by process {existing_pid}. "
                f"If that process is not actually running, delete "
                f"{lock_path} and retry."
            )
            raise CaseLockedError(msg)
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
