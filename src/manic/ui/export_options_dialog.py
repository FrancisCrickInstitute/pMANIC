from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from manic.ui.dialog_kit import (
    MARGIN,
    SECTION_SPACING,
    button_box,
    section_label,
    style_dialog,
    title_label,
    window_title,
)


class ExportOptionsDialog(QDialog):
    """Integration method and optional sheets, chosen before the save location."""

    def __init__(
        self,
        use_legacy_integration: bool,
        offer_carbon_enrichment: bool,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(window_title("Export Data"))
        style_dialog(self)
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        layout.setSpacing(8)
        layout.addWidget(title_label("Export data"))

        layout.addSpacing(SECTION_SPACING - 8)
        layout.addWidget(section_label("Integration method"))
        self.time_radio = QRadioButton("Time-based (recommended)")
        self.legacy_radio = QRadioButton("Legacy (MATLAB-compatible unit spacing)")
        group = QButtonGroup(self)
        for radio in (self.time_radio, self.legacy_radio):
            group.addButton(radio)
            layout.addWidget(radio)
        (self.legacy_radio if use_legacy_integration else self.time_radio).setChecked(True)

        self.carbon_enrichment_check: QCheckBox | None = None
        if offer_carbon_enrichment:
            layout.addSpacing(SECTION_SPACING - 8)
            layout.addWidget(section_label("Optional sheets"))
            self.carbon_enrichment_check = QCheckBox("Include % Carbons Labelled sheet")
            layout.addWidget(self.carbon_enrichment_check)

        layout.addSpacing(SECTION_SPACING)
        buttons, _choose = button_box("Choose Location…")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def use_legacy_integration(self) -> bool:
        return self.legacy_radio.isChecked()

    def include_carbon_enrichment(self) -> bool:
        check = self.carbon_enrichment_check
        return check is not None and check.isChecked()
