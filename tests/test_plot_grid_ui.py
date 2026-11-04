import pytest
from PySide6.QtCharts import QChart
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from manic.ui.chart_style import nice_step, scale_text
from manic.ui.graphs import ClickableChartView, GraphView
from manic.ui.plot_tile import PlotTile, grid_columns


def test_grid_keeps_every_tile_on_screen_when_they_fit():
    assert grid_columns(30, 1284, 900, min_width=190, min_height=135) == (5, 0)


def test_grid_scrolls_with_readable_tiles_when_they_do_not_fit():
    assert grid_columns(30, 970, 700, min_width=190, min_height=135) == (4, 163)


def test_grid_with_no_tiles_is_one_column():
    assert grid_columns(0, 800, 600, min_width=190, min_height=135) == (1, 0)


def test_nice_ticks_and_scale_text():
    assert nice_step(0.39, 2.5) == pytest.approx(0.1)
    assert nice_step(1.44, 2) == pytest.approx(0.5)
    assert scale_text(6) == "×10⁶"
    assert scale_text(-3) == "×10⁻³"
    assert scale_text(0) == ""


@pytest.fixture
def grid(qapp):
    view = GraphView()
    tiles = [PlotTile(ClickableChartView(QChart(), name, "Cmp")) for name in "ABCD"]
    view._current_plots = [tile.chart_view for tile in tiles]
    view._grid_shape = (2, 0)
    emitted = []
    view.selection_changed.connect(lambda names: emitted.append(sorted(names)))
    yield view, emitted
    for tile in tiles:
        tile.deleteLater()
    view.deleteLater()


def test_select_all_and_escape(grid):
    view, emitted = grid
    QTest.keyClick(view, Qt.Key_A, Qt.ControlModifier)
    assert emitted[-1] == ["A", "B", "C", "D"]
    QTest.keyClick(view, Qt.Key_Escape)
    assert emitted[-1] == []


def test_arrows_move_focus_and_space_toggles(grid):
    view, emitted = grid
    QTest.keyClick(view, Qt.Key_Right)  # first arrow focuses the first tile
    QTest.keyClick(view, Qt.Key_Down)
    QTest.keyClick(view, Qt.Key_Right)
    QTest.keyClick(view, Qt.Key_Space)
    assert emitted[-1] == ["D"]
    QTest.keyClick(view, Qt.Key_Up)
    QTest.keyClick(view, Qt.Key_Space)
    assert emitted[-1] == ["B", "D"]
    QTest.keyClick(view, Qt.Key_Space)
    assert emitted[-1] == ["D"]


def test_enter_and_double_click_open_detailed_view(grid, monkeypatch):
    view, _emitted = grid
    opened = []
    monkeypatch.setattr(view, "_show_detailed_view", lambda c, s: opened.append((c, s)))
    QTest.keyClick(view, Qt.Key_Right)
    QTest.keyClick(view, Qt.Key_Right)
    QTest.keyClick(view, Qt.Key_Return)
    assert opened == [("Cmp", "B")]


def test_double_click_opens_once_without_a_second_toggle(qapp):
    plot = ClickableChartView(QChart(), "A", "Cmp")
    plot.resize(200, 150)
    clicks, opens = [], []
    plot.clicked.connect(lambda _view: clicks.append(True))
    plot.double_clicked.connect(lambda view: opens.append(view.sample_name))
    QTest.mouseDClick(plot.viewport(), Qt.LeftButton)
    assert opens == ["A"]
    assert len(clicks) <= 1
    plot.deleteLater()
