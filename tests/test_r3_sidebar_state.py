from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
import pytest

from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.ui.left_toolbar import SPLIT_SETTING, Toolbar

from conftest import _make_window


@pytest.fixture(autouse=True)
def scratch_settings(tmp_path):
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    QSettings().clear()
    yield


def _add_compound(name: str, baseline: int, deconvolution: str = "off") -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms, baseline_correction, deconvolution_level) "
            "VALUES (?, 5.0, 0.1, 0.1, 100.0, 0, ?, ?)",
            (name, baseline, deconvolution),
        )


def _baseline_in_db(name: str) -> int:
    with database.get_connection() as conn:
        return conn.execute(
            "SELECT baseline_correction FROM compounds WHERE compound_name = ?", (name,)
        ).fetchone()[0]


def test_summaries_and_view_menu_follow_compound_switch(qapp, monkeypatch):
    _add_compound("Plain", baseline=0)
    _add_compound("Corrected", baseline=1)
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    monkeypatch.setattr(window, "on_plot_button", lambda *_args: None)
    toolbar = window.toolbar
    actions = {a.text(): a for a in window.review_menu.actions()}
    try:
        toolbar.update_compound_list(["Plain", "Corrected"])
        toolbar.peak_section.set_expanded(False)
        assert toolbar.peak_section.summary.full_text() == "No baseline"
        assert not actions["Baseline Correction"].isChecked()

        toolbar.compound_list.setCurrentRow(1)
        assert toolbar.peak_section.summary.full_text() == "Baseline on"
        assert actions["Baseline Correction"].isChecked()

        toolbar.compound_list.setCurrentRow(0)
        assert toolbar.peak_section.summary.full_text() == "No baseline"
        assert not actions["Baseline Correction"].isChecked()
        # Showing a compound's setting never writes it back.
        assert (_baseline_in_db("Plain"), _baseline_in_db("Corrected")) == (0, 1)

        # The Review action toggles from the live state, then the switch shows the DB.
        actions["Baseline Correction"].trigger()
        assert _baseline_in_db("Plain") == 1
        assert toolbar.peak_section.summary.full_text() == "Baseline on"
    finally:
        window.close()


def test_scale_summary_and_menu_follow_a_forced_scale_change(qapp, monkeypatch):
    _add_compound("Deconvolved", baseline=0, deconvolution="medium")
    _add_compound("Plain", baseline=0)
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    monkeypatch.setattr(window, "on_plot_button", lambda *_args: None)
    toolbar = window.toolbar
    actions = {a.text(): a for a in window.view_menu.actions()}
    try:
        toolbar.update_compound_list(["Deconvolved", "Plain"])
        actions["Scale to Selected Peak"].trigger()
        assert toolbar.display_section.summary.full_text() == "Peak scale"
        assert actions["Scale to Selected Peak"].isChecked()

        # Plain has no deconvolution, so peak scale falls back to own scale.
        toolbar.compound_list.setCurrentRow(1)
        assert toolbar.display_section.summary.full_text() == "Own scale"
        assert not actions["Scale to Selected Peak"].isChecked()
    finally:
        window.close()


def _press_space(widget) -> None:
    QApplication.sendEvent(
        widget, QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Space, Qt.NoModifier)
    )


def test_sample_checkboxes_keep_list_order_and_count_matches(qapp):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    shown: list[list[str]] = []
    toolbar.samples_selected.connect(shown.append)
    try:
        toolbar.update_label_colours(True, True)
        toolbar.update_sample_list(["A1", "A2", "B1"])
        samples = toolbar.sample_list
        assert toolbar.get_selected_samples() == ["A1", "A2", "B1"]

        samples.item(0).setCheckState(Qt.Unchecked)
        samples.item(0).setCheckState(Qt.Checked)
        assert shown[-2:] == [["A2", "B1"], ["A1", "A2", "B1"]]

        toolbar.sample_filter.setText("a")
        assert toolbar.samples_section.summary.full_text() == "3 shown · 2 match"

        samples.setCurrentRow(0)
        samples.item(0).setSelected(True)
        samples.item(1).setSelected(True)
        _press_space(samples)
        assert toolbar.get_selected_samples() == ["B1"]
        assert toolbar.samples_section.summary.full_text() == "1 shown · 2 match"

        toolbar.sample_filter.clear()
        assert toolbar.samples_section.summary.full_text() == "1 of 3 shown"
        toolbar.select_all_samples()
        assert toolbar.samples_section.summary.full_text() == "3 · all shown"
    finally:
        toolbar.deleteLater()


def test_filter_with_no_match_offers_to_clear_it(qapp):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    try:
        toolbar.update_label_colours(False, True)
        toolbar.update_compound_list(["Alanine", "Glycine"])
        toolbar.compound_filter.setText("zzz")
        assert toolbar.compound_no_match.isVisibleTo(toolbar)
        assert not toolbar.compound_list.isVisibleTo(toolbar)
        assert toolbar.compound_count_label.text() == "0 of 2"

        toolbar.compound_no_match.clear_button.click()
        assert toolbar.compound_filter.text() == ""
        assert toolbar.compound_list.isVisibleTo(toolbar)
        assert not toolbar.compound_no_match.isVisibleTo(toolbar)
    finally:
        toolbar.deleteLater()


def _loaded_toolbar(height: int) -> Toolbar:
    toolbar = Toolbar(AnalysisMode.LABELLED)
    toolbar.update_label_colours(True, True)
    toolbar.update_compound_list([f"Compound {i}" for i in range(40)])
    toolbar.update_sample_list([f"S{i}" for i in range(20)])
    toolbar.resize(280, height)
    toolbar.show()
    for _ in range(5):
        QApplication.processEvents()
    toolbar.fit_inspector()
    return toolbar


def test_browse_keeps_six_rows_and_inspector_switches_sections(qapp):
    toolbar = _loaded_toolbar(700)
    try:
        row = toolbar.compound_list.sizeHintForRow(0)
        assert toolbar.compound_list.viewport().height() >= 6 * row
        assert toolbar.section_switcher.isVisible()
    finally:
        toolbar.deleteLater()


def test_dragged_split_is_remembered(qapp):
    toolbar = _loaded_toolbar(700)
    try:
        total = sum(toolbar.splitter.sizes())
        toolbar.splitter.setSizes([200, total - 200])
        toolbar._on_splitter_moved()
        share = 200 / total
        assert QSettings().value(SPLIT_SETTING, type=float) == pytest.approx(share)
    finally:
        toolbar.deleteLater()

    again = _loaded_toolbar(700)
    try:
        browse, inspector = again.splitter.sizes()
        assert browse / (browse + inspector) == pytest.approx(share, abs=0.02)
    finally:
        again.deleteLater()


def test_sections_collapse_and_remember(qapp):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    try:
        assert toolbar.peak_section.is_expanded()
        assert toolbar.summary_section.is_expanded()
        assert toolbar.peak_section.body.isAncestorOf(toolbar.baseline_checkbox)
        assert not toolbar.display_section.body.isAncestorOf(toolbar.baseline_checkbox)
        assert toolbar.integration.regenerate_button.text() == "Apply window"
        toolbar.summary_section.header.click()
        assert not toolbar.summary_section.is_expanded()
    finally:
        toolbar.deleteLater()

    again = Toolbar(AnalysisMode.LABELLED)
    try:
        assert not again.summary_section.is_expanded()
        assert again.peak_section.is_expanded()
    finally:
        again.deleteLater()
