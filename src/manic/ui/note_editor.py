"""The inline editor for a sample note: a small popover beside the plot it annotates."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from manic.models.sample_note import MAX_NOTE_CHARS
from manic.ui import theme
from manic.ui.chart_style import text_style
from manic.ui.sidebar_widgets import ElidedLabel

EDITOR_WIDTH = 324
_GAP = 6
_HINT = "Enter to save · Shift+Enter for a new line"


def anchored_position(anchor: QRect, size: QSize, bounds: QRect) -> QPoint:
    """Top left for a popover of ``size`` beside ``anchor``, always inside ``bounds``.

    Right of the anchor, else left, below, then above. With no free side it covers
    the anchor's lower right corner, which leaves the peak in view.
    """

    def clamp(point: QPoint) -> QPoint:
        x = max(bounds.left(), min(point.x(), bounds.right() - size.width() + 1))
        y = max(bounds.top(), min(point.y(), bounds.bottom() - size.height() + 1))
        return QPoint(x, y)

    beside = (
        QPoint(anchor.right() + 1 + _GAP, anchor.top()),
        QPoint(anchor.left() - _GAP - size.width(), anchor.top()),
        QPoint(anchor.left(), anchor.bottom() + 1 + _GAP),
        QPoint(anchor.left(), anchor.top() - _GAP - size.height()),
    )
    for point in map(clamp, beside):
        if not QRect(point, size).intersects(anchor):
            return point
    return clamp(
        QPoint(
            anchor.right() - _GAP - size.width() + 1,
            anchor.bottom() - _GAP - size.height() + 1,
        )
    )


class _NoteText(QPlainTextEdit):
    submitted = Signal()
    cancelled = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        key = event.key()
        if key == Qt.Key_Escape:
            self.cancelled.emit()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                self.insertPlainText("\n")
            else:
                self.submitted.emit()
        else:
            super().keyPressEvent(event)
            return
        event.accept()


class NoteEditor(QFrame):
    """Not a dialog: a child of the grid, so the chromatograms stay live around it.

    Emits ``saved`` with the stripped text; empty text means delete the note.
    """

    saved = Signal(str)
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("noteEditor")
        self.setAttribute(Qt.WA_StyledBackground, True)
        theme.style(
            self,
            "#noteEditor { background: @surface; border: 1px solid @border_strong;"
            " border-radius: 10px; }",
        )
        self.setFixedWidth(EDITOR_WIDTH)

        title = QLabel("Note")
        theme.style(title, text_style("text", 12, 600))
        self.sample_label = ElidedLabel(mode=Qt.TextElideMode.ElideMiddle, hover=True)
        theme.style(self.sample_label, text_style("text_tertiary", 12))
        heading = QHBoxLayout()
        heading.setSpacing(6)
        heading.addWidget(title)
        heading.addWidget(self.sample_label, stretch=1)
        # Quiet until hovered: removing is rarer than saving and sits apart from it.
        self.remove_button = QPushButton("Remove")
        self.remove_button.setToolTip("Delete this note")
        theme.style(
            self.remove_button,
            "QPushButton { color: @text_secondary; background: transparent; border: none;"
            " font-size: 12px; font-weight: 500; padding: 0px 2px; min-height: 16px; }"
            " QPushButton:hover, QPushButton:focus { color: @danger; }",
        )
        self.remove_button.clicked.connect(lambda: self.saved.emit(""))
        heading.addWidget(self.remove_button)

        self.text = _NoteText()
        self.text.setPlaceholderText("Why was this peak handled this way?")
        self.text.setTabChangesFocus(True)
        self.text.setAccessibleName("Note")
        self.text.setFixedHeight(84)
        self.text.submitted.connect(self.save)
        self.text.cancelled.connect(self.cancel)
        self.text.textChanged.connect(self._show_hint)

        self.hint = QLabel(_HINT)
        self.hint.setWordWrap(True)
        self.save_button = QPushButton("Save")
        self.save_button.setProperty("variant", "primary")
        self.save_button.clicked.connect(self.save)
        for button in (self.remove_button, self.save_button):
            button.setAutoDefault(False)
            button.setCursor(Qt.PointingHandCursor)
        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addWidget(self.hint, stretch=1)
        footer.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        layout.addLayout(heading)
        layout.addWidget(self.text)
        layout.addLayout(footer)
        self._show_hint()
        self.hide()

    def open(self, sample_name: str, note: str) -> None:
        self.sample_label.setText(sample_name)
        self.text.setPlainText(note)
        self.text.moveCursor(self.text.textCursor().MoveOperation.End)
        self.remove_button.setVisible(bool(note))
        self._show_hint()
        self.adjustSize()
        self.show()
        self.raise_()
        self.text.setFocus(Qt.PopupFocusReason)
        # Again once the menu that opened this has closed: a closing menu hands focus back.
        QTimer.singleShot(0, self._focus_text)

    def _focus_text(self) -> None:
        if self.isVisible():
            self.text.setFocus(Qt.PopupFocusReason)

    def place(self, anchor: QRect, bounds: QRect) -> None:
        self.move(anchored_position(anchor, self.size(), bounds))

    def save(self) -> None:
        text = self.text.toPlainText().strip()
        if len(text) > MAX_NOTE_CHARS:
            self.hint.setText(f"Too long for a spreadsheet cell: {MAX_NOTE_CHARS:,} characters at most")
            theme.style(self.hint, text_style("danger", 11))
            return
        self.saved.emit(text)

    def cancel(self) -> None:
        self.cancelled.emit()
        self.hide()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.key() == Qt.Key_Escape:
            self.cancel()
            event.accept()
            return
        super().keyPressEvent(event)

    def _show_hint(self) -> None:
        self.hint.setText(_HINT)
        theme.style(self.hint, text_style("text_tertiary", 11))
