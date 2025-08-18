from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from manic.utils.utils import load_stylesheet


class IntegrationWindow(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Selected Plots: All", parent)
        self.setObjectName("integrationWindow")
        self._build_ui()

        # Load and apply the stylesheet
        stylesheet = load_stylesheet("src/manic/resources/integration_window.qss")
        self.setStyleSheet(stylesheet)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        for label_text, obj_name in [
            ("Left Offset", "lo_input"),
            ("tR", "tr_input"),
            ("Right Offset", "ro_input"),
            ("tR Window", "tr_window_input"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("QLabel { background-color: #F0F0F0; }")
            edt = QLineEdit()
            edt.setObjectName(obj_name)
            row.addWidget(lbl)
            row.addWidget(edt, 1)
            layout.addLayout(row)

        self.apply_button = QPushButton("Apply")
        self.apply_button.setObjectName("ApplyButton")
        layout.addWidget(self.apply_button)
