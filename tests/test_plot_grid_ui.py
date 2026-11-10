import math
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest

from manic.io.compound_reader import Compound
from manic.models.analysis import IonChannel, IonRole
from manic.processors.tile_y_scale import YScalePolicy
from manic.ui import theme
from manic.ui.chart_header import ChartHeader
from manic.ui.graphs import ClickableChartView, GraphView
from manic.ui.plot_tile import (
    TILE_GAP,
    tile_badges,
)
from manic.utils.utils import apply_app_stylesheet
from manic.validation.peak_verdict import PeakVerdict
from manic.validation.unlabelled_identity import (
    IdentityQcResult,
    IdentitySampleAssessment,
    IdentityStatus,
    QualifierRatioResult,
    qualifier_pair,
)


def _eic(sample: str, compound: str):
    time = np.linspace(6.9, 7.3, 81)
    peak = np.exp(-0.5 * ((time - 7.09) / 0.02) ** 2)
    return SimpleNamespace(
        sample_name=sample, compound_name=compound, time=time, intensity=np.vstack([1e6 * peak])
    )


@pytest.fixture
def rts():
    """Retention time per sample; a sample not listed has 7.09."""
    return {}


@pytest.fixture
def grid(qapp, monkeypatch, rts):
    monkeypatch.setattr(
        "manic.ui.graphs.get_eics_for_compound",
        lambda compound, samples, use_corrected=False: [_eic(s, compound) for s in samples],
    )
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session",
        lambda name, sample=None: Compound(
            compound_name=name, retention_time=rts.get(sample, 7.09), loffset=0.08,
            roffset=0.035, label_atoms=0, mass0=174.0, baseline_correction=0,
        ),
    )
    view = GraphView()
    yield view
    view.deleteLater()


@pytest.fixture
def opened(monkeypatch):
    """(compound, sample) of each detailed view the grid opens."""
    shown = []
    monkeypatch.setattr(
        "manic.ui.detailed_plot_dialog.DetailedPlotDialog",
        lambda compound_name, sample_name, **_: SimpleNamespace(
            exec=lambda: shown.append((compound_name, sample_name))
        ),
    )
    return shown


@pytest.fixture(params=[False, True], ids=["light", "dark"])
def scheme(request):
    theme.set_dark(request.param)
    yield
    theme.set_dark(False)


def _plots(view: GraphView) -> dict[str, ClickableChartView]:
    return {p.sample_name: p for p in view.findChildren(ClickableChartView) if p.isVisibleTo(view)}


@pytest.fixture
def styled(qapp):
    """The app's font and stylesheet, which set the header's widths, whatever ran before."""
    before = qapp.font(), qapp.styleSheet()
    apply_app_stylesheet(qapp)
    yield
    qapp.setFont(before[0])
    qapp.setStyleSheet(before[1])


def test_a_retention_time_failure_is_badged_even_when_the_ratios_pass():
    quantifier = IonChannel(217.0, IonRole.QUANTIFIER)
    qualifier = IonChannel(
        147.0, IonRole.QUALIFIER, ordinal=1, expected_ratio=0.4, ratio_tolerance=0.25
    )
    reason = "Retention-time error +0.120 min exceeds ±0.050 min"
    qc = IdentityQcResult(
        status=IdentityStatus.REVIEW_REQUIRED, quantifier_area=100.0, observed_rt=7.21,
        rt_error=0.12, rt_passed=False,
        qualifier_ratios=(QualifierRatioResult(qualifier, 0.41, True),), reasons=(reason,),
    )
    assessment = IdentitySampleAssessment(
        "Shifted", qc, qualifier_pair((quantifier, qualifier), qc, error=None), None
    )

    [badge] = tile_badges(PeakVerdict.PASS, assessment)

    assert (badge.text, badge.tone, badge.tooltip) == ("tR off", "danger", reason)


