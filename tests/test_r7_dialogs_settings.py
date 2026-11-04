import pytest
from PySide6.QtWidgets import QComboBox

from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.models.sample_fit_type import get_sample_fit_types, set_sample_fit_type

from conftest import _make_window


def _insert(name: str, label_atoms: int = 3) -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, "
            "label_atoms, int_std_amount, amount_in_std_mix, mm_files) "
            "VALUES (?, 5.0, 0.6, 0.6, 100.0, ?, 10.0, 1.0, 'S1')",
            (name, label_atoms),
        )


@pytest.fixture
def window(qapp, empty_db, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    monkeypatch.setattr(window, "_replot_current_selection", lambda: None)
    yield window
    if window.settings_window is not None:
        window.settings_window.close()
    window.close()


def _deconvolution_page(window):
    window.open_settings_page("Deconvolution")
    return window.settings_window, window.settings_window.page_named("Deconvolution")


def _row_values(page) -> dict[str, str | None]:
    table = page.sample_fit_table
    return {
        table.item(row, 0).text(): table.cellWidget(row, 1).currentData()
        for row in range(table.rowCount())
    }


def test_a_selected_sample_with_an_override_has_one_fit_editor(window, monkeypatch):
    _insert("Alanine")
    for sample in ("S1", "S2"):
        with database.get_connection() as conn:
            conn.execute("INSERT INTO samples (sample_name) VALUES (?)", (sample,))
    set_sample_fit_type("Alanine", ["S1"], "gaussian")
    window.compound_data_loaded = True
    window.toolbar.update_compound_list(["Alanine"], selected_name="Alanine")
    monkeypatch.setattr(window.graph_view, "get_selected_samples", lambda: ["S1", "S2"])

    settings, page = _deconvolution_page(window)

    # Every per-sample value lives in one table row; no second editor can disagree.
    assert _row_values(page) == {"S1": "gaussian", "S2": None}
    compound_combos = {page.level_combo, page.fit_combo, page.gate_combo}
    row_combos = set(page._row_combos())
    assert set(page.findChildren(QComboBox)) == compound_combos | row_combos

    page.set_fit_for_selected_rows("emg")
    assert _row_values(page) == {"S1": "emg", "S2": "emg"}
    s1 = page._row_combos()[0]
    s1.setCurrentIndex(s1.findData("bi_gaussian"))
    settings.save_button.click()

    assert get_sample_fit_types("Alanine") == {
        ("Alanine", "S1"): "bi_gaussian",
        ("Alanine", "S2"): "emg",
    }
    assert _row_values(page) == {"S1": "bi_gaussian", "S2": "emg"}


def test_bulk_fit_follows_the_rows_the_user_selects(window, monkeypatch):
    _insert("Alanine")
    set_sample_fit_type("Alanine", ["S1", "S2", "S3"], "gaussian")
    window.compound_data_loaded = True
    window.toolbar.update_compound_list(["Alanine"], selected_name="Alanine")
    monkeypatch.setattr(window.graph_view, "get_selected_samples", lambda: [])

    settings, page = _deconvolution_page(window)
    assert page.bulk_fit_button.text() == "Set fit for selected ▾"
    assert not page.bulk_fit_button.isEnabled()
    page.sample_fit_table.selectRow(2)
    assert page.bulk_fit_button.text() == "Set fit for 1 selected ▾"
    page.set_fit_for_selected_rows(None)
    settings.save_button.click()

    assert get_sample_fit_types("Alanine") == {
        ("Alanine", "S1"): "gaussian",
        ("Alanine", "S2"): "gaussian",
    }


def test_internal_standard_page_chooses_the_standard_and_its_reference_peak(window):
    _insert("Alanine")
    _insert("Norvaline", label_atoms=2)
    window.compound_data_loaded = True
    window.toolbar.update_compound_list(["Alanine", "Norvaline"])
    window.open_settings_page("Internal Standard")
    settings = window.settings_window
    page = settings.page_named("Internal Standard")
    assert page.standard_combo.currentText() == "No internal standard"
    assert not page.combo.isEnabled()

    page.standard_combo.setCurrentIndex(page.standard_combo.findData("Norvaline"))
    assert [page.combo.itemText(i) for i in range(page.combo.count())] == [
        "M+0",
        "M+1",
        "M+2",
    ]
    page.combo.setCurrentIndex(2)
    settings.save_button.click()

    assert window.toolbar.get_internal_standard() == "Norvaline"
    assert window.internal_standard_reference_isotope == 2
    assert not page.is_dirty()

    page.standard_combo.setCurrentIndex(0)
    settings.save_button.click()
    assert window.toolbar.get_internal_standard() is None


def test_unsaved_banner_lists_only_other_pages(window):
    window.open_settings_window()
    settings = window.settings_window
    settings.page_named("Mass Tolerance").spin.setValue(0.35)
    assert settings.save_button.isEnabled()
    assert settings.hint_label.text() == ""
    assert not settings.pending_label.isVisible()
    settings.page_list.setCurrentRow(1)
    assert settings.pending_label.isVisible()
    assert "Mass Tolerance" in settings.pending_label.text()
