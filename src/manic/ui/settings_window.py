from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, Qt, QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from manic.io.compound_reader import read_compound
from manic.models.analysis import AnalysisMode
from manic.models.sample_fit_type import FIT_TYPE_LABELS, get_sample_fit_types
from manic.ui.combo_box import ComboBox
from manic.ui.dialog_kit import (
    FORM_LABEL_WIDTH,
    MARKED_ROLE,
    description_label,
    form_layout,
    form_row,
    help_button,
    hint_label,
    resize_to_screen,
    section_label,
    set_variant,
    sidebar_item_size,
    sidebar_list,
    style_dialog,
    window_title,
    with_help,
)
from manic.ui.window_placement import show_over_parent

_ALL_MODES = frozenset(AnalysisMode)
# A short number reads better in a narrow field than stretched across the page.
_NUMBER_FIELD_WIDTH = 120


def _target_moved_hint(loaded: str | None, selected: str | None) -> str:
    """Warn only when the compound selection moved away from the page's edit target."""
    if selected == loaded:
        return ""
    return (
        f"The selected compound is now {selected or 'none'}; "
        f"Save still writes to {loaded}."
    )


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
        return ""

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

        layout.addWidget(
            description_label(
                "The ± window in daltons around each ion's m/z used to extract "
                "its chromatogram (EIC)."
            )
        )

        form = form_layout()
        self.spin = QDoubleSpinBox()
        self.spin.setObjectName("massToleranceSpin")
        self.spin.setMaximumWidth(_NUMBER_FIELD_WIDTH)
        self.spin.setRange(0.01, 1.0)
        self.spin.setSingleStep(0.01)
        self.spin.setDecimals(3)
        self.spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin.valueChanged.connect(self._mark_dirty)
        self._inputs.append(self.spin)
        form_row(form, "Mass tolerance (Da)", self.spin)
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

        layout.addWidget(
            description_label(
                "Peak validation compares each compound's total peak area with the "
                "internal standard's reference peak. A peak below the minimum ratio "
                "gets an amber Below threshold badge on its plot. Right-click the "
                "plot to accept the peak or mark it as bad."
            )
        )

        form = form_layout()
        self.spin = QDoubleSpinBox()
        self.spin.setObjectName("minPeakAreaSpin")
        self.spin.setMaximumWidth(_NUMBER_FIELD_WIDTH)
        self.spin.setRange(0.0, 1.0)
        self.spin.setSingleStep(0.001)
        self.spin.setDecimals(3)
        self.spin.setSpecialValueText("Off")
        self.spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin.valueChanged.connect(self._mark_dirty)
        self._inputs.append(self.spin)
        form_row(form, "Minimum area ratio", self.spin)
        form_row(
            form,
            "",
            hint_label("For example 0.005 = 0.5% of the reference peak area. 0 turns it off."),
        )
        layout.addLayout(form)
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

        layout.addWidget(
            description_label(
                "Tolerance is a fraction of the expected ratio (0.25 = ±25%). "
                "An unset tolerance leaves that qualifier unassessed in Identity QC "
                "and the Qualifier QC sheet."
            )
        )

        self.compound_label = QLabel("Compound: none selected")
        layout.addWidget(self.compound_label)

        form = form_layout()
        self._labels: dict[int, QLabel] = {}
        self._ratio_labels: dict[int, QLabel] = {}
        self._spins: dict[int, QDoubleSpinBox] = {}
        for ordinal in self._ORDINALS:
            label = QLabel()
            label.setMinimumWidth(FORM_LABEL_WIDTH)
            spin = QDoubleSpinBox()
            spin.setObjectName(f"qualifier{ordinal}ToleranceSpin")
            spin.setFixedWidth(_NUMBER_FIELD_WIDTH)
            spin.setRange(0.0, 10.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.01)
            spin.setSpecialValueText("Not set")
            spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            spin.valueChanged.connect(self._mark_dirty)
            ratio_label = QLabel()
            ratio_label.setProperty("role", "hint")
            field = QWidget()
            field_layout = QHBoxLayout(field)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.addWidget(spin)
            field_layout.addWidget(ratio_label, stretch=1)
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
                "Load compounds and select one in the Compounds list to change this.",
            )
        if not self.host.qualifier_channels(name):
            return False, f"{name} has no qualifier ions."
        return True, ""

    def unsaved_hint(self) -> str:
        return _target_moved_hint(self._compound_name, self.host.selected_compound_name())

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
        layout.addWidget(hint_label("Applies to plots. Export asks again."))
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
        layout.addWidget(hint_label("Exports always apply the correction."))
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

        layout.addWidget(
            description_label(
                "The reference peak is the internal standard's isotopologue used for "
                "peak validation, abundance normalization and MRRF calculations."
            )
        )

        form = form_layout()
        self.standard_combo = ComboBox()
        self.standard_combo.setObjectName("internalStandardChoiceCombo")
        self.standard_combo.currentIndexChanged.connect(self._on_standard_changed)
        self._inputs.append(self.standard_combo)
        form_row(form, "Internal standard", self.standard_combo)

        self.combo = ComboBox()
        self.combo.setObjectName("internalStandardCombo")
        self.combo.setMaximumWidth(_NUMBER_FIELD_WIDTH)
        self.combo.currentIndexChanged.connect(self._mark_dirty)
        self._inputs.append(self.combo)
        form_row(form, "Reference peak", self.combo)
        self.reference_hint = hint_label("")
        form_row(form, "", self.reference_hint)
        layout.addLayout(form)
        layout.addStretch()

    def _compound_names(self) -> list[str]:
        return self.host.compound_names()

    def editable(self) -> tuple[bool, str]:
        if not self._compound_names():
            return False, "Load a compound list to choose an internal standard."
        return True, ""

    def set_inputs_enabled(self, enabled: bool) -> None:
        super().set_inputs_enabled(enabled)
        self.combo.setEnabled(enabled and self.combo.count() > 1)

    def _label_atoms(self, name: str | None) -> int:
        if not name:
            return 0
        if name == self.host.internal_standard_name():
            return self.host.internal_standard_label_atoms()
        try:
            return max(int(read_compound(name).label_atoms or 0), 0)
        except LookupError:
            return 0

    def _fill_reference(self, name: str | None, current: int) -> None:
        label_atoms = self._label_atoms(name)
        with QSignalBlocker(self.combo):
            self.combo.clear()
            for idx in range(label_atoms + 1):
                self.combo.addItem(f"M+{idx}", idx)
            self.combo.setCurrentIndex(current if 0 <= current <= label_atoms else 0)
        no_labels = bool(name) and label_atoms == 0
        self.reference_hint.setText(
            f"{name} has no label atoms, so only M+0 can be the reference peak."
            if no_labels
            else ""
        )
        self.reference_hint.setVisible(no_labels)
        self.combo.setEnabled(self.standard_combo.isEnabled() and label_atoms > 0)

    def _on_standard_changed(self, _index: int) -> None:
        # A different standard starts at M+0, as it does when chosen in the sidebar.
        self._fill_reference(self.standard_combo.currentData(), 0)
        self._mark_dirty()

    def load(self) -> None:
        name = self.host.internal_standard_name()
        with QSignalBlocker(self.standard_combo):
            self.standard_combo.clear()
            self.standard_combo.addItem("No internal standard", None)
            for compound in self._compound_names():
                self.standard_combo.addItem(compound, compound)
            index = self.standard_combo.findData(name) if name else 0
            self.standard_combo.setCurrentIndex(max(index, 0))
        self._fill_reference(name, self.host.internal_standard_reference_isotope)
        self._clear_dirty()

    def save(self) -> None:
        chosen = self.standard_combo.currentData()
        if chosen != self.host.internal_standard_name():
            self.host.apply_internal_standard(chosen)
        self.host.apply_internal_standard_reference_isotope(self.combo.currentData() or 0)


