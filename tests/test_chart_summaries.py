from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QFontMetrics, QMouseEvent, QTextDocumentFragment
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from manic.models.analysis import AnalysisMode
from manic.ui import theme
from manic.ui.chart_style import AXIS_LABEL_PX, CAPTION_PX
from manic.ui.isotopologue_ratio_widget import IsotopologueRatioWidget
from manic.ui.summary_panel import SummaryPanel
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


def _category(widget, point) -> str:
    value = widget.chart.mapToValue(point, widget.chart.series()[0])
    return widget.chart.axes(Qt.Vertical)[0].categories()[round(value.y())]


def _selected(widget) -> list[str]:
    """Samples whose bars carry the selection mark, top to bottom."""
    if isinstance(widget, TotalAbundanceWidget):
        bars = widget.chart.series()[0].barSets()[0]
        names = widget.chart.axes(Qt.Vertical)[0].categories()
        return [names[i] for i in sorted(bars.selectedBars(), reverse=True)]
    ticks = [
        item for item in widget.chart.childItems()
        if isinstance(item, QGraphicsRectItem) and item.brush().color() == theme.color("accent")
    ]
    ticks.sort(key=lambda item: item.rect().top())
    return [_category(widget, item.rect().center()) for item in ticks]


def _rows_in_view(widget) -> list[str]:
    series = widget.chart.series()[0]
    top = widget.chart_area.verticalScrollBar().value()
    bottom = top + widget.chart_area.viewport().height()
    return [
        name
        for i, name in enumerate(widget.chart.axes(Qt.Vertical)[0].categories())
        if top <= widget.chart.mapToPosition(QPointF(0, i), series).y() <= bottom
    ]


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


@pytest.mark.parametrize(
    "values, multiplier, ticks",
    [
        ([1.2e6, 3.9e6, 2.5e6], "×10⁶", ["0", "2", "4"]),
        ([1.2e-3, 0.4e-3, 0.9e-3], "×10⁻³", ["0.0", "0.5", "1.0"]),
        ([2.5, 1.0, 2.0], "", ["0", "1", "2"]),
    ],
)
def test_abundance_marks_the_selected_samples_and_ticks_on_round_numbers(qapp, values, multiplier, ticks):
    widget = _shown(_abundance(["S1", "S2", "S3"], values))
    try:
        assert widget.header.detail.text() == multiplier
        assert [text for text, _x in widget.value_axis.tick_positions()] == ticks
        widget.set_highlighted(["S3", "elsewhere"])
        assert _selected(widget) == ["S3"]
        widget.set_highlighted([])
        assert _selected(widget) == []
    finally:
        widget.deleteLater()


def test_the_enlarged_abundance_chart_keeps_the_grid_selection(qapp, monkeypatch):
    from manic.io.compounds_import import CompoundRow, insert_compound
    from manic.ui.chart_popup_dialog import ChartPopupDialog

    insert_compound(CompoundRow(
        compound_name="Alanine", retention_time=6.1, mass0=116.0, loffset=0.1, roffset=0.1,
        label_atoms=2, formula="C3H7NO2", label_type="C", tbdms=1, meox=0, me=0,
    ))
    opened = []
    monkeypatch.setattr(ChartPopupDialog, "exec", lambda dialog: opened.append(dialog))
    widget = _shown(_abundance(["S1", "S2", "S3"]))
    try:
        widget.set_highlighted(["S2"])
        widget._show_popup_chart()
        bars = opened[0].chart.series()[0].barSets()[0]
        names = opened[0].chart.axes(Qt.Vertical)[0].categories()
        assert [names[i] for i in bars.selectedBars()] == ["S2"]
        assert bars.selectedColor() == theme.color("accent")
        assert bars.color() == widget.chart.series()[0].barSets()[0].color() == theme.color("text_tertiary")
    finally:
        widget.deleteLater()
        for dialog in opened:
            dialog.deleteLater()


