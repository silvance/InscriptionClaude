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

if TYPE_CHECKING:
    from inscription.model import RawEvent, ResolvedElement
    from inscription.storage import SessionRepository

logger = logging.getLogger(__name__)


#: Two clicks on the same resolved element within this gap collapse into one.
CLICK_DEDUP_WINDOW_S = 0.8
#: Window-focus events within this window of a subsequent click are assumed
#: to be caused by that click and dropped to reduce noise.
WINDOW_FOCUS_COALESCE_S = 0.6
#: Resolver-confidence threshold above which we trust the UIA name + type.
HIGH_CONFIDENCE = 0.6


@dataclass(frozen=True, slots=True)
class _Action:
    """An intermediate, pre-text representation of a draft step."""

    kind: EventKind
    source_event_ids: tuple[int, ...]
    screenshot_id: int | None
    text: str


def _render_click(event: RawEvent, resolved: ResolvedElement | None) -> str:
    verb = "Double-click" if event.kind is EventKind.DOUBLE_CLICK else "Click"
    if resolved and resolved.confidence >= HIGH_CONFIDENCE and resolved.name:
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


def render_step_text(
    event: RawEvent,
    resolved: ResolvedElement | None,
) -> str:
    """Build a single-step text string from an event + its resolved element.

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
                        text=preserved.text,
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
                    text=action.text,
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
        previous_click_key: tuple[int | None, str | None] | None = None
        previous_click_ts: float | None = None

        for i, event in enumerate(events):
            if event.kind is EventKind.WINDOW_FOCUS and self._window_focus_is_noise(events, i):
                continue

            resolved = self._resolve(event.resolved_element_id)

            if event.kind in {EventKind.CLICK, EventKind.DOUBLE_CLICK}:
                key = (event.resolved_element_id, event.window_title)
                ts = event.occurred_at.timestamp()
                if (
                    previous_click_key == key
                    and previous_click_ts is not None
                    and (ts - previous_click_ts) < CLICK_DEDUP_WINDOW_S
                ):
                    # Merge into the previous action rather than duplicating.
                    last = actions[-1]
                    actions[-1] = _Action(
                        kind=last.kind,
                        source_event_ids=(*last.source_event_ids, event.id or 0),
                        screenshot_id=last.screenshot_id or event.screenshot_id,
                        text=last.text,
                    )
                    previous_click_ts = ts
                    continue
                previous_click_key = key
                previous_click_ts = ts

            actions.append(
                _Action(
                    kind=event.kind,
                    source_event_ids=(event.id or 0,),
                    screenshot_id=event.screenshot_id,
                    text=render_step_text(event, resolved),
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
