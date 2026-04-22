"""Qt-aware capture sink.

Captures arrive on the engine's worker thread. This sink is a small
QObject that re-emits them as a Qt signal, which Qt automatically
marshals to the main thread — from there the controller can safely
touch the repository and the UI.

Note on typing: Python can't merge :class:`QObject`'s metaclass with
:class:`abc.ABC`'s metaclass, so this class does not inherit from
:class:`CaptureSink`. It implements the sink protocol by duck-typing
its :meth:`handle` method to the right signature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from inscription.capture.engine import CaptureResult


class QtCaptureBridge(QObject):
    """Forwards capture results from the engine worker thread to Qt's main thread.

    Implements the :class:`inscription.capture.engine.CaptureSink` protocol
    by duck-typing — it provides a ``handle`` method with the right signature
    even though it doesn't inherit from :class:`CaptureSink`.
    """

    #: Emitted from the worker thread; delivered on the main thread by Qt.
    result_ready = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    def handle(self, result: CaptureResult) -> None:
        # Qt will queue this across threads automatically; slots connected
        # on the main thread receive it there.
        self.result_ready.emit(result)
