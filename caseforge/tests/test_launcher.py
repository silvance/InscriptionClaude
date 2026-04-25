"""Suite-tool launcher: command construction and resolution order."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

from caseforge.launcher import build_command

if TYPE_CHECKING:
    from pathlib import Path


def test_explicit_path_wins(tmp_path: Path) -> None:
    cmd = build_command(
        executable_path="C:/Tools/Inscription.exe",
        module_name="inscription",
        case_dir=tmp_path,
    )
    assert cmd[0] == "C:/Tools/Inscription.exe"
    assert cmd[1:3] == ["--case-dir", str(tmp_path.resolve())]


def test_falls_back_to_path_lookup_for_inscription(tmp_path: Path) -> None:
    with patch(
        "caseforge.launcher.shutil.which",
        side_effect=lambda name: f"/usr/local/bin/{name}" if name == "inscription" else None,
    ):
        cmd = build_command(
            executable_path="", module_name="inscription", case_dir=tmp_path
        )
    assert cmd[0] == "/usr/local/bin/inscription"
    assert cmd[1] == "--case-dir"


def test_falls_back_to_path_lookup_for_caseguide(tmp_path: Path) -> None:
    with patch(
        "caseforge.launcher.shutil.which",
        side_effect=lambda name: f"/opt/bin/{name}" if name == "caseguide" else None,
    ):
        cmd = build_command(
            executable_path="", module_name="caseguide", case_dir=tmp_path
        )
    assert cmd[0] == "/opt/bin/caseguide"


def test_falls_back_to_python_module_when_path_misses(tmp_path: Path) -> None:
    with patch("caseforge.launcher.shutil.which", return_value=None):
        cmd = build_command(
            executable_path="", module_name="caseguide", case_dir=tmp_path
        )
    assert cmd[:3] == [sys.executable, "-m", "caseguide"]
    assert cmd[-2:] == ["--case-dir", str(tmp_path.resolve())]


def test_whitespace_only_path_falls_through(tmp_path: Path) -> None:
    with patch("caseforge.launcher.shutil.which", return_value=None):
        cmd = build_command(
            executable_path="   ", module_name="inscription", case_dir=tmp_path
        )
    assert cmd[:3] == [sys.executable, "-m", "inscription"]
