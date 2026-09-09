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

    def __init__(self, host, parent: QWidget | None = None) -> None:
        super().__init__(host, parent)
        self._compound_name: str | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        info = QLabel(
            "Choose how MANIC fits and separates overlapping chromatographic peaks "
            "before integration. These settings are saved per compound and apply to "
            "every sample of that compound."
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

    def _on_level_changed(self, _index: int) -> None:
        self._sync_fit_enabled()
        self._mark_dirty()

    def _sync_fit_enabled(self) -> None:
        on = self.level_combo.currentData() != "off"
        self.fit_combo.setEnabled(on and self.level_combo.isEnabled())
        self.gate_combo.setEnabled(on and self.level_combo.isEnabled())

    def load(self) -> None:
        self._compound_name = self.host.selected_compound_name()
        self.compound_label.setText(
            f"Compound: {self._compound_name or 'none selected'}"
        )
        level, fit, gate = self.host.deconvolution_settings(self._compound_name)
        with (
            QSignalBlocker(self.level_combo),
            QSignalBlocker(self.fit_combo),
            QSignalBlocker(self.gate_combo),
            QSignalBlocker(self.apply_all),
        ):
            _fill_combo(self.level_combo, _DECONVOLUTION_LEVEL_OPTIONS, level)
            _fill_combo(self.fit_combo, _DECONVOLUTION_FIT_OPTIONS, fit)
            _fill_combo(self.gate_combo, _DECONVOLUTION_GATE_OPTIONS, gate)
            self.apply_all.setChecked(False)
        self._sync_fit_enabled()
        self._clear_dirty()

    def save(self) -> None:
        self.host.apply_deconvolution(
            self._compound_name,
            self.level_combo.currentData(),
            self.fit_combo.currentData(),
            self.gate_combo.currentData(),
            self.apply_all.isChecked(),
        )


SETTINGS_PAGES: tuple[tuple[type[SettingsPage], bool], ...] = (
    (MassTolerancePage, False),
    (PeakValidationPage, False),
    (IntegrationPage, False),
    (NaturalAbundancePage, True),
    (InternalStandardPage, True),
    (DeconvolutionPage, False),
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

        labelled = host.analysis_mode is AnalysisMode.LABELLED
        self._pages: list[SettingsPage] = [
            page_cls(host)
            for page_cls, labelled_only in SETTINGS_PAGES
            if not labelled_only or labelled
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
            self.hint_label.setText("Unsaved changes")
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
        self.show()
        self.raise_()
        self.activateWindow()
