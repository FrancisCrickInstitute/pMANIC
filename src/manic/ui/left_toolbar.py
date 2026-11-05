import logging
from collections.abc import Iterable
from typing import List, NamedTuple

from PySide6.QtCore import QEvent, QPoint, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
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
from .loaded_data_widget import LoadedDataWidget
from .sample_list_widget import SampleListWidget
from .sidebar_widgets import (
    CollapsibleSection,
    FilterField,
    divider,
    section_heading,
    shortcut_text,
)
from .standard_chooser import StandardChooser
from .standard_indicator_widget import StandardIndicator, lacking_amount

logger = logging.getLogger(__name__)

# The lists share the room the Peak window leaves in whole rows, (compounds, samples) per
# tier: short of room they give rows up from the last tier back, so Compounds keeps three as
# long as it can (Samples has its own filter, and the grid shows what is checked).
BROWSE_TIERS = ((1, 1), (3, 1), (3, 3), (4, 3), (6, 4))
# Short of this many rows in each list, the Peak window folds the rows below its editor.
BROWSE_FOLD_ROWS = 3
# Room past the last tier goes compounds:samples in this ratio, up to each one's rows.
BROWSE_WEIGHTS = (3, 2)
Y_SCALE_SETTING = "view/y_scale_policy"


class _BrowseList(NamedTuple):
    widget: QListWidget
    tiers: tuple[int, ...]  # height of its rows in each of BROWSE_TIERS
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

        # Browse: compounds, then samples.
        browse = QWidget()
        browse.setObjectName("sidebarBrowse")
        browse_layout = QVBoxLayout(browse)
        browse_layout.setContentsMargins(16, 14, 16, 12)
        browse_layout.setSpacing(8)

        compounds_heading = QHBoxLayout()
        self._compounds_heading = section_heading("Compounds")
        compounds_heading.addWidget(self._compounds_heading)
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

        self._browse_divider = divider()
        browse_layout.addWidget(self._browse_divider)

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

        # Inspector: the Peak window under the lists, at the height its rows need.
        inspector_content = QWidget()
        inspector_content.setObjectName("sidebarInspector")
        inspector_content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        inspector_layout = QVBoxLayout(inspector_content)
        inspector_layout.setContentsMargins(16, 12, 16, 4)
        inspector_layout.setSpacing(0)
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
        self.inspector = inspector_content

        QWidget.setTabOrder(
            self.integration.findChild(QLineEdit, "ro_input"), self.integration.restore_button
        )
        QWidget.setTabOrder(self.integration.restore_button, self.integration.apply_button)
        QWidget.setTabOrder(self.integration.apply_button, self.integration.more.header)
        QWidget.setTabOrder(self.integration.more.header, self.baseline_checkbox)
        QWidget.setTabOrder(self.baseline_checkbox, self.integration.tr_window_edit)

        self._browse = browse
        self._header = header
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self.fit_inspector)
        for watched in (browse, inspector_content):
            watched.installEventFilter(self)
        for section in (self.samples_section, self.peak_section):
            section.toggled.connect(self._fit_timer.start)

        self._build_scale_actions()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(header)
        main_layout.addWidget(browse, 1)
        main_layout.addWidget(inspector_content)

        self.setMinimumWidth(256)
        # A wider sidebar only pads its rows; the grid makes better use of the room.
        self.setMaximumWidth(480)
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
        # Before anything loads, the status rows say so; empty headings would only repeat it.
        self._compounds_heading.setVisible(has_compounds)
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
        self._browse_divider.setVisible(has_samples)
        self.samples_section.setVisible(has_samples)
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

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.LayoutRequest, QEvent.Type.Resize):
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
                tuple(self._rows_height(lst, rows) for rows in tiers),
                self._rows_height(lst),
                weight,
            )
            for lst, tiers, weight in zip(lists, zip(*BROWSE_TIERS), BROWSE_WEIGHTS)
            if lst.isVisibleTo(self)
        ]

    @staticmethod
    def _share_lists(space: int, lists: list[_BrowseList]) -> list[int]:
        """Each tier in turn (shared in proportion if short), then by weight up to every row."""
        heights = [0] * len(lists)
        for tier in range(len(BROWSE_TIERS)):
            target = [item.tiers[tier] for item in lists]
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
        self._browse.layout().setStretchFactor(
            self.samples_section, int(self.samples_section.is_expanded())
        )
        for item, height in zip(lists, self._share_lists(browse - chrome, lists)):
            # Whole rows only; what is left stays blank under the lists.
            row, frame = max(item.widget.sizeHintForRow(0), 1), 2 * item.widget.frameWidth()
            height = max(height - frame, 0) // row * row + frame
            # A floor of one row leaves the window room for a line the sidebar gains, such
            # as the standard's note.
            item.widget.setMinimumHeight(min(item.tiers[0], height) or 1)
            item.widget.setMaximumHeight(height)

    def _peak_height(self, whole: bool) -> int:
        """Inspector height for the Peak window: all of it, or with the rows below its editor
        folded behind their heading."""
        margins = self.inspector.layout().contentsMargins()
        section = self.peak_section
        height = margins.top() + margins.bottom() + section.header.sizeHint().height()
        if not section.is_expanded():
            return height
        return (
            height
            + section.layout().spacing()
            + self.integration.editor_height()
            + self.integration.layout().spacing()
            + self.integration.lower_height(whole)
        )

    def fit_inspector(self) -> None:
        """The Peak window takes the height it needs under the lists, folding the rows below
        its editor rather than leave the lists short of BROWSE_FOLD_ROWS; they share the rest."""
        lists = self._browse_lists()
        chrome = self._browse.minimumSizeHint().height() - sum(
            item.widget.minimumHeight() for item in lists
        )
        browse = self._browse.height()
        if self._raw_loaded:
            room = self.height() - self._header.height()
            rows = sum(self._rows_height(item.widget, BROWSE_FOLD_ROWS) for item in lists)
            self.integration.set_folded(room - self._peak_height(whole=True) < chrome + rows)
            need = self._peak_height(whole=False)
            # The hidden scope line's room goes to the lists before they drop below their rows.
            editor = self.integration.editor
            reserved = max(self.integration.editor_height() - editor.sizeHint().height(), 0)
            self.inspector.setFixedHeight(max(need - reserved, min(need, room - chrome - rows)))
            browse = room - self.inspector.height()
        self._set_list_heights(browse, chrome, lists)

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
