"""Bundle version-stamp helpers.

The interesting cases are: not frozen, frozen with valid version.json,
frozen with corrupt / missing / oversized / non-dict version.json. We
patch ``sys.frozen`` and ``sys.executable`` to simulate the bundle
layout from a source checkout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from suite_common.bundle import bundle_root, read_version_info


def _make_bundle(tmp_path: Path, *, version_payload: object | None = None) -> Path:
    """Lay out a fake bundle with an Inscription/Inscription.exe and an
    optional version.json. Returns the path that should be used as
    ``sys.executable`` inside the test."""
    root = tmp_path / "InscriptionSuite"
    (root / "Inscription").mkdir(parents=True)
    fake_exe = root / "Inscription" / "Inscription.exe"
    fake_exe.write_text("", encoding="utf-8")
    if version_payload is not None:
        (root / "version.json").write_text(
            json.dumps(version_payload), encoding="utf-8",
        )
    return fake_exe


def test_bundle_root_returns_none_when_not_frozen(monkeypatch) -> None:
    """Source-checkout case: sys.frozen is unset, so we have no bundle."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert bundle_root() is None


def test_bundle_root_returns_none_without_version_json(monkeypatch, tmp_path) -> None:
    """Defensive: bundle dir exists but version.json doesn't. Refuse to
    return the wrong root rather than guess."""
    fake_exe = _make_bundle(tmp_path, version_payload=None)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    assert bundle_root() is None


def test_bundle_root_finds_version_json_two_parents_up(monkeypatch, tmp_path) -> None:
    fake_exe = _make_bundle(tmp_path, version_payload={"git_sha": "abc"})
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    root = bundle_root()
    assert root == fake_exe.parent.parent
    assert (root / "version.json").is_file()


def test_read_version_info_returns_dict_on_happy_path(monkeypatch, tmp_path) -> None:
    payload = {
        "bundle_format_version": 1,
        "git_sha": "abcdef1234",
        "build_timestamp": "2026-05-03T00:00:00Z",
        "models": ["gemma4:latest"],
    }
    fake_exe = _make_bundle(tmp_path, version_payload=payload)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    info = read_version_info()
    assert info is not None
    assert info["git_sha"] == "abcdef1234"
    assert info["models"] == ["gemma4:latest"]


def test_read_version_info_returns_none_when_not_frozen(monkeypatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert read_version_info() is None


def test_read_version_info_handles_corrupt_json(monkeypatch, tmp_path) -> None:
    """Returns None on parse failure rather than raising -- About
    dialogs should never crash the app on a bad version.json."""
    root = tmp_path / "InscriptionSuite"
    (root / "Inscription").mkdir(parents=True)
    fake_exe = root / "Inscription" / "Inscription.exe"
    fake_exe.write_text("", encoding="utf-8")
    (root / "version.json").write_text("{ this is not json", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    assert read_version_info() is None


def test_read_version_info_handles_non_dict_root(monkeypatch, tmp_path) -> None:
    """A version.json whose top-level is a list / string / number must
    be rejected -- callers expect a dict and would otherwise hit
    AttributeError when they `.get(...)` on it."""
    fake_exe = _make_bundle(tmp_path, version_payload=["unexpected", "shape"])
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    assert read_version_info() is None


def test_read_version_info_refuses_oversized(monkeypatch, tmp_path) -> None:
    """64 KB cap. A real version.json is < 1 KB, so anything past the
    cap is either corrupt or hostile."""
    root = tmp_path / "InscriptionSuite"
    (root / "Inscription").mkdir(parents=True)
    fake_exe = root / "Inscription" / "Inscription.exe"
    fake_exe.write_text("", encoding="utf-8")
    (root / "version.json").write_bytes(b'"' + b"x" * (65 * 1024) + b'"')
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    assert read_version_info() is None


@pytest.mark.parametrize("missing_key", ["git_sha", "build_timestamp", "models"])
def test_read_version_info_returns_partial_dict(monkeypatch, tmp_path, missing_key) -> None:
    """We don't enforce a schema -- the caller defaults missing keys.
    Confirms the helper doesn't strip unexpected shapes either."""
    payload = {
        "git_sha": "abc",
        "build_timestamp": "2026-05-03T00:00:00Z",
        "models": ["gemma4:latest"],
    }
    payload.pop(missing_key)
    fake_exe = _make_bundle(tmp_path, version_payload=payload)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    info = read_version_info()
    assert info is not None
    assert missing_key not in info
