import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QWidget

from manic.ui.graphs import GraphView
from manic.validation.peak_verdict import PeakReview, PeakVerdict


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


class FakeChart:
    def __init__(self, sample: str, container: QWidget):
        self.sample_name = sample
        self.compound_name = "Cmp"
        self._container = container

    def parent(self) -> QWidget:
        return self._container


@pytest.fixture
def grid(qapp):
    view = GraphView()
    tiles = {}
    for sample in ("A", "B", "C"):
        container = QWidget()
        chart = FakeChart(sample, container)
        container.chart_view = chart
        tiles[sample] = (container, chart)
    view._current_plots = [chart for _, chart in tiles.values()]
    view.apply_peak_verdicts(
        {"A": PeakVerdict.FAIL, "B": PeakVerdict.REJECTED, "C": PeakVerdict.PASS}
    )
    emitted = []
    view.peak_review_changed.connect(lambda c, s, r: emitted.append((c, s, r)))
    return view, tiles, emitted


def _actions(view: GraphView, chart: FakeChart):
    view._show_context_menu(QPoint(0, 0), chart)
    menu = view._active_context_menu
    return menu, {action.text(): action for action in menu.actions() if action.text()}


def test_apply_peak_verdicts_styles_tiles(grid):
    _view, tiles, _emitted = grid
    assert "rgba(255, 204, 204, 120)" in tiles["A"][0].styleSheet()
    assert "rgba(224, 201, 166, 120)" in tiles["B"][0].styleSheet()
    assert tiles["C"][0].styleSheet() == ""


def test_accept_enabled_only_on_failed_or_accepted_tiles(grid):
    view, tiles, _emitted = grid
    for sample, enabled in (("A", True), ("B", False), ("C", False)):
        menu, actions = _actions(view, tiles[sample][1])
        assert actions["Accept peak (below threshold)"].isEnabled() is enabled
        assert actions["Mark peak as bad"].isEnabled()
        menu.close()


def test_accept_emits_review_for_clicked_tile(grid):
    view, tiles, emitted = grid
    menu, actions = _actions(view, tiles["A"][1])
    actions["Accept peak (below threshold)"].trigger()
    menu.close()
    assert emitted == [("Cmp", ["A"], PeakReview.ACCEPTED)]


def test_toggling_checked_bad_clears_the_review(grid):
    view, tiles, emitted = grid
    menu, actions = _actions(view, tiles["B"][1])
    assert actions["Mark peak as bad"].isChecked()
    actions["Mark peak as bad"].trigger()
    menu.close()
    assert emitted == [("Cmp", ["B"], None)]


def test_action_applies_to_every_selected_tile(grid):
    view, tiles, emitted = grid
    view._selected_plots = {tiles["A"][1], tiles["C"][1]}
    menu, actions = _actions(view, tiles["A"][1])
    actions["Mark peak as bad"].trigger()
    menu.close()
    compound, samples, review = emitted[-1]
    assert compound == "Cmp"
    assert sorted(samples) == ["A", "C"]
    assert review is PeakReview.REJECTED


def test_group_accept_skips_passing_tiles(grid):
    view, tiles, emitted = grid
    view._selected_plots = {tiles["A"][1], tiles["B"][1], tiles["C"][1]}
    menu, actions = _actions(view, tiles["A"][1])
    actions["Accept peak (below threshold)"].trigger()
    menu.close()
    assert emitted == [("Cmp", ["A"], PeakReview.ACCEPTED)]
