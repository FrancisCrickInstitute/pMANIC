from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QContextMenuEvent, QKeyEvent, QKeySequence, QMouseEvent
from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel, QLineEdit, QMenu, QWidget

from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.ui.left_toolbar import SPLIT_SETTING, Toolbar
from manic.ui.loaded_data_widget import LoadedDataWidget
from manic.ui.standard_indicator_widget import StandardIndicator

from conftest import _make_window

# Sidebar heights in a 1024x640, 1280x720 and 1024x768 window (menu and status bar taken off).
LAPTOP_640 = 587
LAPTOP_720 = 667
LAPTOP_768 = 715


def _press(widget, key) -> None:
    QApplication.sendEvent(widget, QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.NoModifier))


def _value(row) -> QLabel:
    """The value a status row shows on its right."""
    return row.findChild(QLabel, "statusValue")


def _add_compound(name: str, baseline: int = 0, deconvolution: str = "off") -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms, baseline_correction, deconvolution_level) "
            "VALUES (?, 1.0, 0.1, 0.1, 217.0, 0, ?, ?)",
            (name, baseline, deconvolution),
        )


def _baseline_in_db(name: str) -> int:
    with database.get_connection() as conn:
        return conn.execute(
            "SELECT baseline_correction FROM compounds WHERE compound_name = ?", (name,)
        ).fetchone()[0]


@pytest.fixture
def stub_compound(monkeypatch):
    """Every compound reads back with baseline correction on and no deconvolution."""
    monkeypatch.setattr(
        "manic.ui.left_toolbar.read_compound",
        lambda _name: SimpleNamespace(deconvolution_level="off", baseline_correction=1),
    )


def _settle(toolbar: Toolbar) -> None:
    for _ in range(3):
        for _ in range(5):
            QApplication.processEvents()
        toolbar.fit_inspector()


def _sidebar(height: int, samples_open: bool = False) -> Toolbar:
    """A shown sidebar with a full-size compound list and sample set loaded."""
    toolbar = Toolbar(AnalysisMode.LABELLED)
    toolbar.update_label_colours(True, True)
    toolbar.update_compound_list([f"Compound {i}" for i in range(95)])
    toolbar.update_sample_list([f"Bio_{i:03d}" for i in range(30)])
    toolbar.samples_section.set_expanded(samples_open)
    toolbar.resize(296, height)
    toolbar.show()
    _settle(toolbar)
    return toolbar


def _full_rows(lst) -> int:
    return lst.viewport().height() // lst.sizeHintForRow(0)


def _in_view(toolbar: Toolbar, widget) -> bool:
    """Shown whole: inside each parent up to the sidebar, scroll viewports included."""
    if not widget.isVisible():
        return False
    rect = widget.rect()
    child = widget
    while child is not toolbar:
        rect = rect.translated(child.pos())
        child = child.parentWidget()
        if not child.rect().contains(rect):
            return False
    return True


def _cut(toolbar: Toolbar, widget) -> bool:
    """Partly shown: visible, not whole, and not wholly scrolled out of its viewport."""
    if not widget.isVisible() or _in_view(toolbar, widget):
        return False
    area = toolbar.integration.more
    if area.isAncestorOf(widget):
        top = widget.mapTo(area.viewport(), QPoint(0, 0)).y()
        return top < area.viewport().height() and top + widget.height() > 0
    return True


def _switch_button(toolbar: Toolbar, key: str) -> QAbstractButton:
    return toolbar.section_switcher.findChild(QAbstractButton, f"switch_{key}")


def _drag_split(toolbar: Toolbar, browse: int) -> None:
    """Drag the splitter handle so the lists get `browse` pixels."""
    handle = toolbar.splitter.handle(1)
    start = handle.rect().center()
    end = start + QPoint(0, browse - toolbar.splitter.sizes()[0])
    for kind, at, buttons in (
        (QEvent.Type.MouseButtonPress, start, Qt.LeftButton),
        (QEvent.Type.MouseMove, end, Qt.LeftButton),
        (QEvent.Type.MouseButtonRelease, end, Qt.NoButton),
    ):
        event = QMouseEvent(
            kind,
            QPointF(at),
            QPointF(handle.mapToGlobal(at)),
            Qt.LeftButton,
            buttons,
            Qt.NoModifier,
        )
        QApplication.sendEvent(handle, event)


