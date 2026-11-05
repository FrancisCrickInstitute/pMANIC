from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QAccessible, QAccessibleActionInterface, QContextMenuEvent, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QMenu, QWidget

from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.ui.left_toolbar import Toolbar
from manic.ui.loaded_data_widget import LoadedDataWidget
from manic.ui.standard_chooser import StandardChooser
from manic.ui.standard_indicator_widget import StandardIndicator
from manic.utils.utils import apply_app_stylesheet

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
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms, int_std_amount, amount_in_std_mix) "
            "VALUES ('Norvaline', 1.0, 0.1, 0.1, 217.0, 0, 2.0, 1.0)"
        )
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


@pytest.mark.parametrize(
    "mode, needs_mix", [(AnalysisMode.LABELLED, True), (AnalysisMode.UNLABELLED, False)]
)
def test_a_standard_without_an_amount_says_how_it_will_export(qapp, mode, needs_mix):
    note = "No amount: exports peak areas"
    with database.get_connection() as conn:
        for name, amount, mix in (
            ("Palatinose", None, 1.0),
            ("Norvaline", 2.0, None),
            ("Scyllo", 2.0, 1.0),
        ):
            conn.execute(
                "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
                "mass0, label_atoms, int_std_amount, amount_in_std_mix) "
                "VALUES (?, 1.0, 0.1, 0.1, 217.0, 0, ?, ?)",
                (name, amount, mix),
            )
    toolbar = Toolbar(mode)
    try:
        toolbar.update_compound_list(["Palatinose", "Norvaline", "Scyllo"])
        calibrated = ["Scyllo"] if needs_mix else ["Norvaline", "Scyllo"]
        chooser = _open_chooser(toolbar)
        assert _shown_rows(chooser) == [
            "No internal standard",
            *calibrated,
            "No amount: exports peak areas",
            *(["Palatinose", "Norvaline"] if needs_mix else ["Palatinose"]),
        ]
        chooser.close()
        shown = {}
        value = toolbar.standard.findChild(QLabel, "statusValue")
        for name in ("Palatinose", "Norvaline", "Scyllo"):
            _choose_standard(toolbar, name)
            tip = toolbar.standard.toolTip()
            shown[name] = (value.text(), value.property("state"), tip.startswith(note))
        warned, calibrated_row = ("warning", True), ("done", False)
        assert shown == {
            "Palatinose": ("Palatinose", *warned),
            "Norvaline": ("Norvaline", *(warned if needs_mix else calibrated_row)),
            "Scyllo": ("Scyllo", *calibrated_row),
        }
        toolbar.on_internal_standard_cleared()
        assert value.property("state") == "optional"
        assert not toolbar.standard.toolTip().startswith(note)
    finally:
        toolbar.deleteLater()


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
    assert [
        QAccessible.queryAccessibleInterface(row).text(QAccessible.Text.Name)
        for row in (rows.compounds_row, rows.raw_data_row)
    ] == ["Compound list: done", "Raw data: done"]


def test_headings_wait_for_what_they_list(qapp):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    try:
        def shown(*widgets):
            return [widget.isVisibleTo(toolbar) for widget in widgets]

        heading = toolbar._compounds_heading
        assert shown(heading, toolbar.samples_section) == [False, False]
        toolbar.update_compound_list(["Alanine"])
        assert shown(heading, toolbar.samples_section) == [True, False]
        toolbar.update_sample_list(["S1"])
        assert shown(heading, toolbar.samples_section) == [True, True]
    finally:
        toolbar.deleteLater()


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


def _open_chooser(toolbar: Toolbar) -> StandardChooser:
    toolbar.standard.click()
    return toolbar.standard.findChildren(StandardChooser)[-1]


def _shown_rows(chooser: StandardChooser) -> list[str]:
    rows = chooser.list
    return [rows.item(r).text() for r in range(rows.count()) if not rows.isRowHidden(r)]


def _choose_standard(toolbar: Toolbar, typed: str) -> None:
    chooser = _open_chooser(toolbar)
    QTest.keyClicks(chooser.filter, typed)
    QTest.keyClick(chooser.filter, Qt.Key_Return)


