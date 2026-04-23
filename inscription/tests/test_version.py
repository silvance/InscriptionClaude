"""Smoke test: the version module exports a non-empty string."""

from __future__ import annotations

from inscription.version import __version__


def test_version_is_nonempty_string() -> None:
    assert isinstance(__version__, str)
    assert __version__.strip()
