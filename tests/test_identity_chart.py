import pytest
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QFontMetrics, QTextDocumentFragment
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from manic.models.analysis import IonChannel, IonRole
from manic.ui import theme
from manic.ui.chart_popup_dialog import ChartPopupDialog
from manic.ui.colors import QUALIFIER_GREEN, QUALIFIER_RED
from manic.ui.targeted_qc_widget import TargetedQcWidget
from manic.validation.unlabelled_identity import (
    IdentityAssessmentSet,
    IdentityQcResult,
    IdentitySampleAssessment,
    IdentityStatus,
    QualifierRatioResult,
    qualifier_pair,
)

Q_ION = IonChannel(217.0, IonRole.QUANTIFIER)
V1 = IonChannel(147.0, IonRole.QUALIFIER, ordinal=1, expected_ratio=0.4, ratio_tolerance=0.25)
LONG = [f"Sample_{i:02d}" for i in range(30)]


def _qualifier(ordinal, ratio=None, tolerance=None):
    return IonChannel(
        100.0 + ordinal, IonRole.QUALIFIER, ordinal=ordinal,
        expected_ratio=ratio, ratio_tolerance=tolerance,
    )


def _identity(names, *, failed=(), qualifiers=(V1,)) -> IdentityAssessmentSet:
    """``names`` top to bottom; checkable qualifiers pass, or fail for the ``failed`` samples."""
    channels = (Q_ION, *qualifiers)

    def qc(passed: bool) -> IdentityQcResult:
        return IdentityQcResult(
            status=IdentityStatus.SUPPORTED if passed else IdentityStatus.REVIEW_REQUIRED,
            quantifier_area=100.0,
            observed_rt=7.0,
            rt_error=0.0,
            rt_passed=True,
            qualifier_ratios=tuple(
                QualifierRatioResult(
                    q,
                    0.41 if passed else 0.9,
                    passed if q.expected_ratio is not None and q.ratio_tolerance is not None else None,
                )
                for q in qualifiers
            ),
            reasons=(),
        )

    samples = []
    for name in names:
        result = qc(name not in failed)
        samples.append(IdentitySampleAssessment(name, result, qualifier_pair(channels, result), None))
    return IdentityAssessmentSet("Pyruvate", channels, tuple(samples))


def _settle(widget, width=260, height=400):
    widget.resize(width, height)
    widget.show()
    for _ in range(5):
        QApplication.processEvents()
    return widget


def _mark_items(chart):
    return [item for item in chart.childItems() if isinstance(item, QGraphicsSimpleTextItem)]


def _marks(chart) -> list[tuple[str, bool]]:
    return sorted((item.text(), item.isVisible()) for item in _mark_items(chart))


def _row_name(chart, point) -> str:
    value = chart.mapToValue(point, chart.series()[0])
    return chart.axes(Qt.Vertical)[0].categories()[round(value.y())]


def _rows(chart) -> dict[str, list[tuple[str, str, str]]]:
    """Each row top to bottom: (mark, fill, border) per qualifier column."""
    series = chart.series()[0]
    names = chart.axes(Qt.Vertical)[0].categories()
    marks = {}
    for item in _mark_items(chart):
        value = chart.mapToValue(item.pos() + item.boundingRect().center(), series)
        marks[(int(value.x()), round(value.y()))] = item.text()
    rows = {name: [] for name in reversed(names)}
    for bar_set in series.barSets():
        row = [bar_set.at(i) for i in range(bar_set.count())].index(1.0)
        cells = rows[names[row]]
        cells.append((marks[(len(cells), row)], bar_set.color().name(), bar_set.borderColor().name()))
    return rows


def _highlighted(widget) -> list[str]:
    """Rows outlined in the accent colour, top to bottom."""
    outlines = [
        item for item in widget.chart.childItems()
        if isinstance(item, QGraphicsRectItem) and item.pen().color() == theme.color("accent")
    ]
    outlines.sort(key=lambda item: item.rect().top())
    return [_row_name(widget.chart, item.rect().center()) for item in outlines]


