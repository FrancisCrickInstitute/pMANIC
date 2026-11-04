from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QRect, QSettings
from PySide6.QtWidgets import QApplication

from manic.models.analysis import AnalysisMode
from manic.ui.left_toolbar import Toolbar


@pytest.fixture(autouse=True)
def scratch_settings(tmp_path):
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    QSettings().clear()
    yield


@pytest.fixture
def toolbar(qapp, monkeypatch):
    monkeypatch.setattr(
        "manic.ui.left_toolbar.read_compound",
        lambda _name: SimpleNamespace(deconvolution_level="off", baseline_correction=1),
    )
    toolbar = Toolbar(AnalysisMode.LABELLED)
    toolbar.update_label_colours(True, True)
    toolbar.update_compound_list(["Alanine"], "Alanine")
    toolbar.update_sample_list(["S1", "S2"])
    toolbar.show()
    yield toolbar
    toolbar.deleteLater()


def test_section_summary_shows_only_while_the_section_is_closed(toolbar):
    for section in (toolbar.peak_section, toolbar.display_section):
        section.set_expanded(True)
        assert not section.summary.isVisible()
        section.set_expanded(False)
        assert section.summary.isVisible()
        assert section.summary.full_text()


def _settle(toolbar: Toolbar) -> None:
    for _ in range(3):
        for _ in range(5):
            QApplication.processEvents()
        toolbar.fit_inspector()


def _whole_in_view(toolbar: Toolbar, widget) -> bool:
    viewport = toolbar.inspector.viewport()
    top = widget.mapTo(viewport, QPoint(0, 0)).y()
    return widget.isVisible() and top >= 0 and top + widget.height() <= viewport.height()


# Sidebar heights of a 1024x640 and a 1280x720 window with Samples open.
@pytest.mark.parametrize("height", [587, 667])
def test_reset_and_apply_are_never_cut_on_a_short_sidebar(qapp, height):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    try:
        toolbar.update_label_colours(True, True)
        toolbar.update_compound_list([f"Compound {i}" for i in range(95)])
        toolbar.update_sample_list([f"Bio_{i:03d}" for i in range(30)])
        toolbar.samples_section.set_expanded(True)
        toolbar.resize(296, height)
        toolbar.show()
        _settle(toolbar)
        lists = (toolbar.compound_list, toolbar.sample_list)
        for lst, rows in zip(lists, (4, 3)):
            assert lst.viewport().height() // lst.sizeHintForRow(0) >= rows

        bar = toolbar.inspector.verticalScrollBar()
        if height == 587:
            assert bar.maximum() > 0, "the Peak window should have to scroll at this height"
        slot = toolbar._pinned_actions._slot
        viewport = toolbar.inspector.viewport()
        for value in range(bar.minimum(), bar.maximum() + 1, 4):
            bar.setValue(value)
            QApplication.processEvents()
            if slot.mapTo(viewport, QPoint(0, 0)).y() < 0:
                break  # scrolled past: the row leaves with its fields
            for button in (toolbar.integration.restore_button, toolbar.integration.apply_button):
                assert _whole_in_view(toolbar, button), value
            row = toolbar.integration.action_row
            at = slot.mapTo(viewport, QPoint(0, 0))
            if at.y() + slot.height() <= viewport.height():
                assert row.geometry() == QRect(at, slot.size())  # in its place
            else:
                assert row.geometry().bottom() == viewport.rect().bottom()  # pinned
    finally:
        toolbar.deleteLater()
