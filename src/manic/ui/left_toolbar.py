import logging
from collections.abc import Iterable
from typing import List

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from manic.io.compound_reader import read_compound
from manic.models.analysis import AnalysisMode
from manic.processors.chromatographic_peak_deconvolution import (
    chromatographic_peak_deconvolution_enabled,
)
from manic.processors.tile_y_scale import YScalePolicy, available_y_scale_policies

from .compound_list_widget import CompoundListWidget
from .integration_window_widget import IntegrationWindow
from .isotopologue_ratio_widget import IsotopologueRatioWidget
from .loaded_data_widget import LoadedDataWidget
from .sample_list_widget import SampleListWidget
from .sidebar_widgets import (
    CollapsibleSection,
    FilterField,
    divider,
    section_heading,
    shortcut_text,
)
from .standard_indicator_widget import StandardIndicator
from .targeted_qc_widget import TargetedQcWidget
from .total_abundance_widget import TotalAbundanceWidget

logger = logging.getLogger(__name__)

BROWSE_MIN_HEIGHT = 240


def _deconvolution_on(compound_name: str) -> bool:
    if not compound_name or compound_name.startswith("- No"):
        return False
    try:
        compound = read_compound(compound_name)
    except LookupError:
        return False
    return chromatographic_peak_deconvolution_enabled(compound.deconvolution_level)


