"""Session integrity verification.

The capture pipeline records the SHA-256 of every screenshot at the
moment of capture. This module re-hashes those PNGs on disk and
reports any divergence — the simplest possible chain-of-custody
check for a forensic exam workflow. Run from
``File → Verify integrity…`` in the UI; ship as a one-click
defensibility win.

Categories of failure surfaced separately so the operator can act on
each:

- **mismatched** — the file exists on disk but its SHA-256 doesn't
  match what was recorded at capture. Strongest signal of tampering
  or an accidental edit.
- **missing** — the file was recorded but isn't on disk anymore.
  Usually a moved / deleted asset rather than tampering.
- **unhashed** — the row predates SHA-256 capture (very early alpha
  databases) or had an empty hash recorded. Reported separately so
  operators can re-hash and pin them.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inscription.storage import SessionRepository

logger = logging.getLogger(__name__)

#: Read PNGs in chunks so a runaway image doesn't blow memory.
_HASH_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class MismatchedScreenshot:
    """One screenshot that hashed differently than recorded."""

    relative_path: str
    expected_sha256: str
    actual_sha256: str


@dataclass(frozen=True, slots=True, kw_only=True)
class IntegrityResult:
    """Outcome of :func:`verify_session_integrity`."""

    total_checked: int
    ok: int
    mismatched: list[MismatchedScreenshot] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unhashed: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        """True only when every screenshot exists and matches its stored hash."""
        return not self.mismatched and not self.missing

    @property
    def has_warnings(self) -> bool:
        """Unhashed rows are not failures but worth surfacing."""
        return bool(self.unhashed)


def verify_session_integrity(repository: SessionRepository) -> IntegrityResult:
    """Re-hash every recorded screenshot and compare to its stored SHA-256.

    Synchronous; typical sessions hold dozens to a few hundred PNGs and
    SHA-256 over a few MB each is fast enough that a wait cursor is
    enough UI. Worker-thread the call from the UI if you ever see a
    session big enough to feel sluggish.
    """
    session_root = repository.session.root
    rows = repository.list_screenshots()

    mismatched: list[MismatchedScreenshot] = []
    missing: list[str] = []
    unhashed: list[str] = []
    ok = 0

    # Resolve session_root once so the per-row prefix check below
    # compares against a canonical path that doesn't itself contain
    # ``..`` segments or symlinks.
    session_root_resolved = session_root.resolve()

    for shot in rows:
        if not _is_inside(session_root_resolved, shot.relative_path):
            # Path-traversal guard: a row whose ``relative_path``
            # escapes the session directory (``../../etc/passwd``,
            # absolute paths, symlink-walked paths) gets reported
            # as missing rather than read off disk.
            logger.warning(
                "Refusing to hash screenshot outside session: %s",
                shot.relative_path,
            )
            missing.append(shot.relative_path)
            continue
        path = session_root / shot.relative_path
        if not path.exists():
            missing.append(shot.relative_path)
            continue
        if not shot.sha256:
            unhashed.append(shot.relative_path)
            continue
        actual = _hash_file(path)
        if actual.lower() == shot.sha256.lower():
            ok += 1
        else:
            mismatched.append(
                MismatchedScreenshot(
                    relative_path=shot.relative_path,
                    expected_sha256=shot.sha256,
                    actual_sha256=actual,
                )
            )

    result = IntegrityResult(
        total_checked=len(rows),
        ok=ok,
        mismatched=mismatched,
        missing=missing,
        unhashed=unhashed,
    )
    logger.info(
        "Integrity check: %d total, %d ok, %d mismatched, %d missing, %d unhashed",
        result.total_checked,
        result.ok,
        len(result.mismatched),
        len(result.missing),
        len(result.unhashed),
    )
    return result


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(_HASH_CHUNK_BYTES)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _is_inside(root_resolved: Path, relative: str) -> bool:
    """True if ``root_resolved / relative`` resolves under ``root_resolved``.

    Belt-and-braces: an absolute ``relative`` short-circuits to False;
    otherwise we resolve and check the prefix. ``Path.is_relative_to``
    is the cleanest way to express the prefix comparison.
    """
    rel = Path(relative)
    if rel.is_absolute():
        return False
    try:
        resolved = (root_resolved / rel).resolve()
    except OSError:
        return False
    return resolved.is_relative_to(root_resolved)
