"""Tests for case number slug generation."""

from __future__ import annotations

import pytest

from inscription.cases.slug import slugify_case_number


def test_standard_case_number_passes_through() -> None:
    assert slugify_case_number("HSV-2026-0317") == "HSV-2026-0317"


def test_alphanumerics_and_dots_preserved() -> None:
    assert slugify_case_number("Case.2026.001") == "Case.2026.001"


def test_spaces_become_dashes() -> None:
    assert slugify_case_number("HSV 2026 0317") == "HSV-2026-0317"


def test_slashes_become_dashes() -> None:
    assert slugify_case_number("HSV/2026/0317") == "HSV-2026-0317"


def test_collapse_multiple_dashes() -> None:
    assert slugify_case_number("HSV---2026") == "HSV-2026"


def test_strip_leading_and_trailing_dashes() -> None:
    assert slugify_case_number("---HSV-2026---") == "HSV-2026"


def test_unicode_replaced() -> None:
    # Non-ASCII characters get replaced with dashes.
    assert slugify_case_number("HSV-Éxposé") == "HSV-xpos"


def test_empty_input_raises() -> None:
    with pytest.raises(ValueError, match="empty slug"):
        slugify_case_number("   ")


def test_only_unsafe_chars_raises() -> None:
    with pytest.raises(ValueError, match="empty slug"):
        slugify_case_number("////")
