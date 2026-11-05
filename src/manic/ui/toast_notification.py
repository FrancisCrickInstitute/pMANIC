from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QStatusBar, QWidget


class ToastNotification(QWidget):
    def __init__(
        self,
        message: str,
        parent: QWidget | None = None,
        *,
        timeout_ms: int = 6000,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("toastNotification")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 6, 2)
        layout.setSpacing(6)

        self._label = QLabel(message)
        self._label.setObjectName("toastLabel")

        self._close_button = QPushButton("×")
        self._close_button.setObjectName("toastCloseButton")
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_button.setToolTip("Dismiss")
        self._close_button.clicked.connect(self.close)

        layout.addWidget(self._label, 1)
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
    toast.adjustSize()
    height = min(toast.sizeHint().height(), bar.height() - 4)
    toast.resize(toast.sizeHint().width(), height)
    toast.move((bar.width() - toast.width()) // 2, (bar.height() - height) // 2)


def show_status_toast(
    bar: QStatusBar, message: str, timeout_ms: int = 7000
) -> ToastNotification:
    """A short-lived message centred in the status bar, so it never covers a plot."""
    for old in bar.findChildren(ToastNotification):
        old.close()
    toast = ToastNotification(message, parent=bar, timeout_ms=timeout_ms)
    toast.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    _KeepCentred(toast, bar)
    _centre(toast, bar)
    toast.show()
    toast.raise_()
    return toast
