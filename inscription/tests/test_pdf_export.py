"""End-to-end test for the PDF exporter.

The full PDF rendering pipeline (QPrinter + QTextDocument +
QPainter) is hard to mock cleanly, so this test drives the real
exporter against a small seeded session and verifies the output
file is a valid PDF.

Pinned assertions:
  - The destination file ends up on disk.
  - Its first 4 bytes are ``%PDF`` (per PDF 1.x spec).
  - It's larger than a trivially-small file (catches the case
    where the renderer silently produces a near-empty PDF).
  - The returned :class:`ExportDocument` carries the right format
    string and the path the caller passed in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("pytestqt")

from inscription.export import export_pdf
from inscription.model import DraftStep, EventKind, ResolvedElement
from inscription.storage import SessionRepository

if TYPE_CHECKING:
    from pathlib import Path


def _seed_session(repo: SessionRepository) -> None:
    """Add a handful of events + steps so the rendered PDF has real
    content (pages, text, image-less rows)."""
    resolved = repo.add_resolved_element(
        ResolvedElement(
            id=None,
            name="Save",
            control_type="Button",
            confidence=0.9,
            method="uia",
        )
    )
    for _ in range(6):
        repo.append_event(
            kind=EventKind.CLICK,
            button="left",
            x=1,
            y=1,
            window_title="Notepad",
            process_name="notepad.exe",
            resolved_element_id=resolved.id,
        )
    events = repo.list_events()
    repo.replace_steps([
        DraftStep(
            id=None,
            sequence=0,
            action=f"Step {i + 1}: click the Save button.",
            result=f"File saved (iteration {i + 1}).",
            source_event_ids=(events[i].id,),
        )
        for i in range(len(events))
    ])


def test_export_pdf_produces_valid_file(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Real exporter, real session -> real PDF on disk."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repo = SessionRepository.create(workspace_root=workspace, name="PDF Test")
    try:
        _seed_session(repo)
        out_path = tmp_path / "notes.pdf"
        doc = export_pdf(
            repo,
            destination=out_path,
            examiner="Alex Smith (Cyber Crimes Unit) · CCU-0421",
            case_reference="CASE-2026-0001",
        )
        assert doc.path == out_path
        assert doc.format == "forensic-notes-pdf"
        assert out_path.is_file()
        # Spec-conformant PDFs start with %PDF; sanity-check we didn't
        # accidentally write the HTML or some intermediate text file.
        head = out_path.read_bytes()[:4]
        assert head == b"%PDF", f"output isn't a PDF, head={head!r}"
        # Anything under ~1 KB is suspicious for a real document with
        # a header band, footer band, and 6 step rows. Set a generous
        # floor so the test catches "produces an empty PDF" without
        # tripping on natural size variation.
        assert out_path.stat().st_size > 1000
    finally:
        repo.close()


def test_export_pdf_handles_no_examiner_metadata(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """examiner / case_reference are optional. No metadata still
    produces a valid PDF (the per-page header just shows the session
    title without the right-aligned meta block)."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repo = SessionRepository.create(workspace_root=workspace, name="No Examiner")
    try:
        _seed_session(repo)
        out_path = tmp_path / "no-meta.pdf"
        export_pdf(repo, destination=out_path)
        assert out_path.read_bytes()[:4] == b"%PDF"
    finally:
        repo.close()