def _rows_in_view(widget) -> list[str]:
    scroll = widget.findChild(QScrollArea)
    top = scroll.verticalScrollBar().value()
    bottom = top + scroll.viewport().height()
    rows = {}
    for item in _mark_items(widget.chart):
        rect = item.sceneBoundingRect()
        y_top = widget.chart_view.mapFromScene(rect.topLeft()).y()
        if top <= y_top and y_top + rect.height() <= bottom:
            rows[_row_name(widget.chart, item.pos() + item.boundingRect().center())] = True
    return list(rows)


def _plain(label) -> str:
    return QTextDocumentFragment.fromHtml(label.text()).toPlainText().replace("\xa0", " ")


def test_every_identity_cell_carries_a_visible_state_mark(qapp):
    identity = _identity(["S1", "S2", "S3"], failed=("S2", "S3"))
    dialog = ChartPopupDialog.for_identity(identity)
    widget = TargetedQcWidget()
    try:
        _settle(dialog, 820, 400)
        widget.update_results(identity)
        _settle(widget)
        green, red = QUALIFIER_GREEN.name(), QUALIFIER_RED.name()
        surface, outline = theme.color("surface").name(), theme.color("border_strong").name()
        # Qualifier 2 is not in the method: an outlined empty slot, not a grey fill.
        expected = {
            "S1": [("✓", green, surface), ("–", surface, outline)],
            "S2": [("✕", red, surface), ("–", surface, outline)],
            "S3": [("✕", red, surface), ("–", surface, outline)],
        }
        for chart in (dialog.chart, widget.chart):
            assert _rows(chart) == expected
            assert all(shown for _mark, shown in _marks(chart))
            assert chart.axes(Qt.Vertical)[0].labelsVisible()

        assert dialog.windowTitle() == "Identity — MANIC"
        assert dialog.compound_title.text() == "Pyruvate"
        assert dialog.subtitle.text() == "Identity · Q ion m/z 217 · 3 samples"
        # The column headers name the qualifiers, so there are no chips.
        assert dialog.ion_legend.labels() == []
        assert [text for text, _x in dialog.pinned_axis.tick_positions()] == [
            "Qualifier 1\nm/z 147   expected 0.400  ±25%",
            "Qualifier 2\nnot in the method",
        ]
        assert [text for text, _x in widget.columns.tick_positions()] == ["Qualifier 1", "Qualifier 2"]

        assert widget.header.detail.text() == "2 samples failed"
        key = "Qualifier cells  ■ ✓ Validated 1 ■ ✕ Failed 2 ■ – Absent 3"
        assert _plain(widget.key) == _plain(dialog.status_legend) == key
        assert widget.key.toolTip() == (
            "Counts are qualifier cells: one per sample for each qualifier ion.\n"
            "No verdict (grey): 3 absent, 0 not assessed, 0 unavailable."
        )
    finally:
        dialog.deleteLater()
        widget.deleteLater()


def test_rebuilding_the_grid_replaces_its_marks(qapp):
    widget = TargetedQcWidget()
    try:
        widget.update_results(_identity(["S1", "S2"], failed=("S2",)))
        assert widget.header.detail.text() == "1 sample failed"
        widget.update_results(_identity(["S1"]))
        assert [text for text, _shown in _marks(widget.chart)] == ["–", "✓"]
        assert widget.header.detail.text() == ""
        widget.clear()
        assert _marks(widget.chart) == []
    finally:
        widget.deleteLater()


