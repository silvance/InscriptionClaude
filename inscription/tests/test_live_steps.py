"""LiveStepGenerator: append/extend draft_steps as events stream in."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from inscription.capture.engine import EnrichedEvent
from inscription.capture.events import RawCaptureEvent
from inscription.model import EventKind, ResolvedElement, utcnow
from inscription.platform import ForegroundInfo
from inscription.steps import LiveStepGenerator
from inscription.storage import SessionRepository

if TYPE_CHECKING:
    from pathlib import Path


def _enriched(
    *,
    kind: EventKind,
    raw_id: int,
    when=None,
    resolved: ResolvedElement | None = None,
    window: str = "App",
    key: str | None = None,
) -> EnrichedEvent:
    raw = RawCaptureEvent(
        kind=kind,
        occurred_at=when or utcnow(),
        button="left" if kind is EventKind.CLICK else None,
        x=1 if kind is EventKind.CLICK else None,
        y=1 if kind is EventKind.CLICK else None,
        key=key,
    )
    return EnrichedEvent(
        raw=raw,
        processed_at=raw.occurred_at,
        foreground=ForegroundInfo(
            window_title=window,
            process_name="app.exe",
            process_id=42,
        ),
        resolved=resolved,
        persisted_event_id=raw_id,
    )


def test_live_generator_appends_one_step_per_event(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="LiveAppend")
    try:
        gen = LiveStepGenerator(repo)
        # Two events, different elements -> two steps.
        gen.handle(_enriched(kind=EventKind.CLICK, raw_id=1))
        gen.handle(_enriched(kind=EventKind.KEY_PRESS, raw_id=2))
        steps = repo.list_steps()
        assert len(steps) == 2
        assert all(s.action for s in steps)  # each got rendered text
    finally:
        repo.close()


def test_live_generator_collapses_rapid_repeat_clicks(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="LiveDedup")
    try:
        gen = LiveStepGenerator(repo)
        resolved = ResolvedElement(
            id=42,
            name="OK",
            control_type="Button",
            confidence=0.9,
            method="uia",
        )
        t0 = utcnow()
        gen.handle(_enriched(kind=EventKind.CLICK, raw_id=1, when=t0, resolved=resolved))
        gen.handle(
            _enriched(
                kind=EventKind.CLICK,
                raw_id=2,
                when=t0 + timedelta(milliseconds=300),
                resolved=resolved,
            )
        )
        steps = repo.list_steps()
        assert len(steps) == 1
        assert steps[0].source_event_ids == (1, 2)
    finally:
        repo.close()


def test_live_generator_drops_backspace_keypresses(tmp_path: Path) -> None:
    """Backspace and Delete are corrective noise; they shouldn't surface
    as their own steps in the live notes panel."""
    repo = SessionRepository.create(workspace_root=tmp_path, name="LiveDropBkspc")
    try:
        gen = LiveStepGenerator(repo)
        for raw_id in range(1, 10):
            gen.handle(
                _enriched(kind=EventKind.KEY_PRESS, raw_id=raw_id, key="backspace")
            )
        assert repo.list_steps() == []
    finally:
        repo.close()


def test_live_generator_drops_clicks_on_static_text_labels(tmp_path: Path) -> None:
    """A click that resolved to a UIA Text control is a label-click —
    almost always a positional accident. The raw event is preserved
    but no step is generated."""
    repo = SessionRepository.create(workspace_root=tmp_path, name="LiveDropLabel")
    try:
        gen = LiveStepGenerator(repo)
        label = ResolvedElement(
            id=99,
            name="No screenshot",
            control_type="Text",
            confidence=0.95,
            method="uia",
        )
        gen.handle(_enriched(kind=EventKind.CLICK, raw_id=1, resolved=label))
        assert repo.list_steps() == []
    finally:
        repo.close()


def test_live_generator_coalesces_repeated_enter_presses(tmp_path: Path) -> None:
    """Three Enter presses in the same window collapse into one step
    whose action reflects the count."""
    repo = SessionRepository.create(workspace_root=tmp_path, name="LiveEnter")
    try:
        gen = LiveStepGenerator(repo)
        t0 = utcnow()
        for offset, raw_id in enumerate((1, 2, 3), start=0):
            gen.handle(
                _enriched(
                    kind=EventKind.KEY_PRESS,
                    raw_id=raw_id,
                    when=t0 + timedelta(seconds=offset),
                    window="Notepad",
                    key="enter",
                )
            )
        steps = repo.list_steps()
        assert len(steps) == 1
        assert "3 times" in steps[0].action
        assert steps[0].source_event_ids == (1, 2, 3)
    finally:
        repo.close()


def test_live_generator_starts_new_step_after_dedup_window(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="LiveSplit")
    try:
        gen = LiveStepGenerator(repo)
        resolved = ResolvedElement(
            id=42,
            name="OK",
            control_type="Button",
            confidence=0.9,
            method="uia",
        )
        t0 = utcnow()
        gen.handle(_enriched(kind=EventKind.CLICK, raw_id=1, when=t0, resolved=resolved))
        # Way past the dedup window — should be a new step.
        gen.handle(
            _enriched(
                kind=EventKind.CLICK,
                raw_id=2,
                when=t0 + timedelta(seconds=5),
                resolved=resolved,
            )
        )
        assert len(repo.list_steps()) == 2
    finally:
        repo.close()