def test_internal_standard_chooser_works_from_the_keyboard(qapp):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    try:
        toolbar.update_compound_list(["Alanine", "Glycine", "Norvaline"])
        chooser = _open_chooser(toolbar)
        assert chooser.list.currentItem().text() == "No internal standard"
        # "in" also matches No internal standard; Return takes the first compound.
        QTest.keyClicks(chooser.filter, "in")
        assert _shown_rows(chooser) == [
            "No internal standard",
            "No amount: exports peak areas",
            "Alanine",
            "Glycine",
            "Norvaline",
        ]
        QTest.keyClick(chooser.filter, Qt.Key_Down)
        QTest.keyClick(chooser.filter, Qt.Key_Return)
        assert not chooser.isVisible()
        assert _value(toolbar.standard).text() == "Glycine"

        chooser = _open_chooser(toolbar)
        assert chooser.list.currentItem().text() == "Glycine"
        QTest.keyClicks(chooser.filter, "xyz")
        assert _shown_rows(chooser) == ["No internal standard", "No matching compounds"]
        # The list shrinks to the rows it shows instead of leaving a blank panel.
        row = chooser.list.sizeHintForRow(0)
        assert chooser.list.height() == 2 * row + 2 * chooser.list.frameWidth()
        QTest.keyClick(chooser.filter, Qt.Key_Return)  # no match: nothing to choose
        assert chooser.isVisible()
        QTest.keyClick(chooser.filter, Qt.Key_Escape)  # clears the filter
        assert chooser.isVisible() and chooser.list.currentItem().text() == "Glycine"
        QTest.keyClick(chooser.filter, Qt.Key_Escape)
        assert not chooser.isVisible()
        assert toolbar.get_internal_standard() == "Glycine"

        chooser = _open_chooser(toolbar)
        for _ in range(3):  # past Alanine and the heading
            QTest.keyClick(chooser.filter, Qt.Key_Up)
        QTest.keyClick(chooser.filter, Qt.Key_Return)
        assert toolbar.get_internal_standard() is None
        assert _value(toolbar.standard).text() == "None"
    finally:
        toolbar.deleteLater()


def test_sections_collapse_and_remember(qapp, stub_compound):
    toolbar = _sidebar(1400)
    try:
        assert toolbar.peak_section.body.isAncestorOf(toolbar.baseline_checkbox)
        assert toolbar.peak_section.is_expanded()

        peak = toolbar.peak_section
        # A section's summary shows only while the section is closed.
        assert not peak.summary.isVisible()
        peak.header.click()
        assert peak.summary.isVisible()
        assert peak.summary.full_text() == "Baseline on"
        peak.header.click()
        assert not peak.summary.isVisible()

        # A screen reader hears the heading as open or closed, and can press it.
        heading = QAccessible.queryAccessibleInterface(peak.header)
        state = heading.state()
        assert (state.checkable, state.checked) == (True, True)
        heading.actionInterface().doAction(QAccessibleActionInterface.toggleAction())
        assert not peak.is_expanded()
        assert not heading.state().checked
    finally:
        toolbar.deleteLater()

    again = _sidebar(1400)
    try:
        assert not again.peak_section.is_expanded()
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
    finally:
        toolbar.deleteLater()


def test_short_of_room_samples_give_up_rows_before_compounds_drop_below_three(qapp):
    # Row heights come from the app stylesheet, as in the app.
    before = qapp.styleSheet()
    apply_app_stylesheet(qapp)
    toolbar = _sidebar(600, samples_open=True)
    try:
        assert _full_rows(toolbar.compound_list) >= 3
        assert _full_rows(toolbar.sample_list) >= 1
    finally:
        toolbar.deleteLater()
        qapp.setStyleSheet(before)


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


def test_short_lists_hug_their_rows_with_the_peak_window_right_under_them(qapp):
    toolbar = Toolbar(AnalysisMode.UNLABELLED)
    toolbar.update_label_colours(True, True)
    toolbar.update_compound_list([f"Compound {i}" for i in range(8)])
    toolbar.update_sample_list([f"Sample_{i:02d}" for i in range(11)])
    toolbar.resize(296, 1357)
    toolbar.show()

    def top(widget) -> int:
        return widget.mapTo(toolbar, QPoint(0, 0)).y()

    def bottom(widget) -> int:
        return top(widget) + widget.height()

    try:
        for samples_open in (False, True):
            toolbar.samples_section.set_expanded(samples_open)
            _settle(toolbar)
            above = toolbar.sample_list if samples_open else toolbar.samples_section.header
            # Directly below what it edits, the slack under it, not in bands between rows.
            assert 0 <= top(toolbar.inspector) - bottom(above) <= 16, samples_open
            assert bottom(toolbar.inspector) < toolbar.height() - 300
            assert _full_rows(toolbar.compound_list) == 8
            if samples_open:
                assert top(toolbar.sample_filter) - bottom(toolbar.samples_section.header) == 8
                assert top(toolbar.sample_list) - bottom(toolbar.sample_filter) == 8
                assert _full_rows(toolbar.sample_list) == 11
    finally:
        toolbar.deleteLater()


def test_closing_samples_gives_its_room_back_without_a_resize(qapp):
    toolbar = _sidebar(700)
    try:
        closed = toolbar.compound_list.height()
        toolbar.samples_section.set_expanded(True)
        _settle(toolbar)
        assert _full_rows(toolbar.sample_list) >= 3
        assert toolbar.compound_list.height() < closed
        toolbar.samples_section.set_expanded(False)
        _settle(toolbar)
        assert toolbar.compound_list.height() == closed
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


def test_a_shrinking_compound_list_keeps_the_current_compound_in_view(qapp):
    toolbar = _sidebar(1400, samples_open=True)
    compounds = toolbar.compound_list
    try:
        compounds.setCurrentRow(40)
        toolbar.resize(296, 560)
        _settle(toolbar)
        row = compounds.visualItemRect(compounds.currentItem())
        assert compounds.viewport().rect().contains(row)
    finally:
        toolbar.deleteLater()


