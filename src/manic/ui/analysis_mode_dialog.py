from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from manic.models.analysis import AnalysisMode


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

        labelled = QPushButton("Labelled isotope-tracing analysis")
        labelled.setToolTip(
            "Analyse consecutive M+0…M+n isotopologues with natural-abundance correction."
        )
        labelled.clicked.connect(
            lambda: self._choose(AnalysisMode.LABELLED)
        )
        layout.addWidget(labelled)

        labelled_help = QLabel(
            "For stable-isotope tracing: M+0, M+1 and later isotopologues are "
            "measured and corrected for natural isotope abundance."
        )
        labelled_help.setWordWrap(True)
        labelled_help.setIndent(12)
        layout.addWidget(labelled_help)

        unlabelled = QPushButton("Unlabelled targeted analysis")
        unlabelled.setToolTip(
            "Quantify one diagnostic ion and use qualifier ions to support identity."
        )
        unlabelled.clicked.connect(
            lambda: self._choose(AnalysisMode.UNLABELLED)
        )
        layout.addWidget(unlabelled)

        unlabelled_help = QLabel(
            "For targeted GC-MS profiling: one quantifier ion provides the response "
            "and qualifier ions check retention and ion-ratio consistency."
        )
        unlabelled_help.setWordWrap(True)
        unlabelled_help.setIndent(12)
        layout.addWidget(unlabelled_help)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        labelled.setDefault(True)
        labelled.setFocus(Qt.OtherFocusReason)

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
