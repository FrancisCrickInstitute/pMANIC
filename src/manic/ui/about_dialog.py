from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from manic.__version__ import APP_NAME, __version__
from manic.utils.paths import resource_path


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedWidth(380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(8)

        logo = QLabel()
        pixmap = QPixmap(resource_path("resources", "manic_logo.png"))
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaledToHeight(56, Qt.TransformationMode.SmoothTransformation)
            )
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        version = QLabel(f"Version {__version__}")
        version.setProperty("role", "secondary")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)
        layout.addSpacing(8)

        description = QLabel(
            "Isotope-tracing and targeted analysis of GC-MS data. Define "
            "compounds, load raw CDF files, review each sample's peaks and "
            "export corrected results."
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(description)

        credit = QLabel("Francis Crick Institute")
        credit.setProperty("role", "hint")
        credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(4)
        layout.addWidget(credit)
        layout.addSpacing(12)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).setDefault(True)
        layout.addWidget(buttons)
