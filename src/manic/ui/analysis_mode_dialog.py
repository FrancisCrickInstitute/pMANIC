from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QPushButton,
    QVBoxLayout,
)

from manic.models.analysis import AnalysisMode
from manic.ui.dialog_kit import (
    MARGIN,
    hint_label,
    style_dialog,
    title_label,
    window_title,
)

_MODE_CHOICES = (
    (AnalysisMode.LABELLED, "Labelled", "Isotope tracing, M+0…M+n"),
    (AnalysisMode.UNLABELLED, "Unlabelled", "Quantifier and qualifier ions"),
)


class AnalysisModeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_mode: AnalysisMode | None = None
        self.setWindowTitle(window_title("Choose Analysis Mode"))
        style_dialog(self)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        layout.setSpacing(16)
        layout.addWidget(title_label("What are you analysing?"))

        choices = QGridLayout()
        choices.setHorizontalSpacing(12)
        choices.setVerticalSpacing(8)
        for row, (mode, name, caption) in enumerate(_MODE_CHOICES):
            button = QPushButton(name)
            # Neither mode is remembered, so neither may become the default.
            button.setAutoDefault(False)
            button.setMinimumWidth(120)
            button.clicked.connect(lambda _c, m=mode: self._choose(m))
            choices.addWidget(button, row, 0)
            caption_label = hint_label(caption)
            caption_label.setWordWrap(False)
            choices.addWidget(caption_label, row, 1)
        choices.setColumnStretch(1, 1)
        layout.addLayout(choices)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Cancel).setAutoDefault(False)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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
