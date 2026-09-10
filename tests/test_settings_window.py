import os
import sys
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMenu

from manic.constants import DEFAULT_MIN_PEAK_HEIGHT_RATIO
from manic.models import database
from manic.models.analysis import AnalysisContext, AnalysisMode
from manic.models.sample_fit_type import get_sample_fit_types
import manic.ui.main_window as main_window_module
from manic.ui.main_window import MainWindow
from manic.ui.settings_window import (
    DeconvolutionPage,
    InternalStandardPage,
    MassTolerancePage,
    PeakValidationPage,
    QualifierRatioPage,
)

SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"

LABELLED_TITLES = [
    "Mass Tolerance",
    "Peak Validation",
    "Integration",
    "Natural Abundance",
    "Internal Standard",
    "Deconvolution",
]
UNLABELLED_TITLES = [
    "Mass Tolerance",
    "Peak Validation",
    "Qualifier Ratios",
    "Integration",
    "Deconvolution",
]


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def empty_db(tmp_path, monkeypatch):
    db_path = tmp_path / "settings.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    with database.get_connection() as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return db_path


def _make_window(mode: AnalysisMode, monkeypatch) -> MainWindow:
    monkeypatch.setattr(MainWindow, "_check_for_updates", lambda self: None)
    return MainWindow(AnalysisContext(mode))


def _page_titles(settings_window) -> list[str]:
    return [
        settings_window.page_list.item(i).text()
        for i in range(settings_window.page_list.count())
    ]


def _select_page(settings_window, title: str) -> None:
    for index in range(settings_window.page_list.count()):
        if settings_window.page_list.item(index).text() == title:
            settings_window.page_list.setCurrentRow(index)
            return
    raise KeyError(title)


@pytest.fixture
def labelled_window(qapp, empty_db, monkeypatch):
    window = _make_window(AnalysisMode.LABELLED, monkeypatch)
    yield window
    if window.settings_window is not None:
        window.settings_window.close()
    if window.documentation_window is not None:
        window.documentation_window.close()
    window.close()


def test_labelled_settings_open_with_no_data(labelled_window):
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    assert settings is not None
    assert settings.isVisible()
    assert _page_titles(settings) == LABELLED_TITLES

    mass = settings.page_named("Mass Tolerance")
    assert isinstance(mass, MassTolerancePage)
    assert mass.spin.isEnabled()

    _select_page(settings, "Internal Standard")
    internal = settings.page_named("Internal Standard")
    assert isinstance(internal, InternalStandardPage)
    assert not internal.combo.isEnabled()
    assert (
        settings.hint_label.text()
        == "Select an internal standard in the toolbar to change this."
    )

    _select_page(settings, "Deconvolution")
    deconvolution = settings.page_named("Deconvolution")
    assert isinstance(deconvolution, DeconvolutionPage)
    assert not deconvolution.level_combo.isEnabled()
    assert (
        settings.hint_label.text()
        == "Load compounds and select one in the toolbar to change this."
    )


def test_unlabelled_settings_lists_five_pages(qapp, empty_db, monkeypatch):
    window = _make_window(AnalysisMode.UNLABELLED, monkeypatch)
    try:
        window.open_settings_window()
        settings = window.settings_window
        assert _page_titles(settings) == UNLABELLED_TITLES
    finally:
        if window.settings_window is not None:
            window.settings_window.close()
        window.close()


def _insert_unlabelled_target(name: str = "Target") -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, "
            "label_atoms) VALUES (?, 1.0, 0.1, 0.1, 217.0, 0)",
            (name,),
        )
        conn.execute(
            "INSERT INTO compound_ions (compound_name, role, ordinal, mz, expected_ratio, "
            "ratio_tolerance) VALUES (?, 'quantifier', 0, 217.0, NULL, NULL)",
            (name,),
        )
        conn.execute(
            "INSERT INTO compound_ions (compound_name, role, ordinal, mz, expected_ratio, "
            "ratio_tolerance) VALUES (?, 'qualifier', 1, 147.0, 0.4, 0.25)",
            (name,),
        )
        conn.execute(
            "INSERT INTO compound_ions (compound_name, role, ordinal, mz, expected_ratio, "
            "ratio_tolerance) VALUES (?, 'qualifier', 2, 73.0, 0.2, NULL)",
            (name,),
        )


