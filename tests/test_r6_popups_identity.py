from PySide6.QtWidgets import QVBoxLayout, QWidget

from manic.models.analysis import IonChannel, IonRole
from manic.ui.chart_popup_dialog import ChartPopupDialog
from manic.ui.targeted_qc_widget import (
    SIDEBAR_ROW,
    SIDEBAR_VISIBLE_ROWS,
    TargetedQcWidget,
)
from manic.validation.unlabelled_identity import (
    IdentityAssessmentSet,
    IdentityQcResult,
    IdentitySampleAssessment,
    IdentityStatus,
    QualifierRatioResult,
    QualifierStatus,
    qualifier_pair,
)

Q_ION = IonChannel(174.0, IonRole.QUANTIFIER)
SET = IonChannel(248.0, IonRole.QUALIFIER, ordinal=1, expected_ratio=0.4, ratio_tolerance=0.25)
UNSET = IonChannel(248.0, IonRole.QUALIFIER, ordinal=1)


def _identity(qualifier: IonChannel, names, *, passed=True) -> IdentityAssessmentSet:
    qc = IdentityQcResult(
        status=IdentityStatus.SUPPORTED if passed else IdentityStatus.REVIEW_REQUIRED,
        quantifier_area=100.0,
        observed_rt=7.0,
        rt_error=0.0,
        rt_passed=True,
        qualifier_ratios=(
            QualifierRatioResult(qualifier, 0.41, passed if qualifier.expected_ratio else None),
        ),
        reasons=(),
    )
    channels = (Q_ION, qualifier)
    samples = tuple(
        IdentitySampleAssessment(name, qc, qualifier_pair(channels, qc), None) for name in names
    )
    return IdentityAssessmentSet("Glycine", channels, samples)


def _marks(chart):
    from manic.ui.identity_chart import _CellMark

    return [item for item in chart.childItems() if isinstance(item, _CellMark)]


def test_compound_with_no_expected_ratios_says_so_instead_of_a_grey_grid(qapp):
    identity = _identity(UNSET, ["MM_01", "MM_02"])
    from manic.ui.identity_chart import MISSING_RATIO_STEP as note
    dialog = ChartPopupDialog.for_identity(identity)
    widget = TargetedQcWidget()
    try:
        dialog.show()
        widget.update_results(identity)
        widget.show()
        qapp.processEvents()
        assert dialog.empty_note.text() == note and dialog.empty_note.isVisible()
        assert not dialog._scroll.isVisible() and not dialog.status_legend.isVisible()
        assert dialog.ion_legend.labels()[1] == "Qualifier ion 1 m/z 248   no expected ratio"
        assert widget.note.text() == note and widget.note.isVisible()
        assert not widget._scroll.isVisible() and not widget.key.isVisible()
    finally:
        dialog.deleteLater()
        widget.deleteLater()


def test_absent_cells_are_outlines_and_assessed_grids_stay(qapp):
    from manic.ui import theme

    dialog = ChartPopupDialog.for_identity(_identity(SET, ["S1"]))
    try:
        assert dialog.empty_note.isHidden()
        cells = {
            dialog._identity_binding.cell_for(bar_set).qualifier.status: bar_set
            for bar_set in dialog._identity_binding.bar_sets
        }
        absent = cells[QualifierStatus.ABSENT]
        assert absent.color() == theme.color("surface")
        assert absent.borderColor() == theme.color("border_strong")
        assert cells[QualifierStatus.VALIDATED].color() != theme.color("surface")
    finally:
        dialog.deleteLater()


def test_sidebar_rows_keep_their_marks_and_names_and_scroll(qapp):
    names = [f"Sample_{i:02d}" for i in range(30)]
    widget = TargetedQcWidget()
    try:
        widget.update_results(_identity(SET, names))
        widget.resize(260, 400)
        widget.show()
        qapp.processEvents()
        # The height cap depends on the settled width, so size it once more.
        widget.resize(260, 400)
        qapp.processEvents()
        assert widget.chart_view.height() == 30 * SIDEBAR_ROW
        assert widget._scroll.height() == SIDEBAR_VISIBLE_ROWS * SIDEBAR_ROW
        assert widget._scroll.verticalScrollBar().maximum() > 0
        assert all(mark.isVisible() for mark in _marks(widget.chart))
        assert widget.chart.axes()[1].labelsVisible()
    finally:
        widget.deleteLater()


def test_sidebar_highlights_the_selection_and_keeps_every_row(qapp):
    widget = TargetedQcWidget()
    try:
        widget.update_results(_identity(SET, ["S1", "S2", "S3"]))
        widget.set_highlighted(["S2"])
        assert widget.highlighted_rows() == ["S2"]
        assert list(widget.chart.axes()[1].categories()) == ["S3", "S2", "S1"]
        # A rebuild for new results keeps the selection marked.
        widget.update_results(_identity(SET, ["S1", "S2", "S3"], passed=False))
        assert widget.highlighted_rows() == ["S2"]
        widget.set_highlighted([])
        assert widget.highlighted_rows() == []
    finally:
        widget.deleteLater()


def test_one_sample_leaves_no_band_below_it(qapp):
    host = QWidget()
    layout = QVBoxLayout(host)
    widget = TargetedQcWidget()
    below = QWidget()
    layout.addWidget(widget, 1)
    layout.addWidget(below, 1)
    try:
        widget.update_results(_identity(SET, ["S1"]))
        host.resize(260, 800)
        host.show()
        qapp.processEvents()
        content = widget.key.geometry().bottom()
        assert widget.height() - content <= 8
    finally:
        host.deleteLater()


def test_long_sidebar_names_shorten_to_fit_instead_of_running_off(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFontMetrics

    names = ["MM_01", "Sample_04_ratio_fail", "Sample_05_rt_shift"]
    widget = TargetedQcWidget()
    try:
        widget.update_results(_identity(SET, names))
        widget.resize(200, 260)
        widget.show()
        qapp.processEvents()
        axis = widget.chart.axes(Qt.Vertical)[0]
        shown = list(reversed(axis.categories()))
        assert shown[0] == "MM_01" and len(set(shown)) == 3
        assert shown[1].startswith("Sampl") and shown[1].endswith("fail") and "…" in shown[1]
        metrics = QFontMetrics(axis.labelsFont())
        assert max(metrics.horizontalAdvance(n) for n in shown) <= widget.chart_view.width() * 0.4
        # The cells still carry the full name for the tooltip and the click.
        assert {c.sample_name for c in widget._binding.cells_by_set.values()} == set(names)
    finally:
        widget.deleteLater()