@pytest.mark.parametrize("count, height, scrolls", [(30, 330, True), (30, 720, False), (3, 330, False)])
@pytest.mark.parametrize("make", [_abundance, _ratios])
def test_thirty_samples_are_named_on_readable_rows_that_scroll(qapp, make, count, height, scrolls):
    names = NAMES[:count]
    widget = _shown(make(names), height)
    try:
        axis = widget.chart.axes(Qt.Vertical)[0]
        assert axis.labelsVisible()
        assert list(axis.categories())[::-1] == names
        # Each row is at least as tall as the name it carries.
        row = widget.chart.plotArea().height() / count
        assert row >= QFontMetrics(axis.labelsFont()).height()
        assert (widget.chart_area.verticalScrollBar().maximum() > 0) is scrolls
        # Roomy rows carry larger names, up to the plot caption size; 30 rows on a
        # 27" monitor's panel (about 20 px each) read at 12 px.
        px = axis.labelsFont().pixelSize()
        assert px == AXIS_LABEL_PX if scrolls else AXIS_LABEL_PX + 2 <= px <= CAPTION_PX
    finally:
        widget.deleteLater()


def test_a_short_cohort_keeps_each_summary_together_with_the_room_below(qapp):
    panel = SummaryPanel(AnalysisMode.LABELLED)
    ratios, abundance = panel.isotopologue_ratios, panel.total_abundance
    ratios.update_ratios("Alanine", _eics(NAMES[:2]))
    abundance.update_abundance_from_data("Alanine", _eics(NAMES[:2]), np.array([1e6, 2e6]))
    try:
        _shown(panel, 1300)
        assert ratios.key.isVisible()
        # Heading, key, axis and rows touch; the spare height sits under both charts.
        assert ratios.value_axis.y() - ratios.key.geometry().bottom() <= 2
        assert abundance.geometry().bottom() < panel.height() / 2
    finally:
        panel.deleteLater()


@pytest.mark.parametrize("make", [_abundance, _ratios])
def test_selecting_a_sample_scrolls_its_row_into_view(qapp, make):
    widget = _shown(make(NAMES))
    try:
        widget.chart_area.verticalScrollBar().setValue(0)
        assert "Bio_029" not in _rows_in_view(widget)
        widget.set_highlighted(["Bio_029"])
        assert _selected(widget) == ["Bio_029"]
        assert "Bio_029" in _rows_in_view(widget)
        widget.set_highlighted(["Bio_000"])
        assert "Bio_000" in _rows_in_view(widget)
        assert "Bio_029" not in _rows_in_view(widget)
        widget.set_highlighted([])
        assert _selected(widget) == []
    finally:
        widget.deleteLater()


@pytest.mark.parametrize(
    "make, ticks",
    [(_abundance, ["0", "1", "2", "3"]), (_ratios, ["0.0", "0.5", "1.0"])],
)
def test_value_axis_stays_in_view_while_rows_scroll(qapp, make, ticks):
    widget = _shown(make(NAMES), 300)
    try:
        bar = widget.chart_area.verticalScrollBar()
        assert bar.maximum() > 0
        before = widget.value_axis.tick_positions()
        assert [text for text, _x in before] == ticks and widget.value_axis.isVisible()
        bar.setValue(bar.maximum())
        for _ in range(10):
            QApplication.processEvents()
        # Pinned outside the scroll area, so still on screen and at the same x.
        assert widget.value_axis.isVisible()
        assert widget.value_axis.geometry().bottom() < widget.chart_area.geometry().top()
        assert widget.value_axis.tick_positions() == before
    finally:
        widget.deleteLater()


def test_two_summaries_share_a_short_sidebar_without_an_outer_scroll(qapp):
    host = QWidget()
    layout = QVBoxLayout(host)
    charts = [_ratios(NAMES), _abundance(NAMES)]
    for chart in charts:
        layout.addWidget(chart, 1)
    try:
        _shown(host, 360)
        for chart in charts:
            assert chart.geometry().bottom() < 360
            assert len(_rows_in_view(chart)) >= 2
    finally:
        host.deleteLater()


