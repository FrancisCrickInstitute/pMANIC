import numpy as np
from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from manic.ui.chart_popup_dialog import ChartPopupDialog

# The sidebar charts hand popups their samples bottom to top.
NAMES = [f"Bio_{i:03d}" for i in range(30, 0, -1)]


def _abundance():
    return ChartPopupDialog(
        "total_abundance", "Total Abundance", np.linspace(3e6, 1e5, 30), NAMES
    )


def test_row_keys_work_from_the_focus_a_real_open_gives(qapp):
    dialog = _abundance()
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
        seen["first"] = (dialog._current_row, dialog._row_marker.isVisible())
        press(Qt.Key_End)
        press(Qt.Key_Up)
        seen["before_return"] = dialog._current_row
        press(Qt.Key_Return)

    QTimer.singleShot(0, drive)
    QTimer.singleShot(5000, dialog.reject)
    try:
        result = dialog.exec()
        assert seen["focus"] is dialog.chart_view
        assert seen["first"] == (0, True)
        assert seen["before_return"] == 28
        assert activated == ["Bio_029"]
        assert result == QDialog.Accepted
    finally:
        dialog.deleteLater()


def test_return_first_shows_the_row_it_would_open(qapp):
    dialog = _abundance()
    activated = []
    dialog.sample_activated.connect(activated.append)
    try:
        dialog.show()
        qapp.processEvents()
        QTest.keyClick(dialog.chart_view, Qt.Key_Return)
        assert activated == [] and dialog._current_row == 0 and dialog._row_marker.isVisible()
        QTest.keyClick(dialog.chart_view, Qt.Key_Home)
        QTest.keyClick(dialog.chart_view, Qt.Key_Enter)
        assert activated == ["Bio_001"]
    finally:
        dialog.deleteLater()


def test_footer_names_the_keys(qapp):
    dialog = _abundance()
    dialog.sample_activated.connect(lambda _name: None)
    try:
        dialog.show()
        qapp.processEvents()
        assert dialog._hint.text() == "Click a sample, or ↑↓ and Return, to show its plot"
    finally:
        dialog.deleteLater()


def test_value_axis_and_unit_stay_in_view_at_the_bottom_of_a_long_list(qapp):
    dialog = _abundance()
    try:
        dialog.resize(820, 420)
        dialog.show()
        qapp.processEvents()
        bar = dialog._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        qapp.processEvents()
        assert bar.maximum() > 0
        axis = dialog.pinned_axis
        assert axis.isVisible() and axis.title() == "×10⁶"
        # Pinned outside the scrolled rows, just above them.
        assert axis.geometry().bottom() < dialog._scroll.geometry().top()
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
        bottom = dialog.chart_view.mapTo(dialog._scroll.viewport(), dialog.chart_view.mapFromScene(last))
        assert 0 <= bottom.y() <= dialog._scroll.viewport().height()
    finally:
        dialog.deleteLater()


def test_ratio_rows_with_no_ratio_show_a_dash_and_say_why(qapp):
    # Bottom to top: Bio_003 has no area, Bio_002 a NaN row, Bio_001 a ratio.
    data = np.array([[0.0, 0.0], [np.nan, np.nan], [0.4, 0.6]])
    original = data.copy()
    dialog = ChartPopupDialog(
        "isotopologue_ratios", "Label Incorporation", data, ["Bio_003", "Bio_002", "Bio_001"]
    )
    try:
        dialog.show()
        qapp.processEvents()
        assert dialog.value_label_texts() == ["—", "—"]
        assert dialog.row_note(0) is None
        assert dialog.row_note(1) == (
            "Bio_002\nNo ratio: this sample has no integrated peak area for this compound."
        )
        assert dialog.row_note(2).startswith("Bio_003\nNo ratio")
        # Display only: the arrays the sidebar and exports share are untouched.
        assert dialog.data is data
        np.testing.assert_array_equal(data, original)
    finally:
        dialog.deleteLater()


def test_hovering_a_blank_ratio_row_shows_its_note(qapp, monkeypatch):
    shown = []
    monkeypatch.setattr(
        "manic.ui.chart_popup_dialog.QToolTip.showText",
        lambda _pos, text, *_args: shown.append(text),
    )
    data = np.array([[0.0, 0.0], [0.4, 0.6]])
    dialog = ChartPopupDialog("isotopologue_ratios", "Label Incorporation", data, ["Bio_002", "Bio_001"])
    try:
        dialog.show()
        qapp.processEvents()
        series = dialog.chart.series()[0]
        point = dialog.chart.mapToScene(dialog.chart.mapToPosition(QPointF(0.5, 0), series))
        pos = QPointF(dialog.chart_view.mapFromScene(point))
        qapp.sendEvent(
            dialog.chart_view.viewport(),
            QMouseEvent(QEvent.MouseMove, pos, pos, Qt.NoButton, Qt.NoButton, Qt.NoModifier),
        )
        assert shown and shown[-1].startswith("Bio_002\nNo ratio")
    finally:
        dialog.deleteLater()
