from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from manic.io.compound_reader import Compound
from manic.models.analysis import AnalysisMode
from manic.models.sample_fit_type import set_sample_fit_type
from manic.ui import theme
from manic.ui.graphs import ClickableChartView, GraphView
from manic.validation.peak_verdict import PeakReview, PeakVerdict

from conftest import _make_window

FAIL, PASS = PeakVerdict.FAIL, PeakVerdict.PASS
ACCEPTED, REJECTED = PeakVerdict.ACCEPTED, PeakVerdict.REJECTED
VERDICTS = {"A": FAIL, "B": REJECTED, "C": PASS}
FIT_OPTIONS = ("Use Compound Setting", "Auto", "Gaussian", "Bi-Gaussian", "EMG")


def _eic(sample: str, compound: str):
    time = np.linspace(6.9, 7.3, 81)
    peak = np.exp(-0.5 * ((time - 7.09) / 0.02) ** 2)
    return SimpleNamespace(
        sample_name=sample, compound_name=compound, time=time, intensity=np.vstack([1e6 * peak])
    )


@pytest.fixture
def plot_data(monkeypatch):
    monkeypatch.setattr(
        "manic.ui.graphs.get_eics_for_compound",
        lambda compound, samples, use_corrected=False: [_eic(s, compound) for s in samples],
    )
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session",
        lambda name, sample=None: Compound(
            compound_name=name, retention_time=7.09, loffset=0.08, roffset=0.035,
            label_atoms=0, mass0=174.0, baseline_correction=0,
        ),
    )


def _close_popups() -> None:
    while (popup := QApplication.activePopupWidget()) is not None:
        popup.close()


@pytest.fixture
def grid(qapp, plot_data):
    view = GraphView()
    yield view
    _close_popups()
    view.deleteLater()


@pytest.fixture(params=[False, True], ids=["light", "dark"])
def scheme(request):
    theme.set_dark(request.param)
    yield
    theme.set_dark(False)


def _plot(view: GraphView, verdicts: dict[str, PeakVerdict]) -> list:
    """Plot a tile per sample of ``verdicts``; return the peak reviews the grid emits."""
    view.plot_compound("Cmp", list(verdicts), verdicts)
    reviews = []
    view.peak_review_changed.connect(lambda c, s, r: reviews.append((c, sorted(s), r)))
    return reviews


def _plots(view: GraphView) -> dict[str, ClickableChartView]:
    return {p.sample_name: p for p in view.findChildren(ClickableChartView) if p.isVisibleTo(view)}


def _context_menu(view: GraphView, sample: str) -> dict[str, QAction]:
    """Right-click ``sample``'s tile; the open menu's actions by text, curve fits included."""
    QTest.mouseClick(_plots(view)[sample].viewport(), Qt.RightButton)
    actions = {}
    for action in QApplication.activePopupWidget().actions():
        actions[action.text()] = action
        if action.menu() is not None:
            actions.update({child.text(): child for child in action.menu().actions()})
    actions.pop("", None)
    return actions


def _review_menu(window) -> dict[str, QAction]:
    """Open and close the menu-bar Review menu; its actions by text."""
    window.review_menu.popup(QPoint(0, 0))
    actions = {action.text(): action for action in window.review_menu.actions() if action.text()}
    window.review_menu.close()
    return actions


def _badge_labels(tile) -> list[QLabel]:
    return [
        label for label in tile.findChildren(QLabel)
        if label.isVisibleTo(tile) and label not in (tile.caption, tile.scale_label)
    ]


