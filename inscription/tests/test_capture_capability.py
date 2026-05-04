"""Tests for the platform-capability flags + their wiring into the UI.

Hard-disabling capture on non-Windows is a forensic-context decision:
a Linux session would produce all-generic ResolvedElements (the
foreground inspector is a stub there), and "low-confidence captures
masquerading as forensic record" is worse than no capture. These tests
pin the contract so a future refactor can't silently re-enable it.
"""

from __future__ import annotations

import os

import pytest

from inscription.platform import (
    CAPTURE_FULLY_SUPPORTED,
    CAPTURE_UNAVAILABLE_REASON,
)

pytest.importorskip("pytestqt")

from PySide6.QtGui import QIcon

from inscription.ui.recorder_bar import RecorderBar
from inscription.ui.tray import SystemTrayController

# ----------------------------------------------------- platform flag

def test_capture_fully_supported_matches_os_name() -> None:
    """The flag is True iff we're on Windows (os.name == 'nt')."""
    assert (os.name == "nt") == CAPTURE_FULLY_SUPPORTED


def test_capture_unavailable_reason_is_user_facing_string() -> None:
    """Used as a tooltip + statusbar message, so it must be a non-empty string."""
    assert isinstance(CAPTURE_UNAVAILABLE_REASON, str)
    assert CAPTURE_UNAVAILABLE_REASON.strip()


# ----------------------------------------------------- recorder bar

def test_recorder_bar_default_is_capture_supported(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Default state is capture-on so the existing Windows path doesn't
    need to opt in via a per-call set_capture_supported(True)."""
    bar = RecorderBar()
    qtbot.addWidget(bar)
    # Record button starts enabled.
    assert bar._record_btn.isEnabled()


def test_set_capture_supported_false_disables_record_and_mark(qtbot) -> None:  # type: ignore[no-untyped-def]
    bar = RecorderBar()
    qtbot.addWidget(bar)
    bar.set_session_name("Some session")  # would normally enable Mark
    bar.set_capture_supported(False, reason="Capture is Windows-only.")
    assert not bar._record_btn.isEnabled()
    assert not bar._marker_btn.isEnabled()
    assert "Windows-only" in bar._record_btn.toolTip()
    assert "Windows-only" in bar._marker_btn.toolTip()


def test_set_capture_supported_true_clears_tooltip(qtbot) -> None:  # type: ignore[no-untyped-def]
    bar = RecorderBar()
    qtbot.addWidget(bar)
    bar.set_capture_supported(False, reason="why not")
    bar.set_capture_supported(True)
    assert bar._record_btn.isEnabled()
    assert bar._record_btn.toolTip() == ""
    assert bar._marker_btn.toolTip() == ""


def test_set_session_name_respects_capture_unsupported(qtbot) -> None:  # type: ignore[no-untyped-def]
    """When capture is unsupported, opening a session must NOT
    re-enable the Mark button."""
    bar = RecorderBar()
    qtbot.addWidget(bar)
    bar.set_capture_supported(False)
    bar.set_session_name("Some session")
    assert not bar._marker_btn.isEnabled()


def test_set_session_name_re_enables_mark_when_capture_supported(qtbot) -> None:  # type: ignore[no-untyped-def]
    """The default Windows code path: opening a session enables Mark."""
    bar = RecorderBar()
    qtbot.addWidget(bar)
    bar.set_session_name("Some session")
    assert bar._marker_btn.isEnabled()


# ----------------------------------------------------- tray controller

def test_tray_recording_toggle_disabled_overrides_session(qtbot) -> None:  # type: ignore[no-untyped-def]
    tray = SystemTrayController(icon=QIcon())
    if tray.parent() is not None:
        qtbot.addWidget(tray.parent())
    tray.set_recording_toggle_enabled(False)
    tray.set_session("session-A")  # would normally re-enable
    assert not tray._toggle_action.isEnabled()


def test_tray_recording_toggle_default_supports_session(qtbot) -> None:  # type: ignore[no-untyped-def]
    tray = SystemTrayController(icon=QIcon())
    if tray.parent() is not None:
        qtbot.addWidget(tray.parent())
    tray.set_session("session-A")
    assert tray._toggle_action.isEnabled()
