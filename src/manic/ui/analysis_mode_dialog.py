from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPushButton,
    QVBoxLayout,
)

from manic.models.analysis import AnalysisMode
from manic.ui.dialog_kit import (
    MARGIN,
    description_label,
    style_dialog,
    title_label,
    window_title,
)

_MODE_CHOICES = (
    (
        AnalysisMode.LABELLED,
        "Labelled isotope-tracing analysis",
        "M+0, M+1 and later isotopologues are measured and corrected for "
        "natural isotope abundance.",
    ),
    (
        AnalysisMode.UNLABELLED,
        "Unlabelled targeted analysis",
        "One quantifier ion provides the response and qualifier ions check "
        "retention and ion-ratio consistency.",
    ),
)


class AnalysisModeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_mode: AnalysisMode | None = None
        self.setWindowTitle(window_title("Choose Analysis Mode"))
        style_dialog(self)
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        layout.setSpacing(8)
        layout.addWidget(title_label("What type of analysis are you performing?"))

        first_button = None
        for mode, button_text, description in _MODE_CHOICES:
            layout.addSpacing(8)
            button = QPushButton(button_text)
            button.clicked.connect(lambda _c, m=mode: self._choose(m))
            layout.addWidget(button)
            if first_button is None:
                first_button = button

            layout.addWidget(description_label(description))

        layout.addSpacing(8)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        first_button.setDefault(True)

    @property
    def selected_mode(self) -> AnalysisMode | None:
        return self._selected_mode

    def _choose(self, mode: AnalysisMode) -> None:
        self._selected_mode = mode
        self.accept()


def choose_analysis_mode(parent=None) -> AnalysisMode | None:
    dialog = AnalysisModeDialog(parent)
    if dialog.exec() != QDialog.Accepted:
        return None
    return dialog.selected_mode
