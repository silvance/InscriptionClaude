"""System-tray entry for Inscription.

When the user closes the main window, Inscription minimises to the
system tray instead of quitting. The tray icon's context menu drives
the recording lifecycle, the compact-overlay toggle, and the actual
quit. Hotkeys (Ctrl+Shift+R / Ctrl+Shift+M / Ctrl+Shift+P) remain
active in the tray-only state because the underlying pynput listeners
are tied to the QApplication event loop, not the main window.

The single first-time toast on close is the user's contract: we tell
them once that the app is still running. After that they're expected
to know the tray icon is there.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class SystemTrayController(QObject):
    """Owns the QSystemTrayIcon and the menu it shows.

    Emits Qt signals for every user intent so the controller / main
    window can wire actions without this module knowing about them.
    """

    show_window_requested = Signal()
    compact_mode_requested = Signal()
    toggle_recording_requested = Signal()
    quit_requested = Signal()

    def __init__(self, *, icon: QIcon, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("Inscription")
        self._tray.activated.connect(self._on_activated)

        menu = QMenu(parent)
        self._show_action = self._add_action(menu, "Show Inscription", self.show_window_requested)
        self._compact_action = self._add_action(
            menu, "Compact view (always on top)", self.compact_mode_requested
        )
        menu.addSeparator()
        self._toggle_action = self._add_action(
            menu, "Toggle recording (Ctrl+Shift+R)", self.toggle_recording_requested
        )
        self._toggle_action.setEnabled(False)
        menu.addSeparator()
        self._add_action(menu, "Quit Inscription", self.quit_requested)
        self._tray.setContextMenu(menu)

        # Capture is Windows-only. Off-platform we leave this False so
        # the tray menu doesn't dangle a "Toggle recording" entry that
        # would, if clicked, kick off a session producing useless
        # zero-confidence steps.
        self._recording_toggle_supported = True

    # ------------------------------------------------------------- API

    def is_supported(self) -> bool:
        """True when the OS exposes a tray. Falls back to "always show
        the main window" when False — there's no useful place to hide."""
        return QSystemTrayIcon.isSystemTrayAvailable()

    def show(self) -> None:
        if self.is_supported():
            self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def set_recording_toggle_enabled(self, enabled: bool) -> None:
        """Gate the tray's "Toggle recording" entry by platform support.

        Independent of session state -- ``set_session`` still controls
        the per-session enablement on top of this.
        """
        self._recording_toggle_supported = enabled
        if not enabled:
            self._toggle_action.setEnabled(False)

    def set_session(self, name: str | None) -> None:
        """Update tooltip + recording-toggle menu enablement."""
        if name:
            self._tray.setToolTip(f"Inscription — {name}")
            self._toggle_action.setEnabled(self._recording_toggle_supported)
        else:
            self._tray.setToolTip("Inscription — no session open")
            self._toggle_action.setEnabled(False)

    def show_message(self, title: str, body: str) -> None:
        """Surface a one-line OS notification from the tray."""
        if not self.is_supported():
            return
        self._tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 6000)

    # ----------------------------------------------------- internals

    def _add_action(self, menu: QMenu, label: str, signal: object) -> QAction:
        # ``signal`` is a SignalInstance at runtime; the static SignalInstance
        # type isn't part of PySide6's public typing surface so we accept
        # ``object`` and lean on duck typing.
        action = QAction(label, menu)
        action.triggered.connect(signal)
        menu.addAction(action)
        return action

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Single-click on Linux often fires Trigger; double-click on
        # Windows fires DoubleClick. Treat both as "show me the window".
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.show_window_requested.emit()


def quit_application() -> None:
    """Helper used by the tray-Quit path so callers don't import QApplication."""
    app = QApplication.instance()
    if app is not None:
        app.quit()
