import logging
from collections.abc import Iterable
from typing import List

from PySide6.QtCore import QEvent, QSettings, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
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
    NoMatchHint,
    divider,
    section_heading,
    shortcut_text,
)
from .standard_indicator_widget import StandardIndicator
from .targeted_qc_widget import TargetedQcWidget
from .total_abundance_widget import TotalAbundanceWidget

logger = logging.getLogger(__name__)

# Before the inspector takes the rest, the lists keep this many rows each (compounds,
# samples) and together this share of the sidebar. The Peak window always stays whole.
BROWSE_MIN_ROWS = (6, 4)
BROWSE_MIN_SHARE = 0.45
# Room past each list's floor goes compounds:samples in this ratio, up to each one's rows.
BROWSE_WEIGHTS = (3, 2)
LIST_MIN_HEIGHT = 72
# Summary opens by itself only when its first chart gets at least this much height.
SUMMARY_MIN_CHART = 100
SPLIT_SETTING = "sidebar/browse_share"
SUMMARY_SETTING = "sidebar/summary_expanded"


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
        browse_layout.addWidget(self.compound_list, 1)
        self.compound_no_match = NoMatchHint(
            "No matching compounds", self.compound_filter
        )
        browse_layout.addWidget(self.compound_no_match)
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
            "Type to filter. Checked samples are the ones shown in the grid."
        )
        samples_body_layout.addWidget(self.sample_filter)
        samples_body_layout.addWidget(self.sample_list, 1)
        self.sample_no_match = NoMatchHint("No matching samples", self.sample_filter)
        samples_body_layout.addWidget(self.sample_no_match)
        self.sample_empty = QLabel("Samples appear here once you load raw data.")
        self.sample_empty.setProperty("role", "hint")
        self.sample_empty.setWordWrap(True)
        samples_body_layout.addWidget(self.sample_empty)
        self.samples_section = CollapsibleSection(
            "Samples", samples_body, settings_key="sidebar/samples_expanded"
        )
        browse_layout.addWidget(self.samples_section)
        # Takes what is left once each list is as tall as its rows.
        browse_layout.addStretch(0)

        # Inspector: peak window, display options and summaries scroll together.
        inspector_content = QWidget()
        inspector_content.setObjectName("sidebarInspector")
        inspector_layout = QVBoxLayout(inspector_content)
        inspector_layout.setContentsMargins(16, 12, 16, 12)
        inspector_layout.setSpacing(12)
        # Programmatic checkbox updates set this so they refresh summaries and
        # menus through toggled without committing anything.
        self._syncing_checkboxes = False

        peak_body = QWidget()
        peak_layout = QVBoxLayout(peak_body)
        peak_layout.setContentsMargins(0, 0, 0, 0)
        peak_layout.setSpacing(8)
        self.integration = IntegrationWindow(self.analysis_mode)
        peak_layout.addWidget(self.integration)

        self.baseline_checkbox = QCheckBox("Baseline correction")
        self.baseline_checkbox.setObjectName("baseline_correction_checkbox")
        self.baseline_checkbox.setToolTip(
            "Enable linear baseline subtraction for this compound.\n"
            "Fits a line through 3 points at each edge of the integration window\n"
            "and subtracts the area under this baseline from the peak area."
        )
        self.baseline_checkbox.stateChanged.connect(self._on_baseline_checkbox_toggled)
        peak_layout.addWidget(self.baseline_checkbox)

        self.peak_section = CollapsibleSection(
            "Peak window",
            peak_body,
            expanded=True,
            settings_key="sidebar/peak_window_expanded",
        )
        self.baseline_checkbox.toggled.connect(self._refresh_peak_summary)
        self.integration.findChild(QLineEdit, "tr_input").textChanged.connect(
            self._refresh_peak_summary
        )
        self._refresh_peak_summary()
        inspector_layout.addWidget(self.peak_section)
        inspector_layout.addWidget(divider())

        display_body = QWidget()
        display_layout = QVBoxLayout(display_body)
        display_layout.setContentsMargins(16, 0, 0, 0)
        display_layout.setSpacing(6)

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

        self.display_section = CollapsibleSection(
            "Display", display_body, settings_key="sidebar/display_expanded"
        )
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
        self.summary_section = CollapsibleSection(
            "Summary", summary, expanded=True, settings_key=SUMMARY_SETTING
        )
        inspector_layout.addWidget(self.summary_section, 1)

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
        self.splitter.handle(1).setToolTip("Drag to share space between lists and inspector")
        # A split the user dragged to is kept, as a share of the height, across runs.
        saved = QSettings().value(SPLIT_SETTING)
        self._browse_share = float(saved) if saved is not None else None
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        self._summary_started = False
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self.fit_inspector)
        inspector_content.installEventFilter(self)
        for section in (
            self.samples_section,
            self.peak_section,
            self.display_section,
            self.summary_section,
        ):
            section.toggled.connect(self._fit_timer.start)

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
        """The Display section's toggles, which the View menu mirrors."""
        boxes = [self.shared_yscale_checkbox]
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
        self.display_section.summary.setText(scale)

    def _refresh_peak_summary(self, *_args) -> None:
        baseline = "Baseline on" if self.baseline_checkbox.isChecked() else "No baseline"
        tr = self.integration.findChild(QLineEdit, "tr_input").text().strip()
        self.peak_section.summary.setText(f"tR {tr} · {baseline}" if tr else baseline)

    def _set_checked_quietly(self, checkbox: QCheckBox, checked: bool) -> None:
        """Show a state that is already committed: summaries and menus follow, nothing is saved."""
        self._syncing_checkboxes = True
        try:
            checkbox.setChecked(checked)
        finally:
            self._syncing_checkboxes = False

    def _refresh_data_state(self) -> None:
        """Header rows, counts and empty hints from what is loaded right now."""
        compounds = self.compound_list.real_count()
        samples = self.sample_list.real_count()
        self.loaded_data.update_status(
            self._raw_loaded, self._compounds_loaded, compounds, samples
        )

        has_compounds = compounds > 0
        visible = self.compound_filter.visible_count()
        no_match = has_compounds and visible == 0
        self.compound_list.setVisible(has_compounds and not no_match)
        self.compound_filter.setVisible(has_compounds)
        self.compound_no_match.setVisible(no_match)
        self.compound_empty.setVisible(not has_compounds)
        self.compound_count_label.setText(
            ""
            if not has_compounds
            else str(compounds)
            if visible == compounds
            else f"{visible} of {compounds}"
        )

        has_samples = samples > 0
        matching = self.sample_filter.visible_count()
        filtering = has_samples and bool(self.sample_filter.text().strip())
        self.sample_list.setVisible(has_samples and matching > 0)
        self.sample_filter.setVisible(has_samples)
        self.sample_no_match.setVisible(has_samples and matching == 0)
        self.sample_empty.setVisible(not has_samples)
        shown = len(self.get_selected_samples())
        if not has_samples:
            summary = ""
        elif filtering:
            summary = f"{shown} shown · {matching} match"
        elif shown == samples:
            summary = f"{samples} · all shown"
        else:
            summary = f"{shown} of {samples} shown"
        self.samples_section.summary.setText(summary)

        self.inspector.setVisible(self._raw_loaded)
        self._fit_timer.start()

    def _on_splitter_moved(self, *_args) -> None:
        total = sum(self.splitter.sizes())
        if total > 0:
            self._browse_share = self.splitter.sizes()[0] / total
            QSettings().setValue(SPLIT_SETTING, self._browse_share)
        self._fit_timer.start()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.LayoutRequest:
            self._fit_timer.start()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_timer.start()

    @staticmethod
    def _rows_height(lst: QListWidget, rows: int | None = None) -> int:
        """Height of ``rows`` rows, or of every row the filter leaves."""
        shown = sum(1 for row in range(lst.count()) if not lst.isRowHidden(row))
        rows = shown if rows is None else min(rows, shown)
        return rows * max(lst.sizeHintForRow(0), 1) + 2 * lst.frameWidth()

    def _browse_lists(self) -> list[tuple[QListWidget, int, int, int]]:
        """Each showing list with the height it keeps, the height of all its rows, its weight."""
        lists = (self.compound_list, self.sample_list)
        return [
            (lst, self._rows_height(lst, keep), self._rows_height(lst), weight)
            for lst, keep, weight in zip(lists, BROWSE_MIN_ROWS, BROWSE_WEIGHTS)
            if lst.isVisibleTo(self)
        ]

    @staticmethod
    def _share_lists(space: int, lists) -> list[int]:
        """Each list its floor first (scaled down if short), then by weight up to its rows."""
        floors = [floor for _lst, floor, _rows, _w in lists]
        if space <= sum(floors):
            return [space * floor // max(sum(floors), 1) for floor in floors]
        heights = list(floors)
        rest = space - sum(floors)
        for _ in lists:
            growing = [i for i, item in enumerate(lists) if heights[i] < item[2]]
            if rest <= 0 or not growing:
                break
            weight = sum(lists[i][3] for i in growing)
            pool = rest
            for i in growing:
                add = min(pool * lists[i][3] // weight, lists[i][2] - heights[i])
                heights[i] += add
                rest -= add
        return heights

    def _set_list_heights(self, browse: int, chrome: int, lists) -> None:
        # A closed section must not grow; an open one grows up to its list's height.
        self.splitter.widget(0).layout().setStretchFactor(
            self.samples_section, int(self.samples_section.is_expanded())
        )
        for (lst, *_rest), height in zip(lists, self._share_lists(browse - chrome, lists)):
            lst.setMinimumHeight(min(LIST_MIN_HEIGHT, height))
            lst.setMaximumHeight(height)

    def _peak_height(self) -> int:
        """Inspector height that shows the whole Peak window without scrolling."""
        content = self.inspector.widget()
        margins = content.layout().contentsMargins()
        width = self.inspector.viewport().width() - margins.left() - margins.right()
        height = self.peak_section.heightForWidth(width)
        if height < 0:
            height = self.peak_section.sizeHint().height()
        return margins.top() + height + margins.bottom()

    def _start_summary(self, inspector: int) -> None:
        """Summary starts open only if its first chart fits, unless the user already chose."""
        self._summary_started = True
        if QSettings().contains(SUMMARY_SETTING):
            return
        header = self.summary_section.header
        chart_top = self.summary_section.y() + header.height() + 8
        self.summary_section.set_expanded(inspector >= chart_top + SUMMARY_MIN_CHART)

    def fit_inspector(self) -> None:
        """The Peak window stays whole, the lists keep their floor, the inspector takes the rest."""
        total = sum(self.splitter.sizes())
        if self.inspector.isHidden() or total <= 0:
            return
        lists = self._browse_lists()
        chrome = self.splitter.widget(0).minimumSizeHint().height() - sum(
            lst.minimumHeight() for lst, *_rest in lists
        )
        full = chrome + sum(rows for _lst, _floor, rows, _w in lists)
        floor = chrome + sum(floor for _lst, floor, _rows, _w in lists)
        # The lists never take more than their rows, nor room the Peak window needs.
        cap = min(full, total - self._peak_height())
        if self._browse_share is not None:
            browse = min(int(total * self._browse_share), cap)
        else:
            browse = min(max(floor, int(total * BROWSE_MIN_SHARE)), cap)
        if not self._summary_started:
            self._start_summary(total - browse)
        if self._browse_share is None:
            wanted = self.inspector.widget().minimumSizeHint().height()
            browse = min(max(browse, total - wanted), cap)
        self._set_list_heights(browse, chrome, lists)
        if self.splitter.sizes()[0] != browse:
            self.splitter.setSizes([browse, total - browse])

    def _connect_signals(self):
        """Connect child widget signals to toolbar signal handlers"""
        self.sample_list.shown_changed.connect(self.on_samples_selection_changed)
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
        self.sample_list.shown_changed.connect(self._refresh_data_state)
        self.compound_filter.filtered.connect(self._refresh_data_state)
        self.sample_filter.filtered.connect(self._refresh_data_state)
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
            menu.addAction("Load a Compound List First").setEnabled(False)
        for name in names:
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name == self.standard.internal_standard)
            action.triggered.connect(
                lambda _checked=False, n=name: self.on_internal_standard_selected(n)
            )
        menu.addSeparator()
        clear = menu.addAction("No Internal Standard")
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
        self.samples_selected.emit(self.get_selected_samples())

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
            self.inspector.verticalScrollBar().setValue(0)
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
        """Show exactly these samples in the grid."""
        self.sample_list.set_shown_samples(names)

    def select_all_samples(self) -> None:
        self.sample_list.show_all_samples()

    def get_selected_samples(self) -> list[str]:
        """The samples shown in the grid, in list order, without emitting signals."""
        return self.sample_list.shown_samples()

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
        except Exception:
            enabled = False
        self._set_checked_quietly(self.baseline_checkbox, enabled)

    def sync_selected_peak_checkbox(self, compound_name: str):
        checkbox = self.selected_peak_yscale_checkbox
        if checkbox is None:
            return
        checkbox.setEnabled(_deconvolution_on(compound_name))
        if not checkbox.isEnabled() and checkbox.isChecked():
            self._commit_y_scale_policy(YScalePolicy.PER_TILE_EXTRACT)

    def _on_shared_yscale_toggled(self, state: int):
        if self._syncing_checkboxes:
            return
        self._commit_y_scale_policy(
            YScalePolicy.SHARED_EXTRACT
            if state != 0
            else YScalePolicy.PER_TILE_EXTRACT
        )

    def _on_selected_peak_yscale_toggled(self, state: int):
        if self._syncing_checkboxes:
            return
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
        self._set_checked_quietly(
            self.shared_yscale_checkbox, policy is YScalePolicy.SHARED_EXTRACT
        )
        if self.selected_peak_yscale_checkbox is not None:
            self._set_checked_quietly(
                self.selected_peak_yscale_checkbox,
                policy is YScalePolicy.PER_TILE_SELECTED_PEAK,
            )
        if changed:
            self.y_scale_policy_changed.emit(self._y_scale_policy)

    def _on_baseline_checkbox_toggled(self, state: int):
        """Handle baseline correction checkbox toggle - update DB and emit signal."""
        compound_name = self.get_selected_compound()
        if self._syncing_checkboxes or not compound_name:
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