def test_a_caption_takes_its_line_from_the_lists_not_the_window(qapp):
    # Just tall enough for the lists' hard rows beside the folded Peak window.
    _add_compound("Compound 0")
    toolbar = _sidebar(560, samples_open=True)
    integration = toolbar.integration
    try:
        integration.populate_fields_from_plots("Compound 0", ["Bio_001"], ["Bio_001", "Bio_002"])
        _settle(toolbar)
        assert integration.scope_label.isVisible()
        assert toolbar.minimumSizeHint().height() <= 560
        assert _full_rows(toolbar.compound_list) >= 1 and _full_rows(toolbar.sample_list) >= 1
        assert _in_view(toolbar, integration.apply_button)
    finally:
        toolbar.deleteLater()


@pytest.mark.parametrize("height, folded", [(LAPTOP_640, True), (LAPTOP_720, False)])
def test_short_sidebar_keeps_the_editor_whole_and_folds_the_rows_below_behind_their_names(
    qapp, height, folded
):
    _add_compound("Compound 0")
    toolbar = _sidebar(height, samples_open=True)
    integration = toolbar.integration
    heading = integration.more.header
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
            assert _full_rows(toolbar.compound_list) >= 2
            assert _full_rows(toolbar.sample_list) >= 3
            assert all(_in_view(toolbar, widget) for widget in editor), selected
            assert heading.isVisible() == folded
            if not folded:
                assert all(_in_view(toolbar, widget) for widget in below), selected
                continue
            assert not any(widget.isVisible() for widget in below)
            assert "Baseline, tR window" in [label.text() for label in heading.findChildren(QLabel)]
            assert QAccessible.queryAccessibleInterface(heading).text(QAccessible.Name) == (
                "Baseline, tR window"
            )

            # Opened, the rows show whole beside the sidebar; the lists and editor keep theirs.
            heading.click()
            _settle(toolbar)
            popover = toolbar.baseline_checkbox.window()
            assert popover is not toolbar.window() and popover.isVisible()
            assert all(widget.isVisible() for widget in below), selected
            assert popover.geometry().left() >= toolbar.mapToGlobal(toolbar.rect().topRight()).x()
            assert _full_rows(toolbar.sample_list) >= 3
            assert all(_in_view(toolbar, widget) for widget in editor), selected
            QTest.keyClick(popover, Qt.Key_Escape)
            _settle(toolbar)
            assert not any(widget.isVisible() for widget in below)
            assert not heading.parentWidget().is_expanded()
    finally:
        toolbar.deleteLater()


def test_a_pending_edit_on_a_150_percent_laptop_leaves_samples_two_rows(qapp):
    # The sidebar of a 1008x633 window with a pending edit, row heights from the stylesheet.
    before = qapp.styleSheet()
    apply_app_stylesheet(qapp)
    _add_compound("Compound 0")
    toolbar = _sidebar(604, samples_open=True)
    integration = toolbar.integration
    left = integration.findChild(QLineEdit, "lo_input")
    try:
        integration.populate_fields_from_plots("Compound 0", [], [f"Bio_{i:03d}" for i in range(30)])
        left.selectAll()
        QTest.keyClicks(left, "0.15")
        _settle(toolbar)
        assert integration.scope_label.text() == "All 30 shown\u00a0·\u00a0not\u00a0applied"
        assert _full_rows(toolbar.compound_list) >= 3
        assert _full_rows(toolbar.sample_list) >= 2
        editor = [integration.findChild(QLineEdit, n) for n in ("lo_input", "tr_input", "ro_input")]
        assert all(_in_view(toolbar, w) for w in editor + [integration.apply_button])
    finally:
        toolbar.deleteLater()
        qapp.setStyleSheet(before)


def test_clearing_a_filter_on_a_short_list_keeps_the_current_compound_in_view(qapp):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    names = ["Pyruvate", "Lactate", "Alanine", "Oxalate", "Valine", "Urea", "Glycine", "Serine"]
    try:
        toolbar.update_compound_list(names, selected_name="Glycine")
        compounds = toolbar.compound_list
        compounds.setFixedHeight(compounds.sizeHintForRow(0) + 2 * compounds.frameWidth())
        toolbar.show()
        toolbar.compound_filter.setText("ine")
        compounds.scrollToTop()

        toolbar.compound_filter.setText("")
        qapp.processEvents()

        row = compounds.visualItemRect(compounds.currentItem())
        assert compounds.currentItem().text() == "Glycine"
        assert compounds.viewport().rect().contains(row)
    finally:
        toolbar.deleteLater()


def test_building_the_standard_chooser_opens_no_other_window(qapp):
    # On Windows a stray window takes activation, and Qt then closes the popup at once.
    shown = []

    class Spy(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Show and isinstance(obj, QWidget) and obj.isWindow():
                shown.append(type(obj).__name__)
            return False

    spy = Spy()
    qapp.installEventFilter(spy)
    parent = QWidget()
    try:
        chooser = StandardChooser(["Alanine", "Glycine"], None, set(), parent)
        chooser.popup(QPoint(10, 10))
        qapp.processEvents()
        assert shown == ["StandardChooser"]
        chooser.close()
    finally:
        qapp.removeEventFilter(spy)
        parent.deleteLater()
