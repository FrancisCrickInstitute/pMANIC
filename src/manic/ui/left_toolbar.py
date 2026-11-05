import logging
from collections.abc import Iterable
from typing import List, NamedTuple

from PySide6.QtCore import QEvent, QPoint, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QSizePolicy,
    QSplitter,
    QToolButton,
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
    SUMMARY_CHART_MAX_HEIGHT,
    CollapsibleSection,
    FilterField,
    divider,
    section_heading,
    shortcut_text,
)
from .standard_chooser import StandardChooser
from .standard_indicator_widget import StandardIndicator, lacking_amount
from .targeted_qc_widget import TargetedQcWidget
from .total_abundance_widget import TotalAbundanceWidget

logger = logging.getLogger(__name__)

# The lists give rows to the Peak window down to BROWSE_HARD_ROWS each (compounds,
# samples) for its editor and folded rows, and down to BROWSE_KEEP_ROWS for the rest
# of it. Then they grow to BROWSE_MIN_ROWS and together this share of the sidebar.
BROWSE_HARD_ROWS = (3, 3)
# Short of those, they give rows up in this order, so Compounds keeps three as long as it
# can (Samples has its own filter, and the grid shows what is checked): down to three
# compounds and one sample, then to one row each.
BROWSE_LAST_ROWS = ((1, 1), (3, 1))
BROWSE_KEEP_ROWS = (4, 3)
BROWSE_MIN_ROWS = (6, 4)
BROWSE_MIN_SHARE = 0.45
# Room past each list's floor goes compounds:samples in this ratio, up to each one's rows.
BROWSE_WEIGHTS = (3, 2)
# The summaries share the inspector with the Peak window only when each chart gets this much.
SUMMARY_MIN_CHART = 140
SPLIT_SETTING = "sidebar/browse_share"
SUMMARY_SETTING = "sidebar/summary_expanded"
Y_SCALE_SETTING = "view/y_scale_policy"


