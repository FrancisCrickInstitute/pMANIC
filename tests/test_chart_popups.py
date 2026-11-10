import gc
import subprocess
import sys
import tempfile

import numpy as np
import pytest
from PySide6.QtCore import QPointF, QSettings, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGraphicsSimpleTextItem,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

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
        # A real zero reads 0; only a sample with no data gets the dash.
        assert _value_labels(low) == ["1.13", "0", "<0.01", "0.91"]
    finally:
        for dialog in (abundance, ratios, low):
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


def _open_and_close_every_popup(scheme: str) -> None:
    """Opens each Summary chart's popup with its enlarge button 30 times, closing it by Esc
    or its Close button, and collects garbage after each close as Python may at any time."""
    from test_chart_summaries import _abundance as summary_abundance, _ratios as summary_ratios
    from test_identity_chart import _identity, _qualifier

    from manic.ui import isotopologue_ratio_widget, total_abundance_widget
    from manic.ui.targeted_qc_widget import TargetedQcWidget
    from manic.utils.utils import set_appearance

    app = QApplication([])
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tempfile.mkdtemp())
    set_appearance(app, scheme)
    total_abundance_widget.peak_area_label = lambda _compound: "Peak area"
    isotopologue_ratio_widget.read_compound_with_session = lambda _compound, _sample: None
    isotopologue_ratio_widget.integrated_display_areas = (
        lambda _time, intensity, _compound, use_corrected: list(intensity.sum(axis=1))
    )
    errors = []

    def report(kind, value, tb):
        errors.append(f"{kind.__name__}: {value}")
        sys.__excepthook__(kind, value, tb)

    sys.excepthook = report

    identity = TargetedQcWidget()
    identity.update_results(_identity(["S1", "S2"], failed=("S2",)))
    # Like Glycine: its qualifiers have no expected ratio, so the popup is a note.
    unassessed = TargetedQcWidget()
    unassessed.update_results(_identity(["S1", "S2"], qualifiers=(_qualifier(1),)))
    charts = [identity, unassessed, summary_abundance(["S1", "S2"]), summary_ratios(["S1", "S2"])]
    host = QWidget()
    row = QHBoxLayout(host)
    for chart in charts:
        row.addWidget(chart)
    host.resize(1200, 500)
    host.show()
    QTest.qWaitForWindowExposed(host)

    opened = 0
    for chart in charts:
        for i in range(30):
            def close(tries=50):
                dialog = QApplication.activeModalWidget()
                if not isinstance(dialog, ChartPopupDialog):
                    if tries:
                        QTimer.singleShot(10, lambda: close(tries - 1))
                    return
                if i % 2:
                    QTest.keyClick(dialog, Qt.Key_Escape)
                else:
                    button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Close")
                    QTest.mouseClick(button, Qt.LeftButton)
                nonlocal opened
                opened += 1

            QTimer.singleShot(0, close)
            QTest.mouseClick(chart.header.expand_button, Qt.LeftButton)
            gc.collect()
            assert not errors, errors
            assert not chart.findChildren(ChartPopupDialog), "a closed popup is left behind"
    print(f"{opened} popups opened and closed")


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_popup_opens_and_closes_thirty_times_without_a_crash(scheme):
    # In a child process, so a crash fails this test instead of ending the run.
    run = subprocess.run(
        [sys.executable, __file__, scheme], capture_output=True, text=True, timeout=600
    )
    assert run.returncode == 0, run.stderr[-4000:]
    assert run.stdout.splitlines()[-1] == "120 popups opened and closed"


if __name__ == "__main__":
    _open_and_close_every_popup(sys.argv[1])
