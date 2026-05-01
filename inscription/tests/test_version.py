"""Process file-version helper.

The full pywin32 round-trip only runs on Windows, so most of these
exercise the pure bit-twiddling and the graceful-failure paths.
"""

from __future__ import annotations

import sys

import pytest

from inscription.platform.version import _format_version, read_file_version


def test_format_version_packs_two_dwords_into_dotted_form() -> None:
    # Replicates the byte layout pywin32's GetFileVersionInfo would
    # return for "8.6.0.42301" -- two DWORDS (FileVersionMS / FileVersionLS),
    # each split into a high-16 and low-16 component.
    ms = (8 << 16) | 6
    ls = (0 << 16) | 42301
    assert _format_version(ms, ls) == "8.6.0.42301"


def test_format_version_handles_zero() -> None:
    assert _format_version(0, 0) == "0.0.0.0"


def test_format_version_masks_to_16_bits() -> None:
    # Anything beyond the low 16 bits of each half must be discarded; a
    # rogue extension shouldn't leak into the dotted form.
    ms = 0xFFFFFFFF
    ls = 0xFFFFFFFF
    assert _format_version(ms, ls) == "65535.65535.65535.65535"


def test_read_file_version_returns_none_for_empty_path() -> None:
    assert read_file_version("") is None
    assert read_file_version(None) is None


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows-only sanity")
def test_read_file_version_returns_none_off_windows() -> None:
    """The helper is best-effort -- on Linux / macOS test runners the
    module shouldn't fail; it just returns None and the caller renders
    the process name without a version suffix.
    """
    assert read_file_version("/etc/passwd") is None
