"""Launch sibling suite tools (Inscription, CaseGuide) against a case directory.

Both tools resolve the same way:

1. The explicit path from CaseForge's config (``inscription_path`` /
   ``caseguide_path``).
2. The tool's exe on ``PATH``.
3. ``python -m <module>`` in the same Python that's running CaseForge
   (development fall-back).

Returns a :class:`LaunchResult` describing what was tried and what
ran. Failures don't raise — the UI wants a friendly message either way.
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
    """Outcome of one launch attempt against a sibling suite tool."""

    ok: bool
    command: list[str]
    message: str
    tool_label: str = ""


def build_command(*, executable_path: str, module_name: str, case_dir: Path) -> list[str]:
    """Compose the argv that should run a tool against ``case_dir``.

    ``executable_path`` of ``""`` triggers the PATH-then-python-module
    fall-through. Pure helper so unit tests can exercise the resolution
    order without spawning subprocesses.

    An explicit path is validated to point at an existing regular file
    before being trusted; if it doesn't, we fall through to the PATH
    lookup rather than handing a stale or hostile path to ``Popen``.
    """
    case_arg = str(case_dir.resolve())
    explicit = executable_path.strip()
    if explicit:
        explicit_path = Path(explicit)
        if explicit_path.is_file():
            return [explicit, "--case-dir", case_arg]
        logger.warning(
            "Configured %s path %r is not a regular file; falling back to PATH.",
            module_name,
            explicit,
        )
    on_path = shutil.which(module_name) or shutil.which(f"{module_name}.exe")
    if on_path:
        return [on_path, "--case-dir", case_arg]
    return [sys.executable, "-m", module_name, "--case-dir", case_arg]


def _spawn(command: list[str], *, tool_label: str, case_dir: Path) -> LaunchResult:
    try:
        subprocess.Popen(  # noqa: S603 - command pieces come from config or our own sys.executable
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, ValueError) as exc:
        logger.warning("%s launch failed: %s (cmd=%r)", tool_label, exc, command)
        return LaunchResult(
            ok=False,
            command=command,
            tool_label=tool_label,
            message=(
                f"Could not launch {tool_label}: {exc}.\n\n"
                f"Tried: {' '.join(command)}\n\n"
                f"Set the path explicitly in Settings → Storage and launcher."
            ),
        )
    logger.info("Launched %s: %s", tool_label, command)
    return LaunchResult(
        ok=True,
        command=command,
        tool_label=tool_label,
        message=f"Launched {tool_label} against {case_dir}.",
    )


def launch_inscription(*, inscription_path: str, case_dir: Path) -> LaunchResult:
    """Spawn Inscription pointed at ``case_dir``. Non-blocking."""
    command = build_command(
        executable_path=inscription_path,
        module_name="inscription",
        case_dir=case_dir,
    )
    return _spawn(command, tool_label="Inscription", case_dir=case_dir)


def launch_caseguide(*, caseguide_path: str, case_dir: Path) -> LaunchResult:
    """Spawn CaseGuide pointed at ``case_dir``. Non-blocking."""
    command = build_command(
        executable_path=caseguide_path,
        module_name="caseguide",
        case_dir=case_dir,
    )
    return _spawn(command, tool_label="CaseGuide", case_dir=case_dir)