def test_selection_leaves_other_bars_their_cohort_colours(qapp):
    widget = _shown(_ratios(NAMES[:5]), 300)
    try:
        bar_sets = widget.chart.series()[0].barSets()
        colours = [bar_set.color().name() for bar_set in bar_sets]
        widget.set_highlighted(["Bio_002"])
        assert _selected(widget) == ["Bio_002"]
        assert [bar_set.color().name() for bar_set in bar_sets] == colours
        assert all(bar_set.count() == 5 for bar_set in bar_sets)
        widget.set_highlighted([])
        assert _selected(widget) == []
    finally:
        widget.deleteLater()


def test_a_sample_with_no_ratio_shows_a_dash_and_explains_on_hover(qapp, monkeypatch):
    names = ["Bio_001", "Bio_018", "Bio_020"]
    widget = _shown(_ratios(names, [[6.0, 3.0, 1.0], [0.0, 0.0, 0.0], [5.0, 5.0, 0.0]]), 300)
    try:
        dashes = [
            item for item in widget.chart.childItems()
            if isinstance(item, QGraphicsSimpleTextItem) and item.isVisible()
        ]
        assert [dash.text() for dash in dashes] == ["—"]
        dash = dashes[0]
        assert _category(widget, dash.pos() + dash.boundingRect().center()) == "Bio_018"
        assert _hover(widget, "Bio_018", monkeypatch)[-1] == (
            "Bio_018\nNo ratio: this sample has no integrated peak area for this compound."
        )
    finally:
        widget.deleteLater()


def _row_notes(widget) -> dict[str, str]:
    """Each row note's sample and text."""
    return {
        _category(widget, item.pos() + item.boundingRect().center()): item.text()
        for item in widget.chart.childItems()
        if isinstance(item, QGraphicsSimpleTextItem) and item.isVisible()
    }


def test_a_peak_area_too_small_to_draw_reads_as_its_popup_value(qapp, monkeypatch):
    names = ["S1", "S2", "S3", "S4"]
    widget = _shown(_abundance(names, [2e6, 0.0, float("nan"), 2e3]), 300)
    try:
        assert _row_notes(widget) == {"S2": "0", "S3": "—", "S4": "<0.01"}
        # Hover answers by row, so an empty or tiny bar names its sample like the rest.
        assert _hover(widget, "S2", monkeypatch)[-1] == "S2\nPeak area  0"
        assert _hover(widget, "S3", monkeypatch)[-1] == "S3\nPeak area  —"
        assert _hover(widget, "S4", monkeypatch)[-1] == "S4\nPeak area  2e+03"
    finally:
        widget.deleteLater()


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


@pytest.mark.parametrize("button", [Qt.LeftButton, Qt.RightButton], ids=["left", "right"])
def test_the_first_click_after_a_double_click_selects(qapp, monkeypatch, button):
    # A modal popup opened by the double-click takes its trailing release, and a right
    # double-click ends with a right release; either way the next left click must select.
    from PySide6.QtTest import QTest

    from manic.ui.chart_popup_dialog import ChartPopupDialog

    names = ["S1", "S2", "S3"]
    widget = _abundance(names)
    widget.update_abundance_from_data("Alanine", _eics(names), np.asarray([3e6, 2e6, 1e6]))
    _shown(widget, 300)
    activated = []
    widget.sample_activated.connect(activated.append)
    monkeypatch.setattr(ChartPopupDialog, "exec", lambda self: 0)
    try:
        for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseButtonPress,
                     QEvent.MouseButtonDblClick):
            _mouse(widget, "S1", kind, button)
        if button == Qt.RightButton:
            _mouse(widget, "S1", QEvent.MouseButtonRelease, button)
        for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            _mouse(widget, "S2", kind)
        QTest.qWait(QApplication.doubleClickInterval() + 100)
        assert activated == ["S2"]
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


