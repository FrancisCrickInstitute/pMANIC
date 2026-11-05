from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QStatusBar, QWidget

from manic.ui.sidebar_widgets import ElidedLabel

# Room the toast leaves at each end of the status bar.
TOAST_MARGIN = 8


class ToastNotification(QWidget):
    def __init__(
        self,
        message: str,
        parent: QWidget | None = None,
        *,
        timeout_ms: int = 6000,
        action: tuple[str, Callable[[], None]] | None = None,
        hover: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("toastNotification")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 6, 2)
        layout.setSpacing(6)

        # A long file name gives up its middle; the buttons always keep their room.
        self._label = ElidedLabel(message, mode=Qt.TextElideMode.ElideMiddle, hover=hover or True)
        self._label.setObjectName("toastLabel")

        self._close_button = QPushButton("×")
        self._close_button.setObjectName("toastCloseButton")
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_button.setToolTip("Dismiss")
        self._close_button.clicked.connect(self.close)

        layout.addWidget(self._label, 1)
        if action is not None:
            text, callback = action
            self.action_button = QPushButton(text)
            self.action_button.setObjectName("toastActionButton")
            self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.action_button.clicked.connect(callback)
            self.action_button.clicked.connect(self.close)
            layout.addWidget(self.action_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._close_button, 0, Qt.AlignmentFlag.AlignVCenter)

        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, self.close)


class _KeepCentred(QObject):
    def __init__(self, toast: ToastNotification, bar: QStatusBar):
        super().__init__(toast)
        self._toast = toast
        bar.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            _centre(self._toast, watched)
        return False


def _centre(toast: ToastNotification, bar: QStatusBar) -> None:
    label = toast._label
    # The label takes no width of its own in the layout; ask for its whole text.
    natural = toast.sizeHint().width() + label.fontMetrics().horizontalAdvance(label.full_text()) + 2
    width = min(natural, bar.width() - 2 * TOAST_MARGIN)
    height = min(toast.sizeHint().height(), bar.height() - 4)
    toast.resize(width, height)
    toast.move((bar.width() - width) // 2, (bar.height() - height) // 2)


def show_status_toast(
    bar: QStatusBar,
    message: str,
    timeout_ms: int = 7000,
    action: tuple[str, Callable[[], None]] | None = None,
    hover: str | None = None,
) -> ToastNotification:
    """A short-lived message centred in the status bar, so it never covers a plot.

    A message too long for the bar is cut in the middle and shown whole, or as
    ``hover``, under the pointer."""
    for old in bar.findChildren(ToastNotification):
        old.close()
    toast = ToastNotification(
        message, parent=bar, timeout_ms=timeout_ms, action=action, hover=hover
    )
    toast.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    _KeepCentred(toast, bar)
    _centre(toast, bar)
    toast.show()
    toast.raise_()
    return toast
