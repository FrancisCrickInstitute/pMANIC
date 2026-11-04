import pytest
from PySide6.QtCore import QPoint, QSettings
from PySide6.QtWidgets import QApplication

from manic.models.analysis import AnalysisMode
from manic.ui.left_toolbar import Toolbar

# Sidebar heights in a 1280x720 and a 1024x768 window (menu and status bar taken off).
LAPTOP_720 = 667
LAPTOP_768 = 715


@pytest.fixture(autouse=True)
def scratch_settings(tmp_path):
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    QSettings().clear()
    yield


def _settle(toolbar: Toolbar) -> None:
    for _ in range(3):
        for _ in range(5):
            QApplication.processEvents()
        toolbar.fit_inspector()


def _toolbar(height: int, samples_open: bool) -> Toolbar:
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
    viewport = toolbar.inspector.viewport()
    top = widget.mapTo(viewport, QPoint(0, 0)).y()
    return widget.isVisible() and top >= 0 and top + widget.height() <= viewport.height()


def test_laptop_lists_keep_four_compounds_and_three_samples_with_samples_open(qapp):
    toolbar = _toolbar(LAPTOP_720, samples_open=True)
    try:
        assert _full_rows(toolbar.compound_list) >= 4
        assert _full_rows(toolbar.sample_list) >= 3
        assert toolbar.section_switcher.isVisible()
    finally:
        toolbar.deleteLater()


@pytest.mark.parametrize("samples_open", [False, True])
def test_peak_window_stays_whole_at_1024x768(qapp, samples_open):
    toolbar = _toolbar(LAPTOP_768, samples_open)
    try:
        assert _in_view(toolbar, toolbar.baseline_checkbox)
        assert _full_rows(toolbar.compound_list) >= 4
    finally:
        toolbar.deleteLater()


def test_switcher_reaches_display_and_summary_in_one_click(qapp):
    toolbar = _toolbar(LAPTOP_720, samples_open=True)
    try:
        buttons = {b.objectName(): b for b in toolbar._switch_buttons.buttons()}
        assert [b.text() for b in toolbar._switch_buttons.buttons()] == [
            "Peak window",
            "Display",
            "Summary",
        ]
        assert buttons["switch_peak"].isChecked()
        assert not toolbar.peak_section.header.isVisible()

        buttons["switch_display"].click()
        assert _in_view(toolbar, toolbar.shared_yscale_checkbox)
        assert not toolbar.integration.isVisible()

        buttons["switch_summary"].click()
        assert _in_view(toolbar, toolbar.total_abundance.header)
        assert not toolbar.shared_yscale_checkbox.isVisible()

        buttons["switch_peak"].click()
        assert _in_view(toolbar, toolbar.integration.apply_button)
    finally:
        toolbar.deleteLater()


def test_tall_sidebar_shows_every_section_heading_and_no_switcher(qapp):
    toolbar = _toolbar(1400, samples_open=True)
    try:
        assert not toolbar.section_switcher.isVisible()
        for section in (toolbar.peak_section, toolbar.display_section, toolbar.summary_section):
            assert _in_view(toolbar, section.header)
    finally:
        toolbar.deleteLater()


def test_switcher_leaves_once_there_is_room_and_sections_keep_their_state(qapp):
    toolbar = _toolbar(LAPTOP_720, samples_open=False)
    try:
        toolbar.display_section.set_expanded(False)
        toolbar.show_pane(toolbar.display_section)
        assert toolbar.shared_yscale_checkbox.isVisible()
        toolbar.resize(296, 1400)
        _settle(toolbar)
        assert not toolbar.section_switcher.isVisible()
        assert toolbar.integration.isVisible()
        assert not toolbar.shared_yscale_checkbox.isVisible()
        assert toolbar.display_section.header.isVisible()
    finally:
        toolbar.deleteLater()