class Toolbar(QWidget):
    # Signal for the currently selected samples
    samples_selected = Signal(list)

    # Signal for the currently selected compound
    compound_selected = Signal(str)

    # Signal for when internal standard is selected
    internal_standard_selected = Signal(str)

    # Signal for when compounds are deleted
    compounds_deleted = Signal(list)

    # Signal for when compounds are restored
    compounds_restored = Signal(list)

    add_compound_requested = Signal()

    # Signal for when samples are deleted
    samples_deleted = Signal(list)

    # Signal for when samples are restored
    samples_restored = Signal(list)

    # Signal emitted when baseline correction checkbox is toggled
    baseline_correction_changed = Signal(str, bool)  # compound_name, enabled

    y_scale_policy_changed = Signal(object)

    load_compounds_requested = Signal()
    load_raw_data_requested = Signal()

    def __init__(
        self,
        analysis_mode: AnalysisMode | str = AnalysisMode.LABELLED,
    ):
        super().__init__()
        self.analysis_mode = AnalysisMode.coerce(analysis_mode)
        self.setObjectName("toolbar")  # Required for CSS targeting
        self._y_scale_policy = YScalePolicy.PER_TILE_EXTRACT
        self._available_y_scale_policies = available_y_scale_policies(
            self.analysis_mode
        )
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        """Pinned data header, then compounds and samples above an inspector."""
        self._raw_loaded = False
        self._compounds_loaded = False

        header = QWidget()
        header.setObjectName("sidebarHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(10, 12, 10, 10)
        header_layout.setSpacing(2)
        mode_label = section_heading(f"{self.analysis_mode.display_name} analysis")
        mode_label.setContentsMargins(6, 0, 0, 4)
        header_layout.addWidget(mode_label)
        self.loaded_data = LoadedDataWidget()
        header_layout.addWidget(self.loaded_data)
        self.standard = StandardIndicator()
        header_layout.addWidget(self.standard)

        # Browse: compounds, then samples.
        browse = QWidget()
        browse.setObjectName("sidebarBrowse")
        browse_layout = QVBoxLayout(browse)
        browse_layout.setContentsMargins(16, 14, 16, 12)
        browse_layout.setSpacing(8)

        compounds_heading = QHBoxLayout()
        compounds_heading.addWidget(section_heading("Compounds"))
        compounds_heading.addStretch(1)
        self.compound_count_label = QLabel()
        self.compound_count_label.setProperty("role", "hint")
        compounds_heading.addWidget(self.compound_count_label)
        browse_layout.addLayout(compounds_heading)

        self.compound_list = CompoundListWidget()
        self.compound_filter = FilterField(self.compound_list, "Filter compounds")
        self.compound_filter.setToolTip(
            f"Type to filter, ↑↓ to move, Enter to pick ({shortcut_text('Ctrl+F')})"
        )
        browse_layout.addWidget(self.compound_filter)
        browse_layout.addWidget(self.compound_list, 3)
        self.compound_empty = QLabel(
            "Compounds appear here once you load a compound list."
        )
        self.compound_empty.setProperty("role", "hint")
        self.compound_empty.setWordWrap(True)
        browse_layout.addWidget(self.compound_empty)

        browse_layout.addWidget(divider())

        self.sample_list = SampleListWidget()
        samples_body = QWidget()
        samples_body_layout = QVBoxLayout(samples_body)
        samples_body_layout.setContentsMargins(0, 0, 0, 0)
        samples_body_layout.setSpacing(8)
        self.sample_filter = FilterField(self.sample_list, "Filter samples")
        self.sample_filter.setToolTip(
            "Type to filter. Selected samples are the ones shown in the grid."
        )
        samples_body_layout.addWidget(self.sample_filter)
        samples_body_layout.addWidget(self.sample_list, 1)
        self.sample_empty = QLabel("Samples appear here once you load raw data.")
        self.sample_empty.setProperty("role", "hint")
        self.sample_empty.setWordWrap(True)
        samples_body_layout.addWidget(self.sample_empty)
        self.samples_section = CollapsibleSection("Samples", samples_body)
        self.samples_section.toggled.connect(self._on_samples_section_toggled)
        browse_layout.addWidget(self.samples_section)
        # Holds the empty space while there is no compound list to fill it.
        self._compound_stretch = QWidget()
        browse_layout.addWidget(self._compound_stretch, 3)

        # Inspector: peak window, display options and summaries scroll together.
        inspector_content = QWidget()
        inspector_content.setObjectName("sidebarInspector")
        inspector_layout = QVBoxLayout(inspector_content)
        inspector_layout.setContentsMargins(16, 12, 16, 12)
        inspector_layout.setSpacing(12)

        self.integration = IntegrationWindow(self.analysis_mode)
        inspector_layout.addWidget(self.integration)
        inspector_layout.addWidget(divider())

        display_body = QWidget()
        display_layout = QVBoxLayout(display_body)
        display_layout.setContentsMargins(16, 0, 0, 0)
        display_layout.setSpacing(6)

        self.baseline_checkbox = QCheckBox("Baseline correction")
        self.baseline_checkbox.setObjectName("baseline_correction_checkbox")
        self.baseline_checkbox.setToolTip(
            "Enable linear baseline subtraction for this compound.\n"
            "Fits a line through 3 points at each edge of the integration window\n"
            "and subtracts the area under this baseline from the peak area."
        )
        self.baseline_checkbox.stateChanged.connect(self._on_baseline_checkbox_toggled)
        display_layout.addWidget(self.baseline_checkbox)

        self.shared_yscale_checkbox = QCheckBox("Shared y-scale")
        self.shared_yscale_checkbox.setObjectName("shared_yscale_checkbox")
        self.shared_yscale_checkbox.setToolTip(
            "Use one common intensity scale for all sample plots.\n"
            "Off: each plot autoscales to its own tallest peak."
        )
        self.shared_yscale_checkbox.stateChanged.connect(
            self._on_shared_yscale_toggled
        )
        display_layout.addWidget(self.shared_yscale_checkbox)

        self.selected_peak_yscale_checkbox = None
        if YScalePolicy.PER_TILE_SELECTED_PEAK in self._available_y_scale_policies:
            self.selected_peak_yscale_checkbox = QCheckBox("Scale to selected peak")
            self.selected_peak_yscale_checkbox.setObjectName(
                "scale_selected_peak_checkbox"
            )
            self.selected_peak_yscale_checkbox.setToolTip(
                "Scale each sample to its selected peak (component nearest tR).\n"
                "Needs deconvolution on for this compound (Settings > Deconvolution).\n"
                "Other peaks in the extract may clip.\n"
                "Off: each plot autoscales to its extract."
            )
            self.selected_peak_yscale_checkbox.stateChanged.connect(
                self._on_selected_peak_yscale_toggled
            )
            display_layout.addWidget(self.selected_peak_yscale_checkbox)

        self.display_section = CollapsibleSection("Display", display_body)
        for checkbox in self.display_checkboxes():
            checkbox.toggled.connect(self._refresh_display_summary)
        self._refresh_display_summary()
        inspector_layout.addWidget(self.display_section)
        inspector_layout.addWidget(divider())

        summary = QWidget()
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(8)
        self.isotopologue_ratios = IsotopologueRatioWidget()
        self.targeted_qc = TargetedQcWidget()
        self.total_abundance = TotalAbundanceWidget()
        for chart in (self.isotopologue_ratios, self.targeted_qc, self.total_abundance):
            summary_layout.addWidget(chart, 1)
        inspector_layout.addWidget(summary, 1)

        if self.analysis_mode is AnalysisMode.UNLABELLED:
            self.isotopologue_ratios.hide()
        else:
            self.targeted_qc.hide()

        self.inspector = QScrollArea()
        self.inspector.setWidgetResizable(True)
        self.inspector.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.inspector.setFrameShape(QFrame.NoFrame)
        self.inspector.setWidget(inspector_content)

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(5)
        self.splitter.addWidget(browse)
        self.splitter.addWidget(self.inspector)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        # Keep the inspector fitted to its content until the user drags the split.
        self._user_sized = False
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self.fit_inspector)
        inspector_content.installEventFilter(self)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(header)
        main_layout.addWidget(self.splitter, 1)

        # Wide enough that sample names on the Identity chart remain readable.
        self.setMinimumWidth(256)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._refresh_data_state()

    def display_checkboxes(self) -> list[QCheckBox]:
        boxes = [self.baseline_checkbox, self.shared_yscale_checkbox]
        if self.selected_peak_yscale_checkbox is not None:
            boxes.append(self.selected_peak_yscale_checkbox)
        return boxes

    def _refresh_display_summary(self, *_args) -> None:
        if self.shared_yscale_checkbox.isChecked():
            scale = "Shared scale"
        elif (
            self.selected_peak_yscale_checkbox is not None
            and self.selected_peak_yscale_checkbox.isChecked()
        ):
            scale = "Peak scale"
        else:
            scale = "Own scale"
        baseline = "Baseline on" if self.baseline_checkbox.isChecked() else "No baseline"
        self.display_section.summary.setText(f"{baseline} · {scale}")

    def _on_samples_section_toggled(self, expanded: bool) -> None:
        # The sample list takes a share of the browse pane only while open.
        layout = self.samples_section.parentWidget().layout()
        layout.setStretchFactor(self.samples_section, 2 if expanded else 0)

    def _refresh_data_state(self) -> None:
        """Header rows, counts and empty hints from what is loaded right now."""
        compounds = self.compound_list.real_count()
        samples = self.sample_list.real_count()
        self.loaded_data.update_status(
            self._raw_loaded, self._compounds_loaded, compounds, samples
        )

        has_compounds = compounds > 0
        self.compound_list.setVisible(has_compounds)
        self.compound_filter.setVisible(has_compounds)
        self.compound_empty.setVisible(not has_compounds)
        self._compound_stretch.setVisible(not has_compounds)
        visible = self.compound_filter.visible_count()
        self.compound_count_label.setText(
            ""
            if not has_compounds
            else str(compounds)
            if visible == compounds
            else f"{visible} of {compounds}"
        )

        has_samples = samples > 0
        self.sample_list.setVisible(has_samples)
        self.sample_filter.setVisible(has_samples)
        self.sample_empty.setVisible(not has_samples)
        shown = len(self.get_selected_samples())
        if not has_samples:
            summary = ""
        elif shown == samples:
            summary = f"{samples} · all shown"
        else:
            summary = f"{shown} of {samples} shown"
        self.samples_section.summary.setText(summary)

        self.inspector.setVisible(self._raw_loaded)
        self._fit_timer.start()

    def _on_splitter_moved(self, *_args) -> None:
        self._user_sized = True

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.LayoutRequest:
            self._fit_timer.start()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_timer.start()

    def fit_inspector(self) -> None:
        """Give the inspector the height it needs to show everything; browse gets the rest."""
        total = sum(self.splitter.sizes())
        if self._user_sized or self.inspector.isHidden() or total <= 0:
            return
        wanted = self.inspector.widget().minimumSizeHint().height()
        browse = max(total - wanted, min(BROWSE_MIN_HEIGHT, total // 2))
        if self.splitter.sizes()[0] != browse:
            self.splitter.setSizes([browse, total - browse])

    def _connect_signals(self):
        """Connect child widget signals to toolbar signal handlers"""
        self.sample_list.itemSelectionChanged.connect(self.on_samples_selection_changed)
        self.compound_list.itemSelectionChanged.connect(
            self.on_compound_selection_changed
        )
        self.compound_list.internal_standard_selected.connect(
            self.on_internal_standard_selected
        )
        self.compound_list.compounds_deleted.connect(self.compounds_deleted.emit)
        self.compound_list.compounds_restored.connect(self.compounds_restored.emit)
        self.compound_list.add_compound_requested.connect(
            self.add_compound_requested.emit
        )
        self.compound_list.internal_standard_cleared.connect(
            self.on_internal_standard_cleared
        )
        self.sample_list.samples_deleted.connect(self.samples_deleted.emit)
        self.sample_list.samples_restored.connect(self.samples_restored.emit)
        self.sample_list.itemSelectionChanged.connect(self._refresh_data_state)
        self.compound_filter.filtered.connect(self._refresh_data_state)
        self.loaded_data.compounds_row.clicked.connect(self._on_compounds_row_clicked)
        self.loaded_data.raw_data_row.clicked.connect(self._on_raw_data_row_clicked)
        self.standard.clicked.connect(self._show_internal_standard_menu)

    def _on_compounds_row_clicked(self) -> None:
        if self._compounds_loaded:
            self.focus_compound_filter()
        else:
            self.load_compounds_requested.emit()

    def _on_raw_data_row_clicked(self) -> None:
        if self._raw_loaded:
            self.samples_section.set_expanded(True)
            self.sample_filter.setFocus()
        else:
            self.load_raw_data_requested.emit()

    def focus_compound_filter(self) -> None:
        self.compound_filter.setFocus()
        self.compound_filter.selectAll()

    def step_compound(self, step: int) -> None:
        """Move to the next or previous compound the filter leaves visible."""
        rows = [
            row
            for row in range(self.compound_list.count())
            if not self.compound_list.isRowHidden(row)
        ]
        if not rows or self.compound_list.real_count() == 0:
            return
        current = self.compound_list.currentRow()
        later = [row for row in rows if (row - current) * step > 0]
        if later:
            self.compound_list.setCurrentRow(later[0] if step > 0 else later[-1])

    def _show_internal_standard_menu(self) -> None:
        menu = QMenu(self.standard)
        names = self.compound_list.real_names()
        if not names:
            menu.addAction("Load a compound list first").setEnabled(False)
        for name in names:
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name == self.standard.internal_standard)
            action.triggered.connect(
                lambda _checked=False, n=name: self.on_internal_standard_selected(n)
            )
        menu.addSeparator()
        clear = menu.addAction("No internal standard")
        clear.setEnabled(self.standard.internal_standard is not None)
        clear.triggered.connect(self.on_internal_standard_cleared)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        menu.popup(self.standard.mapToGlobal(self.standard.rect().bottomLeft()))

    # --- Signal Handlers ---
    def on_samples_selection_changed(self):
        """
        Handler for when the selection changes in the samples list widget.
        Emits the custom signal with the selected samples.
        """
        selected_items = self.sample_list.selectedItems()
        if selected_items:
            selected_samples = [item.text() for item in selected_items]
            self.samples_selected.emit(selected_samples)
        else:
            self.samples_selected.emit([])

    def on_compound_selection_changed(self):
        """
        Handler for when the selection changes in the compounds list widget.
        Emits the custom signal with the selected compound.
        """
        selected_items = self.compound_list.selectedItems()
        if selected_items:
            selected_text = selected_items[0].text()
            self.compound_selected.emit(selected_text)
            # Initial fill - will be updated by plot selection logic after plotting
            self.fill_integration_window(selected_text)
            # Update baseline checkbox state
            self._set_baseline_checkbox_from_compound(selected_text)
            self.sync_selected_peak_checkbox(selected_text)
        else:
            self.compound_selected.emit("")


    def on_internal_standard_selected(self, compound_name: str):
        """
        Handler for when a compound is selected as internal standard.
        Updates the standard indicator widget and emits signal.
        """
        self.standard.set_internal_standard(compound_name)
        self.internal_standard_selected.emit(compound_name)

    # --- Public Methods ---
    def update_label_colours(self, raw_data_loaded, compound_list_loaded):
        """Record what is loaded; the header, hints and inspector follow it."""
        self._raw_loaded = raw_data_loaded
        self._compounds_loaded = compound_list_loaded
        self._refresh_data_state()

    def update_compound_list(
        self, compounds: List[str], selected_name: str | None = None
    ):
        """Update the compounds list widget"""
        self.compound_list.update_compounds(compounds, selected_name)
        self.compound_filter.reapply()

    def update_sample_list(self, samples: List[str]):
        """Update the samples list widget"""
        self.sample_list.update_samples(samples)
        self.sample_filter.reapply()
        self._refresh_data_state()

    def set_selected_samples(self, names: Iterable[str]) -> None:
        self.sample_list.set_selected_samples(names)

    def select_all_samples(self) -> None:
        self.sample_list.select_all_samples()

    def get_selected_samples(self):
        """
        Get the currently selected samples without emitting signals.
        Avoid infinite recursion via signals.
        Returns a list of strings.
        """
        selected_items = self.sample_list.selectedItems()
        if selected_items:
            return [item.text() for item in selected_items]
        else:
            return []

    def get_selected_compound(self):
        """
        Get the currently selected compound without emitting signals.
        Avoid infinite recursion via signals.
        Returns a string.
        """
        selected_items = self.compound_list.selectedItems()
        if selected_items:
            return selected_items[0].text()
        else:
            return ""

    def get_internal_standard(self):
        """
        Get the currently selected internal standard.
        Returns the compound name or None if no standard is selected.
        """
        return self.standard.internal_standard

    def fill_integration_window(self, compound_name: str):
        """
        Legacy method - no longer used.

        Integration window fields are now populated by populate_fields_from_plots()
        which properly handles session data overrides. This method previously
        populated fields with base compound data, overwriting session values.
        """
        pass

    def _set_baseline_checkbox_from_compound(self, compound_name: str):
        """Set baseline correction checkbox state from compound data."""
        try:
            comp = read_compound(compound_name)
            enabled = bool(getattr(comp, "baseline_correction", 0))
            self.baseline_checkbox.blockSignals(True)
            self.baseline_checkbox.setChecked(enabled)
            self.baseline_checkbox.blockSignals(False)
        except Exception:
            self.baseline_checkbox.blockSignals(True)
            self.baseline_checkbox.setChecked(False)
            self.baseline_checkbox.blockSignals(False)

    def sync_selected_peak_checkbox(self, compound_name: str):
        checkbox = self.selected_peak_yscale_checkbox
        if checkbox is None:
            return
        checkbox.setEnabled(_deconvolution_on(compound_name))
        if not checkbox.isEnabled() and checkbox.isChecked():
            self._commit_y_scale_policy(YScalePolicy.PER_TILE_EXTRACT)

    def _on_shared_yscale_toggled(self, state: int):
        self._commit_y_scale_policy(
            YScalePolicy.SHARED_EXTRACT
            if state != 0
            else YScalePolicy.PER_TILE_EXTRACT
        )

    def _on_selected_peak_yscale_toggled(self, state: int):
        self._commit_y_scale_policy(
            YScalePolicy.PER_TILE_SELECTED_PEAK
            if state != 0
            else YScalePolicy.PER_TILE_EXTRACT
        )

    def _commit_y_scale_policy(self, policy: YScalePolicy) -> None:
        if policy not in self._available_y_scale_policies:
            policy = YScalePolicy.PER_TILE_EXTRACT
        changed = policy is not self._y_scale_policy
        self._y_scale_policy = policy
        self.shared_yscale_checkbox.blockSignals(True)
        self.shared_yscale_checkbox.setChecked(
            policy is YScalePolicy.SHARED_EXTRACT
        )
        self.shared_yscale_checkbox.blockSignals(False)
        if self.selected_peak_yscale_checkbox is not None:
            self.selected_peak_yscale_checkbox.blockSignals(True)
            self.selected_peak_yscale_checkbox.setChecked(
                policy is YScalePolicy.PER_TILE_SELECTED_PEAK
            )
            self.selected_peak_yscale_checkbox.blockSignals(False)
        if changed:
            self.y_scale_policy_changed.emit(self._y_scale_policy)

    def _on_baseline_checkbox_toggled(self, state: int):
        """Handle baseline correction checkbox toggle - update DB and emit signal."""
        compound_name = self.get_selected_compound()
        if not compound_name:
            return

        enabled = state != 0

        try:
            from manic.models.database import get_connection

            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE compounds
                    SET baseline_correction = ?
                    WHERE compound_name = ? AND deleted = 0
                    """,
                    (1 if enabled else 0, compound_name),
                )

            self.baseline_correction_changed.emit(compound_name, enabled)

        except Exception as e:
            logger.exception("Failed to update baseline setting: %s", e)
            self._set_baseline_checkbox_from_compound(compound_name)

    def on_internal_standard_cleared(self):
        """Handler for clearing the internal standard."""
        self.standard.clear_internal_standard()  # Calls existing method
        self.internal_standard_selected.emit(None)  # Notify MainWindow standard is gone