def _show_grid_with_viewport(grid, qapp, samples: int, width: int, height: int) -> None:
    grid.resize(width + 400, height + 300)
    grid.show()
    grid.plot_compound("Cmp", [f"S{i}" for i in range(samples)])
    qapp.processEvents()
    viewport_w, viewport_h = grid._grid_viewport()
    grid.resize(grid.width() + width - viewport_w, grid.height() + height - viewport_h)
    # The grid re-lays its tiles shortly after a resize, and again if a scroll bar shows.
    for _ in range(500):
        if grid._grid_viewport()[1] == height and _laid_out(grid):
            return
        QTest.qWait(10)
    raise AssertionError("the grid never finished laying out its tiles")


def _laid_out(grid) -> bool:
    """The tiles have the size the grid's shape gives its current viewport."""
    if grid._resize_timer.isActive():
        return False
    cols, row_height = grid._grid_shape
    rows = math.ceil(len(grid._current_plots) / cols)
    width, height = grid._grid_viewport()
    tile = grid._current_plots[0].parent()
    return (
        abs(tile.width() - (width - TILE_GAP * (cols - 1)) / cols) <= 1
        and abs(tile.height() - (row_height or (height - TILE_GAP * (rows - 1)) / rows)) <= 1
    )


def test_time_ticks_settle_at_every_tile_width(grid, qapp):
    # At some width the chosen step once moved the plot edge enough to flip the step
    # back, forever, freezing the app (ccc9554f). One row of three tiles, 1 px at a time
    # from the narrowest the grid keeps in a row to 260 px.
    _show_grid_with_viewport(grid, qapp, 3, 480, 130)
    extra = grid.width() - grid._grid_viewport()[0]
    views = list(_plots(grid).values())
    axes = [view.chart().axes(Qt.Horizontal)[0] for view in views]
    changes = []

    def count(_area):
        changes.append(1)
        if len(changes) == 50 * len(views):
            for view in views:
                view.chart().plotAreaChanged.disconnect()

    for view in views:
        view.chart().plotAreaChanged.connect(count)
    for tile in range(150, 261):
        changes.clear()
        grid.resize(extra + 3 * tile + 30, grid.height())
        for _ in range(200):
            QTest.qWait(10)
            if _laid_out(grid):
                break
        first = [axis.tickInterval() for axis in axes]
        fired = []
        QTimer.singleShot(0, lambda: fired.append(True))
        QTest.qWait(100)
        settled = fired and [axis.tickInterval() for axis in axes] == first
        assert settled and len(changes) < 50 * len(views), (
            f"ticks never settled at {views[0].width()} px"
        )


def test_next_and_previous_flagged_tile_wrap_and_skip_reviewed_ones(grid):
    grid.plot_compound("Cmp", ["A", "B", "C", "D", "E"])
    assert grid.focus_flagged(1) is False
    grid.apply_peak_verdicts(
        {"B": PeakVerdict.FAIL, "C": PeakVerdict.ACCEPTED, "D": PeakVerdict.REJECTED, "E": PeakVerdict.FAIL}
    )

    def step(direction):
        assert grid.focus_flagged(direction) is True
        assert grid.get_selected_samples() == [grid.review_lead().sample_name]
        return grid.review_lead().sample_name

    assert [step(1), step(1), step(1)] == ["B", "E", "B"]
    assert [step(-1), step(-1)] == ["E", "B"]
    QTest.keyClick(grid, Qt.Key_Right)
    assert grid.review_lead().sample_name == "B"
    grid.clear_selection()
    QTest.keyClick(grid, Qt.Key_Right)
    assert grid.review_lead().sample_name == "D"
    assert step(-1) == "B"


def test_icon_buttons_have_accessible_names(grid):
    assert grid.settings_button.accessibleName() == "Settings"
    assert ChartHeader("Peak area").expand_button.accessibleName() == "Enlarge peak area chart"


def test_replotting_keeps_the_selection_for_samples_still_shown(grid):
    grid.plot_compound("Valine", ["S1", "S2", "S3", "S4"])
    grid.select_samples(["S2", "S4"])

    grid.set_y_scale_policy(YScalePolicy.SHARED_EXTRACT)
    assert grid.get_selected_samples() == ["S2", "S4"]
    grid.plot_compound("Valine", ["S1", "S2", "S3"])
    assert grid.get_selected_samples() == ["S2"]
    grid.plot_compound("Leucine", ["S1", "S2", "S3"])
    assert grid.get_selected_samples() == []
