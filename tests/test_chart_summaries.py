from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QTextDocumentFragment
from PySide6.QtWidgets import (
    QApplication,
    QToolTip,
)

from manic.ui.isotopologue_ratio_widget import IsotopologueRatioWidget
from manic.ui.total_abundance_widget import TotalAbundanceWidget

NAMES = [f"Bio_{i:03d}" for i in range(30)]


@pytest.fixture(autouse=True)
def integration(monkeypatch):
    """Integrating an EIC gives the sums of its intensity rows, one per isotopologue."""
    module = "manic.ui.isotopologue_ratio_widget"
    monkeypatch.setattr(f"{module}.read_compound_with_session", lambda _compound, _sample: None)
    monkeypatch.setattr(
        f"{module}.integrated_display_areas",
        lambda _time, intensity, _compound, use_corrected: list(intensity.sum(axis=1)),
    )


def _eics(names, areas=None):
    if areas is None:
        areas = [[0.6, 0.3, 0.1]] * len(names)
    return [
        SimpleNamespace(
            sample_name=name, time=np.zeros(1), intensity=np.asarray(area, dtype=float)[:, None]
        )
        for name, area in zip(names, areas)
    ]


def _ratios(names, areas=None):
    widget = IsotopologueRatioWidget()
    widget.update_ratios("Alanine", _eics(names, areas))
    return widget


def _abundance(names, values=None):
    widget = TotalAbundanceWidget()
    if values is None:
        values = np.arange(1, len(names) + 1, dtype=float) * 1e6
    widget.update_abundance_from_data("Alanine", _eics(names), np.asarray(values, dtype=float))
    return widget


def _shown(widget, height=330):
    widget.resize(264, height)
    widget.show()
    for _ in range(10):
        QApplication.processEvents()
    return widget


def _mouse(widget, name, kind=QEvent.MouseMove, button=Qt.LeftButton) -> None:
    """A mouse event halfway along a sample's first bar segment (its row's start if empty)."""
    series = widget.chart.series()[0]
    index = list(widget.chart.axes(Qt.Vertical)[0].categories()).index(name)
    point = widget.chart.mapToPosition(QPointF(series.barSets()[0].at(index) / 2, index), series)
    pos = QPointF(widget.chart_view.mapFromScene(widget.chart.mapToScene(point)))
    viewport = widget.chart_view.viewport()
    button = Qt.NoButton if kind == QEvent.MouseMove else button
    QApplication.sendEvent(
        viewport,
        QMouseEvent(kind, pos, viewport.mapToGlobal(pos), button, button, Qt.NoModifier),
    )


def _hover(widget, name, monkeypatch) -> list[str]:
    """Move the mouse onto a sample's bar; the tooltips that shows."""
    shown = []
    monkeypatch.setattr(QToolTip, "showText", lambda _pos, text, *_args: shown.append(text))
    _mouse(widget, name)
    return shown


def test_mini_charts_pair_each_sample_with_its_own_values(qapp, monkeypatch):
    names = ["S1", "S2", "S3"]
    areas = [[90.0, 10.0, 0.0], [1000.0, 600.0, 400.0], [6000.0, 6000.0, 18000.0]]
    ratio_chart = IsotopologueRatioWidget()
    abundance_chart = TotalAbundanceWidget()
    try:
        eics = _eics(names, areas)
        ratio_chart.update_ratios("Cmp", eics)
        abundances, shared = ratio_chart.get_last_total_abundances()
        abundance_chart.update_abundance_from_data("Cmp", shared, abundances)
        _shown(ratio_chart, 300)
        _shown(abundance_chart, 300)

        assert _hover(ratio_chart, "S1", monkeypatch)[-1] == "S1\nM+0  90.0%\nM+1  10.0%\nM+2  0.0%"
        assert _hover(abundance_chart, "S1", monkeypatch)[-1] == "S1\nPeak area  100"
        assert _hover(abundance_chart, "S3", monkeypatch)[-1] == "S3\nPeak area  3e+04"
        assert [e.sample_name for e in eics] == names

        assert ratio_chart.key.isVisible()
        key = QTextDocumentFragment.fromHtml(ratio_chart.key.text()).toPlainText()
        assert key.replace("\xa0", " ") == "■ M+0   ■ M+1   ■ M+2"
    finally:
        ratio_chart.deleteLater()
        abundance_chart.deleteLater()


@pytest.mark.parametrize("make", [_abundance, _ratios])
def test_a_click_on_a_summary_row_selects_its_sample_and_a_double_click_only_enlarges(
    qapp, make, monkeypatch
):
    from PySide6.QtTest import QTest

    from manic.ui.chart_popup_dialog import ChartPopupDialog

    names = ["S1", "S2", "S3"]
    widget = make(names)
    if make is _abundance:
        widget.update_abundance_from_data("Alanine", _eics(names), np.asarray([3e6, 0.0, 1e6]))
    _shown(widget, 300)
    activated, enlarged = [], []
    widget.sample_activated.connect(activated.append)
    monkeypatch.setattr(ChartPopupDialog, "exec", lambda self: enlarged.append(True) or 0)
    monkeypatch.setattr("manic.ui.total_abundance_widget.peak_area_label", lambda _c: "Peak area")
    click = (QEvent.MouseButtonPress, QEvent.MouseButtonRelease)
    try:
        for name in ("S3", "S2"):
            for kind in click:
                _mouse(widget, name, kind)
            QTest.qWait(QApplication.doubleClickInterval() + 100)
        assert activated == ["S3", "S2"]
        # What Qt delivers for a double-click.
        for kind in click + (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick) + click[1:]:
            _mouse(widget, "S1", kind)
        QTest.qWait(QApplication.doubleClickInterval() + 100)
        assert enlarged == [True] and activated == ["S3", "S2"]
    finally:
        widget.deleteLater()


def test_a_click_waiting_for_a_double_click_is_dropped_when_the_rows_change(qapp):
    from PySide6.QtTest import QTest

    widget = _abundance(["S1", "S2", "S3"])
    widget.update_abundance_from_data("Alanine", _eics(["S1", "S2", "S3"]), np.asarray([3e6, 2e6, 1e6]))
    _shown(widget, 300)
    activated = []
    widget.sample_activated.connect(activated.append)
    try:
        for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            _mouse(widget, "S3", kind)
        widget.update_abundance_from_data("Lactate", _eics(["T1"]), np.asarray([5e5]))
        QTest.qWait(QApplication.doubleClickInterval() + 100)
        assert activated == []
    finally:
        widget.deleteLater()


