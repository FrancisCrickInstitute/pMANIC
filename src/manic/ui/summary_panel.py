"""The compound's summary charts in a column beside the plot grid."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from manic.models.analysis import AnalysisMode

from .isotopologue_ratio_widget import IsotopologueRatioWidget
from .targeted_qc_widget import TargetedQcWidget
from .total_abundance_widget import TotalAbundanceWidget

# Narrow enough to leave the grid two Comfortable columns in a 1024 px window.
SUMMARY_MIN_WIDTH = 232


def summary_width_for(window_width: int) -> int:
    """The panel's first width: 300 px on a laptop, up to 400 px on a large monitor."""
    return min(max(window_width * 3 // 20, 300), 400)


class SummaryPanel(QWidget):
    """Label incorporation (Identity when unlabelled) over Peak area, both always in view."""

    def __init__(self, analysis_mode: AnalysisMode | str = AnalysisMode.LABELLED):
        super().__init__()
        self.setObjectName("summaryPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(SUMMARY_MIN_WIDTH)
        self.isotopologue_ratios = IsotopologueRatioWidget()
        self.targeted_qc = TargetedQcWidget()
        self.total_abundance = TotalAbundanceWidget()
        unlabelled = AnalysisMode.coerce(analysis_mode) is AnalysisMode.UNLABELLED
        first, other = (
            (self.targeted_qc, self.isotopologue_ratios)
            if unlabelled
            else (self.isotopologue_ratios, self.targeted_qc)
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
        layout.setSpacing(16)
        # Each chart grows to its rows; once both have, the room left sits below them.
        layout.addWidget(first, 1)
        layout.addWidget(self.total_abundance, 1)
        layout.addStretch(0)
        # Unused in this mode, but the window clears and highlights all three alike.
        other.setParent(self)
        other.hide()
