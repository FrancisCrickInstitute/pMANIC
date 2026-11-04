import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from manic.ui.chart_popup_dialog import ChartPopupDialog

# The sidebar charts hand popups their samples bottom to top.
SIDEBAR_ORDER = ["Std_MM_02", "Bio_002", "Bio_001"]


def _popups():
    abundance = ChartPopupDialog(
        "total_abundance", "Total Abundance", np.array([300.0, 200.0, 100.0]), SIDEBAR_ORDER
    )
    ratios = ChartPopupDialog(
        "isotopologue_ratios",
        "Label Incorporation",
        np.array([[0.3, 0.7], [0.2, 0.8], [0.1, 0.9]]),
        SIDEBAR_ORDER,
    )
    return abundance, ratios


def test_both_popups_read_top_down_in_grid_order_with_values_paired(qapp):
    abundance, ratios = _popups()
    try:
        grid_order = ["Bio_001", "Bio_002", "Std_MM_02"]
        assert abundance.row_names() == ratios.row_names() == grid_order
        assert abundance.value_label_texts() == ["1.00", "2.00", "3.00"]
        m0 = ratios.chart.series()[0].barSets()[0]
        axis = ratios.chart.axes(Qt.Vertical)[0]
        assert {axis.categories()[i]: m0.at(i) for i in range(3)} == {
            "Std_MM_02": 0.3, "Bio_002": 0.2, "Bio_001": 0.1
        }
    finally:
        abundance.deleteLater()
        ratios.deleteLater()


def _row_centre(dialog, row: int):
    category = len(dialog.row_names()) - 1 - row
    point = dialog.chart.mapToPosition(QPointF(0.05, category), dialog.chart.series()[0])
    return dialog.chart_view.mapFromScene(dialog.chart.mapToScene(point))


def test_clicking_a_row_activates_its_sample_and_closes(qapp):
    abundance, _ratios = _popups()
    activated = []
    abundance.sample_activated.connect(activated.append)
    try:
        abundance.show()
        qapp.processEvents()
        assert "Click a sample" in abundance._hint.text()
        QTest.mouseClick(abundance.chart_view.viewport(), Qt.LeftButton, pos=_row_centre(abundance, 1))
        assert activated == ["Bio_002"]
        assert abundance.result() == QDialog.Accepted and not abundance.isVisible()
    finally:
        abundance.deleteLater()
        _ratios.deleteLater()


def test_arrow_keys_and_enter_activate_a_row(qapp):
    _abundance, ratios = _popups()
    activated = []
    ratios.sample_activated.connect(activated.append)
    try:
        ratios.show()
        qapp.processEvents()
        QTest.keyClick(ratios, Qt.Key_Down)
        QTest.keyClick(ratios, Qt.Key_Down)
        QTest.keyClick(ratios, Qt.Key_Down)
        QTest.keyClick(ratios, Qt.Key_Up)
        assert ratios._row_marker.isVisible()
        QTest.keyClick(ratios, Qt.Key_Return)
        assert activated == ["Bio_002"]
        assert not ratios.isVisible()
    finally:
        _abundance.deleteLater()
        ratios.deleteLater()


def test_rows_stay_inert_when_nothing_listens(qapp):
    abundance, _ratios = _popups()
    try:
        abundance.show()
        qapp.processEvents()
        QTest.mouseClick(abundance.chart_view.viewport(), Qt.LeftButton, pos=_row_centre(abundance, 0))
        assert abundance.isVisible()
        assert "Click" not in abundance._hint.text()
    finally:
        abundance.close()
        abundance.deleteLater()
        _ratios.deleteLater()
