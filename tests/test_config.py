"""Tests for the typed Config wrapper around QSettings."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from inscription.config import DEFAULT_CASE_NUMBER_REGEX, Config


@pytest.fixture(autouse=True)
def _org_name() -> None:
    QCoreApplication.setOrganizationName("InscriptionTest")
    QCoreApplication.setApplicationName("InscriptionTest")


def test_defaults(tmp_path: Path) -> None:
    cfg = Config(tmp_path / "config.ini")
    assert cfg.theme == "system"
    assert cfg.case_number_regex == DEFAULT_CASE_NUMBER_REGEX
    assert cfg.nas_root is None


def test_set_and_get_nas_root(tmp_path: Path) -> None:
    cfg = Config(tmp_path / "config.ini")
    target = Path(r"\\nas\cases")
    cfg.nas_root = target
    cfg.sync()

    # Re-open to prove it persisted to disk.
    cfg2 = Config(tmp_path / "config.ini")
    assert cfg2.nas_root == target


def test_clear_nas_root(tmp_path: Path) -> None:
    cfg = Config(tmp_path / "config.ini")
    cfg.nas_root = Path(r"\\nas\cases")
    cfg.nas_root = None
    cfg.sync()

    cfg2 = Config(tmp_path / "config.ini")
    assert cfg2.nas_root is None


def test_case_number_regex_overridable(tmp_path: Path) -> None:
    cfg = Config(tmp_path / "config.ini")
    cfg.case_number_regex = r"^\d{6}$"
    cfg.sync()

    cfg2 = Config(tmp_path / "config.ini")
    assert cfg2.case_number_regex == r"^\d{6}$"


def test_theme_setter(tmp_path: Path) -> None:
    cfg = Config(tmp_path / "config.ini")
    cfg.theme = "dark"
    cfg.sync()

    cfg2 = Config(tmp_path / "config.ini")
    assert cfg2.theme == "dark"


def test_default_case_regex_matches_hsv_format() -> None:
    pattern = re.compile(DEFAULT_CASE_NUMBER_REGEX)
    assert pattern.match("HSV-2026-0317")
    assert pattern.match("FBI-2025-00001")
    assert not pattern.match("hsv-2026-0317")  # case-sensitive
    assert not pattern.match("HSV 2026 0317")  # requires dashes
