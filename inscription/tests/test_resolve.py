"""Element resolver fallbacks."""

from __future__ import annotations

from dataclasses import dataclass

from inscription.platform import ForegroundInfo, ForegroundInspector
from inscription.resolve import ForegroundFallbackResolver, NullResolver
from inscription.resolve.uia import (
    _collect_nearby_text,
    _is_meaningful,
    _walk_up_to_meaningful,
)


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


# ----------------------------------------------------- nearby-text harvesting

@dataclass
class _FakeNodeWithChildren:
    """Like _FakeUiaNode but also exposes a parent that knows its
    children -- needed for the nearby-text sibling walk."""

    name: str = ""
    control_type: str = ""
    runtime_id: str = ""
    parent: _FakeParent | None = None


@dataclass
class _FakeParent:
    """Stand-in for the parent of a clicked element; ``children()`` is
    what _collect_nearby_text iterates."""

    _children: list[_FakeNodeWithChildren]

    def children(self) -> list[_FakeNodeWithChildren]:
        return self._children


def _attach_children(parent: _FakeParent) -> None:
    for c in parent._children:
        c.parent = parent


def test_nearby_text_returns_none_when_no_parent() -> None:
    """Orphan nodes (no parent) shouldn't crash; just return None."""
    info = _FakeNodeWithChildren(name="X", control_type="Pane", parent=None)
    assert _collect_nearby_text(info) is None


def test_nearby_text_picks_up_label_siblings() -> None:
    """Pane with sibling Text labels -> labels joined with ' | '."""
    pane = _FakeNodeWithChildren(name="", control_type="Pane", runtime_id="r1")
    label_a = _FakeNodeWithChildren(name="Pictures", control_type="Text", runtime_id="r2")
    label_b = _FakeNodeWithChildren(name="2,341 hits", control_type="Text", runtime_id="r3")
    parent = _FakeParent(_children=[pane, label_a, label_b])
    _attach_children(parent)
    assert _collect_nearby_text(pane) == "Pictures | 2,341 hits"


def test_nearby_text_skips_interactive_siblings() -> None:
    """A clicked Save button shouldn't drag in adjacent Cancel/Help
    buttons as 'nearby text' -- only label-typed siblings count."""
    save = _FakeNodeWithChildren(name="Save", control_type="Button", runtime_id="r1")
    cancel = _FakeNodeWithChildren(name="Cancel", control_type="Button", runtime_id="r2")
    title = _FakeNodeWithChildren(name="Save changes?", control_type="Header", runtime_id="r3")
    parent = _FakeParent(_children=[save, cancel, title])
    _attach_children(parent)
    assert _collect_nearby_text(save) == "Save changes?"


def test_nearby_text_returns_none_when_no_label_siblings() -> None:
    pane = _FakeNodeWithChildren(name="", control_type="Pane", runtime_id="r1")
    btn = _FakeNodeWithChildren(name="Click me", control_type="Button", runtime_id="r2")
    parent = _FakeParent(_children=[pane, btn])
    _attach_children(parent)
    assert _collect_nearby_text(pane) is None


def test_nearby_text_truncates_long_labels() -> None:
    long_text = "x" * 200
    pane = _FakeNodeWithChildren(name="", control_type="Pane", runtime_id="r1")
    label = _FakeNodeWithChildren(name=long_text, control_type="Text", runtime_id="r2")
    parent = _FakeParent(_children=[pane, label])
    _attach_children(parent)
    out = _collect_nearby_text(pane)
    assert out is not None
    # 40 char cap + ellipsis (truncation marker).
    assert len(out) <= 41 + len("…")
    assert out.endswith("…")


def test_nearby_text_caps_at_max_labels() -> None:
    """Don't bloat the prompt with every text node in a verbose pane."""
    pane = _FakeNodeWithChildren(name="", control_type="Pane", runtime_id="r1")
    siblings = [
        _FakeNodeWithChildren(name=f"Label {i}", control_type="Text", runtime_id=f"r{i+10}")
        for i in range(10)
    ]
    parent = _FakeParent(_children=[pane, *siblings])
    _attach_children(parent)
    out = _collect_nearby_text(pane)
    assert out is not None
    # _MAX_NEARBY_LABELS is 4; expect at most 4 entries joined.
    assert out.count(" | ") <= 3


def test_nearby_text_excludes_clicked_element_itself() -> None:
    """Self shouldn't appear in its own nearby_text. Useful when a
    named element is also a Text-typed sibling of itself in the
    parent's children() output."""
    self_node = _FakeNodeWithChildren(name="My Label", control_type="Text", runtime_id="r-self")
    other = _FakeNodeWithChildren(name="Other", control_type="Text", runtime_id="r-other")
    parent = _FakeParent(_children=[self_node, other])
    _attach_children(parent)
    out = _collect_nearby_text(self_node)
    # "My Label" must not appear; only "Other" may.
    assert out is None or "My Label" not in out
