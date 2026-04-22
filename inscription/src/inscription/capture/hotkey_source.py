"""Hotkey-driven capture source.

Wraps a :class:`HotkeyManager` and turns hotkey presses into
:class:`CaptureRequest` submissions. Bindings are declared up front; the
source is installed into an engine by calling :meth:`CaptureEngine.add_source`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from inscription.capture.engine import CaptureRequest, CaptureSource
from inscription.cases.models import StepKind
from inscription.platform import HotkeyBinding

if TYPE_CHECKING:
    from collections.abc import Callable

    from inscription.capture.engine import CaptureEngine
    from inscription.platform import HotkeyManager

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class HotkeyCaptureBinding:
    """Maps a hotkey sequence to the :class:`StepKind` it produces."""

    sequence: str
    name: str
    kind: StepKind
    monitor_index: int | None = None


#: Sensible defaults for Phase 1. Phase 4 will introduce the panic-pause
#: and all-monitors modifier hotkeys.
DEFAULT_BINDINGS: tuple[HotkeyCaptureBinding, ...] = (
    HotkeyCaptureBinding(
        sequence="<ctrl>+<shift>+s",
        name="capture-with-note",
        kind=StepKind.HOTKEY_CAPTURE,
    ),
)


class HotkeySource(CaptureSource):
    """Capture source driven by global hotkeys.

    The source registers each binding with the provided
    :class:`HotkeyManager`. Hotkey callbacks run on the pynput listener
    thread; we immediately enqueue a :class:`CaptureRequest` and return,
    so the listener isn't blocked on capture I/O.
    """

    def __init__(
        self,
        *,
        hotkey_manager: HotkeyManager,
        bindings: tuple[HotkeyCaptureBinding, ...] = DEFAULT_BINDINGS,
    ) -> None:
        self._hotkeys = hotkey_manager
        self._bindings = bindings
        self._engine: CaptureEngine | None = None

    def start(self, engine: CaptureEngine) -> None:
        self._engine = engine
        for binding in self._bindings:
            self._hotkeys.register(
                HotkeyBinding(sequence=binding.sequence, name=binding.name),
                self._make_callback(binding),
            )

    def stop(self) -> None:
        self._hotkeys.unregister_all()
        self._engine = None

    def _make_callback(self, binding: HotkeyCaptureBinding) -> Callable[[], None]:
        def _fire() -> None:
            if self._engine is None:
                logger.warning("Hotkey %s fired without an engine bound", binding.name)
                return
            request = CaptureRequest(
                kind=binding.kind,
                monitor_index=binding.monitor_index,
                title_hint=binding.name,
            )
            accepted = self._engine.submit(request)
            if not accepted:
                logger.warning("Hotkey %s: engine rejected capture request", binding.name)

        return _fire
