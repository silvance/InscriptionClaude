"""Element resolver fallbacks."""

from __future__ import annotations

from dataclasses import dataclass

from inscription.platform import ForegroundInfo, ForegroundInspector
from inscription.resolve import ForegroundFallbackResolver, NullResolver
from inscription.resolve.uia import _is_meaningful, _walk_up_to_meaningful


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


# ----------------------------------------------- UIA walk-up helper


@dataclass
class _FakeUiaNode:
    """Stand-in for pywinauto's ``UIAElementInfo`` for walk-up tests.

    The real class isn't importable on Linux test runners. We only need
    the attributes the resolver reads (``name`` / ``control_type``) and a
    ``parent`` accessor for the walk to climb.
    """

    name: str = ""
    control_type: str = ""
    parent: _FakeUiaNode | None = None


def test_walkup_returns_immediate_hit_when_already_meaningful() -> None:
    node = _FakeUiaNode(name="Save", control_type="Button")
    out, steps = _walk_up_to_meaningful(node, max_steps=8)
    assert out is node
    assert steps == 0


def test_walkup_climbs_past_anonymous_cells_to_named_tab() -> None:
    """The AXIOM Examine case: the click lands on an unnamed DataGridCell
    inside a row inside a TabItem. We want the TabItem name back.
    """
    tab = _FakeUiaNode(name="Documents", control_type="TabItem")
    grid = _FakeUiaNode(name="", control_type="DataGrid", parent=tab)
    row = _FakeUiaNode(name="", control_type="DataItem", parent=grid)
    cell = _FakeUiaNode(name="", control_type="Custom", parent=row)

    out, steps = _walk_up_to_meaningful(cell, max_steps=8)
    assert out is tab
    assert steps == 3


def test_walkup_skips_named_but_non_interactive_ancestors() -> None:
    """A named Pane / Group is layout chrome, not user intent. Keep climbing."""
    button = _FakeUiaNode(name="Export", control_type="Button")
    pane = _FakeUiaNode(name="Toolbar Container", control_type="Pane", parent=button)
    text = _FakeUiaNode(name="Loading…", control_type="Text", parent=pane)

    out, steps = _walk_up_to_meaningful(text, max_steps=8)
    assert out is button
    assert steps == 2


def test_walkup_returns_original_when_no_meaningful_ancestor() -> None:
    root = _FakeUiaNode(name="", control_type="Pane")
    middle = _FakeUiaNode(name="", control_type="Pane", parent=root)
    leaf = _FakeUiaNode(name="", control_type="Custom", parent=middle)

    out, steps = _walk_up_to_meaningful(leaf, max_steps=8)
    assert out is leaf
    assert steps == 0


def test_walkup_caps_at_max_steps() -> None:
    """A pathological deep tree shouldn't make every click pay the climb cost."""
    deep = _FakeUiaNode(name="OK", control_type="Button")
    for _ in range(20):
        deep = _FakeUiaNode(name="", control_type="Pane", parent=deep)

    out, steps = _walk_up_to_meaningful(deep, max_steps=8)
    assert out is deep  # Couldn't reach the named button within 8 hops.
    assert steps == 0


def test_is_meaningful_rejects_text_label_even_if_named() -> None:
    label = _FakeUiaNode(name="Status: Ready", control_type="Text")
    assert _is_meaningful(label) is False


def test_is_meaningful_accepts_named_button() -> None:
    btn = _FakeUiaNode(name="Save", control_type="Button")
    assert _is_meaningful(btn) is True
