from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from manic.ui.graphs import GraphView
from manic.ui.plot_tile import PlotTile
from manic.validation.peak_verdict import PeakReview, PeakVerdict
from manic.validation.unlabelled_identity import IdentityStatus


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
        container = PlotTile(QWidget())
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
    actions = {action.text(): action for action in menu.actions() if action.text()}
    for action in menu.actions():
        submenu = action.menu()
        if submenu is None:
            continue
        for child in submenu.actions():
            if child.text():
                actions[child.text()] = child
    return menu, actions


def _badge_texts(tile: PlotTile) -> list[str]:
    return [badge.text for badge in tile.badges()]


def test_apply_peak_verdicts_styles_tiles(grid):
    _view, tiles, _emitted = grid
    assert _badge_texts(tiles["A"][0]) == ["Below threshold"]
    assert tiles["A"][0].tint() == "warning_soft"
    assert _badge_texts(tiles["B"][0]) == ["Marked bad"]
    assert tiles["B"][0].tint() == "danger_soft"
    assert _badge_texts(tiles["C"][0]) == []
    assert tiles["C"][0].tint() is None


def test_accept_enabled_only_on_failed_or_accepted_tiles(grid):
    view, tiles, _emitted = grid
    for sample, enabled, reject in (
        ("A", True, "Mark Peak as Bad"),
        ("B", False, "Clear Bad Mark"),
        ("C", False, "Mark Peak as Bad"),
    ):
        menu, actions = _actions(view, tiles[sample][1])
        assert actions["Accept Peak (Below Threshold)"].isEnabled() is enabled
        assert actions[reject].isEnabled()
        menu.close()


def test_accept_emits_review_for_clicked_tile(grid):
    view, tiles, emitted = grid
    menu, actions = _actions(view, tiles["A"][1])
    actions["Accept Peak (Below Threshold)"].trigger()
    menu.close()
    assert emitted == [("Cmp", ["A"], PeakReview.ACCEPTED)]


def test_clear_bad_mark_clears_the_review(grid):
    view, tiles, emitted = grid
    menu, actions = _actions(view, tiles["B"][1])
    actions["Clear Bad Mark"].trigger()
    menu.close()
    assert emitted == [("Cmp", ["B"], None)]


def test_action_applies_to_every_selected_tile(grid):
    view, tiles, emitted = grid
    view._selected_plots = {tiles["A"][1], tiles["C"][1]}
    menu, actions = _actions(view, tiles["A"][1])
    actions["Mark 2 Peaks as Bad"].trigger()
    menu.close()
    compound, samples, review = emitted[-1]
    assert compound == "Cmp"
    assert sorted(samples) == ["A", "C"]
    assert review is PeakReview.REJECTED


def test_not_detected_tile_is_flat_grey_until_reviewed(grid, monkeypatch):
    view, tiles, _emitted = grid
    monkeypatch.setattr(
        view,
        "_sample_identity",
        lambda _name: SimpleNamespace(
            qc=SimpleNamespace(status=IdentityStatus.NOT_DETECTED, reasons=())
        ),
    )
    view.apply_peak_verdicts({"C": PeakVerdict.PASS})
    assert _badge_texts(tiles["C"][0]) == ["Not detected"]
    assert tiles["C"][0].tint() == "surface_hover"

    view.apply_peak_verdicts({"C": PeakVerdict.REJECTED})
    assert _badge_texts(tiles["C"][0]) == ["Marked bad", "Not detected"]
    assert tiles["C"][0].tint() == "danger_soft"


def test_group_accept_skips_passing_tiles(grid):
    view, tiles, emitted = grid
    view._selected_plots = {tiles["A"][1], tiles["B"][1], tiles["C"][1]}
    menu, actions = _actions(view, tiles["A"][1])
    actions["Accept Peak (Below Threshold)"].trigger()
    menu.close()
    assert emitted == [("Cmp", ["A"], PeakReview.ACCEPTED)]


def test_curve_fit_menu_emits_override_for_selected_tiles(grid):
    view, tiles, _emitted = grid
    fits = []
    view.sample_fit_type_changed.connect(lambda c, s, f: fits.append((c, s, f)))
    view._selected_plots = {tiles["A"][1], tiles["C"][1]}
    menu, actions = _actions(view, tiles["A"][1])
    assert actions["Use Compound Setting"].isChecked()
    assert actions["Gaussian"].isChecked() is False
    actions["Gaussian"].trigger()
    menu.close()
    compound, samples, fit_type = fits[-1]
    assert compound == "Cmp"
    assert sorted(samples) == ["A", "C"]
    assert fit_type == "gaussian"


def test_show_only_selected_disabled_when_nothing_selected(grid):
    view, tiles, _emitted = grid
    view._selected_plots = set()
    menu, actions = _actions(view, tiles["A"][1])
    assert actions["Show Only Selected Samples"].isEnabled() is False
    assert actions["Show All Samples"].isEnabled() is True
    menu.close()


def test_show_only_selected_uses_clicked_tile_when_not_in_selection(grid):
    view, tiles, _emitted = grid
    view._selected_plots = {tiles["A"][1]}
    focused: list[list[str]] = []
    view.focus_selected_requested.connect(focused.append)
    menu, actions = _actions(view, tiles["B"][1])
    actions["Show Only This Sample"].trigger()
    menu.close()
    assert focused == [["B"]]


def test_show_all_samples_menu_emits_request(grid):
    view, tiles, _emitted = grid
    shown: list[str] = []
    view.show_all_samples_requested.connect(lambda: shown.append("all"))
    menu, actions = _actions(view, tiles["A"][1])
    actions["Show All Samples"].trigger()
    menu.close()
    assert shown == ["all"]


def test_curve_fit_menu_checks_common_override(grid):
    view, tiles, _emitted = grid
    view._sample_fit_types = {("Cmp", "A"): "emg", ("Cmp", "B"): "emg"}
    view._selected_plots = {tiles["A"][1], tiles["B"][1]}
    menu, actions = _actions(view, tiles["A"][1])
    assert actions["EMG"].isChecked()
    assert actions["Use Compound Setting"].isChecked() is False
    menu.close()
