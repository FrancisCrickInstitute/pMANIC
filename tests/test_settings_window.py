from unittest import mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDoubleSpinBox, QScrollArea

from manic.constants import DEFAULT_MIN_PEAK_HEIGHT_RATIO
from manic.models import database
from manic.models.analysis import AnalysisContext, AnalysisMode
from manic.models.sample_fit_type import get_sample_fit_types, set_sample_fit_type
import manic.ui.main_window as main_window_module
from manic.ui import theme
from manic.ui.dialog_kit import MARKED_ROLE
from manic.ui.main_window import MainWindow
from manic.ui.standard_chooser import StandardChooser
from manic.ui.settings_window import (
    AppearanceSection,
    DeconvolutionPage,
    IntegrationSection,
    InternalStandardSection,
    MassToleranceSection,
    NaturalAbundanceSection,
    PeakValidationSection,
    QualifierRatioPage,
)

from manic.utils.utils import apply_app_stylesheet, apply_color_scheme, set_appearance

from conftest import _make_window

LABELLED_TITLES = ["General", "Deconvolution"]


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


def _insert_compound(name: str, label_atoms: int = 3) -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, "
            "label_atoms, int_std_amount, amount_in_std_mix, mm_files) "
            "VALUES (?, 5.0, 0.6, 0.6, 100.0, ?, 10.0, 1.0, 'S1')",
            (name, label_atoms),
        )


def _row_values(page) -> dict[str, str | None]:
    table = page.sample_fit_table
    return {
        table.item(row, 0).text(): table.cellWidget(row, 1).currentData()
        for row in range(table.rowCount())
    }


def _bulk_fit(page, label: str) -> None:
    menu = page.bulk_fit_button.menu()
    next(action for action in menu.actions() if action.text() == label).trigger()


def _override_row_combo(page, sample: str):
    table = page.sample_fit_table
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item is not None and item.text() == sample:
            return table.cellWidget(row, 1)
    raise AssertionError(f"no override row for {sample}")


