import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from manic.constants import GREEN, RED, create_font


class StandardIndicator(QLabel):
    def __init__(self, parent=None):
        super().__init__("-- No Standard Selected --", parent)
        self.setFont(create_font(10))
        self.setAlignment(Qt.AlignCenter)

        # Platform-specific sizing to match LoadedDataWidget indicators
        if sys.platform == "win32":
            # Windows: Match wider labels (85 + 85 + 4px spacing)
            self.setFixedSize(174, 22)
        else:
            # macOS and Linux: Match original labels (75 + 75 + 4px spacing)
            self.setFixedSize(154, 20)
        self.internal_standard = None
        self._update_appearance()

    def set_internal_standard(self, compound_name: str):
        """Set the internal standard compound"""
        self.internal_standard = compound_name
        self.setText(f"-- {compound_name} --")
        self._update_appearance()

    def clear_internal_standard(self):
        """Clear the internal standard selection"""
        self.internal_standard = None
        self.setText("- No Standard Selected -")
        self._update_appearance()

    def _update_appearance(self):
        """Update the widget appearance based on whether a standard is selected"""
        if self.internal_standard:
            # Green when selected - matching LoadedDataWidget style
            color = GREEN
            self.setStyleSheet(
                f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, "
                f"{color.alpha() / 255}); color: black; border-radius: 10px; padding: 2px;"
            )
        else:
            # Red when not selected - matching LoadedDataWidget style
            color = RED
            self.setStyleSheet(
                f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, "
                f"{color.alpha() / 255}); color: black; border-radius: 10px; padding: 2px;"
            )