class FakePlot(QWidget):
    def __init__(self, sample: str):
        super().__init__()
        self.sample_name = sample
        self.compound_name = "Alanine"
        self.is_selected = False

    def set_selected(self, selected: bool) -> None:
        self.is_selected = selected


@pytest.fixture
def plotted_window(qapp, monkeypatch):
    """A window with Alanine and raw data loaded, whose grid plots stand-in tiles."""
    _add_compound("Alanine")
    window = _make_window(monkeypatch)

    def plot_compound(compound_name, samples, validation_data=None, *, identity=None):
        view = window.graph_view
        view._current_compound = compound_name
        view._current_samples = list(samples)
        view._selected_plots.clear()
        view._current_plots = [FakePlot(name) for name in samples]

    monkeypatch.setattr(window.graph_view, "plot_compound", plot_compound)
    monkeypatch.setattr(window, "_peak_verdicts", lambda *a: {})
    monkeypatch.setattr(window, "_identity_snapshot", lambda *a: (None, None))
    monkeypatch.setattr(window, "_refresh_mode_charts", lambda *a, **k: None)
    window.cdf_data_loaded = True
    window.toolbar.update_compound_list(["Alanine"], "Alanine")
    window.toolbar.update_sample_list(["S1", "S2", "S3"])
    yield window
    window.close()


def _grid_context_menu(window) -> dict:
    view = window.graph_view
    QApplication.sendEvent(
        view,
        QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(1, 1), view.mapToGlobal(QPoint(1, 1))),
    )
    return {a.text(): a for a in view.findChildren(QMenu, options=Qt.FindDirectChildrenOnly)[-1].actions() if a.text()}


def _review_menu(window) -> dict:
    window.review_menu.aboutToShow.emit()
    return {a.text(): a for a in window.review_menu.actions() if a.text()}


def test_internal_standard_row_is_optional_until_chosen(qapp):
    row = StandardIndicator()
    value = _value(row)
    assert row.internal_standard is None
    assert value.text() == "None"
    assert value.property("state") == "optional"

    row.set_internal_standard("Norvaline")
    assert row.internal_standard == "Norvaline"
    assert value.text() == "Norvaline"
    assert value.property("state") == "done"

    row.clear_internal_standard()
    assert row.internal_standard is None
    assert value.text() == "None"
    assert value.property("state") == "optional"


def test_data_rows_report_load_state_without_counts_or_links(qapp):
    rows = LoadedDataWidget()
    compounds, raw = _value(rows.compounds_row), _value(rows.raw_data_row)
    assert compounds.text() == "Not loaded"
    assert raw.text() == "Not loaded"

    rows.update_status(False, True)
    assert compounds.text() == ""
    assert compounds.property("state") == "done"
    assert raw.text() == "Not loaded"

    # The counts live with Compounds and Samples; loading lives on the canvas and in File.
    rows.update_status(True, True)
    assert raw.text() == ""
    assert raw.property("state") == "done"


def test_compound_filter_narrows_list_and_enter_picks_first_match(qapp, stub_compound):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    picked = []
    toolbar.compound_selected.connect(picked.append)
    try:
        toolbar.update_label_colours(False, True)
        toolbar.update_compound_list(["Alanine", "Glutamate", "Glycine"])
        assert toolbar.compound_count_label.text() == "3"

        toolbar.compound_filter.setText("gl")
        assert [
            toolbar.compound_list.item(r).text()
            for r in range(3)
            if not toolbar.compound_list.isRowHidden(r)
        ] == ["Glutamate", "Glycine"]
        assert toolbar.compound_count_label.text() == "2 of 3"

        _press(toolbar.compound_filter, Qt.Key_Return)
        assert toolbar.get_selected_compound() == "Glutamate"

        toolbar.step_compound(1)
        assert toolbar.get_selected_compound() == "Glycine"
        toolbar.step_compound(1)
        assert toolbar.get_selected_compound() == "Glycine"
        toolbar.step_compound(-1)
        assert toolbar.get_selected_compound() == "Glutamate"
        assert picked[-3:] == ["Glutamate", "Glycine", "Glutamate"]
    finally:
        toolbar.deleteLater()


