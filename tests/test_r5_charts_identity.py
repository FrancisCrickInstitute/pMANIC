from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from manic.io.compound_reader import Compound
from manic.models.analysis import IonChannel, IonRole
from manic.ui.chart_popup_dialog import ChartPopupDialog
from manic.ui.graphs import GraphView
from manic.ui.identity_chart import identity_chart_height
from manic.ui.targeted_qc_widget import SIDEBAR_ROW, TargetedQcWidget
from manic.validation.unlabelled_identity import (
    IdentityAssessmentSet,
    IdentityQcResult,
    IdentitySampleAssessment,
    IdentityStatus,
    QualifierRatioResult,
    qualifier_pair,
)

Q_ION = IonChannel(217.0, IonRole.QUANTIFIER)
V1 = IonChannel(147.0, IonRole.QUALIFIER, ordinal=1, expected_ratio=0.4, ratio_tolerance=0.25)


def _qc(status: IdentityStatus, ratio: float | None, passed: bool | None) -> IdentityQcResult:
    return IdentityQcResult(
        status=status,
        quantifier_area=100.0,
        observed_rt=7.09,
        rt_error=0.0,
        rt_passed=True,
        qualifier_ratios=(QualifierRatioResult(V1, ratio, passed),),
        reasons=(),
    )


def _identity(*rows) -> IdentityAssessmentSet:
    """rows: (sample, qc) pairs, top to bottom."""
    samples = tuple(
        IdentitySampleAssessment(name, qc, qualifier_pair((Q_ION, V1), qc, error=None), None)
        for name, qc in rows
    )
    return IdentityAssessmentSet("Pyruvate", (Q_ION, V1), samples)


MIXED = (
    ("S1", _qc(IdentityStatus.SUPPORTED, 0.41, True)),
    ("S2", _qc(IdentityStatus.REVIEW_REQUIRED, 0.9, False)),
)


def _marks(chart) -> list[tuple[str, bool]]:
    from manic.ui.identity_chart import _CellMark

    return sorted(
        (item.text(), item.isVisible())
        for item in chart.childItems()
        if isinstance(item, _CellMark) and item.cell[1] is not None
    )


def test_every_identity_cell_carries_a_visible_state_mark(qapp):
    dialog = ChartPopupDialog.for_identity(_identity(*MIXED))
    try:
        dialog.show()
        qapp.processEvents()
        # Qualifier 1 validated or failed; qualifier 2 is absent (grey) in both.
        assert _marks(dialog.chart) == [("–", True), ("–", True), ("✓", True), ("✕", True)]
        key = dialog.status_legend.text()
        assert "No verdict&nbsp;<b>2</b> (–&nbsp;2&nbsp;absent)" in key
        assert "✓&nbsp;Validated" in key and "✕&nbsp;Failed" in key
    finally:
        dialog.deleteLater()


def test_rebuilding_the_grid_replaces_its_marks(qapp):
    widget = TargetedQcWidget()
    try:
        widget.update_results(_identity(*MIXED))
        widget.update_results(_identity(MIXED[0]))
        assert [text for text, _shown in _marks(widget.chart)] == ["–", "✓"]
        widget.clear()
        assert _marks(widget.chart) == []
    finally:
        widget.deleteLater()


def test_one_sample_is_a_slim_strip_not_a_slab(qapp):
    identity = _identity(MIXED[0])
    widget = TargetedQcWidget()
    dialog = ChartPopupDialog.for_identity(identity)
    try:
        widget.update_results(identity)
        widget.resize(260, 330)
        widget.show()
        dialog.show()
        qapp.processEvents()
        assert widget.chart_view.height() == identity_chart_height(1, SIDEBAR_ROW) == 18
        assert dialog.chart_view.height() == identity_chart_height(1) == 24
        assert dialog.chart_view.y() == 0
        # The column headers sit above the scrolled rows, not inside them.
        for header, scroll in ((dialog.pinned_axis, dialog._scroll), (widget.columns, widget._scroll)):
            assert [text for text, _x in header.tick_positions()] == ["Qualifier 1", "Qualifier 2"]
            assert header.isVisible() and header.geometry().bottom() < scroll.geometry().top()
    finally:
        widget.deleteLater()
        dialog.deleteLater()


def _eic(sample: str):
    time = np.linspace(6.9, 7.3, 81)
    peak = np.exp(-0.5 * ((time - 7.09) / 0.02) ** 2)
    return SimpleNamespace(
        sample_name=sample, compound_name="Pyruvate", time=time, intensity=np.vstack([1e6 * peak])
    )


@pytest.fixture
def grid(qapp, monkeypatch):
    compound = Compound(
        compound_name="Pyruvate", retention_time=7.09, loffset=0.08, roffset=0.035,
        label_atoms=0, mass0=174.0, baseline_correction=0,
    )
    monkeypatch.setattr(
        "manic.ui.graphs.get_eics_for_compound",
        lambda _compound, samples, use_corrected=False: [_eic(s) for s in samples],
    )
    monkeypatch.setattr("manic.ui.graphs.read_compound_with_session", lambda _n, sample=None: compound)
    monkeypatch.setattr("manic.ui.graphs.get_sample_fit_types", lambda _name: {})
    view = GraphView()
    yield view
    view.deleteLater()


def test_not_detected_tile_is_tinted_throughout_and_its_traces_faded(grid):
    identity = _identity(
        ("Found", _qc(IdentityStatus.SUPPORTED, 0.41, True)),
        ("Missing", _qc(IdentityStatus.NOT_DETECTED, None, None)),
    )
    grid.plot_compound("Pyruvate", ["Found", "Missing"], identity=identity)
    tiles = {plot.sample_name: plot.parent() for plot in grid._current_plots}
    assert [badge.text for badge in tiles["Missing"].badges()] == ["Not detected"]
    assert tiles["Missing"].tint() == "surface_alt"
    for name, opacity in (("Found", 1.0), ("Missing", 0.4)):
        chart = tiles[name].chart_view.chart()
        assert not chart.isPlotAreaBackgroundVisible()
        assert {round(series.opacity(), 2) for series in chart.series()} == {opacity}


def test_identity_popup_row_selects_the_sample_through_the_qc_widget(qapp, monkeypatch):
    shown = []
    monkeypatch.setattr(ChartPopupDialog, "exec", lambda self: (shown.append(self), self.show()))
    widget = TargetedQcWidget()
    activated = []
    widget.sample_activated.connect(activated.append)
    try:
        widget.update_results(_identity(*MIXED))
        widget._show_popup_chart()
        dialog = shown[0]
        qapp.processEvents()
        assert dialog.row_names() == ["S1", "S2"]
        QTest.keyClick(dialog, Qt.Key_Up)
        QTest.keyClick(dialog, Qt.Key_Enter)
        assert activated == ["S2"]
        assert not dialog.isVisible()
    finally:
        widget.deleteLater()


def test_activated_sample_is_selected_focused_and_scrolled_to(grid, qapp):
    names = [f"S{i:02d}" for i in range(24)]
    grid.plot_compound("Pyruvate", names)
    grid.resize(600, 300)
    grid.show()
    qapp.processEvents()
    assert grid.select_sample("S23")
    qapp.processEvents()
    assert grid.get_selected_samples() == ["S23"]
    assert grid.review_lead().sample_name == "S23"
    tile = grid._current_plots[-1].parent()
    viewport = grid._scroll.viewport()
    top = tile.mapTo(viewport, tile.rect().topLeft()).y()
    assert 0 <= top and top + tile.height() <= viewport.height()
