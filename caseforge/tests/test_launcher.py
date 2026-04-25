"""Inscription launcher: command construction and resolution order."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

from caseforge.launcher import build_command

if TYPE_CHECKING:
    from pathlib import Path


def test_build_command_uses_explicit_path_when_set(tmp_path: Path) -> None:
    cmd = build_command(inscription_path="C:/Tools/Inscription.exe", case_dir=tmp_path)
    assert cmd[0] == "C:/Tools/Inscription.exe"
    assert cmd[1:3] == ["--case-dir", str(tmp_path.resolve())]


def test_build_command_falls_back_to_path_lookup(tmp_path: Path) -> None:
    with patch(
        "caseforge.launcher.shutil.which",
        side_effect=lambda name: f"/usr/local/bin/{name}" if name == "inscription" else None,
    ):
        cmd = build_command(inscription_path="", case_dir=tmp_path)
    assert cmd[0] == "/usr/local/bin/inscription"
    assert cmd[1] == "--case-dir"


def test_build_command_falls_back_to_python_module(tmp_path: Path) -> None:
    with patch("caseforge.launcher.shutil.which", return_value=None):
        cmd = build_command(inscription_path="", case_dir=tmp_path)
    assert cmd[:3] == [sys.executable, "-m", "inscription"]
    assert cmd[-2:] == ["--case-dir", str(tmp_path.resolve())]


def test_explicit_path_strips_whitespace(tmp_path: Path) -> None:
    cmd = build_command(inscription_path="   ", case_dir=tmp_path)
    # Empty after strip should fall through to PATH/python paths.
    assert cmd[0] != ""
