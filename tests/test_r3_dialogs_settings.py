from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QLabel

from manic.models.analysis import AnalysisMode
from manic.validation.peak_verdict import PeakVerdict
from manic.ui.plot_tile import PEAK_BADGES
from manic.ui.settings_window import SettingsWindow


def _host(mode: AnalysisMode) -> SimpleNamespace:
    return SimpleNamespace(
        analysis_mode=mode,
        mass_tolerance=0.2,
        min_peak_height_ratio=0.005,
        use_legacy_integration=False,
        preview_nat_abundance=False,
        internal_standard_name=lambda: None,
        internal_standard_label_atoms=lambda: 0,
        internal_standard_reference_isotope=0,
        selected_compound_name=lambda: None,
        selected_sample_names=lambda: [],
        qualifier_channels=lambda _name: [],
        deconvolution_settings=lambda _name: ("4", "auto", "balanced"),
        compound_names=lambda: [],
    )


@pytest.fixture
def settings(qapp):
    window = SettingsWindow(None, _host(AnalysisMode.LABELLED))
    window.show()
    window.open()
    qapp.processEvents()
    yield window
    window.close()


def _left(widget, ancestor) -> int:
    return widget.mapTo(ancestor, QPoint()).x()


@pytest.mark.parametrize(
    ("page_title", "field_name"),
    [("Mass Tolerance", "spin"), ("Peak Validation", "spin"), ("Internal Standard", "combo")],
)
def test_short_fields_stay_narrow_and_left_aligned(qapp, settings, page_title, field_name):
    page = settings.page_named(page_title)
    settings.page_list.setCurrentRow(settings._pages.index(page))
    qapp.processEvents()
    field = getattr(page, field_name)
    label = next(
        child
        for child in page.findChildren(QLabel)
        if child.buddy() is field
    )
    assert field.width() <= 120
    assert _left(field, page) > _left(label, page) + label.width()
    assert _left(field, page) < page.width() // 2


def test_footer_buttons_share_one_baseline(settings):
    reset = settings.reset_button
    save = settings.save_button
    assert reset.mapTo(settings, QPoint()).y() == save.mapTo(settings, QPoint()).y()
    assert reset.height() == save.height()


def test_peak_validation_copy_names_the_badge_the_plots_show(settings):
    text = settings.page_named("Peak Validation").findChild(QLabel).text()
    assert PEAK_BADGES[PeakVerdict.FAIL].text in text
    assert "red" not in text.lower()


@pytest.mark.parametrize("mode", list(AnalysisMode))
def test_no_settings_copy_points_at_the_removed_toolbar(qapp, mode):
    window = SettingsWindow(None, _host(mode))
    texts = [label.text() for label in window.findChildren(QLabel)]
    texts += [page.editable()[1] for page in window._pages]
    assert [text for text in texts if "toolbar" in text.lower()] == []
    window.close()


def test_internal_standard_page_offers_the_standard_itself(settings):
    page = settings.page_named("Internal Standard")
    settings.page_list.setCurrentRow(settings._pages.index(page))
    assert page.standard_combo.itemText(0) == "No internal standard"
    assert settings.hint_label.text() == "Load a compound list to choose an internal standard."
