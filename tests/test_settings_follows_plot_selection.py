import pytest

from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.models.sample_fit_type import get_sample_fit_types

from conftest import _make_window
from test_settings_window import _bulk_fit, _insert_compound, _row_values, _select_page


@pytest.fixture
def window(qapp, empty_db, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    yield window
    if window.settings_window is not None:
        window.settings_window.close()
    window.close()


def test_open_deconvolution_page_follows_plot_selection_and_keeps_unsaved_edits(
    window, monkeypatch
):
    _insert_compound("Alanine")
    with database.get_connection() as conn:
        conn.execute("INSERT INTO samples (sample_name) VALUES ('S1')")
        conn.execute("INSERT INTO samples (sample_name) VALUES ('S2')")
    window.compound_data_loaded = True
    window.toolbar.update_compound_list(["Alanine"], selected_name="Alanine")
    monkeypatch.setattr(window, "_replot_current_selection", lambda: None)
    selected: list[str] = []
    monkeypatch.setattr(window.graph_view, "get_selected_samples", lambda: list(selected))

    def select_tiles(*samples: str) -> None:
        selected[:] = samples
        window.graph_view.selection_changed.emit(list(samples))

    window.open_settings_window()
    settings = window.settings_window
    peak_page = settings.page_named("Peak validation")
    page = settings.page_named("Deconvolution")
    _select_page(settings, "Deconvolution")
    assert _row_values(page) == {}

    select_tiles("S1")
    assert _row_values(page) == {"S1": None}
    assert page.bulk_fit_button.text() == "Set fit for 1 selected ▾"

    _bulk_fit(page, "Gaussian")
    page.level_combo.setCurrentIndex(page.level_combo.findData("1"))
    peak_page.spin.setValue(0.123)
    select_tiles("S2")
    assert _row_values(page) == {"S1": "gaussian", "S2": None}
    table = page.sample_fit_table
    selected_rows = table.selectionModel().selectedRows()
    assert [table.item(index.row(), 0).text() for index in selected_rows] == ["S2"]
    assert page.level_combo.currentData() == "1"
    assert peak_page.spin.value() == 0.123

    _bulk_fit(page, "EMG")
    settings.save_button.click()
    assert get_sample_fit_types("Alanine") == {
        ("Alanine", "S1"): "gaussian",
        ("Alanine", "S2"): "emg",
    }
    assert _row_values(page) == {"S1": "gaussian", "S2": "emg"}