def test_identity_popup_row_selects_the_sample_through_the_qc_widget(qapp):
    widget = TargetedQcWidget()
    activated = []
    widget.sample_activated.connect(activated.append)
    seen = {}

    def drive():
        dialog = QApplication.activeModalWidget()
        if dialog is None or QApplication.focusWidget() is None:
            QTimer.singleShot(10, drive)
            return
        seen["rows"] = dialog.row_names()
        seen["dialog"] = dialog
        QTest.keyClick(QApplication.focusWidget(), Qt.Key_Up)
        QTest.keyClick(QApplication.focusWidget(), Qt.Key_Enter)

    try:
        widget.update_results(_identity(["S1", "S2"], failed=("S2",)))
        QTimer.singleShot(0, drive)
        QTimer.singleShot(5000, lambda: QApplication.activeModalWidget() and QApplication.activeModalWidget().reject())
        widget.header.expand_button.click()
        assert seen["rows"] == ["S1", "S2"]
        assert activated == ["S2"]
        assert not seen["dialog"].isVisible()
    finally:
        widget.deleteLater()


@pytest.mark.parametrize(
    "qualifiers, note, chip",
    [
        (
            (_qualifier(1), _qualifier(2)),
            "Expected ratios come from the compound list. Fill its Qualifier Ratio columns "
            "and reload the list; Help › Check Data Setup lists the reload steps.",
            "Qualifier ion 1 m/z 101   no expected ratio",
        ),
        (
            (_qualifier(1, 0.4), _qualifier(2, 0.2)),
            "Set the missing tolerances in Settings › Qualifier Ratios.",
            "Qualifier ion 1 m/z 101   expected 0.400  no tolerance",
        ),
        (
            (_qualifier(1, 0.4),),
            "Set the missing tolerances in Settings › Qualifier Ratios.",
            "Qualifier ion 1 m/z 101   expected 0.400  no tolerance",
        ),
        (
            (_qualifier(1), _qualifier(2, 0.2)),
            "Expected ratios come from the compound list. Fill its Qualifier Ratio columns "
            "and reload the list; Help › Check Data Setup lists the reload steps. "
            "Set the missing tolerances in Settings › Qualifier Ratios.",
            "Qualifier ion 1 m/z 101   no expected ratio",
        ),
        ((_qualifier(1, 0.4, 0.25), _qualifier(2)), None, None),
    ],
    ids=["no-ratios", "no-tolerances", "one-qualifier-no-tolerance", "one-of-each", "checkable"],
)
def test_compound_with_no_expected_ratios_says_so_instead_of_a_grey_grid(qapp, qualifiers, note, chip):
    identity = _identity(["MM_01", "MM_02"], qualifiers=qualifiers)
    dialog = ChartPopupDialog.for_identity(identity)
    widget = TargetedQcWidget()
    try:
        _settle(dialog, 820, 400)
        widget.update_results(identity)
        _settle(widget)
        grid = note is None
        for shown_note, scroll, key in (
            (dialog.empty_note, dialog.findChild(QScrollArea), dialog.status_legend),
            (widget.note, widget.findChild(QScrollArea), widget.key),
        ):
            assert shown_note.isVisible() is not grid
            assert scroll.isVisible() is grid and key.isVisible() is grid
            if not grid:
                assert shown_note.text().replace("\xa0", " ") == note
        if not grid:
            assert dialog.ion_legend.labels()[1] == chip
    finally:
        dialog.deleteLater()
        widget.deleteLater()


@pytest.mark.parametrize("host_height, rows_in_view", [(120, 2), (900, 8)])
def test_sidebar_rows_keep_their_marks_and_names_and_scroll(qapp, host_height, rows_in_view):
    host = QWidget()
    layout = QVBoxLayout(host)
    widget = TargetedQcWidget()
    layout.addWidget(widget, 1)
    try:
        widget.update_results(_identity(LONG))
        _settle(host, 260, host_height)
        # The height cap depends on the settled width, so size it once more.
        _settle(host, 260, host_height)
        assert len(_rows_in_view(widget)) == rows_in_view
        assert widget.findChild(QScrollArea).verticalScrollBar().maximum() > 0
        assert all(shown for _mark, shown in _marks(widget.chart))
        assert len(_marks(widget.chart)) == 60
        axis = widget.chart.axes(Qt.Vertical)[0]
        assert axis.labelsVisible() and list(axis.categories())[::-1] == LONG
    finally:
        host.deleteLater()


