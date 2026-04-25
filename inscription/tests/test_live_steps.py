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
) -> EnrichedEvent:
    raw = RawCaptureEvent(
        kind=kind,
        occurred_at=when or utcnow(),
        button="left" if kind is EventKind.CLICK else None,
        x=1 if kind is EventKind.CLICK else None,
        y=1 if kind is EventKind.CLICK else None,
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
