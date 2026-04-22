"""Smoke tests for package import and version metadata."""

from __future__ import annotations

import re

import inscription


def test_package_importable() -> None:
    assert hasattr(inscription, "__version__")


def test_version_is_semver_like() -> None:
    assert re.match(r"^\d+\.\d+\.\d+", inscription.__version__) is not None
