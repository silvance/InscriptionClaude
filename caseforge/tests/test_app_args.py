"""CLI argument parsing for the CaseForge bootstrap.

Mirrors the test shape inscription/tests/test_app_args.py uses for
its parser: confirm the new --case-dir flag works, defaults to None,
unknown flags pass through to Qt, and --version exits cleanly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from caseforge.app import _parse_args


def test_no_case_dir_defaults_to_none() -> None:
    args, remaining = _parse_args(["caseforge"])
    assert args.case_dir is None
    assert remaining == []


def test_case_dir_returns_path() -> None:
    args, _remaining = _parse_args(["caseforge", "--case-dir", "/tmp/case-001"])
    assert args.case_dir == Path("/tmp/case-001")


def test_unknown_flags_pass_through_to_qt() -> None:
    """Qt's own argv flags (-platform, -style, ...) must survive
    argparse so QApplication sees them. ``parse_known_args`` is the
    contract here; this test pins it."""
    args, remaining = _parse_args(
        ["caseforge", "--case-dir", "/tmp/x", "-platform", "offscreen"],
    )
    assert args.case_dir == Path("/tmp/x")
    assert remaining == ["-platform", "offscreen"]


def test_version_flag_exits_cleanly() -> None:
    """argparse --version raises SystemExit(0); the exit code is the
    only contract that matters for shell-script integration."""
    with pytest.raises(SystemExit) as info:
        _parse_args(["caseforge", "--version"])
    assert info.value.code == 0
