"""Launch Inscription against a case directory.

Resolves the Inscription executable using, in order:

1. The explicit ``inscription_path`` from CaseForge's config.
2. ``inscription`` / ``inscription.exe`` on ``PATH``.
3. ``python -m inscription`` in the same Python that's running CaseForge.

Returns a :class:`LaunchResult` describing what was tried and what
ran. Failures don't raise — callers (the UI) want a friendly message
either way.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class LaunchResult:
    """Outcome of one Inscription launch attempt."""

    ok: bool
    command: list[str]
    message: str


def build_command(*, inscription_path: str, case_dir: Path) -> list[str]:
    """Pure helper used by :func:`launch_inscription` and unit tests.

    Resolution order matches the module docstring; ``inscription_path``
    of ``""`` triggers the fall-throughs.
    """
    case_arg = str(case_dir.resolve())
    explicit = inscription_path.strip()
    if explicit:
        return [explicit, "--case-dir", case_arg]
    on_path = shutil.which("inscription") or shutil.which("inscription.exe")
    if on_path:
        return [on_path, "--case-dir", case_arg]
    return [sys.executable, "-m", "inscription", "--case-dir", case_arg]


def launch_inscription(*, inscription_path: str, case_dir: Path) -> LaunchResult:
    """Spawn Inscription pointed at ``case_dir``. Non-blocking."""
    command = build_command(inscription_path=inscription_path, case_dir=case_dir)
    try:
        subprocess.Popen(  # noqa: S603 - command pieces come from config or our own sys.executable
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, ValueError) as exc:
        logger.warning("Inscription launch failed: %s (cmd=%r)", exc, command)
        return LaunchResult(
            ok=False,
            command=command,
            message=(
                f"Could not launch Inscription: {exc}.\n\n"
                f"Tried: {' '.join(command)}\n\n"
                "Set the path explicitly in Settings → Launcher."
            ),
        )
    logger.info("Launched Inscription: %s", command)
    return LaunchResult(
        ok=True,
        command=command,
        message=f"Launched Inscription against {case_dir}.",
    )
