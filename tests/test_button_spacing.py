"""Adjacent buttons never touch: 4 px between a segmented control's segments, 8 px otherwise."""

from itertools import combinations

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QAbstractButton, QApplication, QLineEdit, QPushButton, QToolButton, QWidget

from manic.models.analysis import AnalysisMode
from manic.models.mm_file_check import MmFileStatus
from manic.utils.utils import apply_app_stylesheet

from conftest import _make_window

SEGMENT_GAP = 4
BUTTON_GAP = 8


def crowded_buttons(window: QWidget) -> list[str]:
    """Visible push and tool buttons that share a row or column and sit too close."""
    buttons = [
        button
        for button in window.findChildren(QAbstractButton)
        if isinstance(button, (QPushButton, QToolButton))
        and button.isVisible()
        and not isinstance(button.parentWidget(), QLineEdit)  # a field's clear button
        # Clickable rows and headings, which read as list rows rather than buttons.
        and button.property("role") not in ("statusRow", "sectionToggle")
    ]
    rects = {button: QRect(button.mapTo(window, QPoint()), button.size()) for button in buttons}
    crowded = []
    for a, b in combinations(buttons, 2):
        if a.isAncestorOf(b) or b.isAncestorOf(a):
            continue
        ra, rb = rects[a], rects[b]
        if min(ra.bottom(), rb.bottom()) >= max(ra.top(), rb.top()):  # one row
            gap = max(rb.left() - ra.right(), ra.left() - rb.right()) - 1
        elif min(ra.right(), rb.right()) >= max(ra.left(), rb.left()):  # one column
            gap = max(rb.top() - ra.bottom(), ra.top() - rb.bottom()) - 1
        else:
            continue
        track = a.parentWidget()
        segments = track is b.parentWidget() and track.property("role") == "segmented"
        need = SEGMENT_GAP if segments else BUTTON_GAP
        if gap < need:
            crowded.append(f"{a.text() or a.accessibleName() or a.objectName()!r} and "
                           f"{b.text() or b.accessibleName() or b.objectName()!r}: {gap}px")
    return crowded


@pytest.fixture
def styled(qapp):
    before = qapp.styleSheet()
    apply_app_stylesheet(qapp)
    yield
    qapp.setStyleSheet(before)


def _shown(widget: QWidget, width: int = 1400, height: int = 900) -> QWidget:
    widget.resize(width, height)
    widget.show()
    for _ in range(5):
        QApplication.processEvents()
    return widget


@pytest.mark.parametrize("mode", [AnalysisMode.LABELLED, AnalysisMode.UNLABELLED])
def test_main_window_buttons_keep_their_gaps(qapp, styled, monkeypatch, mode):
    window = _make_window(monkeypatch, mode)
    monkeypatch.setattr(window, "on_plot_button", lambda *_args: None)
    try:
        _shown(window)
        assert crowded_buttons(window) == []  # the start screen
        window.toolbar.update_compound_list(["Alanine", "Glycine"])
        window.toolbar.update_sample_list(["S1", "S2"])
        window.toolbar.update_label_colours(True, True)
        window.cdf_data_loaded = True
        window._refresh_shell()
        window.toolbar.samples_section.set_expanded(True)
        _shown(window)
        assert window.summary.isVisible() and window.graph_view.isVisible()
        assert window.toolbar.integration.apply_button.isVisible()
        assert crowded_buttons(window) == []
    finally:
        window.close()


def _dialogs(monkeypatch):
    from manic.ui.about_dialog import AboutDialog
    from manic.ui.add_compound_dialog import AddCompoundDialog
    from manic.ui.analysis_mode_dialog import AnalysisModeDialog
    from manic.ui.chart_popup_dialog import ChartPopupDialog
    from manic.ui.compound_recovery_dialog import CompoundRecoveryDialog
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog
    from manic.ui.export_options_dialog import ExportOptionsDialog
    from manic.ui.post_load_checklist_dialog import PostLoadChecklistDialog
    from manic.ui.sample_recovery_dialog import SampleRecoveryDialog
    from manic.ui.update_old_data_dialog import UpdateOldDataDialog

    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    return {
        "about": lambda: AboutDialog(),
        "add compound": lambda: AddCompoundDialog(analysis_mode=AnalysisMode.LABELLED),
        "analysis mode": lambda: AnalysisModeDialog(),
        "chart popup": lambda: ChartPopupDialog(
            "total_abundance", "Total Abundance", np.array([1.0, 2.0]), ["S1", "S2"]
        ),
        "compound recovery": lambda: CompoundRecoveryDialog(),
        "sample recovery": lambda: SampleRecoveryDialog(),
        "detailed view": lambda: DetailedPlotDialog("Alanine", "S1", samples=["S1", "S2"]),
        "export options": lambda: ExportOptionsDialog(False, offer_carbon_enrichment=True),
        "checklist": lambda: PostLoadChecklistDialog(
            ["Alanine"], None, [MmFileStatus("Alanine", None, ())], None
        ),
        "process external data": lambda: UpdateOldDataDialog(),
    }


@pytest.mark.parametrize(
    "name",
    [
        "about",
        "add compound",
        "analysis mode",
        "chart popup",
        "compound recovery",
        "sample recovery",
        "detailed view",
        "export options",
        "checklist",
        "process external data",
    ],
)
def test_dialog_buttons_keep_their_gaps(qapp, styled, monkeypatch, name):
    dialog = _dialogs(monkeypatch)[name]()
    try:
        _shown(dialog, *dialog.sizeHint().expandedTo(dialog.minimumSize()).toTuple())
        assert crowded_buttons(dialog) == []
    finally:
        dialog.close()
        dialog.deleteLater()


def test_settings_buttons_keep_their_gaps_on_every_page(qapp, styled, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.UNLABELLED)
    try:
        window.open_settings_window()
        settings = window.settings_window
        _shown(settings, 900, 700)
        for row in range(settings.page_list.count()):
            settings.page_list.setCurrentRow(row)
            QApplication.processEvents()
            assert crowded_buttons(settings) == [], settings.page_list.item(row).text()
    finally:
        if window.settings_window is not None:
            window.settings_window.close()
        window.close()
