from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel

from manic.constants import FONT, GREEN, RED


class StandardIndicator(QLabel):
    def __init__(self, parent=None):
        super().__init__("-- No Standard Selected --", parent)
        self.setFont(QFont(FONT, 10))
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(24)  # Reduced fixed height for more compact display
        # Match width to the combined width of data indicators (75 + 75 + spacing)
        self.setFixedWidth(154)  # Account for 4px spacing between indicators
        self.internal_standard = None
        self._update_appearance()

    def set_internal_standard(self, compound_name: str):
        """Set the internal standard compound"""
        self.internal_standard = compound_name
        self.setText(f"Internal Standard: {compound_name}")
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
