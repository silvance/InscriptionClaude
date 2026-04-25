"""Custom row renderer for the welcome-page recents list.

Each case is drawn as a two-line card: the case name on top, a muted
metadata row below carrying the case reference (as a chip), the
examiner, and the relative "edited X ago" time. Replaces the default
``QListWidget`` text rendering, which was effectively two newlines
glued together.

Reads the full :class:`caseforge.model.CaseSummary` off
``CASE_SUMMARY_ROLE``; the welcome page sets it on every row.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from caseforge.model import CaseSummary

if TYPE_CHECKING:
    from PySide6.QtCore import QModelIndex, QPersistentModelIndex


CASE_SUMMARY_ROLE = Qt.ItemDataRole.UserRole + 1

_PADDING_H = 14
_PADDING_V = 10
_CHIP_PADDING_H = 8
_CHIP_PADDING_V = 2
_TITLE_TO_META = 4
_META_GAP = 10
_MIN_ROW_HEIGHT = 56


class RecentsDelegate(QStyledItemDelegate):
    """Two-line case card for the welcome page list."""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        summary = index.data(CASE_SUMMARY_ROLE)
        if not isinstance(summary, CaseSummary):
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        opt.text = ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)

        rect = opt.rect.adjusted(_PADDING_H, _PADDING_V, -_PADDING_H, -_PADDING_V)
        is_selected = bool(opt.state & QStyle.StateFlag.State_Selected)

        title_font = QFont(opt.font)
        title_font.setWeight(QFont.Weight.DemiBold)
        title_metrics = QFontMetrics(title_font)
        title_text = title_metrics.elidedText(
            summary.name or "(unnamed case)",
            Qt.TextElideMode.ElideRight,
            rect.width(),
        )

        painter.setFont(title_font)
        painter.setPen(self._text_pen(opt, selected=is_selected))
        painter.drawText(
            rect.left(),
            rect.top() + title_metrics.ascent(),
            title_text,
        )

        meta_top = rect.top() + title_metrics.height() + _TITLE_TO_META
        meta_font = QFont(opt.font)
        meta_font.setPointSize(max(8, opt.font.pointSize() - 1))
        meta_metrics = QFontMetrics(meta_font)
        painter.setFont(meta_font)

        meta_x = rect.left()
        if summary.case_reference:
            chip_w = self._draw_chip(
                painter,
                QRect(meta_x, meta_top, 0, meta_metrics.height() + 2 * _CHIP_PADDING_V),
                summary.case_reference,
                metrics=meta_metrics,
                selected=is_selected,
                option=opt,
            )
            meta_x += chip_w + _META_GAP

        painter.setPen(self._muted_pen(opt, selected=is_selected))
        meta_baseline = meta_top + meta_metrics.ascent() + _CHIP_PADDING_V
        bits: list[str] = []
        if summary.examiner_name:
            bits.append(summary.examiner_name)
        bits.append(_relative_time(summary.updated_at))
        meta_text = "  ·  ".join(bits)
        meta_text = meta_metrics.elidedText(
            meta_text, Qt.TextElideMode.ElideRight, rect.right() - meta_x
        )
        painter.drawText(meta_x, meta_baseline, meta_text)

        painter.restore()

    def sizeHint(  # noqa: N802 - Qt API
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        title_metrics = QFontMetrics(opt.font)
        meta_font = QFont(opt.font)
        meta_font.setPointSize(max(8, opt.font.pointSize() - 1))
        meta_metrics = QFontMetrics(meta_font)
        height = (
            title_metrics.height()
            + _TITLE_TO_META
            + meta_metrics.height()
            + 2 * _CHIP_PADDING_V
            + 2 * _PADDING_V
        )
        width = max(opt.rect.width(), 320)
        return QSize(width, max(_MIN_ROW_HEIGHT, height))

    # -------------------------------------------------------- internals

    @staticmethod
    def _draw_chip(
        painter: QPainter,
        rect: QRect,
        text: str,
        *,
        metrics: QFontMetrics,
        selected: bool,
        option: QStyleOptionViewItem,
    ) -> int:
        chip_h = metrics.height() + 2 * _CHIP_PADDING_V
        chip_w = metrics.horizontalAdvance(text) + 2 * _CHIP_PADDING_H
        actual = QRect(rect.left(), rect.top(), chip_w, chip_h)
        if selected:
            bg = option.palette.color(QPalette.ColorRole.HighlightedText)
            bg.setAlphaF(0.18)
            fg = option.palette.color(QPalette.ColorRole.HighlightedText)
        else:
            bg = option.palette.color(QPalette.ColorRole.AlternateBase)
            if not bg.isValid() or bg.alpha() == 0:
                bg = QColor("#f0f0f5")
            fg = option.palette.color(QPalette.ColorRole.PlaceholderText)
        painter.save()
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(actual), 4, 4)
        painter.setPen(QPen(fg))
        painter.drawText(actual, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()
        return chip_w

    @staticmethod
    def _text_pen(option: QStyleOptionViewItem, *, selected: bool) -> QPen:
        if selected:
            return QPen(option.palette.color(QPalette.ColorRole.HighlightedText))
        return QPen(option.palette.color(QPalette.ColorRole.Text))

    @staticmethod
    def _muted_pen(option: QStyleOptionViewItem, *, selected: bool) -> QPen:
        if selected:
            colour = option.palette.color(QPalette.ColorRole.HighlightedText)
            colour.setAlphaF(0.85)
            return QPen(colour)
        return QPen(option.palette.color(QPalette.ColorRole.PlaceholderText))


_SECONDS_PER_MINUTE = 60
_MINUTES_PER_HOUR = 60
_HOURS_PER_DAY = 24
_DAYS_BEFORE_ABSOLUTE = 7


def _relative_time(when: datetime) -> str:
    """Render ``when`` as a short human-friendly relative timestamp."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    now = datetime.now(tz=when.tzinfo)
    delta = now - when
    seconds = int(delta.total_seconds())
    if seconds < _SECONDS_PER_MINUTE:
        return "just now"
    minutes = seconds // _SECONDS_PER_MINUTE
    if minutes < _MINUTES_PER_HOUR:
        return f"{minutes}m ago"
    hours = minutes // _MINUTES_PER_HOUR
    if hours < _HOURS_PER_DAY:
        return f"{hours}h ago"
    days = hours // _HOURS_PER_DAY
    if days < _DAYS_BEFORE_ABSOLUTE:
        return f"{days}d ago"
    return when.astimezone().strftime("%Y-%m-%d %H:%M")


__all__ = ["CASE_SUMMARY_ROLE", "RecentsDelegate"]
