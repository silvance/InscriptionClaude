"""SessionSink: filename collision fix across recording restarts."""

from __future__ import annotations

from dataclasses import dataclass

from inscription.capture import EnrichedEvent, RawCaptureEvent, SessionSink
from inscription.model import EventKind, ResolvedElement, utcnow
from inscription.platform import ForegroundInfo
from inscription.storage import SessionRepository


@dataclass(frozen=True, slots=True, kw_only=True)
class _Click:
    png: bytes
    x: int = 10
    y: int = 10


def _make_enriched(png: bytes) -> EnrichedEvent:
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
        processed_at=utcnow(),
        foreground=ForegroundInfo(window_title="App", process_name="app.exe", process_id=1),
        image_sha256="hash",
        resolved=ResolvedElement(
            id=None, name="OK", control_type="Button", confidence=0.9, method="uia"
        ),
    )


def test_sink_seeds_counter_from_existing_screenshots(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Recount")
    try:
        first = SessionSink(repo)
        first.handle(_make_enriched(b"first"))
        first.handle(_make_enriched(b"second"))

        # Simulate stop → re-start: fresh sink on the same repo.
        second = SessionSink(repo)
        # Should NOT collide with screenshots/event-000001.png or 000002.png.
        second.handle(_make_enriched(b"third"))

        screenshots = repo.list_screenshots()
        paths = sorted(s.relative_path for s in screenshots)
        assert paths == [
            "screenshots/event-000001.png",
            "screenshots/event-000002.png",
            "screenshots/event-000003.png",
        ]
    finally:
        repo.close()
