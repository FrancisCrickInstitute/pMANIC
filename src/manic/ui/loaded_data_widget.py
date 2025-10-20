import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from manic.constants import GREEN, RED, create_font


class LoadedDataWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("loadedDataWidget")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Store references to labels for easier updates
        # Compounds on the left, Raw Data on the right
        self.compounds_label = self._create_status_label("Compounds", RED)
        self.raw_data_label = self._create_status_label("Raw Data", RED)

        layout.addWidget(self.compounds_label)
        layout.addWidget(self.raw_data_label)

    def _create_status_label(self, text: str, color) -> QLabel:
        """Create a consistently styled status label with platform-specific sizing"""
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setAutoFillBackground(True)
        label.setFont(create_font(10))  # Use cross-platform font
        
        # Platform-specific sizing for better text fit
        if sys.platform == "win32":
            # Windows needs more horizontal space due to Arial font width
            label.setFixedSize(85, 22)  # Wider and slightly taller
        else:
            # macOS and Linux use original dimensions
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
