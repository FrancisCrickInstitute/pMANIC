import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from manic.io.compound_reader import read_compound
from manic.models import database
from manic.models.analysis import AnalysisMode

from conftest import _make_window
from test_settings_window import _select_page


def _open_qualifier_page(window, monkeypatch, first_tolerance):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, "
            "roffset, mass0, label_atoms) VALUES ('Target', 1.0, 0.1, 0.1, 217.0, 0)"
        )
        conn.executemany(
            "INSERT INTO compound_ions (compound_name, role, ordinal, mz, "
            "expected_ratio, ratio_tolerance) VALUES ('Target', ?, ?, ?, ?, ?)",
            [
                ("quantifier", 0, 217.0, None, None),
                ("qualifier", 1, 147.0, 0.4, first_tolerance),
                ("qualifier", 2, 73.0, 0.2, 0.25),
            ],
        )
    window.compound_data_loaded = True
    window.toolbar.update_compound_list(["Target"], selected_name="Target")
    monkeypatch.setattr(window, "_replot_current_selection", lambda: None)
    window.open_settings_window()
    _select_page(window.settings_window, "Qualifier ratios")
    return window.settings_window.page_named("Qualifier ratios")


def _stored_tolerances():
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT ordinal, ratio_tolerance FROM compound_ions "
            "WHERE compound_name = 'Target' AND role = 'qualifier' "
            "ORDER BY ordinal"
        ).fetchall()
    return [tuple(row) for row in rows]


@pytest.mark.parametrize("first_tolerance", [0.0, None])
def test_saving_settings_keeps_an_untouched_qualifier_tolerance(
    qapp, empty_db, monkeypatch, first_tolerance
):
    window = _make_window(monkeypatch, AnalysisMode.UNLABELLED)
    try:
        page = _open_qualifier_page(window, monkeypatch, first_tolerance)
        page._spins[2].setValue(0.3)
        window.settings_window.save_button.click()
        assert _stored_tolerances() == [(1, first_tolerance), (2, 0.3)]
    finally:
        if window.settings_window is not None:
            window.settings_window.close()
        window.close()


def test_stepping_down_past_zero_saves_not_set(qapp, empty_db, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.UNLABELLED)
    try:
        page = _open_qualifier_page(window, monkeypatch, 0.5)
        edit = page._spins[1].lineEdit()
        edit.selectAll()
        QTest.keyClicks(edit, "0.029")
        for _ in range(3):
            QTest.keyClick(edit, Qt.Key_Down)
        assert edit.text() == "Not set"
        window.settings_window.save_button.click()
        assert _stored_tolerances() == [(1, None), (2, 0.25)]
        read_compound("Target")
    finally:
        if window.settings_window is not None:
            window.settings_window.close()
        window.close()
