from __future__ import annotations

from PySide6.QtCore import Qt, QSignalBlocker, QSize, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from manic.models.analysis import AnalysisMode
from manic.models.sample_fit_type import FIT_TYPE_LABELS, get_sample_fit_types
from manic.ui.window_placement import show_over_parent

_ALL_MODES = frozenset(AnalysisMode)


def _count_samples(names: list[str]) -> str:
    return "1 sample" if len(names) == 1 else f"{len(names)} samples"

_SPIN_STYLE = (
    "QDoubleSpinBox { background-color: white; color: #212529; }"
    "QDoubleSpinBox:disabled { background-color: #f8f9fa; color: #adb5bd; "
    "border: 1px solid #e9ecef; }"
)
_COMBO_STYLE = (
    "QComboBox { background-color: white; color: #212529; }"
    "QComboBox:disabled { background-color: #f8f9fa; color: #adb5bd; "
    "border: 1px solid #e9ecef; }"
)
_HINT_STYLE = "color: gray; font-style: italic; padding: 0px;"

_DECONVOLUTION_LEVEL_OPTIONS = [
    ("Off - no chromatographic deconvolution", "off"),
    ("Level 1 - coarsest, fastest, obvious overlaps only", "1"),
    ("Level 2 - conservative splitting", "2"),
    ("Level 3 - moderate resolution", "3"),
    ("Level 4 - default, high-resolution overlap splitting", "4"),
    ("Level 5 - higher resolution, EMG model + shoulder detection", "5"),
    ("Level 6 - very high resolution, shoulder detection", "6"),
    ("Level 7 - finest, slowest, weakest shoulders considered", "7"),
]
_DECONVOLUTION_FIT_OPTIONS = [
    ("Auto - compare peak shapes and pick the best by BIC", "auto"),
    ("Gaussian - symmetric peaks only", "gaussian"),
    ("Bi-Gaussian - asymmetric (separate left/right widths)", "bi_gaussian"),
    ("EMG - exponentially modified Gaussian (tailing)", "emg"),
]
_DECONVOLUTION_GATE_OPTIONS = [
    ("Balanced - skip noise-only peaks (recommended)", "balanced"),
    ("Lenient - only skip near-pure noise", "lenient"),
    ("Aggressive - only fit clearly smooth peaks", "aggressive"),
    ("Off - always attempt a fit", "off"),
]


def _form_layout() -> QFormLayout:
    form = QFormLayout()
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(10)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return form


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(_HINT_STYLE)
    return label


def _fill_combo(combo: QComboBox, options: list[tuple[str, str]], current: str) -> None:
    combo.clear()
    for label, value in options:
        combo.addItem(label, value)
    combo.setCurrentIndex(
        next((i for i, (_, value) in enumerate(options) if value == current), 0)
    )


