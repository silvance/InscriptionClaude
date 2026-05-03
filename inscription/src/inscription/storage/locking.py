"""Per-session lockfile to prevent two instances editing the same session.

The lockfile stores a PID. On startup we reclaim stale locks whose owning
process is no longer alive — this is the usual case after an Inscription
crash.
"""

from __future__ import annotations

import contextlib
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

    A live PID -- including this process's own PID -- is treated as a
    collision: each repository instance is logically a separate holder, so
    reopening an already-open session within one process must fail too.

    Atomicity: the lock is created with ``O_CREAT | O_EXCL``, so two
    processes racing to acquire the same lock have a guaranteed winner.
    The previous check-then-write pattern (``exists()`` + later
    ``write_text``) had a TOCTOU window where both processes could see
    no lock, both write, and both believe they hold it.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    # Stale-lock reclaim: if a lock exists but its PID is dead, drop the
    # stale file BEFORE the atomic create. Best-effort -- if another
    # process raced us to the same reclaim, the create below will still
    # fail loudly with FileExistsError on the next attempt.
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
        with contextlib.suppress(FileNotFoundError):
            # FileNotFoundError = somebody else's reclaim raced ours and
            # got there first. Either way the lock is gone; the O_EXCL
            # create below decides who owns it next.
            lock_path.unlink()

    # O_CREAT | O_EXCL is the atomic "create iff doesn't exist" primitive.
    # Race-safe across processes; FileExistsError means somebody won the
    # create race in the window between our reclaim check and now.
    pid_bytes = str(os.getpid()).encode("utf-8")
    try:
        fd = os.open(
            os.fspath(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644,
        )
    except FileExistsError as exc:
        msg = (
            f"Session lock at {lock_path} was created by another process "
            f"in a race with our acquire. Retry the operation; if it "
            f"persists, inspect the lock file for the current holder's PID."
        )
        raise SessionLockedError(msg) from exc
    try:
        os.write(fd, pid_bytes)
    finally:
        os.close(fd)


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
