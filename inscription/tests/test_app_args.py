"""CLI argument parsing for the application bootstrap."""

from __future__ import annotations

from pathlib import Path

import pytest

from inscription.app import _parse_args


def test_no_case_dir_defaults_to_none() -> None:
    args, remaining = _parse_args(["inscription"])
    assert args.case_dir is None
    assert remaining == []


def test_case_dir_returns_path() -> None:
    args, _remaining = _parse_args(["inscription", "--case-dir", "/tmp/case-001"])
    assert args.case_dir == Path("/tmp/case-001")


def test_unknown_flags_pass_through_to_qt() -> None:
    args, remaining = _parse_args(["inscription", "--case-dir", "/tmp/x", "-platform", "offscreen"])
    assert args.case_dir == Path("/tmp/x")
    assert remaining == ["-platform", "offscreen"]


def test_version_flag_exits_cleanly() -> None:
    # argparse --version raises SystemExit(0).
    with pytest.raises(SystemExit) as info:
        _parse_args(["inscription", "--version"])
    assert info.value.code == 0