@pytest.mark.parametrize("make", [_abundance, _ratios])
def test_rebuilding_a_summary_keeps_its_name_size_and_shortening(qapp, make):
    # The grid's selection rebuilds the chart with an unchanged plot area.
    names = [f"Sample_{i:02d}_ratio_fail_overlap" for i in range(8)]
    widget = _shown(make(names), 400)
    try:
        axis = widget.chart.axes(Qt.Vertical)[0]
        before = axis.labelsFont().pixelSize(), axis.categories()
        assert all("…" in name for name in before[1])
        if make is _abundance:
            widget.update_abundance_from_data(
                "Alanine", _eics(names), np.arange(1, 9, dtype=float) * 1e6
            )
        else:
            widget.update_ratios("Alanine", _eics(names))
        for _ in range(5):
            QApplication.processEvents()
        axis = widget.chart.axes(Qt.Vertical)[0]
        assert (axis.labelsFont().pixelSize(), axis.categories()) == before
    finally:
        widget.deleteLater()


@pytest.mark.parametrize("make", [_ratios, _abundance])
def test_a_summary_hover_tooltip_has_its_own_opaque_background(qapp, make):
    # The chart view's own transparent style must not leak into the tooltip it shows.
    from PySide6.QtGui import QCursor
    from PySide6.QtWidgets import QToolTip, QWidget

    widget = make(["S1", "S2"])
    try:
        _shown(widget)
        _mouse(widget, "S1")
        qapp.processEvents()
        chart_tip = _tip_background()
        QToolTip.hideText()
        plain = QWidget()
        QToolTip.showText(QCursor.pos(), "S1", plain)
        qapp.processEvents()
        assert chart_tip == _tip_background()
        assert chart_tip.alpha() > 0
    finally:
        QToolTip.hideText()
        widget.deleteLater()


def _tip_background():
    from PySide6.QtWidgets import QApplication

    [tip] = [
        w for w in QApplication.topLevelWidgets()
        if w.objectName() == "qtooltip_label" and w.isVisible()
    ]
    return tip.palette().color(tip.backgroundRole())


def test_a_plot_click_highlights_its_sample_in_the_summary_without_rebuilding_it(
    qapp, monkeypatch
):
    from PySide6.QtTest import QTest

    from conftest import _make_window
    from manic.io.compound_reader import Compound
    from manic.models import database

    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES ('Cmp', 1.0, 0.1, 0.1, 217.0, 2)"
        )
    reads = []

    def eics(compound, samples, **_kwargs):
        time = np.linspace(0.8, 1.2, 81)
        return [
            SimpleNamespace(
                sample_name=s, compound_name=compound, time=time,
                intensity=np.vstack([np.ones(81) * (i + 1), np.ones(81), np.ones(81)]),
            )
            for i, s in enumerate(samples)
        ]

    compound = Compound(
        compound_name="Cmp", retention_time=1.0, loffset=0.1, roffset=0.1, mass0=217.0, label_atoms=2
    )
    monkeypatch.setattr("manic.ui.graphs.get_eics_for_compound", eics)
    monkeypatch.setattr("manic.ui.graphs.read_compound_with_session", lambda *_a: compound)
    # What the Summary reads its areas from.
    monkeypatch.setattr(
        "manic.processors.eic_processing.get_eics_for_compound",
        lambda compound, samples, **kwargs: reads.append(samples) or eics(compound, samples),
    )
    monkeypatch.setattr("manic.ui.integration_window_widget.get_eics_for_compound", eics)
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        window.resize(2400, 1300)
        window.compound_data_loaded = window.cdf_data_loaded = True
        window.toolbar.update_label_colours(True, True)
        window.toolbar.update_compound_list(["Cmp"])
        window.toolbar.update_sample_list(["S1", "S2", "S3"])
        window._refresh_shell()
        window.show()
        window.show_summary_action.setChecked(True)
        charts = (window.summary.total_abundance, window.summary.isotopologue_ratios)
        reads.clear()
        plot = next(p for p in window.graph_view._current_plots if p.sample_name == "S2")
        QTest.mouseClick(plot.viewport(), Qt.LeftButton)
        QTest.qWait(50)
        assert [_selected(chart) for chart in charts] == [["S2"], ["S2"]]
        assert reads == []
    finally:
        window.close()
