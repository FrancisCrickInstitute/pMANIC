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
def review_grid(qapp):
    view = GraphView()
    charts = {}
    for sample in ("Pass", "Low1", "Low2"):
        tile = PlotTile(QWidget())
        tile.chart_view = charts[sample] = _FakeChart(sample, tile)
    view._current_plots = list(charts.values())
    emitted = []
    view.peak_review_changed.connect(lambda c, s, r: emitted.append((sorted(s), r)))
    yield view, charts, emitted
    view.deleteLater()


def _menu_texts(view, lead):
    accept, reject = QAction("a"), QAction("r")
    view.update_review_actions(
        lead, inspect=QAction("i"), show_only=QAction("s"),
        accept=accept, reject=reject, fit_menu=QMenu(),
    )
    assert not accept.isChecked() and not reject.isChecked()
    return accept.text(), reject.text()


@pytest.mark.parametrize(
    ("verdicts", "accept_text", "accepted"),
    [
        # Mixed: only the not-yet-accepted eligible peak is accepted; nothing is cleared.
        ((PeakVerdict.ACCEPTED, PeakVerdict.FAIL), "Accept Peak (Below Threshold)",
         (["Low2"], PeakReview.ACCEPTED)),
        ((PeakVerdict.FAIL, PeakVerdict.FAIL), "Accept 2 Peaks (Below Threshold)",
         (["Low1", "Low2"], PeakReview.ACCEPTED)),
        ((PeakVerdict.ACCEPTED, PeakVerdict.ACCEPTED), "Clear Acceptance (2 Peaks)",
         (["Low1", "Low2"], None)),
    ],
    ids=["mixed", "none-accepted", "all-accepted"],
)
def test_group_accept_states_what_it_does(review_grid, verdicts, accept_text, accepted):
    view, charts, emitted = review_grid
    view.apply_peak_verdicts(
        {"Pass": PeakVerdict.PASS, "Low1": verdicts[0], "Low2": verdicts[1]}
    )
    view._selected_plots = set(charts.values())
    assert _menu_texts(view, charts["Pass"])[0] == accept_text
    view.toggle_peak_review(charts["Pass"], PeakReview.ACCEPTED)
    assert emitted == [accepted]


@pytest.mark.parametrize(
    ("verdicts", "reject_text", "rejected"),
    [
        ((PeakVerdict.REJECTED, PeakVerdict.FAIL, PeakVerdict.PASS), "Mark 2 Peaks as Bad",
         (["Low2", "Pass"], PeakReview.REJECTED)),
        ((PeakVerdict.PASS, PeakVerdict.FAIL, PeakVerdict.PASS), "Mark 3 Peaks as Bad",
         (["Low1", "Low2", "Pass"], PeakReview.REJECTED)),
        ((PeakVerdict.REJECTED,) * 3, "Clear Bad Mark (3 Peaks)",
         (["Low1", "Low2", "Pass"], None)),
    ],
    ids=["mixed", "none-marked", "all-marked"],
)
def test_group_mark_bad_states_what_it_does(review_grid, verdicts, reject_text, rejected):
    view, charts, emitted = review_grid
    view.apply_peak_verdicts(dict(zip(("Low1", "Low2", "Pass"), verdicts)))
    view._selected_plots = set(charts.values())
    assert _menu_texts(view, charts["Pass"])[1] == reject_text
    view.toggle_peak_review(charts["Pass"], PeakReview.REJECTED)
    assert emitted == [rejected]