def test_qualifier_ratios_page_is_unlabelled_only(labelled_window):
    labelled_window.open_settings_window()
    titles = _page_titles(labelled_window.settings_window)
    assert "Qualifier Ratios" not in titles
    assert titles == LABELLED_TITLES


def test_qualifier_ratios_not_editable_without_a_selected_compound(
    qapp, empty_db, monkeypatch
):
    window = _make_window(AnalysisMode.UNLABELLED, monkeypatch)
    try:
        window.open_settings_window()
        settings = window.settings_window
        _select_page(settings, "Qualifier Ratios")
        page = settings.page_named("Qualifier Ratios")
        assert isinstance(page, QualifierRatioPage)
        assert page.editable() == (
            False,
            "Load compounds and select one in the toolbar to change this.",
        )
        assert not page._spins[1].isEnabled()
        assert settings.hint_label.text() == (
            "Load compounds and select one in the toolbar to change this."
        )
    finally:
        if window.settings_window is not None:
            window.settings_window.close()
        window.close()


def test_qualifier_ratios_save_writes_tolerance_and_null(
    qapp, empty_db, monkeypatch
):
    window = _make_window(AnalysisMode.UNLABELLED, monkeypatch)
    try:
        _insert_unlabelled_target()
        window.compound_data_loaded = True
        window.toolbar.update_compound_list(["Target"], selected_name="Target")
        replots = []
        monkeypatch.setattr(window, "_replot_current_selection", lambda: replots.append(1))
        window.open_settings_window()
        settings = window.settings_window
        _select_page(settings, "Qualifier Ratios")
        page = settings.page_named("Qualifier Ratios")
        assert page.compound_label.text() == "Compound: Target"
        assert page._labels[1].text() == "Qualifier 1 (m/z 147)"
        assert page._ratio_labels[1].text() == "expected ratio 0.4"
        assert page._spins[1].isVisible()
        assert page._spins[2].isVisible()
        page._spins[1].setValue(0.3)
        page._spins[2].setValue(0.0)
        settings.save_button.click()
        with database.get_connection() as conn:
            rows = conn.execute(
                "SELECT ordinal, ratio_tolerance FROM compound_ions "
                "WHERE compound_name = 'Target' AND role = 'qualifier' "
                "ORDER BY ordinal"
            ).fetchall()
        assert rows[0]["ordinal"] == 1
        assert rows[0]["ratio_tolerance"] == pytest.approx(0.3)
        assert rows[1]["ordinal"] == 2
        assert rows[1]["ratio_tolerance"] is None
        assert replots == [1]
    finally:
        if window.settings_window is not None:
            window.settings_window.close()
        window.close()


def test_mass_tolerance_save_writes_literal_value(labelled_window):
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    _select_page(settings, "Mass Tolerance")
    page = settings.page_named("Mass Tolerance")
    assert labelled_window.mass_tolerance == 0.2

    page.spin.setValue(0.35)
    assert labelled_window.mass_tolerance == 0.2
    assert settings.save_button.isEnabled()

    settings.save_button.click()
    assert labelled_window.mass_tolerance == 0.35
    assert not settings.save_button.isEnabled()


def test_peak_validation_keeps_unsaved_edit_across_pages(labelled_window):
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    _select_page(settings, "Peak Validation")
    page = settings.page_named("Peak Validation")
    assert isinstance(page, PeakValidationPage)
    assert page.spin.value() == DEFAULT_MIN_PEAK_HEIGHT_RATIO

    page.spin.setValue(0.123)
    _select_page(settings, "Mass Tolerance")
    _select_page(settings, "Peak Validation")
    assert page.spin.value() == 0.123
    assert settings.save_button.isEnabled()

    settings.reset_button.click()
    assert page.spin.value() == DEFAULT_MIN_PEAK_HEIGHT_RATIO
    assert not settings.save_button.isEnabled()


