"""Draft step generation.

Reads raw events (and the resolved elements they reference) from a session
repository, collapses them into a reduced set of user-meaningful actions,
and writes the result into the ``draft_steps`` table via
:meth:`SessionRepository.replace_steps`.

Regeneration policy: manually-edited steps (``manual_edit=True``) are kept
verbatim when their source event set hasn't changed. Only untouched or
source-changed steps are rewritten. This preserves examiner edits across
re-runs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from inscription.model import DraftStep, EventKind
from inscription.steps._dedup import (
    CLICK_DEDUP_WINDOW_S,
    WINDOW_FOCUS_COALESCE_S,
    ClickDedup,
    KeyPressDedup,
    ScrollDedup,
)

if TYPE_CHECKING:
    from inscription.model import RawEvent, ResolvedElement
    from inscription.storage import SessionRepository

logger = logging.getLogger(__name__)


#: Resolver-confidence threshold above which we trust the UIA name + type.
HIGH_CONFIDENCE = 0.6

#: Milestone keys whose presses are dropped entirely (mirrors the live
#: generator's set). Backspace/Delete are corrective input, not
#: procedural content; the raw events remain on disk for the AI rewrite
#: but never appear as their own step.
_DROP_KEY_NAMES = frozenset({"backspace", "delete"})

#: Re-exported for callers that import the dedup window through this module.
__all__ = [
    "CLICK_DEDUP_WINDOW_S",
    "WINDOW_FOCUS_COALESCE_S",
    "render_repeat_key_press",
    "render_step_action",
]


@dataclass(frozen=True, slots=True)
class _Action:
    """An intermediate, pre-text representation of a draft step."""

    kind: EventKind
    source_event_ids: tuple[int, ...]
    screenshot_id: int | None
    action: str
    result: str = ""


def _render_click(event: RawEvent, resolved: ResolvedElement | None) -> str:
    verb = "Double-click" if event.kind is EventKind.DOUBLE_CLICK else "Click"
    if resolved and resolved.confidence >= HIGH_CONFIDENCE and resolved.name:
        # UIA "Text" elements are static labels, not interactive controls.
        # Clicks that resolve to them are almost always positional accidents
        # (e.g. clicking near a label or on the recording tool's own UI).
        # Fall through to the lower-confidence window-title path instead.
        if resolved.control_type != "Text":
            control = resolved.control_type or "item"
            in_window = _in_window_clause(event, resolved)
            return f"{verb} the {resolved.name!r} {control}{in_window}.".replace("''", "'")
    if event.window_title:
        return f"{verb} in the {event.window_title} window."
    return f"{verb} the mouse."


def _in_window_clause(event: RawEvent, resolved: ResolvedElement) -> str:
    """Return the `` in <window>`` suffix, or `` `` when it would mislead.

    The suffix is dropped when the resolved element's owning process
    differs from the foreground process at click time. That catches the
    common taskbar / Start menu / Alt-Tab case: UIA resolves the shell
    element correctly, but the foreground window is whatever app the
    user was previously in — gluing the two together produces phrases
    like "Click the 'Python' Button in World of Warcraft."
    """
    if not event.window_title:
        return ""
    owner = resolved.owner_process_name
    if owner and event.process_name and owner != event.process_name:
        return ""
    return f" in {event.window_title}"


def _render_key_press(event: RawEvent) -> str:
    key = (event.key or "a key").replace("_", " ")
    if event.window_title:
        return f"Press {key.capitalize()} in {event.window_title}."
    return f"Press {key.capitalize()}."


def render_repeat_key_press(event: RawEvent, *, count: int) -> str:
    """Render a key-press step that has merged ``count`` repeats.

    Used by both step generators when the keypress dedup machine signals
    a merge: ``Press Enter 3 times in Notepad`` rather than three
    separate "Press Enter" steps. ``count == 1`` falls back to the
    single-press wording so the same renderer handles both cases.
    """
    if count <= 1:
        return _render_key_press(event)
    key = (event.key or "a key").replace("_", " ")
    if event.window_title:
        return f"Press {key.capitalize()} {count} times in {event.window_title}."
    return f"Press {key.capitalize()} {count} times."


def _render_window_focus(event: RawEvent) -> str:
    if event.window_title:
        return f"Switch to the {event.window_title} window."
    return "Switch windows."


def _render_marker(event: RawEvent) -> str:
    return event.text or "Marker placed."


def _render_scroll(event: RawEvent) -> str:
    descriptor = event.text or "scroll"
    if event.window_title:
        return f"Scroll {descriptor} in {event.window_title}."
    return f"Scroll {descriptor}."


def render_step_action(
    event: RawEvent,
    resolved: ResolvedElement | None,
) -> str:
    """Build a single-step Action string from an event + its resolved element.

    The wording scales with resolver confidence:

    - High-confidence (UIA resolved): control name + type.
    - Low-confidence (foreground only): window title only.
    - No resolution: generic ("Click the mouse").
    """
    if event.kind is EventKind.CLICK or event.kind is EventKind.DOUBLE_CLICK:
        return _render_click(event, resolved)
    if event.kind is EventKind.KEY_PRESS:
        return _render_key_press(event)
    if event.kind is EventKind.WINDOW_FOCUS:
        return _render_window_focus(event)
    if event.kind is EventKind.MARKER:
        return _render_marker(event)
    if event.kind is EventKind.SCROLL:
        return _render_scroll(event)
    return f"{event.kind.value}."


class StepGenerator:
    """Build :class:`DraftStep` rows from a session's raw event stream."""

    def __init__(self, repository: SessionRepository) -> None:
        self._repo = repository

    # -------------------------------------------------------------- API

    def regenerate(self) -> list[DraftStep]:
        """Replace the session's draft steps with freshly-generated ones.

        Preserves manual edits where the source event set is unchanged.
        """
        existing = self._repo.list_steps(include_suppressed=True)
        manual_by_sources = {step.source_event_ids: step for step in existing if step.manual_edit}

        events = self._repo.list_events()
        actions = self._reduce_to_actions(events)

        new_steps: list[DraftStep] = []
        for action in actions:
            preserved = manual_by_sources.get(action.source_event_ids)
            if preserved is not None:
                new_steps.append(
                    DraftStep(
                        id=None,
                        sequence=0,  # reassigned by replace_steps
                        action=preserved.action,
                        result=preserved.result,
                        source_event_ids=action.source_event_ids,
                        screenshot_id=action.screenshot_id,
                        manual_edit=True,
                    )
                )
                continue
            new_steps.append(
                DraftStep(
                    id=None,
                    sequence=0,
                    action=action.action,
                    result=action.result,
                    source_event_ids=action.source_event_ids,
                    screenshot_id=action.screenshot_id,
                    manual_edit=False,
                )
            )

        saved = self._repo.replace_steps(new_steps)
        self._repo.flush_manifest()
        return saved

    # -------------------------------------------------------- reduction

    def _reduce_to_actions(self, events: list[RawEvent]) -> list[_Action]:
        actions: list[_Action] = []
        click_dedup = ClickDedup()
        key_dedup = KeyPressDedup()
        scroll_dedup = ScrollDedup()

        for i, event in enumerate(events):
            if event.kind is EventKind.WINDOW_FOCUS and self._window_focus_is_noise(events, i):
                continue

            # Drop corrective key presses (Backspace, Delete) — same
            # rule as the live generator. Reset all dedup state so a
            # post-drop event doesn't accidentally merge into a step
            # that no longer exists in the action list.
            if (
                event.kind is EventKind.KEY_PRESS
                and event.key
                and event.key.lower() in _DROP_KEY_NAMES
            ):
                click_dedup.reset()
                key_dedup.reset()
                scroll_dedup.reset()
                continue

            resolved = self._resolve(event.resolved_element_id)

            # Drop clicks that resolved to UIA "Text" labels — they are
            # positional accidents, not intentional interactions.
            if (
                event.kind in {EventKind.CLICK, EventKind.DOUBLE_CLICK}
                and resolved is not None
                and resolved.control_type == "Text"
                and resolved.name
            ):
                click_dedup.reset()
                key_dedup.reset()
                scroll_dedup.reset()
                continue

            ts = event.occurred_at.timestamp()

            if click_dedup.observe(
                kind=event.kind,
                key=(event.resolved_element_id, event.window_title),
                ts=ts,
            ) and actions:
                last = actions[-1]
                actions[-1] = _Action(
                    kind=last.kind,
                    source_event_ids=(*last.source_event_ids, event.id or 0),
                    screenshot_id=last.screenshot_id or event.screenshot_id,
                    action=last.action,
                    result=last.result,
                )
                continue

            merge_key, key_count = key_dedup.observe(
                kind=event.kind, key=(event.key, event.window_title), ts=ts
            )
            if merge_key and actions:
                last = actions[-1]
                actions[-1] = _Action(
                    kind=last.kind,
                    source_event_ids=(*last.source_event_ids, event.id or 0),
                    screenshot_id=last.screenshot_id or event.screenshot_id,
                    action=render_repeat_key_press(event, count=key_count),
                    result=last.result,
                )
                continue

            merge_scroll, _ = scroll_dedup.observe(
                kind=event.kind, key=(event.text, event.window_title), ts=ts
            )
            if merge_scroll and actions:
                last = actions[-1]
                actions[-1] = _Action(
                    kind=last.kind,
                    source_event_ids=(*last.source_event_ids, event.id or 0),
                    screenshot_id=last.screenshot_id or event.screenshot_id,
                    action=last.action,
                    result=last.result,
                )
                continue

            actions.append(
                _Action(
                    kind=event.kind,
                    source_event_ids=(event.id or 0,),
                    screenshot_id=event.screenshot_id,
                    action=render_step_action(event, resolved),
                )
            )
        return actions

    def _resolve(self, element_id: int | None) -> ResolvedElement | None:
        if element_id is None:
            return None
        return self._repo.get_resolved_element(element_id)

    @staticmethod
    def _window_focus_is_noise(events: list[RawEvent], index: int) -> bool:
        """Return True if this window-focus event is caused by a nearby click."""
        event = events[index]
        focus_ts = event.occurred_at.timestamp()
        for other in events[index + 1 : index + 4]:
            if other.kind not in {EventKind.CLICK, EventKind.DOUBLE_CLICK}:
                continue
            if (other.occurred_at.timestamp() - focus_ts) <= WINDOW_FOCUS_COALESCE_S:
                return True
            break
        return False


def generate_steps(repository: SessionRepository) -> list[DraftStep]:
    """Convenience wrapper: regenerate a session's draft steps."""
    return StepGenerator(repository).regenerate()
