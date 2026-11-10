"""The selected compound's deconvolution choices, as the sidebar edits them."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from manic.models.sample_fit_type import FIT_TYPE_LABELS
from manic.ui.combo_box import ComboBox

LEVEL_OPTIONS = [
    ("Off", "off"),
    ("Level 1 (fastest)", "1"),
    ("Level 2", "2"),
    ("Level 3", "3"),
    ("Level 4 (default)", "4"),
    ("Level 5", "5"),
    ("Level 6", "6"),
    ("Level 7 (finest)", "7"),
]
FIT_OPTIONS = [(label, value) for value, label in FIT_TYPE_LABELS.items()]
GATE_OPTIONS = [
    ("Balanced (default)", "balanced"),
    ("Lenient", "lenient"),
    ("Aggressive", "aggressive"),
    ("Off", "off"),
]
LEVEL_HELP = (
    "Higher levels split closer overlaps and weaker shoulders, but run "
    "slower and are more likely to split noise. Levels 5 to 7 also fit "
    "the EMG shape and look for shoulders."
)
FIT_HELP = (
    "Auto fits each shape the resolution level allows and keeps the best "
    "by BIC. A single shape is faster: Gaussian for symmetric peaks, "
    "Bi-Gaussian for unequal left and right widths, EMG for tailing peaks."
)
GATE_HELP = (
    "Skips fitting where the trace looks like noise; those peaks show the "
    "raw trace. Lenient skips only near-pure noise. Aggressive fits only "
    "clearly smooth peaks, which is faster but may skip weak real peaks. "
    "Off always fits."
)


def deconvolution_summary(level: str, fit: str, gate: str) -> str:
    """"Level 4 · Auto", "Level 6 · EMG · Lenient gate" or "Off": short enough for a sidebar
    heading, so the default gate goes unsaid."""
    if level == "off":
        return "Off"
    parts = [f"Level {level}", FIT_TYPE_LABELS[fit]]
    if gate != "balanced":
        parts.append(f"{dict((value, label) for label, value in GATE_OPTIONS)[gate]} gate")
    return " · ".join(parts)


class DeconvolutionControls(QWidget):
    """Resolution, fit type and noise gate; a pick applies at once, as Baseline correction does."""

    changed = Signal(str, str, str)  # level, fit type, noise gate

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        rows = QGridLayout(self)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setHorizontalSpacing(12)
        rows.setVerticalSpacing(4)
        rows.setColumnStretch(1, 1)
        self.level_combo, self.fit_combo, self.gate_combo = self._combos = [
            self._row(rows, row, *spec)
            for row, spec in enumerate(
                [
                    ("Resolution", "sidebarDeconvolutionLevel", LEVEL_OPTIONS, LEVEL_HELP),
                    ("Fit type", "sidebarDeconvolutionFit", FIT_OPTIONS, FIT_HELP),
                    ("Noise gate", "sidebarDeconvolutionGate", GATE_OPTIONS, GATE_HELP),
                ]
            )
        ]
        self.show_settings(None)

    def _row(self, rows: QGridLayout, row: int, text: str, name: str, options, tip: str) -> ComboBox:
        label = QLabel(text)
        combo = ComboBox()
        combo.setObjectName(name)
        for option, value in options:
            combo.addItem(option, value)
        for widget in (label, combo):
            widget.setToolTip(tip)
        label.setBuddy(combo)
        combo.activated.connect(self._on_picked)  # a user's pick only, never show_settings
        rows.addWidget(label, row, 0)
        rows.addWidget(combo, row, 1)
        return combo

    def settings(self) -> tuple[str, str, str]:
        return tuple(combo.currentData() for combo in self._combos)

    def show_settings(self, settings: tuple[str, str, str] | None) -> None:
        """Show a compound's saved settings; None, with no compound, disables the rows."""
        for combo, value in zip(self._combos, settings or ("off", "auto", "balanced")):
            with QSignalBlocker(combo):
                combo.setCurrentIndex(combo.findData(value))
        self.level_combo.setEnabled(settings is not None)
        on = settings is not None and self.level_combo.currentData() != "off"
        self.fit_combo.setEnabled(on)
        self.gate_combo.setEnabled(on)

    def _on_picked(self, _index: int) -> None:
        self.changed.emit(*self.settings())