def test_filter_with_no_match_shows_the_count_and_escape_clears_it(qapp):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    try:
        toolbar.update_label_colours(False, True)
        toolbar.update_compound_list(["Alanine", "Glycine"])
        toolbar.compound_filter.setText("zzz")
        assert not toolbar.compound_list.isVisibleTo(toolbar)
        assert toolbar.compound_count_label.text() == "0 of 2"

        _press(toolbar.compound_filter, Qt.Key_Escape)
        assert toolbar.compound_filter.text() == ""
        assert toolbar.compound_list.isVisibleTo(toolbar)
        assert toolbar.compound_count_label.text() == "2"
    finally:
        toolbar.deleteLater()


def test_inspector_waits_for_raw_data(qapp, stub_compound):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    try:
        assert not toolbar.inspector.isVisibleTo(toolbar)
        toolbar.update_label_colours(True, True)
        assert toolbar.inspector.isVisibleTo(toolbar)
    finally:
        toolbar.deleteLater()


def test_set_selected_samples_emits_samples_selected_once(qapp):
    toolbar = Toolbar()
    toolbar.update_sample_list(["S1", "S2", "S3"])
    seen: list[list[str]] = []
    toolbar.samples_selected.connect(seen.append)
    toolbar.set_selected_samples(["S2", "S1", "missing"])
    assert seen == [["S1", "S2"]]
    toolbar.set_selected_samples(["nope"])
    assert seen == [["S1", "S2"]]
    toolbar.deleteLater()


def test_sample_checkboxes_keep_list_order_and_count_matches(qapp, monkeypatch):
    menus: list[QMenu] = []
    monkeypatch.setattr(QMenu, "exec_", lambda menu, *args: menus.append(menu))
    toolbar = Toolbar(AnalysisMode.LABELLED)
    shown: list[list[str]] = []
    toolbar.samples_selected.connect(shown.append)
    samples = toolbar.sample_list

    def context_menu() -> dict:
        QApplication.sendEvent(
            samples,
            QContextMenuEvent(QContextMenuEvent.Reason.Keyboard, QPoint(1, 1), samples.mapToGlobal(QPoint(1, 1))),
        )
        return {a.text(): a for a in menus[-1].actions() if a.text()}

    try:
        toolbar.update_label_colours(True, True)
        toolbar.update_sample_list(["A1", "A2", "B1"])
        assert toolbar.get_selected_samples() == ["A1", "A2", "B1"]
        assert toolbar.samples_section.summary.full_text() == "3 · all shown"

        samples.item(0).setCheckState(Qt.Unchecked)
        samples.item(0).setCheckState(Qt.Checked)
        assert shown[-2:] == [["A2", "B1"], ["A1", "A2", "B1"]]

        toolbar.sample_filter.setText("a")
        assert toolbar.samples_section.summary.full_text() == "3 shown · 2 match"

        samples.setCurrentRow(0)
        samples.item(0).setSelected(True)
        samples.item(1).setSelected(True)
        _press(samples, Qt.Key_Space)
        assert toolbar.get_selected_samples() == ["B1"]
        assert toolbar.samples_section.summary.full_text() == "1 shown · 2 match"

        toolbar.sample_filter.clear()
        assert toolbar.samples_section.summary.full_text() == "1 of 3 shown"
        toolbar.select_all_samples()
        assert toolbar.samples_section.summary.full_text() == "3 · all shown"

        samples.clearSelection()
        samples.item(2).setSelected(True)
        samples.item(0).setSelected(True)
        actions = context_menu()
        assert list(actions)[:4] == [
            "Delete 2 Samples",
            "Show Only 2 Samples",
            "Hide 2 Samples",
            "Show All Samples",
        ]
        actions["Hide 2 Samples"].trigger()
        assert toolbar.get_selected_samples() == ["A2"]
        assert toolbar.samples_section.summary.full_text() == "1 of 3 shown"

        context_menu()["Show Only 2 Samples"].trigger()
        assert toolbar.get_selected_samples() == ["A1", "B1"]
        assert toolbar.samples_section.summary.full_text() == "2 of 3 shown"
    finally:
        toolbar.deleteLater()


