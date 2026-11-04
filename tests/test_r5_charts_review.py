import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from manic.ui.graphs import GraphView
from manic.ui.plot_tile import PlotTile
from manic.validation.peak_verdict import PeakReview, PeakVerdict


class _FakeChart:
    def __init__(self, sample: str, container: QWidget):
        self.sample_name = sample
        self.compound_name = "Cmp"
        self._container = container

    def parent(self) -> QWidget:
        return self._container


@pytest.fixture
def mixed_grid(qapp):
    view = GraphView()
    charts = {}
    for sample in ("Pass", "Low1", "Low2"):
        tile = PlotTile(QWidget())
        tile.chart_view = charts[sample] = _FakeChart(sample, tile)
    view._current_plots = list(charts.values())
    view.apply_peak_verdicts(
        {"Pass": PeakVerdict.PASS, "Low1": PeakVerdict.FAIL, "Low2": PeakVerdict.FAIL}
    )
    yield view, charts
    view.deleteLater()


def _review_actions(view, lead):
    accept, reject = QAction("a"), QAction("r")
    view.update_review_actions(
        lead,
        inspect=QAction("i"),
        show_only=QAction("s"),
        accept=accept,
        reject=reject,
        fit_menu=QMenu(),
    )
    return accept, reject


def test_accept_reaches_eligible_peaks_when_the_lead_passes(mixed_grid):
    view, charts = mixed_grid
    view._selected_plots = set(charts.values())
    accept, _reject = _review_actions(view, charts["Pass"])
    assert accept.isEnabled()
    assert not accept.isChecked()
    assert accept.text() == "Accept 2 Peaks (Below Threshold)"

    emitted = []
    view.peak_review_changed.connect(lambda *args: emitted.append(args))
    view.toggle_peak_review(charts["Pass"], PeakReview.ACCEPTED)
    assert len(emitted) == 1
    compound, samples, review = emitted[0]
    assert (compound, sorted(samples), review) == ("Cmp", ["Low1", "Low2"], PeakReview.ACCEPTED)


def test_accept_shows_checked_and_clears_when_the_eligible_peaks_are_accepted(mixed_grid):
    view, charts = mixed_grid
    view.apply_peak_verdicts(
        {"Pass": PeakVerdict.PASS, "Low1": PeakVerdict.ACCEPTED, "Low2": PeakVerdict.ACCEPTED}
    )
    view._selected_plots = set(charts.values())
    accept, _reject = _review_actions(view, charts["Pass"])
    assert accept.isEnabled() and accept.isChecked()

    emitted = []
    view.peak_review_changed.connect(lambda *args: emitted.append(args))
    view.toggle_peak_review(charts["Pass"], PeakReview.ACCEPTED)
    assert sorted(emitted[0][1]) == ["Low1", "Low2"] and emitted[0][2] is None


def test_accept_stays_disabled_when_nothing_selected_is_below_threshold(mixed_grid):
    view, charts = mixed_grid
    view._selected_plots = {charts["Pass"]}
    accept, reject = _review_actions(view, charts["Pass"])
    assert not accept.isEnabled()
    assert reject.isEnabled() and reject.text() == "Mark Peak as Bad"
