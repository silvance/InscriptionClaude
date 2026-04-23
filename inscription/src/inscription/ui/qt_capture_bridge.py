"""Qt-aware capture sink.

Enriched events arrive on the engine's worker thread. This sink is a small
:class:`QObject` that re-emits them as a Qt signal, which Qt automatically
marshals to the main thread — from there the controller can safely touch
the repository and the UI.

Note on typing: :class:`QObject`'s metaclass can't be merged with
:class:`abc.ABC`'s metaclass, so this class duck-types the
:class:`inscription.capture.CaptureSink` protocol instead of inheriting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from inscription.capture import EnrichedEvent


class QtCaptureBridge(QObject):
    """Forwards enriched events from the worker thread to Qt's main thread."""

    #: Emitted with the :class:`EnrichedEvent`. Delivered on the main thread
    #: by Qt's queued-connection machinery.
    event_ready = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    def handle(self, event: EnrichedEvent) -> None:
        self.event_ready.emit(event)