@pytest.mark.parametrize("menu", [_grid_context_menu, _review_menu])
def test_focus_selected_then_show_all(plotted_window, menu):
    window = plotted_window
    menu_bar_show_all = [
        action
        for menu in window.menuBar().findChildren(QMenu)
        for action in menu.actions()
        if action.text() == "Show All Samples"
    ]
    assert menu_bar_show_all == [window.show_all_samples_action]
    assert window.show_all_samples_action in window.review_menu.actions()

    window.graph_view.select_samples(["S1", "S2"])
    menu(window)["Show Only 2 Selected Samples"].trigger()
    assert window.toolbar.get_selected_samples() == ["S1", "S2"]
    assert window.graph_view.get_current_samples() == ["S1", "S2"]
    assert window.graph_view.get_selected_samples() == ["S1", "S2"]
    assert window.toolbar.integration.scope_label.text() == "Applies to 2 selected samples"

    menu(window)["Show All Samples"].trigger()
    assert window.toolbar.get_selected_samples() == ["S1", "S2", "S3"]
    assert window.graph_view.get_current_samples() == ["S1", "S2", "S3"]
    assert window.graph_view.get_selected_samples() == []
    # Every shown sample is the default scope, so it goes unsaid.
    assert window.toolbar.integration.scope_label.isHidden()


def test_unchecking_every_sample_empties_the_workspace(plotted_window):
    window = plotted_window
    integration = window.toolbar.integration
    assert window.workspace.currentWidget() is window.graph_view
    assert window.graph_view.get_current_samples() == ["S1", "S2", "S3"]

    for row in range(window.toolbar.sample_list.count()):
        window.toolbar.sample_list.item(row).setCheckState(Qt.CheckState.Unchecked)

    assert window.workspace.currentWidget() is window.no_samples_panel
    assert window.graph_view.get_current_samples() == []
    assert window.toolbar.samples_section.summary.full_text() == "0 of 3 shown"
    # The canvas explains the empty grid; the inspector does not repeat it.
    assert integration.scope_label.isHidden()
    assert integration.apply_button.text() == "Apply"
    assert not integration.apply_button.isEnabled()
    assert not integration.regenerate_button.isEnabled()

    window.show_all_samples_button.click()
    assert window.workspace.currentWidget() is window.graph_view
    assert window.graph_view.get_current_samples() == ["S1", "S2", "S3"]
    assert integration.apply_button.isEnabled()


def test_summaries_and_view_menu_follow_compound_switch(qapp, monkeypatch):
    _add_compound("Plain", baseline=0)
    _add_compound("Corrected", baseline=1)
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    monkeypatch.setattr(window, "on_plot_button", lambda *_args: None)
    toolbar = window.toolbar
    review = [a.text() for a in window.review_menu.actions() if a.text()]
    baseline = window.baseline_action
    try:
        # Baseline correction sits with the peak commands, not with Display.
        assert review.index("Baseline Correction") > review.index("Curve Fit")
        assert "Baseline Correction" not in [a.text() for a in window.view_menu.actions()]
        assert baseline.shortcut() == QKeySequence("Ctrl+Shift+B")

        toolbar.update_compound_list(["Plain", "Corrected"])
        toolbar.peak_section.set_expanded(False)
        assert toolbar.peak_section.summary.full_text() == "No baseline"
        assert not baseline.isChecked()

        toolbar.compound_list.setCurrentRow(1)
        assert toolbar.peak_section.summary.full_text() == "Baseline on"
        assert baseline.isChecked()

        toolbar.compound_list.setCurrentRow(0)
        assert toolbar.peak_section.summary.full_text() == "No baseline"
        assert not baseline.isChecked()
        # Showing a compound's setting never writes it back.
        assert (_baseline_in_db("Plain"), _baseline_in_db("Corrected")) == (0, 1)

        # The Review action toggles from the live state, then the switch shows the DB.
        baseline.trigger()
        assert _baseline_in_db("Plain") == 1
        assert toolbar.peak_section.summary.full_text() == "Baseline on"
    finally:
        window.close()


def _open_standard_menu(toolbar: Toolbar) -> QMenu:
    toolbar.standard.click()
    return toolbar.standard.findChildren(QMenu)[-1]


