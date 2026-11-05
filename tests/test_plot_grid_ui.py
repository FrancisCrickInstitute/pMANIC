from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QFontMetricsF, QTextDocumentFragment
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QScrollArea, QToolButton, QVBoxLayout, QWidget

from manic.io.compound_reader import Compound
from manic.models.analysis import IonChannel, IonRole
from manic.processors.tile_y_scale import YScalePolicy
from manic.ui import theme
from manic.ui.chart_header import ChartHeader
from manic.ui.chart_popup_dialog import value_axis_ticks
from manic.ui.channel_chips import ChannelChip, ChannelChipRow
from manic.ui.colors import ChannelTraceStyle, label_colors, verdict_colours
from manic.ui.graphs import ClickableChartView, GraphView
from manic.ui.plot_tile import DENSITY_MIN_TILE, PEAK_BADGES, PlotTile, grid_columns, tile_badges
from manic.validation.peak_verdict import PeakVerdict
from manic.validation.unlabelled_identity import (
    IdentityAssessmentSet,
    IdentityQcResult,
    IdentitySampleAssessment,
    IdentityStatus,
    QualifierRatioResult,
    qualifier_pair,
)


@pytest.mark.parametrize(
    ("count", "width", "height", "min_size", "columns"),
    [
        (30, 1284, 900, (190, 135), 5),
        (0, 800, 600, (190, 135), 1),
        # The grid viewport of a 1512x949 window with the sidebar open.
        (30, 1180, 790, DENSITY_MIN_TILE["compact"], 6),
        # 1280x800 at 150% leaves about 700x520 for the grid.
        (11, 700, 520, DENSITY_MIN_TILE["compact"], 3),
    ],
    ids=["fits", "empty", "compact-laptop", "compact-small-laptop"],
)
def test_grid_keeps_every_tile_on_screen_when_they_fit(count, width, height, min_size, columns):
    min_width, min_height = min_size
    shape = grid_columns(count, width, height, min_width=min_width, min_height=min_height)
    assert shape == (columns, 0)


@pytest.mark.parametrize(
    ("width", "height", "min_size", "shape"),
    [
        (970, 700, (190, 135), (4, 163)),
        (1180, 790, DENSITY_MIN_TILE["comfortable"], (4, 199)),
    ],
    ids=["scrolls", "comfortable-laptop"],
)
def test_grid_scrolls_with_readable_tiles_when_they_do_not_fit(width, height, min_size, shape):
    min_width, min_height = min_size
    assert grid_columns(30, width, height, min_width=min_width, min_height=min_height) == shape


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


def _badge_labels(tile: PlotTile) -> list[QLabel]:
    return [
        label for label in tile.findChildren(QLabel)
        if label.isVisibleTo(tile) and label not in (tile.caption, tile.scale_label)
    ]


def test_select_all_and_escape(grid):
    grid.plot_compound("Cmp", ["A", "B", "C", "D"])
    emitted = []
    grid.selection_changed.connect(lambda names: emitted.append(sorted(names)))
    QTest.keyClick(grid, Qt.Key_A, Qt.ControlModifier)
    assert emitted[-1] == ["A", "B", "C", "D"]
    QTest.keyClick(grid, Qt.Key_Escape)
    assert emitted[-1] == []


def test_arrows_move_focus_and_space_toggles(grid, qapp):
    grid.resize(600, 560)
    grid.show()
    qapp.processEvents()
    grid.plot_compound("Cmp", ["A", "B", "C", "D"])
    emitted = []
    grid.selection_changed.connect(lambda names: emitted.append(sorted(names)))
    QTest.keyClick(grid, Qt.Key_Right)  # first arrow focuses the first tile
    QTest.keyClick(grid, Qt.Key_Down)
    QTest.keyClick(grid, Qt.Key_Right)
    QTest.keyClick(grid, Qt.Key_Space)
    assert emitted[-1] == ["D"]
    QTest.keyClick(grid, Qt.Key_Up)
    QTest.keyClick(grid, Qt.Key_Space)
    assert emitted[-1] == ["B", "D"]
    QTest.keyClick(grid, Qt.Key_Space)
    assert emitted[-1] == ["D"]


