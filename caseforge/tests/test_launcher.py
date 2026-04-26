"""Suite-tool launcher: command construction and resolution order."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

from caseforge.launcher import build_command

if TYPE_CHECKING:
    from pathlib import Path


def test_explicit_path_wins(tmp_path: Path) -> None:
    fake_exe = tmp_path / "Inscription.exe"
    fake_exe.write_text("", encoding="utf-8")
    cmd = build_command(
        executable_path=str(fake_exe),
        module_name="inscription",
        case_dir=tmp_path,
    )
    assert cmd[0] == str(fake_exe)
    assert cmd[1:3] == ["--case-dir", str(tmp_path.resolve())]


def test_missing_explicit_path_falls_back_to_path_lookup(tmp_path: Path) -> None:
    """An explicit path that doesn't exist on disk should fall through.

    Hardening — a stale config (e.g. dragged-and-dropped to a path that
    the user later renamed) should resolve via PATH rather than be
    handed unchanged to ``Popen``.
    """
    bogus = tmp_path / "not-installed.exe"
    with patch(
        "caseforge.launcher.shutil.which",
        side_effect=lambda name: f"/usr/local/bin/{name}" if name == "inscription" else None,
    ):
        cmd = build_command(
            executable_path=str(bogus), module_name="inscription", case_dir=tmp_path
        )
    assert cmd[0] == "/usr/local/bin/inscription"


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
