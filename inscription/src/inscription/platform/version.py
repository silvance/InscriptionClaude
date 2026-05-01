"""Read Windows file-version metadata off a process executable.

Used by :class:`inscription.capture.window_source.WindowFocusSource` to
record what version of an external app the examiner was driving (e.g.
"Magnet AXIOM Examine v8.6.0.42301") the first time that app gains
focus during a session. The version string ends up in the rendered
step text, so the AI rewrite pass and the exported notes both carry
provenance for "which build was running at exam time".

Best-effort by design: anything that fails (non-Windows, missing
pywin32, unsigned binary with no version resource, file removed by
the user mid-session) returns None. Callers fall back to "process
name only" rather than block recording on a metadata fetch.
"""

from __future__ import annotations

import logging
import sys
from typing import Final

logger = logging.getLogger(__name__)

#: Sub-block name returned by ``GetFileVersionInfo`` for the fixed
#: file-info struct. The struct has FileVersionMS / FileVersionLS
#: 32-bit halves, which we combine into the four-part dotted form.
_FIXED_INFO: Final = "\\"


def read_file_version(path: str | None) -> str | None:
    """Return ``"<a>.<b>.<c>.<d>"`` or None.

    ``None`` results cover three cases the caller treats identically:
    (a) we're not on Windows, (b) ``pywin32`` isn't importable,
    (c) the binary has no version resource or the read failed.
    """
    if not path:
        return None
    if sys.platform != "win32":
        return None
    try:
        import win32api  # noqa: PLC0415 - Windows-only optional dep
    except Exception as exc:
        logger.debug("pywin32 unavailable for version read: %s", exc)
        return None
    try:
        info = win32api.GetFileVersionInfo(path, _FIXED_INFO)
    except Exception as exc:
        logger.debug("GetFileVersionInfo(%r) failed: %s", path, exc)
        return None
    try:
        ms = int(info["FileVersionMS"])
        ls = int(info["FileVersionLS"])
    except (KeyError, TypeError, ValueError) as exc:
        logger.debug("Version struct from %r missing/malformed: %s", path, exc)
        return None
    return _format_version(ms, ls)


def _format_version(ms: int, ls: int) -> str:
    """Combine the two 32-bit halves into the four-part dotted version.

    Pure helper so tests can exercise the bit-twiddling without a
    Windows binary in the fixture set.
    """
    major = (ms >> 16) & 0xFFFF
    minor = ms & 0xFFFF
    build = (ls >> 16) & 0xFFFF
    revision = ls & 0xFFFF
    return f"{major}.{minor}.{build}.{revision}"
