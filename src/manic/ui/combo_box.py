from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QListView, QWidget


class ComboBox(QComboBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # macOS native combo popup ignores ::item stylesheet rules unless the view is a QListView.
        self.setView(QListView())
