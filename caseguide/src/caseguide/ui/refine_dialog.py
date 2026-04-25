"""Modal "Refining suggestions…" progress dialog.

Mirrors Inscription's :class:`inscription.ui.rewrite_dialog`. The LLM
call is synchronous and can take seconds-to-minutes on a local model,
so the controller runs :class:`SuggestionsRefiner` on a
:class:`QThread` and shows this dialog meanwhile. The dialog is
deliberately thin: a label, an indeterminate progress bar, and a
cancel button. It closes itself when the worker emits ``finished_ok``
or ``failed``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from caseguide.case_reader import CaseScope
    from caseguide.llm.augment import SuggestionsRefiner
    from caseguide.model import Suggestion

logger = logging.getLogger(__name__)


class RefineWorker(QThread):
    """Runs :meth:`SuggestionsRefiner.refine` on a background thread."""

    finished_ok = Signal(list)  # list[Suggestion]
    failed = Signal(str)

    def __init__(
        self,
        *,
        refiner: SuggestionsRefiner,
        scope: CaseScope,
        drafts: list[Suggestion],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._refiner = refiner
        self._scope = scope
        self._drafts = drafts

    def run(self) -> None:
        try:
            refined = self._refiner.refine(scope=self._scope, drafts=self._drafts)
        except Exception as exc:
            logger.exception("LLM refinement failed")
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(refined)


class RefineProgressDialog(QDialog):
    """Indeterminate progress dialog with a cancel button."""

    succeeded = Signal(list)  # list[Suggestion]
    failed = Signal(str)

    def __init__(self, worker: RefineWorker, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Refining with LLM")
        self.setModal(True)
        self.setMinimumWidth(380)
        # The X button would just hide the dialog while the worker
        # keeps running; force the user through Cancel so the path
        # is explicit.
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, on=False)

        label = QLabel(
            "Asking the model to tailor the suggestions to this case.\n"
            "This can take a minute on a local model.",
            self,
        )
        label.setWordWrap(True)

        progress = QProgressBar(self)
        progress.setRange(0, 0)  # indeterminate

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.rejected.connect(self._on_cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(progress)
        layout.addWidget(buttons)

        self._worker = worker
        self._worker.finished_ok.connect(self._on_success)
        self._worker.failed.connect(self._on_failure)

    def start(self) -> None:
        self._worker.start()

    # ------------------------------------------------------------ slots

    def _on_success(self, refined: list[Suggestion]) -> None:
        self.succeeded.emit(refined)
        self.accept()

    def _on_failure(self, message: str) -> None:
        self.failed.emit(message)
        self.reject()

    def _on_cancel(self) -> None:
        # QThread can't be killed mid-HTTP, but the request will finish
        # on its own and the connected slots will no-op after reject().
        logger.info("User cancelled LLM refinement (request may still complete in background)")
        self.reject()
