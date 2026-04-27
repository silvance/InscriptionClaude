"""Cross-cutting helpers that don't belong to a specific subsystem.

Inscription consistently shows event timestamps in the user's local
clock time so an examiner correlating Inscription notes with other
artefacts (event logs, video, dispatch logs) reads the same numbers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

#: HH:MM:SS in the user's local timezone.
CLOCK_TIME_FMT = "%H:%M:%S"


def format_clock_time(when: datetime) -> str:
    """Return ``HH:MM:SS`` for ``when`` in the user's local timezone."""
    return when.astimezone().strftime(CLOCK_TIME_FMT)


def format_local(when: datetime, fmt: str) -> str:
    """Return ``when`` rendered with ``fmt`` after converting to local time."""
    return when.astimezone().strftime(fmt)