class DeconvolutionPage(SettingsPage):
    title = "Deconvolution"

    def __init__(self, host, parent: QWidget | None = None) -> None:
        super().__init__(host, parent)
        self._compound_name: str | None = None
        self._loaded_overrides: dict[str, str] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(
            description_label(
                "Fits and separates overlapping chromatographic peaks before integration."
            )
        )

        layout.addSpacing(4)
        layout.addWidget(section_label("Compound settings"))
        self.compound_label = QLabel("Compound: none selected")
        layout.addWidget(self.compound_label)

        form = form_layout()
        self.level_combo = ComboBox()
        self.level_combo.setObjectName("deconvolutionLevelCombo")
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        form_row(
            form,
            "Resolution",
            with_help(
                self.level_combo,
                "Higher levels split closer overlaps and weaker shoulders, but run "
                "slower and are more likely to split noise.",
            ),
        )

        self.fit_combo = ComboBox()
        self.fit_combo.setObjectName("deconvolutionFitCombo")
        self.fit_combo.currentIndexChanged.connect(self._mark_dirty)
        form_row(
            form,
            "Fit type",
            with_help(
                self.fit_combo,
                "Auto tries each peak shape and keeps the best. A single fit type is "
                "faster because fewer shapes are tried.",
            ),
        )

        self.gate_combo = ComboBox()
        self.gate_combo.setObjectName("deconvolutionGateCombo")
        self.gate_combo.currentIndexChanged.connect(self._mark_dirty)
        form_row(
            form,
            "Noise gate",
            with_help(
                self.gate_combo,
                "Skips fitting on noise-only peaks, which then show the raw trace. "
                "A stricter gate is faster but may skip weak real peaks.",
            ),
        )

        self._inputs.extend([self.level_combo, self.fit_combo, self.gate_combo])

        self.apply_all = QCheckBox("Apply to all compounds")
        self.apply_all.setObjectName("deconvolutionApplyAllCheck")
        self.apply_all.setToolTip(
            "Overwrite the deconvolution settings of every compound with the "
            "values chosen above (e.g. tick this with 'Off' to disable "
            "deconvolution globally)."
        )
        self.apply_all.toggled.connect(self._mark_dirty)
        self._inputs.append(self.apply_all)
        form_row(form, "", self.apply_all)
        layout.addLayout(form)

        layout.addSpacing(12)
        heading = QHBoxLayout()
        heading.setSpacing(8)
        heading.addWidget(section_label("Per-sample curve fit"))
        heading.addWidget(
            help_button(
                "An override replaces the compound fit type for one sample. Choose "
                "Use compound setting to remove it. Samples selected in the plot "
                "area are listed and selected here."
            )
        )
        heading.addStretch()
        layout.addLayout(heading)

        # The only per-sample editor: one row per overridden or plot-selected sample.
        self.sample_fit_table = QTableWidget(0, 2)
        self.sample_fit_table.setObjectName("sampleFitTable")
        self.sample_fit_table.setHorizontalHeaderLabels(["Sample", "Fit type"])
        self.sample_fit_table.verticalHeader().setVisible(False)
        self.sample_fit_table.horizontalHeader().setStretchLastSection(True)
        self.sample_fit_table.horizontalHeader().setHighlightSections(False)
        self.sample_fit_table.horizontalHeader().setDefaultAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )
        self.sample_fit_table.setShowGrid(False)
        self.sample_fit_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.sample_fit_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sample_fit_table.setAlternatingRowColors(False)
        self.sample_fit_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sample_fit_table.verticalHeader().setDefaultSectionSize(36)
        self.sample_fit_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        self.sample_fit_table.itemSelectionChanged.connect(self._sync_bulk_button)
        layout.addWidget(self.sample_fit_table)

        self.empty_overrides_label = hint_label(
            "No per-sample overrides. Select plots to set their fit here."
        )
        layout.addWidget(self.empty_overrides_label)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.bulk_fit_button = QPushButton("Set fit for selected")
        self.bulk_fit_button.setObjectName("bulkFitButton")
        self.bulk_fit_button.setAutoDefault(False)
        bulk_menu = QMenu(self.bulk_fit_button)
        for label, value in (("Use compound setting", None), *(
            (label, value) for value, label in FIT_TYPE_LABELS.items()
        )):
            bulk_menu.addAction(label).triggered.connect(
                lambda _checked=False, v=value: self.set_fit_for_selected_rows(v)
            )
        self.bulk_fit_button.setMenu(bulk_menu)
        actions.addWidget(self.bulk_fit_button)
        actions.addStretch()
        self.remove_all_button = QPushButton("Remove all overrides")
        self.remove_all_button.setObjectName("removeAllOverridesButton")
        self.remove_all_button.setAutoDefault(False)
        self.remove_all_button.setDefault(False)
        set_variant(self.remove_all_button, "danger")
        self.remove_all_button.clicked.connect(self._stage_remove_all_overrides)
        actions.addWidget(self.remove_all_button)
        layout.addLayout(actions)
        layout.addStretch()

    def editable(self) -> tuple[bool, str]:
        if self.host.selected_compound_name():
            return True, ""
        return (
            False,
            "Load compounds and select one in the Compounds list to change this.",
        )

    def set_inputs_enabled(self, enabled: bool) -> None:
        super().set_inputs_enabled(enabled)
        if enabled:
            self._sync_fit_enabled()
        self.sample_fit_table.setEnabled(enabled)
        self._sync_bulk_button()
        self._sync_remove_all()

    def unsaved_hint(self) -> str:
        return _target_moved_hint(self._compound_name, self.host.selected_compound_name())

    def _on_level_changed(self, _index: int) -> None:
        self._sync_fit_enabled()
        self._mark_dirty()

    def _sync_fit_enabled(self) -> None:
        on = self.level_combo.currentData() != "off"
        self.fit_combo.setEnabled(on and self.level_combo.isEnabled())
        self.gate_combo.setEnabled(on and self.level_combo.isEnabled())

    def _row_combos(self) -> list[QComboBox]:
        table = self.sample_fit_table
        return [table.cellWidget(row, 1) for row in range(table.rowCount())]

    def _selected_rows(self) -> list[int]:
        return sorted({index.row() for index in self.sample_fit_table.selectedIndexes()})

    def _sync_bulk_button(self) -> None:
        count = len(self._selected_rows())
        self.bulk_fit_button.setVisible(self.sample_fit_table.rowCount() > 0)
        self.bulk_fit_button.setEnabled(self.sample_fit_table.isEnabled() and count > 0)
        self.bulk_fit_button.setText(
            f"Set fit for {count} selected ▾" if count else "Set fit for selected ▾"
        )

    def _sync_remove_all(self) -> None:
        # One override is removed from its own row; the bulk button is for several.
        overridden = sum(combo.currentData() is not None for combo in self._row_combos())
        self.remove_all_button.setVisible(overridden > 1)
        self.remove_all_button.setEnabled(self.sample_fit_table.isEnabled())

    def _on_row_fit_changed(self, *_args) -> None:
        self._sync_remove_all()
        self._mark_dirty()

    def set_fit_for_selected_rows(self, fit_type: str | None) -> None:
        for row in self._selected_rows():
            combo = self.sample_fit_table.cellWidget(row, 1)
            with QSignalBlocker(combo):
                combo.setCurrentIndex(combo.findData(fit_type))
        self._on_row_fit_changed()

    def _fill_fit_options(self, combo: QComboBox, current: str | None) -> None:
        combo.clear()
        combo.addItem("Use compound setting", None)
        for value, label in FIT_TYPE_LABELS.items():
            combo.addItem(label, value)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _fit_override_table_height(self) -> None:
        header = max(self.sample_fit_table.horizontalHeader().sizeHint().height(), 24)
        row_h = self.sample_fit_table.verticalHeader().defaultSectionSize()
        frame = 2 * self.sample_fit_table.frameWidth()
        visible_rows = min(max(self.sample_fit_table.rowCount(), 1), 6)
        self.sample_fit_table.setFixedHeight(header + visible_rows * row_h + frame)

    def _rebuild_override_table(
        self, overrides: dict[tuple[str, str], str], selected: list[str]
    ) -> None:
        self._loaded_overrides = {
            sample: fit_type for (_, sample), fit_type in overrides.items()
        }
        samples = sorted(set(self._loaded_overrides) | set(selected))
        table = self.sample_fit_table
        with QSignalBlocker(table):
            table.clearSelection()
            table.setRowCount(len(samples))
            for row, sample in enumerate(samples):
                item = QTableWidgetItem(sample)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                table.setItem(row, 0, item)
                combo = ComboBox()
                self._fill_fit_options(combo, self._loaded_overrides.get(sample))
                combo.currentIndexChanged.connect(self._on_row_fit_changed)
                table.setCellWidget(row, 1, combo)
                if sample in selected:
                    table.selectionModel().select(
                        table.model().index(row, 0),
                        QItemSelectionModel.Select | QItemSelectionModel.Rows,
                    )
        table.resizeColumnToContents(0)
        empty = not samples
        table.setVisible(not empty)
        self.empty_overrides_label.setVisible(empty)
        self._fit_override_table_height()

    def _stage_remove_all_overrides(self) -> None:
        for combo in self._row_combos():
            with QSignalBlocker(combo):
                combo.setCurrentIndex(combo.findData(None))
        self._on_row_fit_changed()

    def _staged_sample_changes(self) -> dict[str, str | None]:
        table = self.sample_fit_table
        return {
            table.item(row, 0).text(): combo.currentData()
            for row, combo in enumerate(self._row_combos())
            if combo.currentData() != self._loaded_overrides.get(table.item(row, 0).text())
        }

    def load(self) -> None:
        self._compound_name = self.host.selected_compound_name()
        self.compound_label.setText(
            f"Compound: {self._compound_name or 'none selected'}"
        )
        overrides = (
            get_sample_fit_types(self._compound_name) if self._compound_name else {}
        )
        selected = list(self.host.selected_sample_names()) if self._compound_name else []
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
        self._rebuild_override_table(overrides, selected)
        self._sync_fit_enabled()
        self.set_inputs_enabled(self.editable()[0])
        self._clear_dirty()

    def save(self) -> None:
        changes = self._staged_sample_changes()
        self.host.apply_deconvolution(
            self._compound_name,
            self.level_combo.currentData(),
            self.fit_combo.currentData(),
            self.gate_combo.currentData(),
            self.apply_all.isChecked(),
            replot=not changes,
        )
        if changes:
            self.host.apply_sample_fit_types(self._compound_name, changes)


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
    """Non-modal, shown with show(); a QDialog only so style.qss dialog rules apply.

    Each page saves on its own: a page writes to the compound and samples it
    loaded with, so "Save this page" never commits another page's edits.
    """

    def __init__(self, parent: QWidget, host) -> None:
        super().__init__(parent)
        self._host = host
        self.setObjectName("settingsWindow")
        # [*] lets setWindowModified() mark unsaved pages in the title bar.
        self.setWindowTitle(window_title("Settings[*]"))
        style_dialog(self)
        resize_to_screen(self, 880, 720)
        self.setMinimumSize(640, 400)

        self._pages: list[SettingsPage] = [
            page_cls(host)
            for page_cls, modes in SETTINGS_PAGES
            if host.analysis_mode in modes
        ]

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.page_list = sidebar_list("settingsPageList", 200)
        for page in self._pages:
            item = QListWidgetItem(page.title)
            item.setSizeHint(sidebar_item_size())
            self.page_list.addItem(item)
        root.addWidget(self.page_list)

        right = QVBoxLayout()
        right.setContentsMargins(24, 20, 24, 16)
        right.setSpacing(16)

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

        self.pending_label = QLabel()
        self.pending_label.setObjectName("settingsPending")
        self.pending_label.setProperty("role", "pending")
        self.pending_label.setWordWrap(True)
        self.pending_label.linkActivated.connect(
            lambda href: self.page_list.setCurrentRow(int(href))
        )
        right.addWidget(self.pending_label)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.hint_label = hint_label("")
        self.hint_label.setObjectName("settingsHint")
        footer.addWidget(self.hint_label, stretch=1)

        self.reset_button = QPushButton("Discard changes")
        self.reset_button.setObjectName("settingsResetButton")
        self.reset_button.setAutoDefault(False)
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(self._reset_current)

        self.save_button = QPushButton("Save this page")
        self.save_button.setObjectName("settingsSaveButton")
        self.save_button.setDefault(True)
        self.save_button.setAutoDefault(True)
        set_variant(self.save_button, "primary")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save_current)
        buttons = QDialogButtonBox()
        buttons.addButton(self.save_button, QDialogButtonBox.AcceptRole)
        buttons.addButton(self.reset_button, QDialogButtonBox.RejectRole)
        footer.addWidget(buttons, alignment=Qt.AlignBottom)
        # The macOS style gives a default button different layout margins, which
        # put Save 8px above Discard; lay both out by their visible rects.
        for button in (self.reset_button, self.save_button):
            button.setAttribute(Qt.WA_LayoutUsesWidgetRect)

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
        self._update_pending()

    def _update_pending(self) -> None:
        dirty_rows = [row for row, page in enumerate(self._pages) if page.is_dirty()]
        for row, page in enumerate(self._pages):
            self.page_list.item(row).setData(MARKED_ROLE, page.is_dirty())
        self.setWindowModified(bool(dirty_rows))
        # The current page shows its own state through Save; list only the others.
        other_rows = [row for row in dirty_rows if row != self.stack.currentIndex()]
        if not other_rows:
            self.pending_label.clear()
            self.pending_label.hide()
            return
        # Link colour comes from the palette, so it follows scheme switches.
        links = ", ".join(
            f'<a href="{row}" style="text-decoration: none;">{self._pages[row].title}</a>'
            for row in other_rows
        )
        self.pending_label.setText(f"Also unsaved: {links}")
        self.pending_label.show()

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
