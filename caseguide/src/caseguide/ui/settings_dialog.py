"""Application settings dialog for CaseGuide.

CaseGuide's settings surface is narrower than Inscription's by design —
the case metadata (examiner identity, case scope) belongs to CaseForge
and propagates via ``case.json``, so the only thing CaseGuide owns at
the user level is the LLM endpoint that powers the Refine pass.

The dialog mirrors Inscription's LLM section verbatim — same form
shape, same "Test connection" worker pattern — so an examiner who's
configured the local Ollama once can copy the same values across and
expect identical behaviour.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QSignalBlocker, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from suite_common.llm import LLMClient, LLMError, list_available_models

from caseguide.config import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TIMEOUT_S,
    Config,
)

logger = logging.getLogger(__name__)


class _ConnectionTest(QObject):
    """One-shot LLM ping; runs on a worker thread so the UI stays live.

    Two outcome signals (instead of a single ``finished(ok: bool, …)``)
    so the boolean isn't a positional flag at the call site — the
    failure message goes through ``failed`` and the success message
    through ``succeeded``.
    """

    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_s: float,
        api_key: str | None,
    ) -> None:
        super().__init__()
        self._base_url = base_url
        self._model = model
        self._timeout_s = timeout_s
        self._api_key = api_key

    def run(self) -> None:
        try:
            client = LLMClient(
                base_url=self._base_url,
                model=self._model,
                timeout_s=self._timeout_s,
                api_key=self._api_key,
            )
            reply = client.chat(
                system="You are a connectivity test.",
                user='Reply with the exact JSON: {"ok": true}',
                json_mode=True,
            )
        except LLMError as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        except Exception as exc:  # noqa: BLE001 - worker's job is to catch everything
            self.failed.emit(f"Unexpected error: {exc}")
            return
        self.succeeded.emit(f"Connected. Model replied with {len(reply)} chars.")


class _ModelListFetch(QObject):
    """Fetch the endpoint's model catalogue on a worker thread.

    Failures emit an empty list — the combobox stays editable so users can
    still type any tag they want.
    """

    finished = Signal(list)  # list[str]

    def __init__(self, *, base_url: str, api_key: str | None) -> None:
        super().__init__()
        self._base_url = base_url
        self._api_key = api_key

    def run(self) -> None:
        try:
            ids = list_available_models(
                base_url=self._base_url, api_key=self._api_key, timeout_s=3.0,
            )
        except Exception:  # noqa: BLE001 - silent fallback to free-text entry
            ids = []
        self.finished.emit(ids)


class SettingsDialog(QDialog):
    """Edit the LLM endpoint configuration."""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._test_thread: QThread | None = None
        self._test_worker: _ConnectionTest | None = None
        self._models_thread: QThread | None = None
        self._models_worker: _ModelListFetch | None = None

        self.setWindowTitle("Settings")
        self.resize(520, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(self._build_llm_group())
        layout.addStretch(1)

        # Populate the model dropdown from whatever the configured endpoint
        # advertises. Silent on failure; the combobox stays editable.
        self._refresh_model_options()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setProperty("role", "primary")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ----------------------------------------------------------------- LLM

    def _build_llm_group(self) -> QGroupBox:
        box = QGroupBox("Local LLM (for Refine)", self)

        self._base_url_edit = QLineEdit(self._config.llm_base_url, box)
        self._base_url_edit.setPlaceholderText(DEFAULT_LLM_BASE_URL)
        self._model_edit = QComboBox(box)
        self._model_edit.setEditable(True)
        self._model_edit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._model_edit.setEditText(self._config.llm_model)
        line_edit = self._model_edit.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText(DEFAULT_LLM_MODEL)
        self._timeout_spin = QDoubleSpinBox(box)
        self._timeout_spin.setRange(5.0, 1800.0)
        self._timeout_spin.setSingleStep(10.0)
        self._timeout_spin.setSuffix(" s")
        self._timeout_spin.setValue(self._config.llm_timeout_s or DEFAULT_LLM_TIMEOUT_S)
        self._api_key_edit = QLineEdit(self._config.llm_api_key or "", box)
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("Leave blank for local Ollama / LM Studio")

        self._test_btn = QPushButton("Test connection", box)
        self._test_btn.clicked.connect(self._on_test_connection)
        self._test_status = QLabel("", box)
        self._test_status.setWordWrap(True)
        self._test_status.setProperty("muted", "true")

        hint = QLabel(
            "These match Inscription's LLM settings — point both apps "
            "at the same local Ollama / LM Studio instance.",
            box,
        )
        hint.setProperty("muted", "true")
        hint.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Base URL", self._base_url_edit)
        form.addRow("Model", self._model_edit)
        form.addRow("Timeout", self._timeout_spin)
        form.addRow("API key", self._api_key_edit)

        test_row = QHBoxLayout()
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._test_status, 1)

        outer = QVBoxLayout(box)
        outer.addLayout(form)
        outer.addLayout(test_row)
        outer.addWidget(hint)
        return box

    # -------------------------------------------------------- internals

    def _on_save(self) -> None:
        self._config.llm_base_url = self._base_url_edit.text().strip() or DEFAULT_LLM_BASE_URL
        self._config.llm_model = self._model_edit.currentText().strip() or DEFAULT_LLM_MODEL
        self._config.llm_timeout_s = float(self._timeout_spin.value())
        self._config.llm_api_key = self._api_key_edit.text().strip() or None
        self._config.sync()
        self.accept()

    def _on_test_connection(self) -> None:
        if self._test_thread is not None:
            return  # already running
        base_url = self._base_url_edit.text().strip() or DEFAULT_LLM_BASE_URL
        model = self._model_edit.currentText().strip() or DEFAULT_LLM_MODEL
        timeout = float(self._timeout_spin.value())
        api_key = self._api_key_edit.text().strip() or None

        self._test_btn.setEnabled(False)
        self._test_status.setText("Testing…")
        # Reset to muted while the test runs; success / failure paths
        # set a status colour explicitly via setStyleSheet later.
        self._test_status.setStyleSheet("")
        self._test_status.setProperty("muted", "true")
        self._test_status.style().unpolish(self._test_status)
        self._test_status.style().polish(self._test_status)

        worker = _ConnectionTest(
            base_url=base_url, model=model, timeout_s=timeout, api_key=api_key
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._on_test_succeeded)
        worker.failed.connect(self._on_test_failed)
        # Worker emits exactly one outcome signal; tear the thread down
        # on the next event loop tick after either path lands.
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._test_worker = worker
        self._test_thread = thread
        thread.start()

    def _on_test_succeeded(self, message: str) -> None:
        self._test_btn.setEnabled(True)
        self._test_thread = None
        self._test_worker = None
        self._test_status.setStyleSheet("color: #2c7a2c;")
        self._test_status.setText(f"✓ {message}")
        # Endpoint just confirmed as reachable — refresh the model list too.
        self._refresh_model_options()

    def _on_test_failed(self, message: str) -> None:
        self._test_btn.setEnabled(True)
        self._test_thread = None
        self._test_worker = None
        self._test_status.setStyleSheet("color: #c0392b;")
        self._test_status.setText(f"✗ {message}")

    def _refresh_model_options(self) -> None:
        """Kick off an async fetch of the endpoint's model list."""
        if self._models_thread is not None:
            return  # already running
        base_url = self._base_url_edit.text().strip() or DEFAULT_LLM_BASE_URL
        api_key = self._api_key_edit.text().strip() or None

        worker = _ModelListFetch(base_url=base_url, api_key=api_key)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_models_fetched)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._models_worker = worker
        self._models_thread = thread
        thread.start()

    def _on_models_fetched(self, ids: list[str]) -> None:
        self._models_thread = None
        self._models_worker = None
        if not ids:
            return
        current = self._model_edit.currentText()
        with QSignalBlocker(self._model_edit):
            self._model_edit.clear()
            self._model_edit.addItems(ids)
            self._model_edit.setEditText(current)

    def done(self, result: int) -> None:
        """Wait for in-flight worker threads before closing.

        Without this, dialog closure can race a still-running test or
        model-list worker -- the dialog's deleteLater fires while the
        QThread is mid-HTTP, producing
            QThread: Destroyed while thread is still running
        on stderr and (occasionally on Windows) a crash. 5s is enough
        for the workers' own 3s HTTP timeouts to elapse; if a thread
        is still alive after that, we let Qt's parent-child cleanup
        try to handle it rather than blocking the UI indefinitely.
        """
        for thread in (self._test_thread, self._models_thread):
            if thread is not None and thread.isRunning():
                thread.quit()
                thread.wait(5000)
        super().done(result)
