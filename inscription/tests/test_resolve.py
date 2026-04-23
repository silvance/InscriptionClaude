"""Element resolver fallbacks."""

from __future__ import annotations

from inscription.platform import ForegroundInfo, ForegroundInspector
from inscription.resolve import ForegroundFallbackResolver, NullResolver


class _StubInspector(ForegroundInspector):
    def __init__(self, info: ForegroundInfo) -> None:
        self._info = info

    def inspect(self) -> ForegroundInfo:
        return self._info


def test_null_resolver_returns_zero_confidence() -> None:
    resolved = NullResolver().resolve_at(1, 2)
    assert resolved.confidence == 0.0
    assert resolved.method == "none"


def test_foreground_fallback_uses_window_title() -> None:
    inspector = _StubInspector(
        ForegroundInfo(
            window_title="Calculator",
            process_name="calc.exe",
            process_id=1234,
        )
    )
    resolved = ForegroundFallbackResolver(inspector).resolve_at(10, 20)
    assert resolved.method == "foreground-only"
    assert resolved.name == "Calculator"
    assert resolved.class_name == "calc.exe"
    assert resolved.confidence == 0.3


def test_foreground_fallback_returns_null_when_empty() -> None:
    inspector = _StubInspector(ForegroundInfo(window_title="", process_name="", process_id=None))
    resolved = ForegroundFallbackResolver(inspector).resolve_at(10, 20)
    assert resolved.method == "none"
    assert resolved.confidence == 0.0
