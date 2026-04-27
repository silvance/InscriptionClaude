"""Slug generation for session directory names."""

from __future__ import annotations

import pytest

from inscription.storage import slugify


def test_simple_name_passes_through() -> None:
    assert slugify("Reset AWS password") == "Reset-AWS-password"


def test_unsafe_chars_become_hyphens() -> None:
    assert slugify("foo/bar:baz") == "foo-bar-baz"


def test_runs_collapse() -> None:
    assert slugify("foo / / bar") == "foo-bar"


def test_empty_slug_raises() -> None:
    with pytest.raises(ValueError, match="empty slug"):
        slugify("   ")


def test_leading_and_trailing_hyphens_stripped() -> None:
    assert slugify("---foo---") == "foo"