def test_legacy_radio_save_enables_legacy_integration(labelled_window):
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    _select_page(settings, "Integration")
    page = settings.page_named("Integration")
    assert labelled_window.use_legacy_integration is False

    page.legacy_radio.setChecked(True)
    assert settings.save_button.isEnabled()
    settings.save_button.click()
    assert labelled_window.use_legacy_integration is True


def test_gear_button_and_menu_action_open_settings(labelled_window):
    labelled_window.graph_view.settings_button.click()
    assert labelled_window.settings_window.isVisible()

    labelled_window.settings_window.close()
    assert not labelled_window.settings_window.isVisible()
    labelled_window.settings_action.trigger()
    assert labelled_window.settings_window.isVisible()


def test_natural_abundance_save_propagates_preview_flag(labelled_window):
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    _select_page(settings, "Natural Abundance")
    page = settings.page_named("Natural Abundance")
    assert labelled_window.graph_view.use_corrected is False

    page.preview_check.setChecked(True)
    assert labelled_window.preview_nat_abundance is False
    settings.save_button.click()
    assert labelled_window.preview_nat_abundance is True
    assert labelled_window.graph_view.use_corrected is True
    assert labelled_window.toolbar.isotopologue_ratios.use_corrected is True


def test_deconvolution_page_unlocks_for_selected_compound_and_saves(labelled_window):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, "
            "label_atoms, int_std_amount, amount_in_std_mix, mm_files) "
            "VALUES ('Alanine', 5.0, 0.6, 0.6, 100.0, 3, 10.0, 1.0, 'S1')"
        )
    labelled_window.compound_data_loaded = True
    labelled_window.toolbar.update_compound_list(["Alanine"], selected_name="Alanine")
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    _select_page(settings, "Deconvolution")
    page = settings.page_named("Deconvolution")

    assert page.compound_label.text() == "Compound: Alanine"
    assert page.level_combo.isEnabled()
    assert page.level_combo.currentData() == "4"

    page.level_combo.setCurrentIndex(0)
    assert page.fit_combo.isEnabled() is False
    settings.save_button.click()

    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT deconvolution_level, deconvolution_fit_type FROM compounds "
            "WHERE compound_name = 'Alanine'"
        ).fetchone()
    assert tuple(row) == ("off", "auto")
    assert settings.save_button.isEnabled() is False


def test_internal_standard_without_label_atoms_disables_combo(labelled_window):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, "
            "label_atoms, int_std_amount, amount_in_std_mix, mm_files) "
            "VALUES ('Norvaline', 5.0, 0.6, 0.6, 100.0, 0, 10.0, 1.0, 'S1')"
        )
    labelled_window.compound_data_loaded = True
    labelled_window.toolbar.update_compound_list(["Norvaline"])
    labelled_window.toolbar.on_internal_standard_selected("Norvaline")
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    _select_page(settings, "Internal Standard")
    page = settings.page_named("Internal Standard")
    assert not page.combo.isEnabled()
    assert (
        settings.hint_label.text()
        == "'Norvaline' has no label atoms, so only M+0 can be the reference peak."
    )


def test_internal_standard_reference_peak_saves_selected_isotope(labelled_window):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, "
            "label_atoms, int_std_amount, amount_in_std_mix, mm_files) "
            "VALUES ('Norvaline', 5.0, 0.6, 0.6, 100.0, 3, 10.0, 1.0, 'S1')"
        )
    labelled_window.compound_data_loaded = True
    labelled_window.toolbar.update_compound_list(["Norvaline"])
    labelled_window.toolbar.on_internal_standard_selected("Norvaline")
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    _select_page(settings, "Internal Standard")
    page = settings.page_named("Internal Standard")
    assert page.combo.isEnabled()
    assert page.combo.count() == 4
    page.combo.setCurrentIndex(2)
    settings.save_button.click()
    assert labelled_window.internal_standard_reference_isotope == 2