def test_enter_opens_detailed_view_of_focused_tile(grid, opened):
    grid.plot_compound("Cmp", ["A", "B", "C", "D"])
    QTest.keyClick(grid, Qt.Key_Right)
    QTest.keyClick(grid, Qt.Key_Right)
    QTest.keyClick(grid, Qt.Key_Return)
    assert opened == [("Cmp", "B")]


def test_double_click_opens_once_without_a_second_toggle(grid, opened):
    grid.plot_compound("Cmp", ["A", "B", "C", "D"])
    selections = []
    grid.selection_changed.connect(lambda names: selections.append(sorted(names)))
    viewport = _plots(grid)["A"].viewport()
    # A real double-click: press, release, then a double-click press and its release.
    QTest.mouseClick(viewport, Qt.LeftButton)
    QTest.mouseDClick(viewport, Qt.LeftButton)
    QTest.mouseRelease(viewport, Qt.LeftButton)
    assert selections == [["A"]]
    assert opened == [("Cmp", "A")]


def test_grid_header_names_the_compound_with_tr_and_count(grid, rts):
    samples = ["S1", "S2", "S3"]
    grid.plot_compound("Pyruvate", samples)
    assert not grid.compound_title.isHidden()
    assert grid.compound_title.text() == "Pyruvate"
    assert grid.selection_summary.text() == "tR 7.09"

    grid.select_samples(["S2"])
    assert grid.selection_summary.text() == "tR 7.09 · 1 of 3 selected"

    rts["S3"] = 7.12
    grid.plot_compound("Pyruvate", samples)
    assert grid.selection_summary.text() == "tR 7.09–7.12 · 1 of 3 selected"

    rts.update(S1=7.05, S3=7.1234)
    grid.plot_compound("Pyruvate", samples)
    assert grid.selection_summary.text() == "tR 7.05–7.123 · 1 of 3 selected"

    rts["S1"] = 7.2
    grid.plot_compound("Pyruvate", ["S1"])
    assert grid.selection_summary.text() == "tR 7.2"

    grid.clear_all_plots()
    assert grid.compound_title.isHidden()
    assert grid.selection_summary.text() == ""


def test_chip_row_wraps_before_truncating_a_chip(qapp):
    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    row = ChannelChipRow()
    layout.addWidget(row)
    layout.addStretch()
    labels = [f"M+{i} m/z {174 + i}" for i in range(4)]
    row.set_channels(labels, [ChannelTraceStyle(c, Qt.SolidLine) for c in label_colors[:4]])
    try:
        host.resize(260, 200)
        host.show()
        qapp.processEvents()
        chips = row.chips()
        # A chip shows its label as a tooltip only once the label is cut.
        assert [chip.toolTip() for chip in chips] == ["", "", "", ""]
        assert len({chip.y() for chip in chips}) == 2
        assert all(row.rect().contains(chip.geometry()) for chip in chips)
    finally:
        host.deleteLater()


def test_badges_sit_below_the_caption_at_every_width(qapp):
    tile = PlotTile(QWidget())
    tile.set_caption("Sample_05_rt_shift")
    tile.set_badges([PEAK_BADGES[PeakVerdict.FAIL]])
    try:
        tile.show()
        for width in (200, 600):
            tile.resize(width, 300)
            qapp.processEvents()
            [badge] = _badge_labels(tile)
            assert (tile.caption.text(), badge.text()) == ("Sample_05_rt_shift", "Below threshold")
            assert badge.mapTo(tile, QPoint(0, 0)).y() >= tile.caption.geometry().bottom()
    finally:
        tile.deleteLater()


