import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QScrollArea,
    QToolTip,
)

from manic.ui import theme
from manic.ui.chart_popup_dialog import ChartPopupDialog

# The sidebar charts hand popups their samples bottom to top.
SIDEBAR_ORDER = ["Std_MM_02", "Bio_002", "Bio_001"]
NAMES = [f"Bio_{i:03d}" for i in range(30, 0, -1)]


def _abundance(values, names):
    return ChartPopupDialog("total_abundance", "Total Abundance", np.array(values), names)


def _ratios(data, names):
    return ChartPopupDialog("isotopologue_ratios", "Label Incorporation", np.array(data), names)


def _value_labels(dialog) -> list[str]:
    """The value printed beside each row, top to bottom."""
    items = [item for item in dialog.chart.childItems() if isinstance(item, QGraphicsSimpleTextItem)]
    return [item.text() for item in sorted(items, key=lambda item: item.pos().y())]


def _marked_row(dialog) -> str | None:
    """The sample whose row carries the accent outline."""
    for item in dialog.chart.childItems():
        if (
            isinstance(item, QGraphicsRectItem)
            and item.isVisible()
            and item.pen().color() == theme.color("accent")
        ):
            value = dialog.chart.mapToValue(item.rect().center(), dialog.chart.series()[0])
            return dialog.chart.axes(Qt.Vertical)[0].categories()[round(value.y())]
    return None


def _row_point(dialog, row: int, x: float = 0.05):
    """A point on a row (top to bottom), in the chart view's viewport."""
    category = len(dialog.row_names()) - 1 - row
    point = dialog.chart.mapToPosition(QPointF(x, category), dialog.chart.series()[0])
    return dialog.chart_view.mapFromScene(dialog.chart.mapToScene(point))


def test_both_popups_read_top_down_in_grid_order_with_values_paired(qapp):
    abundance = _abundance([300.0, 200.0, 100.0], SIDEBAR_ORDER)
    ratios = _ratios([[0.3, 0.7], [0.2, 0.8], [0.1, 0.9]], SIDEBAR_ORDER)
    low = _abundance([9100.0, 0.6, 0.0, 11300.0], ["A", "B", "C", "D"])
    try:
        for dialog in (abundance, low):
            dialog.show()
        qapp.processEvents()
        grid_order = ["Bio_001", "Bio_002", "Std_MM_02"]
        assert abundance.row_names() == ratios.row_names() == grid_order
        assert _value_labels(abundance) == ["1.00", "2.00", "3.00"]
        m0 = ratios.chart.series()[0].barSets()[0]
        axis = ratios.chart.axes(Qt.Vertical)[0]
        assert {axis.categories()[i]: m0.at(i) for i in range(3)} == {
            "Std_MM_02": 0.3, "Bio_002": 0.2, "Bio_001": 0.1
        }

        bars = low.chart.series()[0].barSets()[0]
        axis = low.chart.axes(Qt.Vertical)[0]
        by_name = {name: bars.at(i) for i, name in enumerate(axis.categories())}
        assert (by_name["A"], by_name["C"], by_name["D"]) == (0.91, 0.0, 1.13)
        assert low.row_names() == ["D", "C", "B", "A"]
        assert _value_labels(low) == ["1.13", "—", "<0.01", "0.91"]
    finally:
        for dialog in (abundance, ratios, low):
            dialog.deleteLater()


def test_a_sample_with_no_abundance_shows_a_dash_on_a_sane_axis(qapp):
    dialog = _abundance([9100.0, float("nan"), 11300.0], ["A", "B", "C"])
    try:
        dialog.show()
        qapp.processEvents()
        assert _value_labels(dialog) == ["1.13", "—", "0.91"]
        assert dialog.pinned_axis.title() == "×10⁴"
        assert [text for text, _x in dialog.pinned_axis.tick_positions()] == ["0.0", "0.2", "0.4", "0.6", "0.8", "1.0", "1.2"]
    finally:
        dialog.deleteLater()


