from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from manic.__version__ import APP_NAME, __version__
from manic.ui.dialog_kit import BUTTON_GAP, MARGIN, description_label, hint_label, style_dialog
from manic.ui.logo import LogoLabel


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        style_dialog(self)
        self.setFixedWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, 16)
        layout.setSpacing(8)

        logo = LogoLabel(40)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        for label in (
            hint_label(f"Version {__version__}"),
            description_label("Isotope tracing and targeted GC-MS analysis."),
            hint_label("Francis Crick Institute"),
        ):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
        layout.addSpacing(8)

        # Close is neutral: an About box has no primary action.
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.layout().setSpacing(BUTTON_GAP)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).setAutoDefault(False)
        layout.addWidget(buttons)
