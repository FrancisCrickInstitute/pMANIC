from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


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
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self._label = QLabel(message)
        self._label.setObjectName("toastLabel")
        self._label.setWordWrap(True)

        self._close_button = QPushButton("×")
        self._close_button.setObjectName("toastCloseButton")
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_button.clicked.connect(self.close)

        layout.addWidget(self._label, 1)
        layout.addWidget(self._close_button, 0, Qt.AlignmentFlag.AlignTop)

        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, self.close)

    def set_message(self, message: str) -> None:
        self._label.setText(message)