class _BrowseList(NamedTuple):
    widget: QListWidget
    last: tuple[int, ...]  # heights of its BROWSE_LAST_ROWS, the rows it gives up last
    hard: int  # height of the rows it keeps even beside the Peak window editor
    keep: int  # height of the rows it never gives up to the rest of the Peak window
    floor: int  # height of the rows it keeps while the Peak window fits
    full: int  # height of every row the filter leaves
    weight: int


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

    def __init__(
        self,
        analysis_mode: AnalysisMode | str = AnalysisMode.LABELLED,
    ):
        super().__init__()
        self.analysis_mode = AnalysisMode.coerce(analysis_mode)
        self.setObjectName("toolbar")  # Required for CSS targeting
        self.y_scale_policy = YScalePolicy.PER_TILE_EXTRACT
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
        self.standard = StandardIndicator(self.analysis_mode)
        header_layout.addWidget(self.standard)
        # Under the row's title: the row's padding and icon, then its spacing.
        self.standard.note.setContentsMargins(28, 0, 6, 2)
        header_layout.addWidget(self.standard.note)

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

        browse_layout.addWidget(divider())

        self.sample_list = SampleListWidget()
        for lst in (self.compound_list, self.sample_list):
            # fit_inspector sets each list's floor; Qt's default must not hold the window open.
            lst.setMinimumHeight(1)
        samples_body = QWidget()
        samples_body_layout = QVBoxLayout(samples_body)
        samples_body_layout.setContentsMargins(0, 0, 0, 0)
        samples_body_layout.setSpacing(8)
        self.sample_filter = FilterField(self.sample_list, "Filter samples")
        self.sample_filter.setToolTip("Checked samples are the ones shown in the grid")
        samples_body_layout.addWidget(self.sample_filter)
        samples_body_layout.addWidget(self.sample_list, 1)
        self.samples_section = CollapsibleSection(
            "Samples", samples_body, settings_key="sidebar/samples_expanded"
        )
        browse_layout.addWidget(self.samples_section)
        # Takes what is left once each list is as tall as its rows.
        browse_layout.addStretch(0)

        # Inspector: the Peak window over the summaries. Nothing here scrolls as a whole;
        # fit_inspector gives it the height its parts need.
        inspector_content = QWidget()
        inspector_content.setObjectName("sidebarInspector")
        inspector_layout = QVBoxLayout(inspector_content)
        inspector_layout.setContentsMargins(16, 8, 16, 8)
        inspector_layout.setSpacing(12)
        # Programmatic checkbox updates set this so they refresh summaries and
        # menus through toggled without committing anything.
        self._syncing_checkboxes = False

        self.integration = IntegrationWindow(self.analysis_mode)
        self.baseline_checkbox = QCheckBox("Baseline correction")
        self.baseline_checkbox.setObjectName("baseline_correction_checkbox")
        self.baseline_checkbox.setToolTip(
            "Enable linear baseline subtraction for this compound.\n"
            "Fits a line through 3 points at each edge of the integration window\n"
            "and subtracts the area under this baseline from the peak area."
        )
        self.baseline_checkbox.stateChanged.connect(self._on_baseline_checkbox_toggled)
        self.integration.more.body.layout().insertWidget(0, self.baseline_checkbox)

        self.peak_section = CollapsibleSection(
            "Peak window",
            self.integration,
            expanded=True,
            settings_key="sidebar/peak_window_expanded",
        )
        self.baseline_checkbox.toggled.connect(self._refresh_peak_summary)
        self.integration.findChild(QLineEdit, "tr_input").textChanged.connect(
            self._refresh_peak_summary
        )
        self.integration.tr_window_edit.textChanged.connect(self._refresh_peak_summary)
        self.integration.state_changed.connect(self._refresh_peak_summary)
        self._refresh_peak_summary()
        inspector_layout.addWidget(self.peak_section)
        # An open section's own controls show its state, so the heading summary is for a closed one.
        self.peak_section.toggled.connect(self.peak_section.summary.setHidden)
        self.peak_section.summary.setHidden(self.peak_section.is_expanded())
        self._inspector_divider = divider()
        inspector_layout.addWidget(self._inspector_divider)

        summary = QWidget()
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(8)
        self.isotopologue_ratios = IsotopologueRatioWidget()
        self.targeted_qc = TargetedQcWidget()
        self.total_abundance = TotalAbundanceWidget()
        first = (
            self.targeted_qc
            if self.analysis_mode is AnalysisMode.UNLABELLED
            else self.isotopologue_ratios
        )
        # Each chart folds to its title when the switcher shows one at a time.
        self._charts: list[CollapsibleSection] = []
        for chart in (first, self.total_abundance):
            section = CollapsibleSection(chart.header.title.text(), chart, expanded=True)
            section.set_headless(True)
            section.header.clicked.connect(lambda _c=False, s=section: self._choose_chart(s))
            # A chart at its tallest sits at the top of its room, not in the middle.
            section.layout().setStretchFactor(chart, 1)
            section.layout().addStretch(0)
            summary_layout.addWidget(section, 1)
            self._charts.append(section)
        self._chart = self._charts[0]
        other = ({self.isotopologue_ratios, self.targeted_qc} - {first}).pop()
        other.setParent(summary)
        other.hide()
        self.summary_section = CollapsibleSection(
            "Summary", summary, expanded=True, settings_key=SUMMARY_SETTING
        )
        inspector_layout.addWidget(self.summary_section)
        inspector_layout.addStretch(0)
        self.inspector = inspector_content

        QWidget.setTabOrder(
            self.integration.findChild(QLineEdit, "ro_input"), self.integration.restore_button
        )
        QWidget.setTabOrder(self.integration.restore_button, self.integration.apply_button)
        QWidget.setTabOrder(self.integration.apply_button, self.integration.more.header)
        QWidget.setTabOrder(self.integration.more.header, self.baseline_checkbox)
        QWidget.setTabOrder(self.baseline_checkbox, self.integration.tr_window_edit)

        # On a short sidebar this stands in for the section headings: one section at a time.
        self._compact = False
        self._pane = self.peak_section
        self.section_switcher = QWidget()
        self.section_switcher.setObjectName("inspectorSwitcher")
        switcher_layout = QHBoxLayout(self.section_switcher)
        switcher_layout.setContentsMargins(16, 4, 16, 0)
        switcher_layout.setSpacing(0)
        self._switch_buttons = QButtonGroup(self.section_switcher)
        for key, text, section in (
            ("peak", "Peak window", self.peak_section),
            ("summary", "Summary", self.summary_section),
        ):
            button = QToolButton()
            button.setObjectName(f"switch_{key}")
            button.setText(text)
            button.setCheckable(True)
            button.setChecked(section is self._pane)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _checked=False, s=section: self.show_pane(s))
            self._switch_buttons.addButton(button)
            switcher_layout.addWidget(button)
        self.section_switcher.hide()

        self._inspector_pane = QWidget()
        pane_layout = QVBoxLayout(self._inspector_pane)
        pane_layout.setContentsMargins(0, 0, 0, 0)
        pane_layout.setSpacing(0)
        pane_layout.addWidget(self.section_switcher)
        pane_layout.addWidget(self.inspector, 1)

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(5)
        self.splitter.addWidget(browse)
        self.splitter.addWidget(self._inspector_pane)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.handle(1).setToolTip("Drag to share space between lists and inspector")
        # A split the user dragged to is kept, as a share of the height, across runs.
        saved = QSettings().value(SPLIT_SETTING)
        self._browse_share = float(saved) if saved is not None else None
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self.fit_inspector)
        inspector_content.installEventFilter(self)
        for section in (self.samples_section, self.peak_section, self.summary_section):
            section.toggled.connect(self._fit_timer.start)

        self._build_scale_actions()
        self._hold_inspector_floor()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(header)
        main_layout.addWidget(self.splitter, 1)

        # Wide enough that sample names on the Identity chart remain readable.
        self.setMinimumWidth(256)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._refresh_data_state()

    def _build_scale_actions(self) -> None:
        """The plots' y-scale choices, which the View menu lists; the last choice is remembered."""
        self.shared_yscale_action = QAction("Shared Y-Scale", self)
        self.shared_yscale_action.setCheckable(True)
        self.shared_yscale_action.setToolTip(
            "Use one common intensity scale for all sample plots.\n"
            "Off: each plot autoscales to its own tallest peak."
        )
        self.shared_yscale_action.triggered.connect(
            lambda on: self._choose_y_scale(
                YScalePolicy.SHARED_EXTRACT if on else YScalePolicy.PER_TILE_EXTRACT
            )
        )
        self.selected_peak_yscale_action = None
        if YScalePolicy.PER_TILE_SELECTED_PEAK in self._available_y_scale_policies:
            self.selected_peak_yscale_action = QAction("Scale to Selected Peak", self)
            self.selected_peak_yscale_action.setCheckable(True)
            self.selected_peak_yscale_action.setToolTip(
                "Scale each sample to its selected peak (component nearest tR).\n"
                "Needs deconvolution on for this compound (Settings > Deconvolution).\n"
                "Other peaks in the extract may clip.\n"
                "Off: each plot autoscales to its extract."
            )
            self.selected_peak_yscale_action.triggered.connect(
                lambda on: self._choose_y_scale(
                    YScalePolicy.PER_TILE_SELECTED_PEAK if on else YScalePolicy.PER_TILE_EXTRACT
                )
            )
        try:
            saved = YScalePolicy(QSettings().value(Y_SCALE_SETTING, ""))
        except ValueError:
            saved = YScalePolicy.PER_TILE_EXTRACT
        self._commit_y_scale_policy(saved)

    def scale_actions(self) -> list[QAction]:
        return [
            action
            for action in (self.shared_yscale_action, self.selected_peak_yscale_action)
            if action is not None
        ]

    def _refresh_peak_summary(self, *_args) -> None:
        baseline = "Baseline on" if self.baseline_checkbox.isChecked() else "No baseline"
        tr = self.integration.findChild(QLineEdit, "tr_input").text().strip()
        self.peak_section.summary.setText(f"tR {tr} · {baseline}" if tr else baseline)
        window = self.integration.tr_window_edit.text().strip()
        state = "On" if self.baseline_checkbox.isChecked() else "Off"
        if self.integration.has_window_draft():
            summary = f"{state} · not applied"
        else:
            summary = f"{state} · {window} min" if window else state
        self.integration.more.summary.setText(summary)

    def _set_checked_quietly(self, checkbox: QCheckBox, checked: bool) -> None:
        """Show a state that is already committed: summaries and menus follow, nothing is saved."""
        self._syncing_checkboxes = True
        try:
            checkbox.setChecked(checked)
        finally:
            self._syncing_checkboxes = False

    def _refresh_data_state(self) -> None:
        """Header rows, counts and filter hints from what is loaded right now."""
        compounds = self.compound_list.real_count()
        samples = self.sample_list.real_count()
        self.loaded_data.update_status(self._raw_loaded, self._compounds_loaded)

        has_compounds = compounds > 0
        visible = self.compound_filter.visible_count()
        no_match = has_compounds and visible == 0
        self.compound_list.setVisible(has_compounds and not no_match)
        self.compound_filter.setVisible(has_compounds)
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

        self._inspector_pane.setVisible(self._raw_loaded)
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

    def _browse_lists(self) -> list[_BrowseList]:
        lists = (self.compound_list, self.sample_list)
        return [
            _BrowseList(
                lst,
                tuple(self._rows_height(lst, rows) for rows in last),
                self._rows_height(lst, hard),
                self._rows_height(lst, keep),
                self._rows_height(lst, floor),
                self._rows_height(lst),
                weight,
            )
            for lst, last, hard, keep, floor, weight in zip(
                lists,
                zip(*BROWSE_LAST_ROWS),
                BROWSE_HARD_ROWS,
                BROWSE_KEEP_ROWS,
                BROWSE_MIN_ROWS,
                BROWSE_WEIGHTS,
            )
            if lst.isVisibleTo(self)
        ]

    @staticmethod
    def _share_lists(space: int, lists: list[_BrowseList]) -> list[int]:
        """Last rows, hard rows, kept rows, then floors (each shared in proportion if short),
        then by weight up to every row."""
        heights = [0] * len(lists)
        for target in (
            *([item.last[tier] for item in lists] for tier in range(len(BROWSE_LAST_ROWS))),
            [item.hard for item in lists],
            [item.keep for item in lists],
            [item.floor for item in lists],
        ):
            need = [max(goal - height, 0) for goal, height in zip(target, heights)]
            rest = space - sum(heights)
            if rest <= sum(need):
                return [h + rest * n // max(sum(need), 1) for h, n in zip(heights, need)]
            heights = [max(h, goal) for h, goal in zip(heights, target)]
        rest = space - sum(heights)
        for _ in lists:
            growing = [i for i, item in enumerate(lists) if heights[i] < item.full]
            if rest <= 0 or not growing:
                break
            weight = sum(lists[i].weight for i in growing)
            pool = rest
            for i in growing:
                add = min(pool * lists[i].weight // weight, lists[i].full - heights[i])
                heights[i] += add
                rest -= add
        return heights

    def _set_list_heights(self, browse: int, chrome: int, lists: list[_BrowseList]) -> None:
        # A closed section must not grow; an open one grows up to its content.
        self.splitter.widget(0).layout().setStretchFactor(
            self.samples_section, int(self.samples_section.is_expanded())
        )
        self.inspector.layout().setStretchFactor(
            self.summary_section,
            int(self.summary_section.is_expanded() or self._compact),
        )
        for item, height in zip(lists, self._share_lists(browse - chrome, lists)):
            # Whole rows only; what is left stays blank under the lists.
            row, frame = max(item.widget.sizeHintForRow(0), 1), 2 * item.widget.frameWidth()
            height = max(height - frame, 0) // row * row + frame
            # A floor of one row leaves the window room for a line the sidebar gains, such
            # as the standard's note; fit_inspector restores the hard rows when it can.
            item.widget.setMinimumHeight(min(item.last[0], height) or 1)
            item.widget.setMaximumHeight(height)
        # Set here as well, one level under the splitter like the inspector's floor: Qt reads
        # a list's new floor through each layout in turn, too late when the inspector's rises.
        self.splitter.widget(0).setMinimumHeight(
            chrome + sum(item.widget.minimumHeight() for item in lists)
        )

    def _peak_height(self, compact: bool, whole: bool) -> int:
        """Inspector height for the Peak window: its editor and the folded rows below, or all of it."""
        margins = self.inspector.layout().contentsMargins()
        height = margins.top() + margins.bottom()
        section = self.peak_section
        if compact:
            height += self.section_switcher.sizeHint().height()
        else:
            height += section.header.sizeHint().height()
            if not section.is_expanded():
                return height
            height += section.layout().spacing()
        return (
            height
            + self.integration.editor_height()
            + self.integration.layout().spacing()
            + self.integration.lower_height(whole)
        )

    def _full_inspector_height(self) -> int:
        """Height for the whole Peak window and every summary chart, with no switcher."""
        spacing = self.inspector.layout().spacing()
        section = self.summary_section
        height = (
            self._peak_height(compact=False, whole=True)
            + 2 * spacing
            + self._inspector_divider.height()
            + section.header.sizeHint().height()
        )
        if section.is_expanded():
            charts = len(self._charts)
            height += section.layout().spacing() + charts * SUMMARY_MIN_CHART
            height += (charts - 1) * section.body.layout().spacing()
        return height

    def _summary_pane_height(self) -> int:
        """Inspector height for the switcher's Summary: the open chart at its tallest,
        the others folded to their titles."""
        margins = self.inspector.layout().contentsMargins()
        folded = self.summary_section.body.layout().spacing() + self._chart.header.sizeHint().height()
        return (
            self.section_switcher.sizeHint().height()
            + margins.top()
            + margins.bottom()
            + (len(self._charts) - 1) * folded
            + SUMMARY_CHART_MAX_HEIGHT
        )

    def _set_compact(self, compact: bool) -> None:
        """Too short for every section: the switcher shows one at a time, in place of their headings."""
        if compact == self._compact:
            return
        self._compact = compact
        self.section_switcher.setVisible(compact)
        self._inspector_divider.setVisible(not compact)
        self.show_pane(self._pane)
        self._choose_chart(self._chart)

    def show_pane(self, section: CollapsibleSection) -> None:
        """Pick the section the switcher shows; it shows every section again once there is room."""
        self._pane = section
        for button, candidate in zip(
            self._switch_buttons.buttons(), (self.peak_section, self.summary_section)
        ):
            button.setChecked(candidate is section)
            candidate.set_headless(self._compact)
            candidate.setVisible(not self._compact or candidate is section)

    def _choose_chart(self, chart: CollapsibleSection) -> None:
        """With the switcher, one summary chart takes the height and the others fold to a title."""
        self._chart = chart
        layout = self.summary_section.body.layout()
        for candidate in self._charts:
            whole = not self._compact or candidate is chart
            candidate.set_expanded(whole)
            candidate.set_headless(whole)
            layout.setStretchFactor(candidate, int(whole))

    def _hold_inspector_floor(self) -> None:
        # Below the stacked sections' own minimum the switcher takes over, so that minimum
        # must never hold the window open.
        integration = self.integration
        # The hidden scope line's room; a shown caption's size hint can wrap taller than it shows.
        reserved = max(integration.editor_height() - integration.editor.sizeHint().height(), 0)
        self._inspector_pane.setMinimumHeight(
            self._peak_height(compact=True, whole=False) - reserved
        )

    def fit_inspector(self) -> None:
        """The lists keep their hard rows, the Peak window editor stays whole, the lists keep
        their kept rows, the rest of the Peak window fits, then the summaries take the rest."""
        total = sum(self.splitter.sizes())
        if self._inspector_pane.isHidden() or total <= 0:
            self.splitter.widget(0).setMinimumHeight(0)
            return
        lists = self._browse_lists()
        chrome = self.splitter.widget(0).minimumSizeHint().height() - sum(
            item.widget.minimumHeight() for item in lists
        )
        # Fold the rows below the editor when the whole Peak window cannot sit beside the
        # lists' hard rows; whether the user opened them does not change that.
        hard = dict(zip((self.compound_list, self.sample_list), BROWSE_HARD_ROWS))
        fold = total - self._peak_height(compact=True, whole=True) < chrome + sum(
            self._rows_height(item.widget, hard[item.widget]) for item in lists
        )
        self.integration.set_folded(fold)
        self._hold_inspector_floor()

        def rows(field: str) -> int:
            return chrome + sum(getattr(item, field) for item in lists)

        def browse_for(compact: bool) -> tuple[int, int]:
            least = total - self._peak_height(compact, whole=False)
            most = total - self._peak_height(compact, whole=True)
            cap = min(rows("full"), max(most, min(rows("keep"), least), rows("hard")))
            if self._browse_share is not None:
                return min(int(total * self._browse_share), cap), cap
            return min(max(rows("floor"), int(total * BROWSE_MIN_SHARE)), cap), cap

        # Judged without the switcher's own height, so the answer does not depend on
        # which layout shows now.
        inspector = total - browse_for(compact=False)[0]
        self._set_compact(inspector < self._full_inspector_height())
        browse, cap = browse_for(self._compact)
        if self._compact and self._browse_share is None:
            # The lists take what the switcher's tallest pane, Summary, cannot use.
            browse = min(max(browse, total - self._summary_pane_height()), cap)
        # The Peak window's floor outranks the lists' hard rows: a caption that needs a line
        # takes it from them, down to one row each, and never grows the window off the screen.
        one_row = chrome + sum(item.last[0] for item in lists)
        browse = min(browse, max(total - self._inspector_pane.minimumHeight(), one_row))
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
        self.standard.clicked.connect(lambda: self.show_internal_standard_menu())

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

    def show_internal_standard_menu(self, global_pos: QPoint | None = None) -> None:
        """The one internal standard chooser: under the sidebar row, or at ``global_pos``."""
        names = self.compound_list.real_names()
        chooser = StandardChooser(
            names,
            self.standard.internal_standard,
            lacking_amount(names, self.analysis_mode),
            self.standard,
        )
        chooser.chosen.connect(self._on_standard_chosen)
        chooser.popup(global_pos or self.standard.mapToGlobal(self.standard.rect().bottomLeft()))

    def _on_standard_chosen(self, name: str | None) -> None:
        if name is not None:
            self.on_internal_standard_selected(name)
        elif self.standard.internal_standard is not None:
            self.on_internal_standard_cleared()

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
            # Update baseline checkbox state
            self._set_baseline_checkbox_from_compound(selected_text)
            self.sync_selected_peak_scale(selected_text)
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

    def _set_baseline_checkbox_from_compound(self, compound_name: str):
        """Set baseline correction checkbox state from compound data."""
        try:
            comp = read_compound(compound_name)
            enabled = bool(getattr(comp, "baseline_correction", 0))
        except Exception:
            enabled = False
        self._set_checked_quietly(self.baseline_checkbox, enabled)

    def sync_selected_peak_scale(self, compound_name: str):
        action = self.selected_peak_yscale_action
        if action is None:
            return
        action.setEnabled(_deconvolution_on(compound_name))
        if not action.isEnabled() and action.isChecked():
            self._commit_y_scale_policy(YScalePolicy.PER_TILE_EXTRACT)

    def _choose_y_scale(self, policy: YScalePolicy) -> None:
        self._commit_y_scale_policy(policy)
        QSettings().setValue(Y_SCALE_SETTING, self.y_scale_policy.value)

    def _commit_y_scale_policy(self, policy: YScalePolicy) -> None:
        if policy not in self._available_y_scale_policies:
            policy = YScalePolicy.PER_TILE_EXTRACT
        changed = policy is not self.y_scale_policy
        self.y_scale_policy = policy
        self.shared_yscale_action.setChecked(policy is YScalePolicy.SHARED_EXTRACT)
        if self.selected_peak_yscale_action is not None:
            self.selected_peak_yscale_action.setChecked(
                policy is YScalePolicy.PER_TILE_SELECTED_PEAK
            )
        if changed:
            self.y_scale_policy_changed.emit(self.y_scale_policy)

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