def test_clicking_a_row_activates_its_sample_and_closes(qapp):
    dialog = _abundance([300.0, 200.0, 100.0], SIDEBAR_ORDER)
    activated = []
    dialog.sample_activated.connect(activated.append)
    try:
        dialog.show()
        qapp.processEvents()
        QTest.mouseClick(dialog.chart_view.viewport(), Qt.LeftButton, pos=_row_point(dialog, 1))
        assert activated == ["Bio_002"]
        assert dialog.result() == QDialog.Accepted and not dialog.isVisible()
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize(
    "make",
    [
        lambda: _abundance(np.linspace(3e6, 1e5, 30), NAMES),
        lambda: _ratios(np.tile([0.3, 0.7], (30, 1)), NAMES),
    ],
    ids=["abundance", "ratios"],
)
def test_row_keys_work_from_the_focus_a_real_open_gives(qapp, make):
    dialog = make()
    activated = []
    dialog.sample_activated.connect(activated.append)
    seen = {}

    def press(key):
        QTest.keyClick(QApplication.focusWidget(), key)

    def drive():
        # The window takes focus once it is activated, a moment after exec().
        if QApplication.focusWidget() is None:
            QTimer.singleShot(10, drive)
            return
        seen["focus"] = QApplication.focusWidget()
        press(Qt.Key_Down)
        seen["first"] = _marked_row(dialog)
        press(Qt.Key_End)
        press(Qt.Key_Up)
        seen["before_return"] = _marked_row(dialog)
        press(Qt.Key_Return)

    QTimer.singleShot(0, drive)
    QTimer.singleShot(5000, dialog.reject)
    try:
        result = dialog.exec()
        assert seen["focus"] is dialog.chart_view
        assert seen["first"] == "Bio_001"
        assert seen["before_return"] == "Bio_029"
        assert activated == ["Bio_029"]
        assert result == QDialog.Accepted
    finally:
        dialog.deleteLater()


def test_return_first_shows_the_row_it_would_open(qapp):
    dialog = _abundance(np.linspace(3e6, 1e5, 30), NAMES)
    activated = []
    dialog.sample_activated.connect(activated.append)
    try:
        dialog.show()
        qapp.processEvents()
        assert _marked_row(dialog) is None
        QTest.keyClick(dialog.chart_view, Qt.Key_Return)
        assert activated == [] and _marked_row(dialog) == "Bio_001"
        QTest.keyClick(dialog.chart_view, Qt.Key_Home)
        QTest.keyClick(dialog.chart_view, Qt.Key_Enter)
        assert activated == ["Bio_001"]
    finally:
        dialog.deleteLater()


def test_value_axis_and_unit_stay_in_view_at_the_bottom_of_a_long_list(qapp):
    dialog = _abundance(np.linspace(3e6, 1e5, 30), NAMES)
    try:
        dialog.resize(820, 420)
        dialog.show()
        qapp.processEvents()
        scroll = dialog.findChild(QScrollArea)
        bar = scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        qapp.processEvents()
        assert bar.maximum() > 0
        axis = dialog.pinned_axis
        assert axis.isVisible() and axis.title() == "×10⁶"
        # Pinned outside the scrolled rows, just above them.
        assert axis.geometry().bottom() < scroll.geometry().top()
        assert not dialog.chart.axes(Qt.Horizontal)[0].labelsVisible()
        # Each tick label sits over the gridline of its own value.
        series = dialog.chart.series()[0]
        for text, x in axis.tick_positions():
            point = dialog.chart.mapToScene(
                dialog.chart.mapToPosition(QPointF(float(text), 0), series)
            )
            in_view = dialog.chart_view.mapFromScene(point)
            assert abs(axis.mapFrom(dialog, dialog.chart_view.mapTo(dialog, in_view)).x() - x) <= 1
        assert [text for text, _x in axis.tick_positions()] == ["0.0", "0.5", "1.0", "1.5", "2.0", "2.5", "3.0"]
        # The last rows really are on screen while the axis is.
        last = dialog.chart.mapToScene(dialog.chart.mapToPosition(QPointF(0, 0), series))
        bottom = dialog.chart_view.mapTo(scroll.viewport(), dialog.chart_view.mapFromScene(last))
        assert 0 <= bottom.y() <= scroll.viewport().height()
    finally:
        dialog.deleteLater()


def test_ratio_rows_with_no_ratio_show_a_dash_and_say_why(qapp, monkeypatch):
    shown = []
    monkeypatch.setattr(QToolTip, "showText", lambda _pos, text, *_args: shown.append(text))
    # Bottom to top: Bio_003 has no area, Bio_002 a NaN row, Bio_001 a ratio.
    data = np.array([[0.0, 0.0], [np.nan, np.nan], [0.4, 0.6]])
    original = data.copy()
    dialog = ChartPopupDialog(
        "isotopologue_ratios", "Label Incorporation", data, ["Bio_003", "Bio_002", "Bio_001"]
    )

    def hover(row):
        pos = QPointF(_row_point(dialog, row, x=0.5))
        qapp.sendEvent(
            dialog.chart_view.viewport(),
            QMouseEvent(QEvent.MouseMove, pos, pos, Qt.NoButton, Qt.NoButton, Qt.NoModifier),
        )

    try:
        dialog.show()
        qapp.processEvents()
        assert _value_labels(dialog) == ["—", "—"]
        hover(0)
        assert not any("No ratio" in text for text in shown)
        hover(1)
        assert shown[-1] == (
            "Bio_002\nNo ratio: this sample has no integrated peak area for this compound."
        )
        hover(2)
        assert shown[-1] == (
            "Bio_003\nNo ratio: this sample has no integrated peak area for this compound."
        )
        # Display only: the arrays the sidebar and exports share are untouched.
        np.testing.assert_array_equal(data, original)
    finally:
        dialog.deleteLater()