def test_qc_badges_never_tint_the_card_so_only_peak_verdicts_do(scheme, grid):
    quantifier = IonChannel(217.0, IonRole.QUANTIFIER)
    qualifier = IonChannel(
        147.0, IonRole.QUALIFIER, ordinal=1, expected_ratio=0.4, ratio_tolerance=0.25
    )

    def assessment(sample, status, ratio, passed):
        qc = IdentityQcResult(
            status=status, quantifier_area=100.0, observed_rt=7.09, rt_error=0.0,
            rt_passed=True, qualifier_ratios=(QualifierRatioResult(qualifier, ratio, passed),),
            reasons=(),
        )
        pair = qualifier_pair((quantifier, qualifier), qc, error=None)
        return IdentitySampleAssessment(sample, qc, pair, None)

    identity = IdentityAssessmentSet(
        "Pyruvate",
        (quantifier, qualifier),
        (
            assessment("Found", IdentityStatus.SUPPORTED, 0.41, True),
            assessment("Missing", IdentityStatus.NOT_DETECTED, None, None),
        ),
    )
    grid.plot_compound("Pyruvate", ["Found", "Missing"], identity=identity)
    tiles = {name: plot.parent() for name, plot in _plots(grid).items()}
    [badge] = _badge_labels(tiles["Missing"])
    assert badge.text() == "Not detected"

    def card(name):  # a point on the card's own fill, above the caption
        return tiles[name].grab().toImage().pixelColor(16, 3)

    pill = badge.grab().toImage().pixelColor(2, badge.height() // 2)
    assert theme.contrast(badge.palette().color(badge.foregroundRole()), pill) >= 4.5
    assert pill != card("Missing") and card("Missing") == card("Found") == theme.color("surface")
    for name in ("Found", "Missing"):
        chart = tiles[name].chart_view.chart()
        assert not chart.isPlotAreaBackgroundVisible()
        # A Not detected tile's traces are the evidence to inspect, never faded.
        assert {series.opacity() for series in chart.series()} == {1.0}

    grid.apply_peak_verdicts({"Missing": PeakVerdict.REJECTED})
    assert [label.text() for label in _badge_labels(tiles["Missing"])] == [
        "Marked bad", "Not detected"
    ]
    assert card("Missing").name() == verdict_colours(PeakVerdict.REJECTED).tint.name()


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


def test_density_toggle_is_one_tab_stop_that_arrow_keys_switch(grid, qapp):
    grid.show()
    qapp.processEvents()
    changed = []
    grid.density_changed.connect(changed.append)
    compact, comfortable = (grid.findChild(QToolButton, f"density_{key}") for key in ("compact", "comfortable"))
    assert (compact.focusPolicy(), comfortable.focusPolicy()) == (Qt.NoFocus, Qt.TabFocus)
    comfortable.setFocus()
    QTest.keyClick(comfortable, Qt.Key_Left)
    assert grid.density() == "compact" and changed == ["compact"]
    assert compact.isChecked() and compact.hasFocus()
    assert (compact.focusPolicy(), comfortable.focusPolicy()) == (Qt.TabFocus, Qt.NoFocus)
    QTest.keyClick(compact, Qt.Key_Right)
    assert grid.density() == "comfortable" and comfortable.hasFocus()
    # The View menu sets it through the same method.
    grid.set_density("compact")
    assert compact.isChecked() and changed == ["compact", "comfortable", "compact"]


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


def test_a_qualifier_the_method_cannot_check_is_one_header_note_not_a_badge_per_tile(grid):
    quantifier = IonChannel(116.0, IonRole.QUANTIFIER)
    checked = IonChannel(147.0, IonRole.QUALIFIER, ordinal=1, expected_ratio=0.4, ratio_tolerance=0.25)
    # Serine's qualifier 2: in the method, but with no expected ratio.
    unchecked = IonChannel(73.0, IonRole.QUALIFIER, ordinal=2)

    def assessment(sample, passed):
        qc = IdentityQcResult(
            status=IdentityStatus.NOT_ASSESSED if passed else IdentityStatus.REVIEW_REQUIRED,
            quantifier_area=100.0, observed_rt=7.09, rt_error=0.0, rt_passed=True,
            qualifier_ratios=(
                QualifierRatioResult(checked, 0.41 if passed else 0.9, passed),
                QualifierRatioResult(unchecked, 0.2, None),
            ),
            reasons=(),
        )
        pair = qualifier_pair((quantifier, checked, unchecked), qc, error=None)
        return IdentitySampleAssessment(sample, qc, pair, None)

    samples = ["Sample_01", "Sample_04_ratio_fail", "Sample_05"]
    identity = IdentityAssessmentSet(
        "Serine",
        (quantifier, checked, unchecked),
        tuple(assessment(name, name != "Sample_04_ratio_fail") for name in samples),
    )
    grid.plot_compound("Serine", samples, identity=identity)
    tiles = {name: plot.parent() for name, plot in _plots(grid).items()}
    assert {name: [b.text() for b in _badge_labels(t)] for name, t in tiles.items()} == {
        "Sample_01": [], "Sample_04_ratio_fail": ["QC fail"], "Sample_05": [],
    }
    assert grid.qc_note.isVisibleTo(grid)
    assert QTextDocumentFragment.fromHtml(grid.qc_note.text()).toPlainText().replace("\xa0", " ") == (
        "Qualifier 2 is not assessed: the compound list gives it no expected ratio. "
        "See Fix a missing qualifier ratio."
    )
    links = []
    grid.guide_requested.connect(links.append)
    grid.qc_note.linkActivated.emit("01_user_guide.md#fix-a-missing-qualifier-ratio")
    assert links == ["01_user_guide.md#fix-a-missing-qualifier-ratio"]

    grid.plot_compound("Serine", samples)
    assert not grid.qc_note.isVisibleTo(grid)

    # Glycine: its only qualifier has no expected ratio, so nothing is assessed.
    qc = IdentityQcResult(
        status=IdentityStatus.NOT_ASSESSED, quantifier_area=100.0, observed_rt=7.09,
        rt_error=0.0, rt_passed=True, qualifier_ratios=(QualifierRatioResult(unchecked, 0.2, None),),
        reasons=(),
    )
    glycine = IdentityAssessmentSet(
        "Glycine",
        (quantifier, unchecked),
        tuple(
            IdentitySampleAssessment(name, qc, qualifier_pair((quantifier, unchecked), qc, error=None), None)
            for name in samples
        ),
    )
    grid.plot_compound("Glycine", samples, identity=glycine)
    assert grid.qc_note.isVisibleTo(grid)
    assert QTextDocumentFragment.fromHtml(grid.qc_note.text()).toPlainText().replace("\xa0", " ") == (
        "Qualifier 2 is not assessed: the compound list gives it no expected ratio. "
        "See Fix a missing qualifier ratio."
    )


def test_activated_sample_is_selected_focused_and_scrolled_to(grid, qapp):
    grid.plot_compound("Pyruvate", [f"S{i:02d}" for i in range(24)])
    grid.resize(600, 300)
    grid.show()
    QTest.qWait(100)
    # Widening re-flows the tiles into three columns, but only once a timer fires.
    grid.resize(900, 300)
    assert grid.select_sample("S12")
    QTest.qWait(100)
    assert grid.get_selected_samples() == ["S12"]
    assert grid.review_lead().sample_name == "S12"
    tile = _plots(grid)["S12"].parent()
    viewport = grid.findChild(QScrollArea).viewport()
    top = tile.mapTo(viewport, tile.rect().topLeft()).y()
    assert 0 <= top and top + tile.height() <= viewport.height()


def test_replotting_the_same_compound_keeps_selection_and_focus(grid, opened):
    samples = ["S1", "S2", "S3", "S4"]
    grid.plot_compound("Valine", samples)
    grid.select_samples(["S2", "S4"])
    for _ in range(4):
        QTest.keyClick(grid, Qt.Key_Right)
    emitted = []
    grid.selection_changed.connect(emitted.append)

    grid.set_y_scale_policy(YScalePolicy.SHARED_EXTRACT)
    assert grid.get_selected_samples() == ["S2", "S4"]
    assert grid.review_lead().sample_name == "S4"
    assert {name: plot.is_selected for name, plot in _plots(grid).items()} == {
        "S1": False, "S2": True, "S3": False, "S4": True
    }
    assert grid.selection_summary.text().endswith("2 of 4 selected")

    # A curve-fit change re-plots through plot_compound with the same arguments.
    grid.plot_compound("Valine", samples)
    assert grid.get_selected_samples() == ["S2", "S4"]
    assert emitted == []
    # Every tile is now a reused one; its signals still reach the grid once.
    QTest.mouseDClick(_plots(grid)["S1"].viewport(), Qt.LeftButton)
    assert opened == [("Valine", "S1")]

    grid.plot_compound("Leucine", ["S1", "S2", "S3"])
    assert grid.get_selected_samples() == []
    assert not any(plot.is_selected for plot in _plots(grid).values())


def test_replotting_drops_only_the_samples_no_longer_shown(grid):
    grid.plot_compound("Valine", ["S1", "S2", "S3", "S4"])
    grid.select_samples(["S2", "S4"])
    for _ in range(4):
        QTest.keyClick(grid, Qt.Key_Right)
    emitted = []
    grid.selection_changed.connect(emitted.append)

    grid.plot_compound("Valine", ["S1", "S2", "S3"])
    assert grid.get_selected_samples() == ["S2"]
    assert emitted == [["S2"]]
    # The focused tile is gone, so Space has nothing to toggle.
    QTest.keyClick(grid, Qt.Key_Space)
    assert emitted == [["S2"]]


def test_caption_tooltip_appears_only_when_the_name_is_cut(qapp):
    tile = PlotTile(QWidget())
    tile.set_caption("Sample_05_rt_shift_with_a_long_name")
    try:
        tile.show()
        tile.resize(600, 300)
        qapp.processEvents()
        assert tile.caption.text() == "Sample_05_rt_shift_with_a_long_name"
        assert tile.caption.toolTip() == ""
        tile.resize(90, 300)
        qapp.processEvents()
        assert tile.caption.text() != "Sample_05_rt_shift_with_a_long_name"
        assert tile.caption.toolTip() == "Sample_05_rt_shift_with_a_long_name"
    finally:
        tile.deleteLater()


def test_chip_tooltip_appears_only_when_the_label_is_cut(qapp):
    chip = ChannelChip("Qualifier ion 1 m/z 147", ChannelTraceStyle(label_colors[0], Qt.SolidLine))
    try:
        chip.show()
        chip.resize(chip.sizeHint())
        qapp.processEvents()
        assert chip.toolTip() == ""
        chip.resize(60, chip.height())
        qapp.processEvents()
        assert chip.toolTip() == "Qualifier ion 1 m/z 147"
    finally:
        chip.deleteLater()


@pytest.mark.parametrize("density", ["compact", "comfortable"])
def test_time_labels_never_touch_at_the_narrowest_tile(grid, qapp, density):
    min_width = DENSITY_MIN_TILE[density][0]
    grid.set_density(density)
    grid.resize(1200, 600)
    grid.show()
    grid.plot_compound("Cmp", [f"S{i}" for i in range(30)])
    qapp.processEvents()
    # Four tiles at their narrowest fill the row.
    grid.resize(1200 - grid._grid_viewport()[0] + 4 * min_width + 3 * 8, 600)
    QTest.qWait(150)  # the grid re-lays its tiles shortly after a resize
    plot = _plots(grid)["S0"]
    assert plot.parent().width() <= min_width
    chart = plot.chart()
    axis = chart.axes(Qt.Horizontal)[0]
    metrics = QFontMetricsF(axis.labelsFont())
    edges = []
    for value, text in value_axis_ticks(axis):
        centre = chart.mapToPosition(QPointF(value, 0)).x()
        half = metrics.horizontalAdvance(text) / 2
        edges.append((centre - half, centre + half))
    assert len(edges) >= 2
    assert all(right + 4 < left for (_, right), (left, _) in zip(edges, edges[1:]))


def test_icon_buttons_have_accessible_names(grid):
    assert [b.accessibleName() for b in (grid.docs_button, grid.settings_button)] == [
        "Documentation", "Settings"
    ]
    assert ChartHeader("Peak area").expand_button.accessibleName() == "Enlarge peak area chart"
