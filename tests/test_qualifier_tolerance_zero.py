import pytest

from manic.models import database
from manic.models.analysis import AnalysisMode

from conftest import _make_window
from test_settings_window import _select_page


@pytest.mark.parametrize("first_tolerance", [0.0, None])
def test_saving_settings_keeps_an_untouched_qualifier_tolerance(
    qapp, empty_db, monkeypatch, first_tolerance
):
    window = _make_window(monkeypatch, AnalysisMode.UNLABELLED)
    try:
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
        settings = window.settings_window
        _select_page(settings, "Qualifier ratios")
        settings.page_named("Qualifier ratios")._spins[2].setValue(0.3)
        settings.save_button.click()
        with database.get_connection() as conn:
            rows = conn.execute(
                "SELECT ordinal, ratio_tolerance FROM compound_ions "
                "WHERE compound_name = 'Target' AND role = 'qualifier' "
                "ORDER BY ordinal"
            ).fetchall()
        assert [tuple(row) for row in rows] == [(1, first_tolerance), (2, 0.3)]
    finally:
        if window.settings_window is not None:
            window.settings_window.close()
        window.close()
