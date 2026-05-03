"""Application settings dialog.

Two sections in one window:

- **Examiner identity** — name, organisation, badge / employee ID.
  Saved to :class:`Config` and auto-fills the forensic-notes header.
- **LLM endpoint** — base URL, model, timeout, optional API key, plus
  a "Test connection" button that fires a tiny chat completion against
  the configured server and reports back. Examiners shouldn't need to
  open ``config.ini`` to point Inscription at their local Ollama.

Saving writes through to ``QSettings`` via :class:`Config.sync`.
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
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from suite_common.llm import list_available_models

from inscription.config import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TIMEOUT_S,
    Config,
)
from inscription.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)


class _ConnectionTest(QObject):
    """One-shot LLM ping; runs on a worker thread so the UI stays live."""

    finished = Signal(bool, str)  # ok, message

    def __init__(self, *, base_url: str, model: str, timeout_s: float, api_key: str | None) -> None:
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
            self.finished.emit(False, str(exc))
            return
        except Exception as exc:
            self.finished.emit(False, f"Unexpected error: {exc}")
            return
        self.finished.emit(True, f"Connected. Model replied with {len(reply)} chars.")


class _ModelListFetch(QObject):
    """Fetch the endpoint's model catalogue on a worker thread.

    Emits ``finished(ids, error)``. On success ``error`` is empty.
    On failure (Ollama not running, network down, endpoint doesn't
    speak OpenAI's ``/models``) ``ids`` is empty and ``error``
    carries a one-liner the dialog can render inline so the user
    knows *why* the dropdown is empty -- previously we swallowed
    the exception silently and the operator had no signal that
    something was wrong until they tried to use the saved model.
    """

    finished = Signal(list, str)  # ids, error_message

    def __init__(self, *, base_url: str, api_key: str | None) -> None:
        super().__init__()
        self._base_url = base_url
        self._api_key = api_key

    def run(self) -> None:
        try:
            ids = list_available_models(
                base_url=self._base_url, api_key=self._api_key, timeout_s=3.0,
            )
        except Exception as exc:
            self.finished.emit([], str(exc) or type(exc).__name__)
            return
        self.finished.emit(ids, "")


class SettingsDialog(QDialog):
    """Edit examiner identity and LLM endpoint configuration."""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._test_thread: QThread | None = None
        self._test_worker: _ConnectionTest | None = None
        self._models_thread: QThread | None = None
        self._models_worker: _ModelListFetch | None = None

        self.setWindowTitle("Settings")
        self.resize(560, 440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(self._build_examiner_group())
        layout.addWidget(self._build_llm_group())
        layout.addStretch(1)

        # Populate the model dropdown from whatever the configured endpoint
        # advertises. Silent on failure — the combobox stays editable so
        # the user can type any tag they want.
        self._refresh_model_options()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setProperty("role", "primary")
        # Pressing Enter from any field saves -- the default OS-style
        # behaviour, but Qt's QDialogButtonBox doesn't infer the default
        # button automatically when there are multiple ApplyRole-class
        # candidates. Explicit setDefault means we don't rely on
        # creation-order heuristics.
        save_btn.setDefault(True)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------ examiner

    def _build_examiner_group(self) -> QGroupBox:
        box = QGroupBox("Examiner identity", self)

        self._name_edit = QLineEdit(self._config.examiner_name, box)
        self._name_edit.setPlaceholderText("e.g. Alex Smith")
        self._org_edit = QLineEdit(self._config.examiner_org, box)
        self._org_edit.setPlaceholderText("e.g. Cyber Crimes Unit")
        self._id_edit = QLineEdit(self._config.examiner_id, box)
        self._id_edit.setPlaceholderText("e.g. CCU-0421")

        hint = QLabel(
            "Auto-fills the forensic-notes header so you don't have to "
            "type it on every export.",
            box,
        )
        hint.setProperty("muted", "true")
        hint.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Name", self._name_edit)
        form.addRow("Organisation", self._org_edit)
        form.addRow("Badge / ID", self._id_edit)

        outer = QVBoxLayout(box)
        outer.addLayout(form)
        outer.addWidget(hint)
        return box

    # ----------------------------------------------------------------- LLM

    def _build_llm_group(self) -> QGroupBox:
        box = QGroupBox("Local LLM (for AI rewrite)", self)

        self._base_url_edit = QLineEdit(self._config.llm_base_url, box)
        self._base_url_edit.setPlaceholderText(DEFAULT_LLM_BASE_URL)
        self._model_edit = QComboBox(box)
        self._model_edit.setEditable(True)
        self._model_edit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._model_edit.setEditText(self._config.llm_model)
        line_edit = self._model_edit.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText(DEFAULT_LLM_MODEL)
        # One-liner status under the Model field. Populated by the
        # background model-list fetch when the endpoint is unreachable
        # so the operator can see *why* the dropdown is empty rather
        # than just the empty list.
        self._model_status = QLabel("", box)
        self._model_status.setProperty("muted", "true")
        self._model_status.setWordWrap(True)
        self._model_status.setVisible(False)
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

        form = QFormLayout()
        form.addRow("Base URL", self._base_url_edit)
        form.addRow("Model", self._model_edit)
        # Empty-label row so the status text aligns with the field
        # column on the right.
        form.addRow("", self._model_status)
        form.addRow("Timeout", self._timeout_spin)
        form.addRow("API key", self._api_key_edit)

        test_row = QHBoxLayout()
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._test_status, 1)

        outer = QVBoxLayout(box)
        outer.addLayout(form)
        outer.addLayout(test_row)
        return box

    # -------------------------------------------------------- internals

    def _on_save(self) -> None:
        self._config.examiner_name = self._name_edit.text().strip()
        self._config.examiner_org = self._org_edit.text().strip()
        self._config.examiner_id = self._id_edit.text().strip()
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
        # Reset to muted while the test runs; success/failure paths
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
        worker.finished.connect(self._on_test_finished)
        # Worker emits once; tear the thread down on the next event loop tick.
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._test_worker = worker
        self._test_thread = thread
        thread.start()

    def _on_test_finished(self, ok: bool, message: str) -> None:
        self._test_btn.setEnabled(True)
        self._test_thread = None
        self._test_worker = None
        if ok:
            self._test_status.setStyleSheet("color: #2c7a2c;")
            self._test_status.setText(f"✓ {message}")
            # A successful ping confirms the endpoint is reachable, so it's
            # also a good moment to refresh the dropdown of available models.
            self._refresh_model_options()
        else:
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

    def _on_models_fetched(self, ids: list[str], error: str) -> None:
        self._models_thread = None
        self._models_worker = None
        base_url = self._base_url_edit.text().strip() or DEFAULT_LLM_BASE_URL
        if error:
            self._model_status.setText(
                f"Couldn't list models from {base_url} -- {error}. "
                f"Type the model tag manually, or fix the Base URL "
                f"above and click Test connection."
            )
            self._model_status.setVisible(True)
            return
        if not ids:
            self._model_status.setText(
                f"{base_url} reached, but advertises no models. "
                f"Type the model tag manually."
            )
            self._model_status.setVisible(True)
            return
        # Success: hide the status row and populate the dropdown.
        self._model_status.setVisible(False)
        current = self._model_edit.currentText()
        with QSignalBlocker(self._model_edit):
            self._model_edit.clear()
            self._model_edit.addItems(ids)
            # Preserve whatever the user already had typed/selected.
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


def prompt_for_examiner_identity(config: Config, parent: QWidget | None = None) -> bool:
    """First-run helper: open Settings if the examiner hasn't filled in a name.

    Returns True if the user completed (or already had) an identity, False
    if they cancelled. Callers don't have to use this — Settings is
    always reachable from the menu — but the forensic-notes export uses
    it to nudge the user before a header would otherwise read "—".
    """
    if config.has_examiner_identity():
        return True
    QMessageBox.information(
        parent,
        "Examiner identity needed",
        "Set your examiner name and organisation so the notes header is "
        "filled in automatically.",
    )
    dialog = SettingsDialog(config, parent=parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    return config.has_examiner_identity()
