"""SessionSink: timestamp-based filenames survive recording restarts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from inscription.capture import EnrichedEvent, RawCaptureEvent, SessionSink
from inscription.model import EventKind, ResolvedElement, utcnow
from inscription.platform import ForegroundInfo
from inscription.storage import SessionRepository


def _make_enriched(*, png: bytes, processed_at: datetime | None = None) -> EnrichedEvent:
    return EnrichedEvent(
        raw=RawCaptureEvent(
            kind=EventKind.CLICK,
            button="left",
            x=10,
            y=10,
            png_bytes=png,
            png_width=1,
            png_height=1,
        ),
        processed_at=processed_at or utcnow(),
        foreground=ForegroundInfo(window_title="App", process_name="app.exe", process_id=1),
        image_sha256="hash",
        resolved=ResolvedElement(
            id=None, name="OK", control_type="Button", confidence=0.9, method="uia"
        ),
    )


def test_sink_filenames_are_unique_across_recording_restarts(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Restart")
    try:
        t0 = datetime(2026, 4, 24, 7, 21, 50, 100000, tzinfo=UTC)
        first = SessionSink(repo)
        first.handle(_make_enriched(png=b"first", processed_at=t0))
        first.handle(_make_enriched(png=b"second", processed_at=t0 + timedelta(microseconds=1)))

        # Simulate stop → re-start on the same session.
        second = SessionSink(repo)
        second.handle(_make_enriched(png=b"third", processed_at=t0 + timedelta(microseconds=2)))

        screenshots = repo.list_screenshots()
        paths = sorted(s.relative_path for s in screenshots)
        assert len(paths) == 3
        assert len(set(paths)) == 3  # all unique
        assert all(p.startswith("screenshots/event-") and p.endswith(".png") for p in paths)
    finally:
        repo.close()
