"""Shared "Local LLM" settings group for the suite apps.

Both Inscription (for the AI rewrite step) and CaseGuide (for the
suggestions Refine step) ship a Settings dialog with a Local-LLM
section: Base URL / Model / Timeout / API key + a "Test connection"
button that pings the endpoint on a worker thread and refreshes the
model dropdown on success. This module owns that widget and its
worker-thread plumbing so both apps share a single implementation.

Each app's :class:`SettingsDialog` instantiates :class:`LlmSettingsGroup`,
adds it to its layout, calls :meth:`commit` from its Save handler,
and forwards :meth:`cancel_workers` from its ``done()`` override so
in-flight worker threads finish before the dialog tears down.
"""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QObject, QSignalBlocker, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
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

from suite_common.llm import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TIMEOUT_S,
    LLMClient,
    LLMError,
    list_available_models,
)


class LlmSettingsConfig(Protocol):
    """Structural contract for the config object the widget reads/writes.

    Both ``inscription.config.Config`` and ``caseguide.config.Config``
    expose these properties already; the widget doesn't import either
    type directly so the dependency stays one-way (apps depend on
    suite_common, not the other way around).
    """

    llm_base_url: str
    llm_model: str
    llm_timeout_s: float
    llm_api_key: str | None


class _ConnectionTest(QObject):
    """One-shot LLM ping; runs on a worker thread so the UI stays live."""

    finished = Signal(bool, str)  # ok, message

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
            self.finished.emit(False, str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - dialog must not crash on unknown errors
            self.finished.emit(False, f"Unexpected error: {exc}")
            return
        self.finished.emit(True, f"Connected. Model replied with {len(reply)} chars.")


class _ModelListFetch(QObject):
    """Fetch the endpoint's model catalogue on a worker thread.

    Emits ``finished(ids, error)``. On success ``error`` is empty.
    On failure (Ollama not running, network down, endpoint doesn't
    speak OpenAI's ``/models``) ``ids`` is empty and ``error``
    carries a one-liner the dialog can render inline so the user
    knows *why* the dropdown is empty.
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
        except Exception as exc:  # noqa: BLE001 - dialog needs the message, not the type
            self.finished.emit([], str(exc) or type(exc).__name__)
            return
        self.finished.emit(ids, "")


class LlmSettingsGroup(QGroupBox):
    """Local-LLM settings group: form + Test button + worker plumbing.

    Reads its initial values from ``config`` (a structural type that
    matches both Inscription's and CaseGuide's ``Config`` classes),
    writes back via :meth:`commit` from the dialog's Save handler.
    The dialog's ``done()`` override should call :meth:`cancel_workers`
    so in-flight HTTP probes don't outlive the widget.

    ``title`` / ``purpose_hint`` let each app brand the section
    appropriately ("Local LLM (for AI rewrite)" vs "Local LLM (for
    Refine)") without forking the widget itself.
    """

    def __init__(
        self,
        config: LlmSettingsConfig,
        *,
        title: str = "Local LLM",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        self._config = config
        self._test_worker: _ConnectionTest | None = None
        self._test_thread: QThread | None = None
        self._models_worker: _ModelListFetch | None = None
        self._models_thread: QThread | None = None

        self._base_url_edit = QLineEdit(config.llm_base_url, self)
        self._base_url_edit.setPlaceholderText(DEFAULT_LLM_BASE_URL)

        self._model_edit = QComboBox(self)
        self._model_edit.setEditable(True)
        self._model_edit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._model_edit.setEditText(config.llm_model)
        line_edit = self._model_edit.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText(DEFAULT_LLM_MODEL)

        # One-liner status under the Model field. Populated by the
        # background model-list fetch when the endpoint is unreachable
        # so the operator can see *why* the dropdown is empty rather
        # than just the empty list.
        self._model_status = QLabel("", self)
        self._model_status.setProperty("muted", "true")
        self._model_status.setWordWrap(True)
        self._model_status.setVisible(False)

        self._timeout_spin = QDoubleSpinBox(self)
        self._timeout_spin.setRange(5.0, 1800.0)
        self._timeout_spin.setSingleStep(10.0)
        self._timeout_spin.setSuffix(" s")
        self._timeout_spin.setValue(config.llm_timeout_s or DEFAULT_LLM_TIMEOUT_S)

        self._api_key_edit = QLineEdit(config.llm_api_key or "", self)
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("Leave blank for local Ollama / LM Studio")

        self._test_btn = QPushButton("Test connection", self)
        self._test_btn.clicked.connect(self._on_test_connection)
        self._test_status = QLabel("", self)
        self._test_status.setWordWrap(True)
        self._test_status.setProperty("muted", "true")

        form = QFormLayout()
        form.addRow("Base URL", self._base_url_edit)
        form.addRow("Model", self._model_edit)
        form.addRow("", self._model_status)
        form.addRow("Timeout", self._timeout_spin)
        form.addRow("API key", self._api_key_edit)

        test_row = QHBoxLayout()
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._test_status, 1)

        outer = QVBoxLayout(self)
        outer.addLayout(form)
        outer.addLayout(test_row)

    # -------------------------------------------------------------- API

    def commit(self) -> None:
        """Write the current widget values back to the config object."""
        self._config.llm_base_url = self._base_url_edit.text().strip() or DEFAULT_LLM_BASE_URL
        self._config.llm_model = self._model_edit.currentText().strip() or DEFAULT_LLM_MODEL
        self._config.llm_timeout_s = float(self._timeout_spin.value())
        self._config.llm_api_key = self._api_key_edit.text().strip() or None

    def cancel_workers(self, wait_ms: int = 5000) -> None:
        """Quit and wait on any in-flight worker threads.

        Mirrors what each app's old SettingsDialog.done() override did
        manually. Without this, dialog closure can race a still-running
        test or model-list worker and produce
        ``QThread: Destroyed while thread is still running`` on
        stderr. ``wait_ms`` is enough for the workers' own 3 s HTTP
        timeouts to elapse.
        """
        for thread in (self._test_thread, self._models_thread):
            if thread is not None and thread.isRunning():
                thread.quit()
                thread.wait(wait_ms)

    # -------------------------------------------------------- internals

    def _on_test_connection(self) -> None:
        if self._test_thread is not None:
            return  # already running
        base_url = self._base_url_edit.text().strip() or DEFAULT_LLM_BASE_URL
        model = self._model_edit.currentText().strip() or DEFAULT_LLM_MODEL
        timeout = float(self._timeout_spin.value())
        api_key = self._api_key_edit.text().strip() or None

        self._test_btn.setEnabled(False)
        self._test_status.setText("Testing…")
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
            # A successful ping confirms the endpoint is reachable, so
            # it's also a good moment to refresh the dropdown of
            # available models.
            self._refresh_model_options()
        else:
            self._test_status.setStyleSheet("color: #c0392b;")
            self._test_status.setText(f"✗ {message}")

    def _refresh_model_options(self) -> None:
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
                f"Couldn't list models from {base_url} — {error}. "
                "Type the model tag manually, or fix the Base URL above "
                "and click Test connection."
            )
            self._model_status.setVisible(True)
            return
        if not ids:
            self._model_status.setText(
                f"{base_url} reached, but advertises no models. "
                "Type the model tag manually."
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