def test_internal_standard_menu_checks_the_current_choice(qapp):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    try:
        toolbar.update_compound_list(["Alanine", "Glycine"])
        menu = _open_standard_menu(toolbar)
        assert [a.text() for a in menu.actions() if a.isChecked()] == ["No Internal Standard"]
        groups = {a.actionGroup() for a in menu.actions() if a.isCheckable()}
        assert len(groups) == 1 and next(iter(groups)).isExclusive()

        next(a for a in menu.actions() if a.text() == "Glycine").trigger()
        menu.close()
        assert toolbar.get_internal_standard() == "Glycine"
        assert _value(toolbar.standard).text() == "Glycine"

        menu = _open_standard_menu(toolbar)
        assert [a.text() for a in menu.actions() if a.isChecked()] == ["Glycine"]
        menu.close()
    finally:
        toolbar.deleteLater()


def test_sections_collapse_and_remember(qapp, stub_compound):
    toolbar = _sidebar(1400)
    try:
        assert toolbar.peak_section.body.isAncestorOf(toolbar.baseline_checkbox)
        assert toolbar.peak_section.is_expanded()
        assert toolbar.summary_section.is_expanded()

        peak = toolbar.peak_section
        # A section's summary shows only while the section is closed.
        assert not peak.summary.isVisible()
        peak.header.click()
        assert peak.summary.isVisible()
        assert peak.summary.full_text() == "Baseline on"
        peak.header.click()
        assert not peak.summary.isVisible()

        toolbar.summary_section.header.click()
        assert not toolbar.summary_section.is_expanded()
    finally:
        toolbar.deleteLater()

    again = _sidebar(1400)
    try:
        assert not again.summary_section.is_expanded()
        assert again.peak_section.is_expanded()
    finally:
        again.deleteLater()


def test_dragged_split_is_remembered(qapp):
    toolbar = _sidebar(700)
    try:
        total = sum(toolbar.splitter.sizes())
        # Dragged so far the Peak window would not fit: the layout stays safe,
        # but the user's share is what is saved.
        _drag_split(toolbar, total - 60)
        dragged = toolbar.splitter.sizes()[0] / total
        _settle(toolbar)
        assert _in_view(toolbar, toolbar.integration.apply_button)
        assert QSettings().value(SPLIT_SETTING, type=float) == pytest.approx(dragged)

        _drag_split(toolbar, 200)
        _settle(toolbar)
        assert toolbar.splitter.sizes()[0] == 200
        share = 200 / total
        assert QSettings().value(SPLIT_SETTING, type=float) == pytest.approx(share)
    finally:
        toolbar.deleteLater()

    again = _sidebar(700)
    try:
        browse, inspector = again.splitter.sizes()
        assert browse / (browse + inspector) == pytest.approx(share, abs=0.02)
    finally:
        again.deleteLater()


@pytest.mark.parametrize(
    "height, samples_open, compound_rows, sample_rows",
    [(LAPTOP_720, True, 4, 3), (700, False, 6, 0)],
)
def test_laptop_lists_keep_four_compounds_and_three_samples_with_samples_open(
    qapp, height, samples_open, compound_rows, sample_rows
):
    toolbar = _sidebar(height, samples_open)
    try:
        assert _full_rows(toolbar.compound_list) >= compound_rows
        assert _full_rows(toolbar.sample_list) >= sample_rows
        assert toolbar.section_switcher.isVisible()
    finally:
        toolbar.deleteLater()


# 680 is about the sidebar of a 1024x768 window with a taller menu bar.
@pytest.mark.parametrize("height", [680, LAPTOP_768])
def test_peak_window_stays_whole_at_1024x768(qapp, height):
    toolbar = _sidebar(height)
    try:
        for samples_open in (False, True, False):
            toolbar.samples_section.set_expanded(samples_open)
            _settle(toolbar)
            assert _in_view(toolbar, toolbar.integration.regenerate_button), samples_open
            assert _full_rows(toolbar.compound_list) >= 4, samples_open
    finally:
        toolbar.deleteLater()


def test_closing_samples_gives_its_room_back_without_a_resize(qapp):
    toolbar = _sidebar(700)
    try:
        closed = toolbar.splitter.sizes()
        toolbar.samples_section.set_expanded(True)
        _settle(toolbar)
        assert _full_rows(toolbar.sample_list) >= 3
        toolbar.samples_section.set_expanded(False)
        _settle(toolbar)
        assert toolbar.splitter.sizes() == closed
    finally:
        toolbar.deleteLater()


