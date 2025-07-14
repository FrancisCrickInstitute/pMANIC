import math
from typing import List

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QGridLayout, QWidget

from manic.io.compound_reader import read_compound
from manic.io.sample_reader import list_active_samples
from manic.processors.eic_processing import get_eics_for_compound


class GraphView(QWidget):
    """
    Re-implements the old grid-of-charts look with pyqtgraph,
    but fetches data via the new processors/io stack.
    """

    # ---- colour helpers -------------------------------------------------
    _PEN_C = pg.mkPen(color=(139, 0, 0), width=1)  # dark-red EIC curve
    _PEN_RT = pg.mkPen(color=(0, 0, 0), width=1)  # retention-time line
    _PEN_LOFF = pg.mkPen(
        color=(255, 140, 0), width=1, style=Qt.DashLine
    )  # lOffset guide
    _PEN_ROFF = pg.mkPen(
        color=(138, 43, 226), width=1, style=Qt.DashLine
    )  # rOffset guide

    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QGridLayout(self)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # throttle resize events – avoids constant redraw while user resizes
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._update_graph_sizes)

    # ------------------------------------------------------------------ #
    #  public slot called from MainWindow                                #
    # ------------------------------------------------------------------ #
    def plot_compound(self, compound_name: str) -> None:
        """
        Build one mini-plot per active sample for the selected *compound*.
        """
        self._clear_layout()

        samples: List[str] = list_active_samples()
        if not samples:
            return

        eics = get_eics_for_compound(compound_name, samples)  # new pipeline
        num = len(eics)
        cols = math.ceil(math.sqrt(num))
        rows = math.ceil(num / cols)

        for i, eic in enumerate(eics):
            plot_widget = self._build_plot(eic)
            self._layout.addWidget(plot_widget, i // cols, i % cols)

        self._update_graph_sizes()

    # ------------------------------------------------------------------ #
    #  internals                                                         #
    # ------------------------------------------------------------------ #
    def _build_plot(self, eic) -> pg.PlotWidget:
        """
        Create a PlotWidget with curve + three guide lines + small title.
        """
        compound = read_compound(eic.compound_name)

        w = pg.PlotWidget(background="w")
        w.hideAxis("right")
        w.hideAxis("top")

        # curve
        w.plot(eic.time, eic.intensity, pen=self._PEN_C)

        # axes style
        for ax in ("bottom", "left"):
            axis = w.getAxis(ax)
            axis.setPen(pg.mkPen("k"))
            axis.setTextPen("k")
            axis.setTickFont(pg.QtGui.QFont("Arial", 8))
            axis.setGrid(False)

        # y-range
        y_max = float(np.max(eic.intensity))
        w.setYRange(0, y_max)

        # x-range (±0.2 min around RT)
        rt = compound.retention_time
        xmin = max(rt - 0.2, eic.time.min())
        xmax = min(rt + 0.2, eic.time.max())
        w.setXRange(xmin, xmax)

        # guide lines
        w.addLine(x=rt, pen=self._PEN_RT)
        w.addLine(x=rt - compound.loffset, pen=self._PEN_LOFF)
        w.addLine(x=rt + compound.roffset, pen=self._PEN_ROFF)

        # sample name – small label in upper-right
        label = pg.TextItem(
            eic.sample_name,
            anchor=(1, 0),  # right-top corner
            color=(0, 0, 0),
        )
        w.addItem(label)
        label.setPos(xmax, y_max)

        return w

    def _update_graph_sizes(self) -> None:
        """
        Resize every PlotWidget so the grid fills the parent without scrollbars.
        """
        if self._layout.count() == 0:
            return

        cols = self._layout.columnCount() or 1
        rows = self._layout.rowCount() or 1

        avail_w = self.width() - (cols + 1) * self._layout.spacing()
        avail_h = self.height() - (rows + 1) * self._layout.spacing()

        w = avail_w // cols
        h = avail_h // rows

        for i in range(self._layout.count()):
            widget = self._layout.itemAt(i).widget()
            widget.setFixedSize(w, h)

    def _clear_layout(self) -> None:
        while self._layout.count():
            w = self._layout.takeAt(0).widget()
            if w:
                w.setParent(None)

    # throttle rapid resize events
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._resize_timer.start(100)
