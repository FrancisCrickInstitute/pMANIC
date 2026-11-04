from types import SimpleNamespace

import numpy as np
from PySide6.QtCharts import QValueAxis
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from manic.ui.isotopologue_ratio_widget import IsotopologueRatioWidget
from manic.ui.total_abundance_widget import TotalAbundanceWidget


def _abundance_chart(names, values) -> TotalAbundanceWidget:
    widget = TotalAbundanceWidget()
    widget.resize(260, 330)
    widget.show()
    eics = [SimpleNamespace(sample_name=name) for name in names]
    widget.update_abundance_from_data("Alanine", eics, np.asarray(values, dtype=float))
    for _ in range(5):
        QApplication.processEvents()
    return widget


def _sample_axis(widget):
    return widget.chart.axes(Qt.Vertical)[0]


def test_abundance_marks_the_selected_samples_and_ticks_on_round_numbers(qapp):
    widget = _abundance_chart(["S1", "S2", "S3"], [1.2e6, 3.9e6, 2.5e6])
    try:
        widget.set_highlighted(["S3", "elsewhere"])
        assert widget.highlighted_bars() == ["S3"]
        axis = widget.chart.axes(Qt.Horizontal)[0]
        assert axis.tickType() == QValueAxis.TicksDynamic
        assert axis.tickInterval() == 2.0
        assert axis.labelFormat() == "%.0f"
        widget.set_highlighted([])
        assert widget.highlighted_bars() == []
    finally:
        widget.deleteLater()


def test_abundance_names_its_bars_when_they_fit_and_points_to_hover_when_not(qapp):
    few = _abundance_chart([f"S{i}" for i in range(6)], range(1, 7))
    many = _abundance_chart([f"S{i}" for i in range(30)], range(1, 31))
    try:
        assert _sample_axis(few).labelsVisible()
        assert not few.names_hint.isVisible()
        assert not _sample_axis(many).labelsVisible()
        assert many.names_hint.isVisible()
        assert many.names_hint.text() == "Hover or enlarge for sample names"
    finally:
        few.deleteLater()
        many.deleteLater()


def test_label_incorporation_marks_only_the_selected_rows(qapp):
    widget = IsotopologueRatioWidget()
    widget.resize(260, 330)
    widget.show()
    names = ["S3", "S2", "S1"]
    ratios = np.array([[0.5, 0.5], [0.9, 0.1], [0.2, 0.8]])
    widget._current_sample_names = names
    widget._current_ratios = ratios
    try:
        widget._update_chart(ratios, names)
        for _ in range(5):
            QApplication.processEvents()
        widget.set_highlighted(["S2"])
        assert widget.highlighted_bars() == ["S2"]
        widget.set_highlighted([])
        assert widget.highlighted_bars() == []
    finally:
        widget.deleteLater()
