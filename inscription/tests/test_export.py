"""HTML export."""

from __future__ import annotations

from inscription.export import export_html
from inscription.model import EventKind, ResolvedElement, utcnow
from inscription.steps import generate_steps
from inscription.storage import SessionRepository

_MIN_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000b49444154789c6360000200000500017a5eab3f0000000049454e44ae"
    "426082"
)


def _seed_click(repo: SessionRepository) -> None:
    shot_dir = repo.session.screenshots_dir
    shot_dir.mkdir(exist_ok=True)
    shot_path = shot_dir / "click.png"
    shot_path.write_bytes(_MIN_PNG)
    shot = repo.add_screenshot(
        relative_path="screenshots/click.png",
        captured_at=utcnow(),
        width=1,
        height=1,
        sha256="abc",
    )
    resolved = repo.add_resolved_element(
        ResolvedElement(id=None, name="Save", control_type="Button", confidence=0.9, method="uia")
    )
    repo.append_event(
        kind=EventKind.CLICK,
        button="left",
        x=1,
        y=1,
        window_title="App",
        process_name="app.exe",
        screenshot_id=shot.id,
        resolved_element_id=resolved.id,
    )


def test_export_html_writes_self_contained_document(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Exportable")
    try:
        _seed_click(repo)
        generate_steps(repo)
        doc = export_html(repo)
    finally:
        repo.close()

    assert doc.path.exists()
    text = doc.path.read_text(encoding="utf-8")
    assert "<!doctype html>" in text
    assert "Exportable" in text
    assert "Save" in text
    assets = doc.path.parent / "assets"
    assert assets.exists()
    assert any(assets.iterdir())
