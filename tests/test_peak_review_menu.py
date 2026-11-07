from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from manic.io.compound_reader import Compound
from manic.models.analysis import AnalysisMode
from manic.models.sample_fit_type import set_sample_fit_type
from manic.ui import theme
from manic.ui.graphs import ClickableChartView, GraphView
from manic.validation.peak_verdict import PEAK_VERDICT_FILL, PeakReview, PeakVerdict

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


def test_tile_colours_match_the_workbook_verdict_fills(scheme, grid):
    verdicts = {"A": FAIL, "B": REJECTED, "C": PASS, "D": PeakVerdict.ACCEPTED}
    _plot(grid, verdicts)
    for sample, texts in (
        ("A", ["Below threshold"]), ("B", ["Marked bad"]), ("C", []), ("D", ["Accepted"])
    ):
        tile = _plots(grid)[sample].parent()
        badges = _badge_labels(tile)
        assert [badge.text() for badge in badges] == texts
        # A point on the card's own fill, above the caption.
        card = tile.grab().toImage().pixelColor(16, 3)
        fill = PEAK_VERDICT_FILL[verdicts[sample]]
        if fill is None:
            assert card == theme.color("surface")
        else:
            # A translucent wash of the workbook colour: its hue, between the card and the fill.
            surface, wash = theme.color("surface"), QColor(fill)
            hue_gap = abs(card.hslHue() - wash.hslHue()) % 360
            assert min(hue_gap, 360 - hue_gap) <= (35 if theme.is_dark() else 5)
            assert card != surface and card != wash
            assert min(surface.lightness(), wash.lightness()) <= card.lightness()
            assert card.lightness() <= max(surface.lightness(), wash.lightness())
        for badge in badges:
            pill = badge.grab().toImage().pixelColor(2, badge.height() // 2)
            assert pill != card
            assert theme.contrast(badge.palette().color(badge.foregroundRole()), pill) >= 4.5


def test_accept_enabled_only_on_failed_or_accepted_tiles(grid):
    _plot(grid, VERDICTS)
    grid.select_samples(["C"])
    for sample, accept, reject in (
        ("A", "Accept A (Below Threshold)", "Mark A as Bad"),
        ("B", "Accept Peak (Below Threshold)", "Clear Bad Mark (B)"),
        ("C", "Accept Peak (Below Threshold)", "Mark C as Bad"),
    ):
        actions = _context_menu(grid, sample)
        assert actions[accept].isEnabled() is (sample == "A")
        assert actions[reject].isEnabled()


def test_accept_emits_review_for_clicked_tile(grid):
    reviews = _plot(grid, VERDICTS)
    grid.select_samples(["B", "C"])
    actions = _context_menu(grid, "A")
    assert {"Mark A as Bad", "Curve Fit"} <= actions.keys()
    actions["Accept A (Below Threshold)"].trigger()
    assert reviews == [("Cmp", ["A"], PeakReview.ACCEPTED)]


def test_clear_bad_mark_clears_the_review(grid):
    reviews = _plot(grid, VERDICTS)
    _context_menu(grid, "B")["Clear Bad Mark (B)"].trigger()
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
        ((ACCEPTED, FAIL), "Accept Low2 (Below Threshold)", (["Low2"], PeakReview.ACCEPTED)),
        ((REJECTED, FAIL), "Accept Low2 (Below Threshold)", (["Low2"], PeakReview.ACCEPTED)),
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
            "Accept A (Below Threshold)": True,
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
        review["Accept A (Below Threshold)"].trigger()
        assert reviews[-1] == ("Cmp", ["A"], PeakReview.ACCEPTED)

        QTest.keyClick(view, Qt.Key_Escape)
        QTest.keyClick(view, Qt.Key_Right)
        QTest.keyClick(view, Qt.Key_Right)
        focused = _review_menu(window)
        assert "Mark B as Bad" in focused and "Inspect B..." in focused
        assert not focused["Accept Peak (Below Threshold)"].isEnabled()
    finally:
        _close_popups()
        window.close()


def _review_window(monkeypatch, verdicts):
    """A shown, active window whose grid plots ``verdicts``; the reviews it emits."""
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    view = window.graph_view
    view.peak_review_changed.disconnect(window.on_peak_review_changed)
    window.show()
    reviews = _plot(view, verdicts)
    window.workspace.setCurrentWidget(view)
    window.activateWindow()
    assert QTest.qWaitForWindowActive(window)
    return window, reviews


def test_review_keys_reach_the_grid_from_the_sidebar_lists_but_not_a_text_field(
    qapp, monkeypatch, plot_data
):
    window, reviews = _review_window(monkeypatch, {"A": FAIL, "B": PASS, "C": FAIL})
    view, toolbar = window.graph_view, window.toolbar
    try:
        review = _review_menu(window)
        for name, key in (
            ("Next Flagged Sample", "N"),
            ("Previous Flagged Sample", "Shift+N"),
            ("Accept Peak (Below Threshold)", "A"),
            ("Mark Peak as Bad", "B"),
        ):
            assert review[name].shortcut() == QKeySequence(key)
            assert review[name].isShortcutVisibleInContextMenu()
        # Names that type-ahead would jump to on N, A or B.
        toolbar.compound_selected.disconnect(window.on_compound_selected)
        toolbar.update_compound_list(["Alanine", "Bio", "Cmp", "nor-Leucine"], "Cmp")
        samples = toolbar.sample_list
        samples.blockSignals(True)
        toolbar.update_sample_list(["A", "B", "C", "N"])
        samples.setCurrentRow(3)
        window.show_samples_action.setChecked(True)
        compounds = toolbar.compound_list

        compounds.setFocus()
        QTest.keyClick(compounds, Qt.Key_N)
        assert view.hasFocus() and view.get_selected_samples() == ["A"]
        compounds.setFocus()
        QTest.keyClick(compounds, Qt.Key_A)
        samples.setFocus()
        QTest.keyClick(samples, Qt.Key_B)
        QTest.keyClick(samples, Qt.Key_N, Qt.ShiftModifier)
        assert compounds.currentItem().text() == "Cmp" and samples.currentRow() == 3
        assert reviews == [
            ("Cmp", ["A"], PeakReview.ACCEPTED),
            ("Cmp", ["A"], PeakReview.REJECTED),
        ]
        assert view.get_selected_samples() == ["C"]

        compounds.setFocus()
        QTest.keyClick(compounds, Qt.Key_Down)
        assert compounds.currentItem().text() == "nor-Leucine"

        toolbar.compound_filter.setFocus()
        QTest.keyClicks(toolbar.compound_filter, "nab")
        assert toolbar.compound_filter.text() == "nab"
        assert len(reviews) == 2 and view.get_selected_samples() == ["C"]
    finally:
        _close_popups()
        window.close()


def test_n_makes_the_flagged_tile_the_one_target_of_a_and_b(qapp, monkeypatch, plot_data):
    window, reviews = _review_window(monkeypatch, {"A": PASS, "B": PASS, "C": FAIL, "D": FAIL})
    view = window.graph_view
    try:
        # Nothing focused or selected yet: N alone must enable the verdict commands.
        QTest.keyClick(view, Qt.Key_N)
        review = _review_menu(window)
        assert review["Accept C (Below Threshold)"].isEnabled()
        assert review["Mark C as Bad"].isEnabled()

        view.select_samples(["A", "B"])
        QTest.keyClick(view, Qt.Key_N)
        assert view.get_selected_samples() == ["D"]
        review = _review_menu(window)
        assert "Inspect D..." in review and review["Mark D as Bad"].isEnabled()
        QTest.keyClick(view, Qt.Key_B)
        assert reviews == [("Cmp", ["D"], PeakReview.REJECTED)]
    finally:
        _close_popups()
        window.close()


def test_review_keys_that_cannot_act_say_why(qapp, monkeypatch, plot_data):
    from manic.ui.toast_notification import ToastNotification

    window, reviews = _review_window(monkeypatch, {"A": PASS, "B": ACCEPTED, "C": REJECTED})
    view = window.graph_view

    def toast_after(key):
        QTest.keyClick(view, key)
        toasts = window.statusBar().findChildren(ToastNotification)
        [toast] = [toast for toast in toasts if toast.isVisible()]
        return toast.findChild(QLabel, "toastLabel").text()

    try:
        review = _review_menu(window)
        assert not review["Next Flagged Sample"].isEnabled()
        assert not review["Previous Flagged Sample"].isEnabled()
        assert toast_after(Qt.Key_N) == "No flagged plots in Cmp"
        assert toast_after(Qt.Key_A) == "Select a plot first"
        assert toast_after(Qt.Key_B) == "Select a plot first"
        view.select_samples(["A"])
        assert toast_after(Qt.Key_A) == "A is not Below threshold"
        view.select_samples(["A", "C"])
        assert toast_after(Qt.Key_A) == "No selected plot is Below threshold"
        assert reviews == []

        view.apply_peak_verdicts({"A": FAIL})
        assert _review_menu(window)["Next Flagged Sample"].isEnabled()
    finally:
        _close_popups()
        window.close()


def test_a_review_that_goes_through_clears_the_refusal_before_it(
    qapp, empty_db, monkeypatch, plot_data
):
    from manic.ui.toast_notification import ToastNotification

    window, _reviews = _review_window(monkeypatch, {"A": PASS})
    view = window.graph_view
    view.peak_review_changed.connect(window.on_peak_review_changed)
    monkeypatch.setattr(window, "_peak_verdicts", lambda compound, samples: {"A": REJECTED})

    def shown():
        toasts = window.statusBar().findChildren(ToastNotification)
        return [t.findChild(QLabel, "toastLabel").text() for t in toasts if t.isVisible()]

    try:
        view.select_samples(["A"])
        QTest.keyClick(view, Qt.Key_A)
        assert shown() == ["A is not Below threshold"]
        QTest.keyClick(view, Qt.Key_B)
        assert shown() == []
    finally:
        _close_popups()
        window.close()