def test_sidebar_highlights_the_selection_and_keeps_every_row(qapp):
    widget = TargetedQcWidget()
    try:
        widget.update_results(_identity(["S1", "S2", "S3"]))
        _settle(widget)
        widget.set_highlighted(["S2"])
        assert _highlighted(widget) == ["S2"]
        assert list(widget.chart.axes(Qt.Vertical)[0].categories()) == ["S3", "S2", "S1"]
        # A rebuild for new results keeps the selection marked.
        widget.update_results(_identity(["S1", "S2", "S3"], failed=("S1", "S2", "S3")))
        assert _highlighted(widget) == ["S2"]
        widget.set_highlighted([])
        assert _highlighted(widget) == []
    finally:
        widget.deleteLater()


def test_one_sample_leaves_no_band_below_it(qapp):
    identity = _identity(["S1"])
    host = QWidget()
    layout = QVBoxLayout(host)
    widget = TargetedQcWidget()
    layout.addWidget(widget, 1)
    layout.addWidget(QWidget(), 1)
    dialog = ChartPopupDialog.for_identity(identity)
    try:
        widget.update_results(identity)
        _settle(host, 260, 800)
        _settle(dialog, 820, 400)
        assert widget.height() - widget.key.geometry().bottom() <= 8
        # A slim strip, not a slab.
        assert widget.chart_view.height() == 18
        assert dialog.chart_view.height() == 24 and dialog.chart_view.y() == 0
        # The column headers sit above the scrolled rows, not inside them.
        for header, owner in ((dialog.pinned_axis, dialog), (widget.columns, widget)):
            assert [text.split("\n")[0] for text, _x in header.tick_positions()] == [
                "Qualifier 1", "Qualifier 2"
            ]
            scroll = owner.findChild(QScrollArea)
            assert header.isVisible() and header.geometry().bottom() < scroll.geometry().top()
    finally:
        host.deleteLater()
        dialog.deleteLater()


def test_long_sidebar_names_shorten_to_fit_instead_of_running_off(qapp):
    names = ["MM_01", "Sample_04_ratio_fail", "Sample_05_rt_shift"]
    widget = TargetedQcWidget()
    activated = []
    widget.sample_activated.connect(activated.append)
    try:
        widget.update_results(_identity(names))
        _settle(widget, 200, 260)
        axis = widget.chart.axes(Qt.Vertical)[0]
        shown = list(reversed(axis.categories()))
        assert shown[0] == "MM_01" and len(set(shown)) == 3
        assert shown[1].startswith("Sampl") and shown[1].endswith("fail") and "…" in shown[1]
        metrics = QFontMetrics(axis.labelsFont())
        assert max(metrics.horizontalAdvance(n) for n in shown) <= widget.chart_view.width() * 0.4
        # Clicking the shortened row still selects the full sample name.
        point = widget.chart.mapToPosition(QPointF(0.5, 1), widget.chart.series()[0])
        QTest.mouseClick(
            widget.chart_view.viewport(),
            Qt.LeftButton,
            pos=widget.chart_view.mapFromScene(widget.chart.mapToScene(point)),
        )
        assert activated == ["Sample_04_ratio_fail"]
    finally:
        widget.deleteLater()


def test_identity_scrolls_a_selected_row_below_the_fold_into_view(qapp):
    widget = TargetedQcWidget()
    try:
        widget.update_results(_identity(LONG))
        _settle(widget)
        bar = widget.findChild(QScrollArea).verticalScrollBar()
        assert bar.value() == 0
        assert "Sample_25" not in _rows_in_view(widget)
        widget.set_highlighted(["Sample_25"])
        assert _highlighted(widget) == ["Sample_25"]
        assert "Sample_25" in _rows_in_view(widget)
    finally:
        widget.deleteLater()
