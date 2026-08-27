from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from manic.models.analysis import AnalysisMode

_MODE_CHOICES = (
    (
        AnalysisMode.LABELLED,
        "Labelled isotope-tracing analysis",
        "Analyse consecutive M+0…M+n isotopologues with natural-abundance correction.",
        "For stable-isotope tracing: M+0, M+1 and later isotopologues are "
        "measured and corrected for natural isotope abundance.",
    ),
    (
        AnalysisMode.UNLABELLED,
        "Unlabelled targeted analysis",
        "Quantify one diagnostic ion and use qualifier ions to support identity.",
        "For targeted GC-MS profiling: one quantifier ion provides the response "
        "and qualifier ions check retention and ion-ratio consistency.",
    ),
)


class AnalysisModeDialog(QDialog):
    """Choose the analytical workflow before a database session is cleared."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_mode: AnalysisMode | None = None
        self.setWindowTitle("Choose Analysis Mode")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        heading = QLabel("What type of analysis are you performing?")
        heading.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(heading)

        description = QLabel(
            "The mode is fixed for this analysis so that compounds and results "
            "cannot be interpreted using the wrong scientific workflow."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        first_button = None
        for mode, button_text, tooltip, help_text in _MODE_CHOICES:
            button = QPushButton(button_text)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda _c, m=mode: self._choose(m))
            layout.addWidget(button)
            if first_button is None:
                first_button = button

            help_label = QLabel(help_text)
            help_label.setWordWrap(True)
            help_label.setIndent(12)
            layout.addWidget(help_label)

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