def test_deconvolution_page_saves_per_sample_override_and_clear(labelled_window, monkeypatch):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, "
            "label_atoms, int_std_amount, amount_in_std_mix, mm_files) "
            "VALUES ('Alanine', 5.0, 0.6, 0.6, 100.0, 3, 10.0, 1.0, 'S1')"
        )
        conn.execute("INSERT INTO samples (sample_name) VALUES ('S1')")
        conn.execute("INSERT INTO samples (sample_name) VALUES ('S2')")
    labelled_window.compound_data_loaded = True
    labelled_window.toolbar.update_compound_list(["Alanine"], selected_name="Alanine")
    monkeypatch.setattr(
        labelled_window.graph_view,
        "get_selected_samples",
        lambda: ["S1", "S2"],
    )
    replots = []
    monkeypatch.setattr(
        labelled_window, "_replot_current_selection", lambda: replots.append(1)
    )

    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    _select_page(settings, "Deconvolution")
    page = settings.page_named("Deconvolution")
    assert page.sample_scope_label.text() == (
        "Applies to the 2 samples selected in the plot area"
    )
    assert page.sample_group.isEnabled()
    page.sample_fit_combo.setCurrentIndex(page.sample_fit_combo.findData("gaussian"))
    settings.save_button.click()
    assert get_sample_fit_types("Alanine") == {
        ("Alanine", "S1"): "gaussian",
        ("Alanine", "S2"): "gaussian",
    }
    assert replots == [1]

    page.clear_overrides.setChecked(True)
    settings.save_button.click()
    assert get_sample_fit_types("Alanine") == {}
    assert replots == [1, 1]


def test_deconvolution_unsaved_hint_names_the_compound_it_will_write(labelled_window):
    with database.get_connection() as conn:
        for name in ("Alanine", "Glycine"):
            conn.execute(
                "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, "
                "label_atoms, int_std_amount, amount_in_std_mix, mm_files) "
                "VALUES (?, 5.0, 0.6, 0.6, 100.0, 3, 10.0, 1.0, 'S1')",
                (name,),
            )
    labelled_window.compound_data_loaded = True
    labelled_window.toolbar.update_compound_list(["Alanine", "Glycine"], selected_name="Alanine")
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    _select_page(settings, "Deconvolution")
    page = settings.page_named("Deconvolution")
    page.level_combo.setCurrentIndex(0)
    assert settings.hint_label.text() == "Unsaved changes for Alanine"

    labelled_window.toolbar.update_compound_list(["Alanine", "Glycine"], selected_name="Glycine")
    settings.refresh()
    assert page.compound_label.text() == "Compound: Alanine"
    assert settings.hint_label.text() == (
        "Unsaved changes for Alanine. The toolbar now selects Glycine; "
        "Save still writes to Alanine."
    )


def test_manic_menu_holds_settings_docs_updates_and_about(labelled_window):
    menus = [
        m for m in labelled_window.menuBar().findChildren(QMenu) if m.title() == "MANIC"
    ]
    assert len(menus) == 1
    texts = [a.text() for a in menus[0].actions() if not a.isSeparator()]
    assert texts == [
        "Settings...",
        "Documentation",
        "Check for Updates...",
        "About MANIC...",
    ]


def test_settings_window_opens_centred_on_a_visible_main_window(labelled_window):
    labelled_window.resize(1200, 800)
    labelled_window.show()
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    screen_area = labelled_window.screen().availableGeometry()
    frame = settings.frameGeometry()
    assert screen_area.contains(frame.topLeft())
    parent_centre = labelled_window.frameGeometry().center()
    if frame.height() <= screen_area.height():
        assert abs(frame.center().y() - parent_centre.y()) <= 4
    if frame.width() <= screen_area.width():
        assert abs(frame.center().x() - parent_centre.x()) <= 4


class _StuckWorker:
    instances = 0

    def __init__(self):
        type(self).instances += 1
        self.result = mock.Mock()
        self.started = False

    def start(self):
        self.started = True

    def isRunning(self):
        return self.started


def test_check_for_updates_does_not_start_a_second_worker_while_one_runs(
    qapp, empty_db, monkeypatch
):
    _StuckWorker.instances = 0
    monkeypatch.setattr(main_window_module, "UpdateCheckWorker", _StuckWorker)
    window = MainWindow(AnalysisContext(AnalysisMode.LABELLED))
    try:
        window.check_updates_action.trigger()
        window.check_updates_action.trigger()
        assert _StuckWorker.instances == 1
    finally:
        window.close()