class SettingsPage(QWidget):
    title: str = ""
    dirty_changed = Signal(bool)

    def __init__(self, host, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.host = host
        self._dirty = False
        self._inputs: list[QWidget] = []

    def load(self) -> None:
        raise NotImplementedError

    def save(self) -> None:
        raise NotImplementedError

    def is_dirty(self) -> bool:
        return self._dirty

    def editable(self) -> tuple[bool, str]:
        return True, ""

    def unsaved_hint(self) -> str:
        return "Unsaved changes"

    def set_inputs_enabled(self, enabled: bool) -> None:
        for widget in self._inputs:
            widget.setEnabled(enabled)

    def _mark_dirty(self, *_args) -> None:
        if not self._dirty:
            self._dirty = True
            self.dirty_changed.emit(True)

    def _clear_dirty(self) -> None:
        if self._dirty:
            self._dirty = False
            self.dirty_changed.emit(False)


class MassTolerancePage(SettingsPage):
    title = "Mass Tolerance"

    def __init__(self, host, parent: QWidget | None = None) -> None:
        super().__init__(host, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        info = QLabel("Set the mass tolerance (±Da) for EIC extraction:")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = _form_layout()
        self.spin = QDoubleSpinBox()
        self.spin.setObjectName("massToleranceSpin")
        self.spin.setRange(0.01, 1.0)
        self.spin.setSingleStep(0.01)
        self.spin.setDecimals(3)
        self.spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin.setStyleSheet(_SPIN_STYLE)
        self.spin.valueChanged.connect(self._mark_dirty)
        self._inputs.append(self.spin)
        form.addRow("Mass tolerance (Da)", self.spin)
        layout.addLayout(form)
        layout.addStretch()

    def load(self) -> None:
        with QSignalBlocker(self.spin):
            self.spin.setValue(self.host.mass_tolerance)
        self._clear_dirty()

    def save(self) -> None:
        self.host.apply_mass_tolerance(self.spin.value())


class PeakValidationPage(SettingsPage):
    title = "Peak Validation"

    def __init__(self, host, parent: QWidget | None = None) -> None:
        super().__init__(host, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        info = QLabel(
            "Set the minimum peak area threshold as a fraction of the internal standard "
            "reference peak area.\n"
            "Peaks below this threshold will be highlighted with a red background.\n"
            "Peak validation compares compound total area vs the internal standard "
            "reference peak."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = _form_layout()
        self.spin = QDoubleSpinBox()
        self.spin.setObjectName("minPeakAreaSpin")
        self.spin.setRange(0.001, 1.0)
        self.spin.setSingleStep(0.001)
        self.spin.setDecimals(3)
        self.spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin.setStyleSheet(_SPIN_STYLE)
        self.spin.valueChanged.connect(self._mark_dirty)
        self._inputs.append(self.spin)
        form.addRow("Minimum area ratio", self.spin)
        layout.addLayout(form)
        layout.addWidget(
            _hint(
                "(e.g. 0.005 = 0.5% of the internal standard reference peak area)"
            )
        )
        layout.addStretch()

    def load(self) -> None:
        with QSignalBlocker(self.spin):
            self.spin.setValue(self.host.min_peak_height_ratio)
        self._clear_dirty()

    def save(self) -> None:
        self.host.apply_min_peak_area_ratio(self.spin.value())


class QualifierRatioPage(SettingsPage):
    title = "Qualifier Ratios"
    _ORDINALS = (1, 2)

    def __init__(self, host, parent: QWidget | None = None) -> None:
        super().__init__(host, parent)
        self._compound_name: str | None = None
        self._present_ordinals: tuple[int, ...] = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        info = QLabel(
            "Tolerance is a fraction of the expected ratio (0.25 = ±25%). "
            "An unset tolerance leaves that qualifier unassessed in Identity QC "
            "and the Qualifier QC sheet."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.compound_label = QLabel("Compound: none selected")
        layout.addWidget(self.compound_label)

        form = _form_layout()
        self._labels: dict[int, QLabel] = {}
        self._ratio_labels: dict[int, QLabel] = {}
        self._spins: dict[int, QDoubleSpinBox] = {}
        for ordinal in self._ORDINALS:
            label = QLabel()
            spin = QDoubleSpinBox()
            spin.setObjectName(f"qualifier{ordinal}ToleranceSpin")
            spin.setRange(0.0, 10.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.01)
            spin.setSpecialValueText("Not set")
            spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            spin.setStyleSheet(_SPIN_STYLE)
            spin.valueChanged.connect(self._mark_dirty)
            ratio_label = QLabel()
            ratio_label.setStyleSheet(_HINT_STYLE)
            field = QWidget()
            field_layout = QHBoxLayout(field)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.addWidget(spin, stretch=1)
            field_layout.addWidget(ratio_label)
            form.addRow(label, field)
            self._labels[ordinal] = label
            self._ratio_labels[ordinal] = ratio_label
            self._spins[ordinal] = spin
            self._inputs.append(spin)
        layout.addLayout(form)
        layout.addStretch()

    def editable(self) -> tuple[bool, str]:
        name = self.host.selected_compound_name()
        if not name:
            return (
                False,
                "Load compounds and select one in the toolbar to change this.",
            )
        if not self.host.qualifier_channels(name):
            return False, f"{name} has no qualifier ions."
        return True, ""

    def unsaved_hint(self) -> str:
        selected = self.host.selected_compound_name()
        if selected == self._compound_name:
            return f"Unsaved changes for {self._compound_name}"
        return (
            f"Unsaved changes for {self._compound_name}. "
            f"The toolbar now selects {selected or 'nothing'}; Save still writes to "
            f"{self._compound_name}."
        )

    def load(self) -> None:
        self._compound_name = self.host.selected_compound_name()
        self.compound_label.setText(
            f"Compound: {self._compound_name or 'none selected'}"
        )
        channels = {
            channel.ordinal: channel
            for channel in self.host.qualifier_channels(self._compound_name)
        }
        self._present_ordinals = tuple(sorted(channels))
        for ordinal, spin in self._spins.items():
            label = self._labels[ordinal]
            channel = channels.get(ordinal)
            visible = channel is not None
            label.setVisible(visible)
            spin.parentWidget().setVisible(visible)
            if channel is None:
                continue
            ratio = (
                f"{channel.expected_ratio:g}"
                if channel.expected_ratio is not None
                else "not set"
            )
            label.setText(f"Qualifier {channel.ordinal} (m/z {channel.mz:g})")
            self._ratio_labels[ordinal].setText(f"expected ratio {ratio}")
            with QSignalBlocker(spin):
                spin.setValue(
                    0.0 if channel.ratio_tolerance is None else channel.ratio_tolerance
                )
        self._clear_dirty()

    def save(self) -> None:
        if not self._compound_name:
            return
        tolerances = {
            ordinal: None if spin.value() == 0.0 else spin.value()
            for ordinal, spin in self._spins.items()
            if ordinal in self._present_ordinals
        }
        self.host.apply_qualifier_tolerances(self._compound_name, tolerances)


class IntegrationPage(SettingsPage):
    title = "Integration"

    def __init__(self, host, parent: QWidget | None = None) -> None:
        super().__init__(host, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.time_radio = QRadioButton("Time-based (recommended)")
        self.time_radio.setObjectName("integrationTimeRadio")
        self.legacy_radio = QRadioButton("Legacy")
        self.legacy_radio.setObjectName("integrationLegacyRadio")
        group = QButtonGroup(self)
        group.addButton(self.time_radio)
        group.addButton(self.legacy_radio)
        self.time_radio.toggled.connect(self._on_radio_toggled)
        self.legacy_radio.toggled.connect(self._on_radio_toggled)
        self._inputs.extend([self.time_radio, self.legacy_radio])

        layout.addWidget(self.time_radio)
        layout.addWidget(self.legacy_radio)
        layout.addWidget(
            _hint(
                "The change will only apply to graphs in the GUI. Integration method "
                "for export is chosen at the time of export. See documentation for "
                "detailed information about integration methods."
            )
        )
        layout.addStretch()

    def _on_radio_toggled(self, checked: bool) -> None:
        if checked:
            self._mark_dirty()

    def load(self) -> None:
        with QSignalBlocker(self.time_radio), QSignalBlocker(self.legacy_radio):
            if self.host.use_legacy_integration:
                self.legacy_radio.setChecked(True)
            else:
                self.time_radio.setChecked(True)
        self._clear_dirty()

    def save(self) -> None:
        self.host.apply_use_legacy_integration(self.legacy_radio.isChecked())


class NaturalAbundancePage(SettingsPage):
    title = "Natural Abundance"

    def __init__(self, host, parent: QWidget | None = None) -> None:
        super().__init__(host, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.preview_check = QCheckBox(
            "Preview natural-abundance-corrected data in plots"
        )
        self.preview_check.setObjectName("natAbundancePreviewCheck")
        self.preview_check.toggled.connect(self._mark_dirty)
        self._inputs.append(self.preview_check)
        layout.addWidget(self.preview_check)
        layout.addWidget(_hint("Exports always apply the correction."))
        layout.addStretch()

    def load(self) -> None:
        with QSignalBlocker(self.preview_check):
            self.preview_check.setChecked(bool(self.host.preview_nat_abundance))
        self._clear_dirty()

    def save(self) -> None:
        self.host.apply_nat_abundance_preview(self.preview_check.isChecked())


class InternalStandardPage(SettingsPage):
    title = "Internal Standard"

    def __init__(self, host, parent: QWidget | None = None) -> None:
        super().__init__(host, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        info = QLabel(
            "Select which internal standard isotopologue peak is the reference peak (M+N).\n"
            "This reference peak is used for peak validation, abundance normalization, and MRRF calculations.\n"
            "Changing the internal standard compound resets this setting to M0."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.standard_label = QLabel("Internal standard: none")
        layout.addWidget(self.standard_label)

        form = _form_layout()
        self.combo = QComboBox()
        self.combo.setObjectName("internalStandardCombo")
        self.combo.setStyleSheet(_COMBO_STYLE)
        self.combo.currentIndexChanged.connect(self._mark_dirty)
        self._inputs.append(self.combo)
        form.addRow("Reference peak", self.combo)
        layout.addLayout(form)
        layout.addStretch()

    def editable(self) -> tuple[bool, str]:
        name = self.host.internal_standard_name()
        if not name:
            return False, "Select an internal standard in the toolbar to change this."
        if self.host.internal_standard_label_atoms() == 0:
            return (
                False,
                f"'{name}' has no label atoms, so only M+0 can be the reference peak.",
            )
        return True, ""

    def load(self) -> None:
        name = self.host.internal_standard_name()
        self.standard_label.setText(f"Internal standard: {name or 'none'}")
        with QSignalBlocker(self.combo):
            self.combo.clear()
            if name:
                label_atoms = self.host.internal_standard_label_atoms()
                for idx in range(label_atoms + 1):
                    self.combo.addItem(f"M+{idx}", idx)
                current = self.host.internal_standard_reference_isotope
                self.combo.setCurrentIndex(current if 0 <= current <= label_atoms else 0)
            else:
                self.combo.addItem("M+0", 0)
        self._clear_dirty()

    def save(self) -> None:
        self.host.apply_internal_standard_reference_isotope(self.combo.currentData())


class DeconvolutionPage(SettingsPage):
    title = "Deconvolution"
    _MIXED = "_mixed"

    def __init__(self, host, parent: QWidget | None = None) -> None:
        super().__init__(host, parent)
        self._compound_name: str | None = None
        self._sample_names: list[str] = []
        self._sample_section_touched = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        info = QLabel(
            "Choose how MANIC fits and separates overlapping chromatographic peaks "
            "before integration. Resolution, fit type, and noise gate are saved per "
            "compound. A sample can override the curve fit from the plot context menu "
            "or the Per-sample curve fit section below."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.compound_label = QLabel("Compound: none selected")
        layout.addWidget(self.compound_label)

        form = _form_layout()
        self.level_combo = QComboBox()
        self.level_combo.setObjectName("deconvolutionLevelCombo")
        self.level_combo.setStyleSheet(_COMBO_STYLE)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        form.addRow("Resolution", self.level_combo)

        self.fit_combo = QComboBox()
        self.fit_combo.setObjectName("deconvolutionFitCombo")
        self.fit_combo.setStyleSheet(_COMBO_STYLE)
        self.fit_combo.currentIndexChanged.connect(self._mark_dirty)
        form.addRow("Fit type", self.fit_combo)

        self.gate_combo = QComboBox()
        self.gate_combo.setObjectName("deconvolutionGateCombo")
        self.gate_combo.setStyleSheet(_COMBO_STYLE)
        self.gate_combo.currentIndexChanged.connect(self._mark_dirty)
        form.addRow("Noise gate", self.gate_combo)
        layout.addLayout(form)

        self._inputs.extend([self.level_combo, self.fit_combo, self.gate_combo])

        layout.addWidget(
            _hint(
                "Lower levels are faster and less likely to split noise. Forcing a single "
                "fit type (instead of Auto) is faster because fewer peak shapes are tried. "
                "The noise gate skips fitting on messy/noise-only peaks (shown as the raw "
                "trace); a stricter gate is faster but may skip weak real peaks."
            )
        )

        self.apply_all = QCheckBox("Apply to all compounds")
        self.apply_all.setObjectName("deconvolutionApplyAllCheck")
        self.apply_all.setToolTip(
            "Overwrite the deconvolution settings of every compound with the "
            "values chosen above (e.g. tick this with 'Off' to disable "
            "deconvolution globally)."
        )
        self.apply_all.toggled.connect(self._mark_dirty)
        self._inputs.append(self.apply_all)
        layout.addWidget(self.apply_all)

        self.sample_group = QGroupBox("Per-sample curve fit")
        sample_layout = QVBoxLayout(self.sample_group)
        self.sample_scope_label = QLabel(
            "Applies to the 0 samples selected in the plot area"
        )
        self.sample_scope_label.setWordWrap(True)
        sample_layout.addWidget(self.sample_scope_label)

        sample_form = _form_layout()
        self.sample_fit_combo = QComboBox()
        self.sample_fit_combo.setObjectName("sampleFitCombo")
        self.sample_fit_combo.setStyleSheet(_COMBO_STYLE)
        self.sample_fit_combo.currentIndexChanged.connect(self._mark_sample_section_dirty)
        sample_form.addRow("Fit type", self.sample_fit_combo)
        sample_layout.addLayout(sample_form)

        self.clear_overrides = QCheckBox(
            "Clear all per-sample overrides for this compound (0)"
        )
        self.clear_overrides.setObjectName("clearSampleFitCheck")
        self.clear_overrides.toggled.connect(self._mark_sample_section_dirty)
        sample_layout.addWidget(self.clear_overrides)
        layout.addWidget(self.sample_group)
        layout.addStretch()

    def editable(self) -> tuple[bool, str]:
        if self.host.selected_compound_name():
            return True, ""
        return (
            False,
            "Load compounds and select one in the toolbar to change this.",
        )

    def set_inputs_enabled(self, enabled: bool) -> None:
        super().set_inputs_enabled(enabled)
        if enabled:
            self._sync_fit_enabled()
        self._sync_sample_section(enabled)

    def unsaved_hint(self) -> str:
        selected = self.host.selected_compound_name()
        if selected == self._compound_name:
            hint = f"Unsaved changes for {self._compound_name}"
        else:
            hint = (
                f"Unsaved changes for {self._compound_name}. "
                f"The toolbar now selects {selected or 'nothing'}; Save still writes to "
                f"{self._compound_name}."
            )
        current_samples = list(self.host.selected_sample_names())
        if current_samples != self._sample_names:
            hint += (
                f" The plot area now selects {_count_samples(current_samples)}; "
                f"Save still writes to the {_count_samples(self._sample_names)} "
                "selected when this page loaded."
            )
        return hint

    def _on_level_changed(self, _index: int) -> None:
        self._sync_fit_enabled()
        self._mark_dirty()

    def _sync_fit_enabled(self) -> None:
        on = self.level_combo.currentData() != "off"
        self.fit_combo.setEnabled(on and self.level_combo.isEnabled())
        self.gate_combo.setEnabled(on and self.level_combo.isEnabled())

    def _mark_sample_section_dirty(self, *_args) -> None:
        self._sample_section_touched = True
        self._mark_dirty()

    def _sync_sample_section(self, page_enabled: bool) -> None:
        self.sample_group.setEnabled(page_enabled)
        self.sample_fit_combo.setEnabled(page_enabled and bool(self._sample_names))
        overrides = (
            get_sample_fit_types(self._compound_name) if self._compound_name else {}
        )
        self.clear_overrides.setEnabled(page_enabled and bool(overrides))

    def _fill_sample_fit_combo(self, values: set) -> None:
        combo = self.sample_fit_combo
        combo.clear()
        combo.addItem("Use compound setting", None)
        for value, label in FIT_TYPE_LABELS.items():
            combo.addItem(label, value)
        if not self._sample_names or len(values) <= 1:
            common = next(iter(values), None) if self._sample_names else None
            index = combo.findData(common)
            combo.setCurrentIndex(index if index >= 0 else 0)
            return
        combo.addItem("(mixed)", self._MIXED)
        combo.setCurrentIndex(combo.findData(self._MIXED))

    def load(self) -> None:
        self._compound_name = self.host.selected_compound_name()
        self._sample_names = list(self.host.selected_sample_names())
        self._sample_section_touched = False
        self.compound_label.setText(
            f"Compound: {self._compound_name or 'none selected'}"
        )
        self.sample_scope_label.setText(
            f"Applies to the {_count_samples(self._sample_names)} selected in the plot area"
        )
        overrides = (
            get_sample_fit_types(self._compound_name) if self._compound_name else {}
        )
        self.clear_overrides.setText(
            f"Clear all per-sample overrides for this compound ({len(overrides)})"
        )
        level, fit, gate = self.host.deconvolution_settings(self._compound_name)
        values = {
            overrides.get((self._compound_name, sample)) for sample in self._sample_names
        }
        with (
            QSignalBlocker(self.level_combo),
            QSignalBlocker(self.fit_combo),
            QSignalBlocker(self.gate_combo),
            QSignalBlocker(self.apply_all),
            QSignalBlocker(self.sample_fit_combo),
            QSignalBlocker(self.clear_overrides),
        ):
            _fill_combo(self.level_combo, _DECONVOLUTION_LEVEL_OPTIONS, level)
            _fill_combo(self.fit_combo, _DECONVOLUTION_FIT_OPTIONS, fit)
            _fill_combo(self.gate_combo, _DECONVOLUTION_GATE_OPTIONS, gate)
            self.apply_all.setChecked(False)
            self._fill_sample_fit_combo(values)
            self.clear_overrides.setChecked(False)
        self._sync_fit_enabled()
        self._sync_sample_section(self.editable()[0])
        self._clear_dirty()

    def save(self) -> None:
        fit_type = self.sample_fit_combo.currentData()
        will_write_samples = self._sample_section_touched and (
            self.clear_overrides.isChecked() or fit_type != self._MIXED
        )
        self.host.apply_deconvolution(
            self._compound_name,
            self.level_combo.currentData(),
            self.fit_combo.currentData(),
            self.gate_combo.currentData(),
            self.apply_all.isChecked(),
            replot=not will_write_samples,
        )
        if not will_write_samples:
            return
        if self.clear_overrides.isChecked():
            self.host.clear_sample_fit_types(self._compound_name)
            return
        self.host.apply_sample_fit_type(
            self._compound_name, self._sample_names, fit_type
        )


SETTINGS_PAGES: tuple[tuple[type[SettingsPage], frozenset[AnalysisMode]], ...] = (
    (MassTolerancePage, _ALL_MODES),
    (PeakValidationPage, _ALL_MODES),
    (QualifierRatioPage, frozenset({AnalysisMode.UNLABELLED})),
    (IntegrationPage, _ALL_MODES),
    (NaturalAbundancePage, frozenset({AnalysisMode.LABELLED})),
    (InternalStandardPage, frozenset({AnalysisMode.LABELLED})),
    (DeconvolutionPage, _ALL_MODES),
)


class SettingsWindow(QDialog):
    """Non-modal, shown with show(); a QDialog only so style.qss dialog rules apply."""

    def __init__(self, parent: QWidget, host) -> None:
        super().__init__(parent)
        self._host = host
        self.setObjectName("settingsWindow")
        self.setWindowTitle("Settings")
        self.resize(880, 600)
        self.setMinimumSize(720, 480)

        self._pages: list[SettingsPage] = [
            page_cls(host)
            for page_cls, modes in SETTINGS_PAGES
            if host.analysis_mode in modes
        ]

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.page_list = QListWidget()
        self.page_list.setObjectName("settingsPageList")
        self.page_list.setFixedWidth(200)
        self.page_list.setUniformItemSizes(True)
        for page in self._pages:
            item = QListWidgetItem(page.title)
            item.setSizeHint(QSize(0, 36))
            self.page_list.addItem(item)
        root.addWidget(self.page_list)

        right = QVBoxLayout()
        right.setContentsMargins(20, 16, 20, 16)
        right.setSpacing(12)

        self.heading = QLabel(self._pages[0].title if self._pages else "")
        self.heading.setStyleSheet("font-size: 16px; font-weight: 600;")
        right.addWidget(self.heading)

        self.stack = QStackedWidget()
        for page in self._pages:
            self.stack.addWidget(page)
            page.dirty_changed.connect(self._on_page_dirty_changed)

        scroll = QScrollArea()
        scroll.setObjectName("settingsPageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.stack)
        right.addWidget(scroll, stretch=1)

        footer = QHBoxLayout()
        self.hint_label = QLabel()
        self.hint_label.setObjectName("settingsHint")
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet(_HINT_STYLE)
        footer.addWidget(self.hint_label, stretch=1)

        self.reset_button = QPushButton("Reset")
        self.reset_button.setObjectName("settingsResetButton")
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(self._reset_current)
        footer.addWidget(self.reset_button)

        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("settingsSaveButton")
        self.save_button.setDefault(True)
        self.save_button.setAutoDefault(True)
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save_current)
        footer.addWidget(self.save_button)

        right.addLayout(footer)
        root.addLayout(right, stretch=1)

        self.page_list.currentRowChanged.connect(self._on_page_changed)
        self.page_list.setCurrentRow(0)

    def page_named(self, title: str) -> SettingsPage:
        for page in self._pages:
            if page.title == title:
                return page
        raise KeyError(title)

    def _current_page(self) -> SettingsPage:
        return self._pages[self.stack.currentIndex()]

    def _on_page_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._pages):
            return
        self.stack.setCurrentIndex(index)
        self.heading.setText(self._pages[index].title)
        self._update_footer()

    def _on_page_dirty_changed(self, _dirty: bool) -> None:
        self._update_footer()

    def _update_footer(self) -> None:
        if not self._pages:
            return
        page = self._current_page()
        editable, reason = page.editable()
        dirty = page.is_dirty()
        if not editable:
            self.hint_label.setText(reason)
        elif dirty:
            self.hint_label.setText(page.unsaved_hint())
        else:
            self.hint_label.setText("")
        self.reset_button.setEnabled(dirty)
        self.save_button.setEnabled(dirty and editable)

    def _save_current(self) -> None:
        page = self._current_page()
        page.save()
        page.load()
        page.set_inputs_enabled(page.editable()[0])
        self._update_footer()

    def _reset_current(self) -> None:
        page = self._current_page()
        page.load()
        page.set_inputs_enabled(page.editable()[0])
        self._update_footer()

    def refresh(self) -> None:
        for page in self._pages:
            if not page.is_dirty():
                page.load()
            page.set_inputs_enabled(page.editable()[0])
        self._update_footer()

    def open(self) -> None:
        self.refresh()
        show_over_parent(self)
