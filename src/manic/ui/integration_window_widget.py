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

    def populate_fields(self, compound_dict):
        """Populate the line edit fields with compound data"""
        if compound_dict is None:
            # Clear all fields
            self._clear_fields()
            return

        # Map compound data to UI fields
        field_mappings = {
            "lo_input": compound_dict.get("loffset", ""),
            "tr_input": compound_dict.get("retention_time", ""),
            "ro_input": compound_dict.get("roffset", ""),
            "tr_window_input": compound_dict.get("tr_window", ""),
        }

        for obj_name, value in field_mappings.items():
            line_edit = self.findChild(QLineEdit, obj_name)
            if line_edit:
                line_edit.setText(str(value) if value is not None else "")

    def _clear_fields(self):
        """Clear all line edit fields"""
        for obj_name in ["lo_input", "tr_input", "ro_input", "tr_window_input"]:
            line_edit = self.findChild(QLineEdit, obj_name)
            if line_edit:
                line_edit.clear()