@pytest.fixture
def labelled_window(qapp, empty_db, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
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

    assert settings.findChild(MassToleranceSection).spin.isEnabled()
    internal = settings.findChild(InternalStandardSection)
    assert not internal.combo.isEnabled()
    assert internal.standard_label.text() == "None"
    assert settings.hint_label.text() == ""

    _select_page(settings, "Deconvolution")
    deconvolution = settings.page_named("Deconvolution")
    assert isinstance(deconvolution, DeconvolutionPage)
    assert not deconvolution.level_combo.isEnabled()
    assert (
        settings.hint_label.text()
        == "Load compounds and select one in the Compounds list to change this."
    )


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
    window = _make_window(monkeypatch, AnalysisMode.UNLABELLED)
    try:
        window.open_settings_window()
        settings = window.settings_window
        _select_page(settings, "Qualifier Ratios")
        page = settings.page_named("Qualifier Ratios")
        assert isinstance(page, QualifierRatioPage)
        for ordinal in (1, 2):
            spin = page.findChild(QDoubleSpinBox, f"qualifier{ordinal}ToleranceSpin")
            assert not spin.isEnabled()
        assert settings.hint_label.text() == (
            "Load compounds and select one in the Compounds list to change this."
        )
    finally:
        if window.settings_window is not None:
            window.settings_window.close()
        window.close()


def test_qualifier_ratios_save_writes_tolerance_and_null(
    qapp, empty_db, monkeypatch
):
    window = _make_window(monkeypatch, AnalysisMode.UNLABELLED)
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
    page = settings.findChild(MassToleranceSection)
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
    page = settings.findChild(PeakValidationSection)
    assert page.spin.value() == DEFAULT_MIN_PEAK_HEIGHT_RATIO

    page.spin.setValue(0.123)
    _select_page(settings, "Deconvolution")
    _select_page(settings, "General")
    assert page.spin.value() == 0.123
    assert settings.save_button.isEnabled()

    settings.reset_button.click()
    assert page.spin.value() == DEFAULT_MIN_PEAK_HEIGHT_RATIO
    assert not settings.save_button.isEnabled()


def test_unsaved_pages_stay_marked_after_switching_away(labelled_window):
    _insert_compound("Alanine")
    labelled_window.compound_data_loaded = True
    labelled_window.toolbar.update_compound_list(["Alanine"], selected_name="Alanine")
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    settings.findChild(MassToleranceSection).spin.setValue(0.35)
    assert settings.save_button.isEnabled()
    assert settings.hint_label.text() == ""
    assert not settings.pending_label.isVisible()
    settings.findChild(PeakValidationSection).spin.setValue(0.123)
    _select_page(settings, "Deconvolution")
    settings.page_named("Deconvolution").level_combo.setCurrentIndex(0)

    marked = [
        settings.page_list.item(row).text()
        for row in range(settings.page_list.count())
        if settings.page_list.item(row).data(MARKED_ROLE)
    ]
    assert marked == ["General", "Deconvolution"]
    assert settings.isWindowModified()
    assert settings.pending_label.isVisible()
    assert "General" in settings.pending_label.text()

    settings.pending_label.linkActivated.emit("0")
    assert settings.page_list.currentItem().text() == "General"
    assert settings.pending_label.text().count("<a ") == 1
    assert "Deconvolution" in settings.pending_label.text()
    settings.save_button.click()
    assert labelled_window.mass_tolerance == 0.35
    assert labelled_window.min_peak_height_ratio == 0.123
    assert not settings.page_list.item(0).data(MARKED_ROLE)
    assert settings.page_list.item(1).data(MARKED_ROLE)

    _select_page(settings, "Deconvolution")
    settings.reset_button.click()
    assert not settings.isWindowModified()
    assert not settings.pending_label.isVisible()


@pytest.fixture
def restore_system_appearance(qapp):
    yield
    set_appearance(qapp, "system")
    apply_color_scheme(qapp, False)
    qapp.setStyleSheet("")


def _window_colour(qapp) -> str:
    return qapp.palette().color(QPalette.Window).name()


def test_appearance_switches_at_once_and_is_never_unsaved(
    qapp, labelled_window, monkeypatch, restore_system_appearance
):
    apply_app_stylesheet(qapp)
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    combo = settings.findChild(AppearanceSection).combo
    assert combo.currentText() == "System"

    combo.setCurrentIndex(combo.findText("Dark"))
    assert theme.is_dark()
    assert _window_colour(qapp) == theme.DARK["bg"].lower()
    assert not settings.save_button.isEnabled()

    # Revert undoes the page's unsaved edits, not the scheme the user just chose.
    settings.findChild(MassToleranceSection).spin.setValue(0.5)
    settings.reset_button.click()
    assert theme.is_dark()
    assert combo.currentText() == "Dark"

    # A restart reapplies it before the first window, and Settings shows it.
    apply_color_scheme(qapp, False)
    apply_app_stylesheet(qapp)
    assert theme.is_dark()
    second = _make_window(monkeypatch, AnalysisMode.LABELLED)
    second.open_settings_window()
    assert second.settings_window.findChild(AppearanceSection).combo.currentText() == "Dark"
    second.settings_window.close()
    second.close()

    # A forced scheme ignores the OS; System follows it again.
    os_scheme = qapp.styleHints().colorSchemeChanged
    combo.setCurrentIndex(combo.findText("Light"))
    os_scheme.emit(Qt.ColorScheme.Dark)
    assert not theme.is_dark()
    combo.setCurrentIndex(combo.findText("System"))
    os_scheme.emit(Qt.ColorScheme.Dark)
    assert theme.is_dark()
    os_scheme.emit(Qt.ColorScheme.Light)
    assert not theme.is_dark()
    assert _window_colour(qapp) == theme.LIGHT["bg"].lower()


def test_legacy_radio_save_enables_legacy_integration(labelled_window):
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    page = settings.findChild(IntegrationSection)
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
    page = settings.findChild(NaturalAbundanceSection)
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
    page = settings.findChild(InternalStandardSection)
    assert page.combo.isEnabled()
    assert page.combo.count() == 4
    page.combo.setCurrentIndex(2)
    settings.save_button.click()
    assert labelled_window.internal_standard_reference_isotope == 2


@pytest.mark.parametrize("existing", [None, "emg"])
def test_deconvolution_page_saves_per_sample_override_and_clear(
    labelled_window, monkeypatch, existing
):
    _insert_compound("Alanine")
    with database.get_connection() as conn:
        conn.execute("INSERT INTO samples (sample_name) VALUES ('S1')")
        conn.execute("INSERT INTO samples (sample_name) VALUES ('S2')")
    if existing:
        set_sample_fit_type("Alanine", ["S1"], existing)
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
    table = page.sample_fit_table
    assert _row_values(page) == {"S1": existing, "S2": None}
    assert [index.row() for index in table.selectionModel().selectedRows()] == [0, 1]
    assert page.bulk_fit_button.text() == "Set fit for 2 selected ▾"
    assert not page.empty_overrides_label.isVisible()
    _bulk_fit(page, "Gaussian")
    assert _row_values(page) == {"S1": "gaussian", "S2": "gaussian"}
    settings.save_button.click()
    assert get_sample_fit_types("Alanine") == {
        ("Alanine", "S1"): "gaussian",
        ("Alanine", "S2"): "gaussian",
    }
    assert replots == [1]
    assert page.remove_all_button.isVisible()

    s1_combo = _override_row_combo(page, "S1")
    s1_combo.setCurrentIndex(s1_combo.findData("bi_gaussian"))
    s2_combo = _override_row_combo(page, "S2")
    s2_combo.setCurrentIndex(s2_combo.findData(None))
    assert not page.remove_all_button.isVisible()
    settings.save_button.click()
    assert get_sample_fit_types("Alanine") == {("Alanine", "S1"): "bi_gaussian"}
    assert replots == [1, 1]

    _override_row_combo(page, "S2").setCurrentIndex(
        _override_row_combo(page, "S2").findData("bi_gaussian")
    )
    page.remove_all_button.click()
    settings.save_button.click()
    assert get_sample_fit_types("Alanine") == {}
    assert replots == [1, 1, 1]

    _bulk_fit(page, "EMG")
    _bulk_fit(page, "Use compound setting")
    assert settings.save_button.isEnabled()
    settings.save_button.click()
    assert get_sample_fit_types("Alanine") == {}
    assert replots == [1, 1, 1]


def test_bulk_fit_follows_the_rows_the_user_selects(labelled_window, monkeypatch):
    _insert_compound("Alanine")
    set_sample_fit_type("Alanine", ["S1", "S2", "S3"], "gaussian")
    labelled_window.compound_data_loaded = True
    labelled_window.toolbar.update_compound_list(["Alanine"], selected_name="Alanine")
    monkeypatch.setattr(labelled_window.graph_view, "get_selected_samples", lambda: [])

    labelled_window.open_settings_page("Deconvolution")
    settings = labelled_window.settings_window
    page = settings.page_named("Deconvolution")
    assert page.bulk_fit_button.text() == "Set fit for selected ▾"
    assert not page.bulk_fit_button.isEnabled()
    page.sample_fit_table.selectRow(2)
    assert page.bulk_fit_button.text() == "Set fit for 1 selected ▾"
    _bulk_fit(page, "Use compound setting")
    settings.save_button.click()

    assert get_sample_fit_types("Alanine") == {
        ("Alanine", "S1"): "gaussian",
        ("Alanine", "S2"): "gaussian",
    }


def test_internal_standard_page_names_the_sidebar_choice(labelled_window):
    _insert_compound("Alanine", label_atoms=0)
    _insert_compound("Norvaline", label_atoms=2)
    labelled_window.compound_data_loaded = True
    labelled_window.toolbar.update_compound_list(["Alanine", "Norvaline"])
    labelled_window.open_settings_page("General")
    settings = labelled_window.settings_window
    page = settings.findChild(InternalStandardSection)
    assert page.standard_label.text() == "None"
    # An unsaved edit elsewhere on the page must not freeze the standard's name.
    settings.findChild(MassToleranceSection).spin.setValue(0.35)
    assert not page.combo.isEnabled()

    labelled_window.toolbar.on_internal_standard_selected("Norvaline")
    assert page.standard_label.text() == "Norvaline"
    assert [page.combo.itemText(i) for i in range(page.combo.count())] == [
        "M+0",
        "M+1",
        "M+2",
    ]
    assert settings.hint_label.text() == ""

    labelled_window.toolbar.on_internal_standard_selected("Alanine")
    assert page.standard_label.text() == "Alanine"
    assert not page.combo.isEnabled()
    assert page.reference_hint.text() == (
        "Alanine has no label atoms, so only M+0 can be the reference peak."
    )

    labelled_window.toolbar.on_internal_standard_cleared()
    assert page.standard_label.text() == "None"
    assert settings.findChild(MassToleranceSection).spin.value() == 0.35


def test_choose_opens_the_sidebar_standard_chooser_under_the_button(labelled_window):
    _insert_compound("Norvaline", label_atoms=2)
    labelled_window.compound_data_loaded = True
    labelled_window.toolbar.update_compound_list(["Norvaline"])
    labelled_window.open_settings_page("General")
    page = labelled_window.settings_window.findChild(InternalStandardSection)
    button = page.choose_button

    button.click()

    chooser = labelled_window.toolbar.standard.findChildren(StandardChooser)[-1]
    assert chooser.pos() == button.mapToGlobal(button.rect().bottomLeft())
    QTest.keyClicks(chooser.filter, "norv")
    QTest.keyClick(chooser.filter, Qt.Key_Return)
    assert page.standard_label.text() == "Norvaline"
    assert page.combo.isEnabled()


def test_changing_the_standard_drops_an_unsaved_reference_peak(labelled_window):
    _insert_compound("Norvaline", label_atoms=2)
    _insert_compound("Leucine", label_atoms=2)
    labelled_window.compound_data_loaded = True
    labelled_window.toolbar.update_compound_list(["Norvaline", "Leucine"])
    labelled_window.toolbar.on_internal_standard_selected("Norvaline")
    labelled_window.open_settings_page("General")
    settings = labelled_window.settings_window
    page = settings.findChild(InternalStandardSection)
    page.combo.setCurrentIndex(2)

    labelled_window.toolbar.on_internal_standard_selected("Leucine")
    assert not settings.save_button.isEnabled()
    settings.save_button.click()

    assert page.combo.currentText() == "M+0"
    assert labelled_window.internal_standard_reference_isotope == 0


def test_deconvolution_without_overrides_or_selection_shows_empty_state(labelled_window):
    _insert_compound("Alanine")
    labelled_window.compound_data_loaded = True
    labelled_window.toolbar.update_compound_list(["Alanine"], selected_name="Alanine")
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
    _select_page(settings, "Deconvolution")
    page = settings.page_named("Deconvolution")
    assert not page.sample_fit_table.isVisible()
    assert not page.bulk_fit_button.isVisible()
    assert not page.remove_all_button.isVisible()
    assert page.empty_overrides_label.isVisible()


def test_settings_window_opens_centred_on_a_visible_main_window(labelled_window):
    screen_area = labelled_window.screen().availableGeometry()
    # A parent hanging off the screen makes the clamp, not the centring, decide x.
    labelled_window.move(screen_area.topLeft())
    labelled_window.resize(
        min(1200, screen_area.width() - 40), min(800, screen_area.height() - 40)
    )
    labelled_window.show()
    labelled_window.open_settings_window()
    settings = labelled_window.settings_window
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


def test_settings_grows_to_show_override_rows_without_scrolling(
    qapp, empty_db, monkeypatch
):
    window = _make_window(monkeypatch, AnalysisMode.UNLABELLED)
    try:
        _insert_unlabelled_target()
        window.compound_data_loaded = True
        window.toolbar.update_compound_list(["Target"], selected_name="Target")
        window.open_settings_window()
        settings = window.settings_window
        scroll = settings.findChild(QScrollArea, "settingsPageScroll")
        monkeypatch.setattr(window.graph_view, "get_selected_samples", lambda: ["S1", "S2"])

        _select_page(settings, "Deconvolution")
        settings.refresh()
        qapp.processEvents()

        assert settings.page_named("Deconvolution").sample_fit_table.isVisible()
        assert not scroll.verticalScrollBar().isVisible()
    finally:
        if window.settings_window is not None:
            window.settings_window.close()
        window.close()
