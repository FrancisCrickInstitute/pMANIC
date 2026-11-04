from PySide6.QtCore import QPoint, QSettings
from PySide6.QtWidgets import QApplication
import pytest

from manic.models.analysis import AnalysisMode
from manic.ui.left_toolbar import SPLIT_SETTING, SUMMARY_SETTING, Toolbar


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


def _toolbar(height: int, compounds: int = 95, samples: int = 30) -> Toolbar:
    toolbar = Toolbar(AnalysisMode.LABELLED)
    toolbar.update_label_colours(True, True)
    toolbar.update_compound_list([f"Compound {i}" for i in range(compounds)])
    toolbar.update_sample_list([f"Sample {i}" for i in range(samples)])
    toolbar.resize(280, height)
    toolbar.show()
    _settle(toolbar)
    return toolbar


def _peak_window_whole(toolbar: Toolbar) -> bool:
    viewport = toolbar.inspector.viewport()
    box = toolbar.baseline_checkbox
    return box.mapTo(viewport, QPoint(0, box.height())).y() <= viewport.height()


def _rows(lst) -> float:
    return lst.height() / lst.sizeHintForRow(0)


@pytest.mark.parametrize("samples_open", [False, True])
def test_peak_window_stays_whole_on_a_short_sidebar(qapp, samples_open):
    # About the sidebar of a 1024x768 window.
    toolbar = _toolbar(680)
    try:
        toolbar.samples_section.set_expanded(samples_open)
        _settle(toolbar)
        assert _peak_window_whole(toolbar)
        assert toolbar.compound_list.height() > 0
    finally:
        toolbar.deleteLater()


def test_closing_samples_gives_its_room_back_without_a_resize(qapp):
    toolbar = _toolbar(700)
    try:
        closed = toolbar.splitter.sizes()
        toolbar.samples_section.set_expanded(True)
        _settle(toolbar)
        assert _rows(toolbar.sample_list) >= 3
        toolbar.samples_section.set_expanded(False)
        _settle(toolbar)
        assert toolbar.splitter.sizes() == closed
    finally:
        toolbar.deleteLater()


def test_a_short_filtered_list_leaves_its_room_to_samples(qapp):
    toolbar = _toolbar(900)
    try:
        toolbar.samples_section.set_expanded(True)
        _settle(toolbar)
        before = toolbar.sample_list.height()
        toolbar.compound_filter.setText("Compound 1")  # 1 and 10-19: 11 rows
        toolbar.compound_filter.setText("Compound 9")  # 9 and 90-94: 6 rows
        _settle(toolbar)
        assert _rows(toolbar.compound_list) == pytest.approx(6, abs=0.2)
        assert toolbar.sample_list.height() > before
    finally:
        toolbar.deleteLater()


def test_dragged_split_is_kept_only_while_the_peak_window_fits(qapp):
    toolbar = _toolbar(700)
    try:
        total = sum(toolbar.splitter.sizes())
        toolbar.splitter.setSizes([total - 60, 60])
        dragged = toolbar.splitter.sizes()[0] / total
        toolbar._on_splitter_moved()
        _settle(toolbar)
        assert _peak_window_whole(toolbar)
        assert QSettings().value(SPLIT_SETTING, type=float) == pytest.approx(dragged)

        toolbar.splitter.setSizes([200, total - 200])
        toolbar._on_splitter_moved()
        _settle(toolbar)
        assert toolbar.splitter.sizes()[0] == 200
    finally:
        toolbar.deleteLater()


def test_summary_starts_collapsed_only_when_short_and_the_user_choice_wins(qapp):
    short = _toolbar(560)
    try:
        assert not short.summary_section.is_expanded()
    finally:
        short.deleteLater()

    tall = _toolbar(1400)
    try:
        assert tall.summary_section.is_expanded()
    finally:
        tall.deleteLater()

    QSettings().setValue(SUMMARY_SETTING, True)
    chosen = _toolbar(560)
    try:
        assert chosen.summary_section.is_expanded()
    finally:
        chosen.deleteLater()


def test_switching_compound_scrolls_the_inspector_back_to_the_top(qapp, monkeypatch):
    monkeypatch.setattr(Toolbar, "_set_baseline_checkbox_from_compound", lambda *a: None)
    monkeypatch.setattr(Toolbar, "sync_selected_peak_checkbox", lambda *a: None)
    QSettings().setValue(SUMMARY_SETTING, True)
    toolbar = _toolbar(560)
    try:
        toolbar.show_pane(toolbar.summary_section)
        # Summaries now shrink to fit, so make the pane overflow to have something to scroll.
        toolbar.summary_section.body.setMinimumHeight(1000)
        _settle(toolbar)
        bar = toolbar.inspector.verticalScrollBar()
        bar.setValue(bar.maximum())
        assert bar.value() > 0
        toolbar.compound_list.setCurrentRow(3)
        assert bar.value() == 0
    finally:
        toolbar.deleteLater()
