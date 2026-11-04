"""One layout pattern for every dialog: title, sections, aligned forms, button roles.

Button colours come from the app stylesheet (``QPushButton:default`` and the
``variant`` property); this module only adds the label roles and the sidebar
list that no app-wide rule covers, built from ``theme`` tokens.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from manic.ui import theme

MARGIN = 24
SECTION_SPACING = 20
FORM_LABEL_WIDTH = 150
SIDEBAR_ROW_HEIGHT = 32
MARKED_ROLE = Qt.UserRole + 1

_DIALOG_STYLE = theme.substitute_tokens(
    """
QLabel { padding: 0px; background: transparent; }
QLabel[role="title"] { font-size: 16px; font-weight: 600; color: @text; }
QLabel[role="section"] { font-size: 11px; font-weight: 600; color: @text_tertiary; }
QLabel[role="description"] { font-size: 13px; color: @text_secondary; }
QLabel[role="hint"] { font-size: 12px; color: @text_secondary; }
QLabel[role="error"] { font-size: 12px; color: @danger; }
QLabel[role="pending"] { font-size: 12px; color: @warning; }
*[invalid="true"] { border: 1px solid @danger; border-radius: 6px; }
"""
)

_SIDEBAR_STYLE = theme.substitute_tokens(
    """
QListWidget {
    background: @surface_alt;
    border: none;
    border-right: 1px solid @border;
    border-radius: 0px;
    padding: 12px 8px;
    outline: 0;
}
QListWidget::item {
    color: @text;
    padding: 0px 10px;
    border: none;
    border-radius: 6px;
}
QListWidget::item:hover { background: @surface_hover; }
QListWidget::item:selected { background: @accent_soft; color: @text; }
"""
)


def window_title(thing: str) -> str:
    return f"{thing} — MANIC"


def style_dialog(dialog: QWidget) -> None:
    dialog.setStyleSheet(_DIALOG_STYLE)


def _role_label(text: str, role: str, *, wrap: bool = True) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", role)
    label.setWordWrap(wrap)
    return label


def title_label(text: str) -> QLabel:
    return _role_label(text, "title", wrap=False)


def section_label(text: str) -> QLabel:
    label = _role_label(text.upper(), "section", wrap=False)
    font = label.font()
    font.setLetterSpacing(QFont.AbsoluteSpacing, 0.5)
    label.setFont(font)
    return label


def description_label(text: str) -> QLabel:
    return _role_label(text, "description")


def hint_label(text: str) -> QLabel:
    return _role_label(text, "hint")


def error_label() -> QLabel:
    label = _role_label("", "error")
    label.hide()
    return label


def form_layout(label_width: int = FORM_LABEL_WIDTH) -> QFormLayout:
    """Left-aligned label column of fixed width, so stacked forms line up."""
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(8)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.DontWrapRows)
    form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
    form.setProperty("labelWidth", label_width)
    return form


def form_row(form: QFormLayout, text: str, field: QWidget | object) -> QLabel:
    label = QLabel(text)
    label.setMinimumWidth(int(form.property("labelWidth") or FORM_LABEL_WIDTH))
    label.setBuddy(field if isinstance(field, QWidget) else None)
    form.addRow(label, field)
    return label


def set_invalid(widget: QWidget, invalid: bool) -> None:
    if bool(widget.property("invalid")) == invalid:
        return
    widget.setProperty("invalid", invalid)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def set_variant(button: QPushButton, variant: str) -> None:
    button.setProperty("variant", variant)
    button.style().unpolish(button)
    button.style().polish(button)


def button_box(
    primary: str, secondary: str | None = "Cancel"
) -> tuple[QDialogButtonBox, QPushButton]:
    """Platform-ordered buttons: one primary (default) action, neutral others."""
    box = QDialogButtonBox()
    primary_button = box.addButton(primary, QDialogButtonBox.AcceptRole)
    primary_button.setDefault(True)
    set_variant(primary_button, "primary")
    if secondary is not None:
        box.addButton(secondary, QDialogButtonBox.RejectRole).setAutoDefault(False)
    return box, primary_button


def status_icon(passed: bool, size: int = 14) -> QIcon:
    """Filled circle with a check (pass) or an exclamation mark (needs attention)."""
    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(theme.color("success" if passed else "warning"))
    painter.drawEllipse(0, 0, size, size)
    pen = QPen(QColor("white"), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    s = size / 14
    if passed:
        painter.drawPolyline(
            [QPointF(4 * s, 7.2 * s), QPointF(6.2 * s, 9.4 * s), QPointF(10 * s, 5 * s)]
        )
    else:
        painter.drawLine(QPointF(7 * s, 3.8 * s), QPointF(7 * s, 8 * s))
        painter.drawPoint(QPointF(7 * s, 10.3 * s))
    painter.end()
    return QIcon(pixmap)


class _MarkedItemDelegate(QStyledItemDelegate):
    """Draws a small dot at the right edge of rows whose MARKED_ROLE is set."""

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        super().paint(painter, option, index)
        if not index.data(MARKED_ROLE):
            return
        size = 7
        rect: QRect = option.rect
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(theme.color("warning"))
        painter.drawEllipse(
            rect.right() - 12 - size, rect.center().y() - size // 2, size, size
        )
        painter.restore()


def sidebar_list(object_name: str, width: int) -> QListWidget:
    """Page list for sidebar dialogs (Settings, Documentation)."""
    sidebar = QListWidget()
    sidebar.setObjectName(object_name)
    sidebar.setFixedWidth(width)
    sidebar.setUniformItemSizes(True)
    sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sidebar.setTextElideMode(Qt.ElideRight)
    sidebar.setStyleSheet(_SIDEBAR_STYLE)
    sidebar.setItemDelegate(_MarkedItemDelegate(sidebar))
    return sidebar


def sidebar_item_size() -> QSize:
    return QSize(0, SIDEBAR_ROW_HEIGHT)