def test_apply_peak_verdicts_styles_tiles(scheme, grid):
    _plot(grid, VERDICTS)
    for sample, texts, tint in (
        ("A", ["Below threshold"], "warning_soft"),
        ("B", ["Marked bad"], "danger_soft"),
        ("C", [], None),
    ):
        tile = _plots(grid)[sample].parent()
        badges = _badge_labels(tile)
        assert [badge.text() for badge in badges] == texts
        assert tile.tint() == tint
        # A point on the card's own fill, above the caption.
        card = tile.grab().toImage().pixelColor(16, 3)
        for badge in badges:
            pill = badge.grab().toImage().pixelColor(2, badge.height() // 2)
            assert pill != card
            assert theme.contrast(badge.palette().color(badge.foregroundRole()), pill) >= 4.5


def test_accept_enabled_only_on_failed_or_accepted_tiles(grid):
    _plot(grid, VERDICTS)
    grid.select_samples(["C"])
    for sample, enabled, reject in (
        ("A", True, "Mark Peak as Bad"),
        ("B", False, "Clear Bad Mark"),
        ("C", False, "Mark Peak as Bad"),
    ):
        actions = _context_menu(grid, sample)
        assert actions["Accept Peak (Below Threshold)"].isEnabled() is enabled
        assert actions[reject].isEnabled()


def test_accept_emits_review_for_clicked_tile(grid):
    reviews = _plot(grid, VERDICTS)
    grid.select_samples(["B", "C"])
    actions = _context_menu(grid, "A")
    assert {"Mark Peak as Bad", "Curve Fit"} <= actions.keys()
    actions["Accept Peak (Below Threshold)"].trigger()
    assert reviews == [("Cmp", ["A"], PeakReview.ACCEPTED)]


def test_clear_bad_mark_clears_the_review(grid):
    reviews = _plot(grid, VERDICTS)
    _context_menu(grid, "B")["Clear Bad Mark"].trigger()
    assert reviews == [("Cmp", ["B"], None)]


def test_action_applies_to_every_selected_tile(grid):
    reviews = _plot(grid, VERDICTS)
    grid.select_samples(["A", "C"])
    _context_menu(grid, "A")["Mark 2 Peaks as Bad"].trigger()
    assert reviews == [("Cmp", ["A", "C"], PeakReview.REJECTED)]


@pytest.mark.parametrize(
    ("overrides", "selected", "checked", "chosen", "emitted"),
    [
        ({}, ["A", "C"], "Use Compound Setting", "Gaussian", ("Cmp", ["A", "C"], "gaussian")),
        ({"emg": ["A", "B"]}, ["A", "B"], "EMG", "Use Compound Setting", ("Cmp", ["A", "B"], None)),
    ],
    ids=["no-override", "common-override"],
)
def test_curve_fit_menu_emits_override_for_selected_tiles(
    grid, overrides, selected, checked, chosen, emitted
):
    for fit_type, samples in overrides.items():
        set_sample_fit_type("Cmp", samples, fit_type)
    _plot(grid, VERDICTS)
    fits = []
    grid.sample_fit_type_changed.connect(lambda c, s, f: fits.append((c, sorted(s), f)))
    grid.select_samples(selected)
    actions = _context_menu(grid, "A")
    assert [name for name in FIT_OPTIONS if actions[name].isChecked()] == [checked]
    actions[chosen].trigger()
    assert fits == [emitted]


def test_show_only_selected_uses_clicked_tile_when_not_in_selection(grid):
    _plot(grid, VERDICTS)
    grid.select_samples(["A"])
    focused: list[list[str]] = []
    grid.focus_selected_requested.connect(focused.append)
    _context_menu(grid, "B")["Show Only This Sample"].trigger()
    assert focused == [["B"]]


@pytest.mark.parametrize(
    ("verdicts", "accept_text", "accepted"),
    [
        # Mixed: only the not-yet-accepted eligible peak is accepted; nothing is cleared.
        ((ACCEPTED, FAIL), "Accept Peak (Below Threshold)", (["Low2"], PeakReview.ACCEPTED)),
        ((REJECTED, FAIL), "Accept Peak (Below Threshold)", (["Low2"], PeakReview.ACCEPTED)),
        ((FAIL, FAIL), "Accept 2 Peaks (Below Threshold)", (["Low1", "Low2"], PeakReview.ACCEPTED)),
        ((ACCEPTED, ACCEPTED), "Clear Acceptance (2 Peaks)", (["Low1", "Low2"], None)),
    ],
    ids=["mixed", "rejected-skipped", "none-accepted", "all-accepted"],
)
def test_group_accept_states_what_it_does(grid, verdicts, accept_text, accepted):
    reviews = _plot(grid, {"Pass": PASS, "Low1": verdicts[0], "Low2": verdicts[1]})
    grid.select_samples(["Pass", "Low1", "Low2"])
    actions = _context_menu(grid, "Pass")
    assert "Curve Fit for 3 Samples" in actions
    accept = actions[accept_text]
    assert accept.isEnabled() and not accept.isChecked()
    accept.trigger()
    assert reviews == [("Cmp", *accepted)]


@pytest.mark.parametrize(
    ("verdicts", "reject_text", "rejected"),
    [
        ((REJECTED, FAIL, PASS), "Mark 2 Peaks as Bad", (["Low2", "Pass"], PeakReview.REJECTED)),
        ((PASS, FAIL, PASS), "Mark 3 Peaks as Bad", (["Low1", "Low2", "Pass"], PeakReview.REJECTED)),
        ((REJECTED,) * 3, "Clear Bad Mark (3 Peaks)", (["Low1", "Low2", "Pass"], None)),
    ],
    ids=["mixed", "none-marked", "all-marked"],
)
def test_group_mark_bad_states_what_it_does(grid, verdicts, reject_text, rejected):
    reviews = _plot(grid, dict(zip(("Low1", "Low2", "Pass"), verdicts)))
    grid.select_samples(["Pass", "Low1", "Low2"])
    reject = _context_menu(grid, "Pass")[reject_text]
    assert not reject.isChecked()
    reject.trigger()
    assert reviews == [("Cmp", *rejected)]


def test_review_menu_names_its_targets_and_acts_on_them(qapp, monkeypatch, plot_data):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    view = window.graph_view
    view.peak_review_changed.disconnect(window.on_peak_review_changed)
    try:
        reviews = _plot(view, {"A": FAIL, "B": PASS, "C": PASS})
        idle = _review_menu(window)
        for name in ("Inspect Sample...", "Show Only Selected Samples", "Mark Peak as Bad", "Curve Fit"):
            assert not idle[name].isEnabled()
        context = _context_menu(view, "A")
        assert not context["Show Only Selected Samples"].isEnabled()
        assert context["Show All Samples"].isEnabled()

        view.select_samples(["A", "B"])
        # Only A is below threshold, so only A can be accepted.
        expected = {
            "Inspect A...": True,
            "Show Only 2 Selected Samples": True,
            "Accept Peak (Below Threshold)": True,
            "Mark 2 Peaks as Bad": True,
            "Curve Fit for 2 Samples": True,
        }
        review, context = _review_menu(window), _context_menu(view, "A")
        for actions in (review, context):
            assert {name: actions[name].isEnabled() for name in expected} == expected
        fits = review["Curve Fit for 2 Samples"].menu().actions()
        assert "Use Compound Setting" in [action.text() for action in fits]

        review["Mark 2 Peaks as Bad"].trigger()
        context["Mark 2 Peaks as Bad"].trigger()
        assert reviews == [("Cmp", ["A", "B"], PeakReview.REJECTED)] * 2
        review["Accept Peak (Below Threshold)"].trigger()
        assert reviews[-1] == ("Cmp", ["A"], PeakReview.ACCEPTED)

        QTest.keyClick(view, Qt.Key_Escape)
        QTest.keyClick(view, Qt.Key_Right)
        QTest.keyClick(view, Qt.Key_Right)
        focused = _review_menu(window)
        assert "Mark Peak as Bad" in focused and "Inspect B..." in focused
        assert not focused["Accept Peak (Below Threshold)"].isEnabled()
    finally:
        _close_popups()
        window.close()