def test_a_short_filtered_list_leaves_its_room_to_samples(qapp):
    toolbar = _sidebar(900, samples_open=True)
    try:
        before = toolbar.sample_list.height()
        toolbar.compound_filter.setText("Compound 1")  # 1 and 10-19: 11 rows
        toolbar.compound_filter.setText("Compound 9")  # 9 and 90-94: 6 rows
        _settle(toolbar)
        assert _full_rows(toolbar.compound_list) == 6
        assert toolbar.sample_list.height() > before
    finally:
        toolbar.deleteLater()


def test_switcher_shows_the_peak_window_or_one_summary_chart_at_full_height(qapp):
    toolbar = _sidebar(LAPTOP_720)
    ratios, abundance = toolbar._charts
    try:
        assert [
            b.text() for b in toolbar.section_switcher.findChildren(QAbstractButton)
        ] == ["Peak window", "Summary"]
        assert _switch_button(toolbar, "peak").isChecked()
        assert not toolbar.peak_section.header.isVisible()

        _switch_button(toolbar, "summary").click()
        _settle(toolbar)
        assert not toolbar.integration.isVisible()
        # One chart takes the pane; the other folds to its title, which opens it.
        assert _in_view(toolbar, toolbar.isotopologue_ratios)
        assert not toolbar.total_abundance.isVisible()
        assert _in_view(toolbar, abundance.header)
        pane = toolbar._inspector_pane.height()
        assert toolbar.isotopologue_ratios.height() > pane // 2

        abundance.header.click()
        _settle(toolbar)
        assert _in_view(toolbar, toolbar.total_abundance)
        assert not toolbar.isotopologue_ratios.isVisible()
        assert _in_view(toolbar, ratios.header)

        _switch_button(toolbar, "peak").click()
        assert _in_view(toolbar, toolbar.integration.apply_button)
    finally:
        toolbar.deleteLater()


@pytest.mark.parametrize("samples_open", [False, True])
def test_switcher_leaves_once_there_is_room_and_sections_keep_their_state(qapp, samples_open):
    toolbar = _sidebar(LAPTOP_720, samples_open)
    try:
        _switch_button(toolbar, "summary").click()
        toolbar.resize(296, 1400)
        _settle(toolbar)
        assert not toolbar.section_switcher.isVisible()
        assert toolbar.integration.isVisible()
        assert toolbar.isotopologue_ratios.isVisible() and toolbar.total_abundance.isVisible()
    finally:
        toolbar.deleteLater()
    tall = _sidebar(1400, samples_open)
    try:
        assert not tall.section_switcher.isVisible()
        for widget in (
            tall.peak_section.header,
            tall.integration.regenerate_button,
            tall.summary_section.header,
            tall.isotopologue_ratios,
            tall.total_abundance,
        ):
            assert _in_view(tall, widget)
    finally:
        tall.deleteLater()


@pytest.mark.parametrize("height, rows", [(LAPTOP_640, (2, 1)), (LAPTOP_720, (4, 3))])
def test_no_peak_window_field_is_ever_cut_on_a_short_sidebar(qapp, height, rows):
    _add_compound("Compound 0")
    toolbar = _sidebar(height, samples_open=True)
    integration = toolbar.integration
    editor = [
        integration.findChild(QLineEdit, name) for name in ("lo_input", "tr_input", "ro_input")
    ] + [integration.restore_button, integration.apply_button]
    below = [toolbar.baseline_checkbox, integration.tr_window_edit, integration.regenerate_button]
    shown = [f"Bio_{i:03d}" for i in range(30)]
    try:
        for selected in ([], ["Bio_001"]):
            integration.populate_fields_from_plots("Compound 0", selected, shown)
            _settle(toolbar)
            assert integration.scope_label.isVisible() == bool(selected)
            assert _full_rows(toolbar.compound_list) >= rows[0]
            assert _full_rows(toolbar.sample_list) >= rows[1]
            assert all(_in_view(toolbar, widget) for widget in editor), selected
            # Scrolled any way, the rows below show whole or not at all, and each can show.
            bar = integration.more.verticalScrollBar()
            if height == LAPTOP_640:
                assert bar.maximum() > 0, "the rows below should page at this height"
            seen = set()
            for value in [*range(bar.maximum() + 1), *range(bar.maximum(), -1, -1)]:
                bar.setValue(value)
                assert not any(_cut(toolbar, widget) for widget in below), (selected, value)
                seen.update(w for w in below if _in_view(toolbar, w))
            assert seen == set(below), selected
    finally:
        toolbar.deleteLater()
