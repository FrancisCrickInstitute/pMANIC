from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.manic.utils.constants import FONT, GREEN, RED


class LoadedDataWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("loadedDataWidget")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Store references to labels for easier updates
        self.raw_data_label = self._create_status_label("Raw Data", RED)
        self.compounds_label = self._create_status_label("Compounds", RED)

        layout.addWidget(self.raw_data_label)
        layout.addWidget(self.compounds_label)

    def _create_status_label(self, text: str, color) -> QLabel:
        """Create a consistently styled status label"""
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setAutoFillBackground(True)
        label.setFont(QFont(FONT, 10))
        label.setFixedSize(75, 20)
        self._apply_color(label, color)
        return label

    def _apply_color(self, label: QLabel, color):
        """Apply color styling to a label"""
        label.setStyleSheet(
            f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, "
            f"{color.alpha() / 255}); color: black; border-radius: 10px;"
        )

    def update_status(self, raw_loaded: bool, compounds_loaded: bool):
        """Update the visual status of both indicators"""
        self._apply_color(self.raw_data_label, GREEN if raw_loaded else RED)
        self._apply_color(self.compounds_label, GREEN if compounds_loaded else RED)
