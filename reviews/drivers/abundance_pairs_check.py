"""Every abundance bar (sidebar and popup) must carry its own sample's value."""
import sys, tempfile
from pathlib import Path
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import ui_tour
from PySide6.QtCore import QSettings
from PySide6.QtCharts import QBarCategoryAxis, QAbstractBarSeries
from PySide6.QtWidgets import QApplication, QDialog
from manic.models import database
scratch = Path(tempfile.mkdtemp()); database.DB_FILE = scratch / "t.db"
QSettings.setDefaultFormat(QSettings.IniFormat); QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(scratch))
from manic.models.database import init_db
from manic.models.analysis import AnalysisMode
from manic.ui.main_window import MainWindow
from manic.utils.utils import apply_app_stylesheet
from manic.io.data_provider import DataProvider as P
app = QApplication([]); apply_app_stylesheet(app); init_db(); MainWindow._check_for_updates = lambda self: None
tour = ui_tour.Tour(app, scratch, (1600, 1000))
w = ui_tour.make_window(tour, AnalysisMode.LABELLED); ui_tour.load(tour, ui_tour.LABELLED)
popups = []
QDialog.exec = lambda self: (popups.append(self), self.show(), 0)[2]

def pairs(chart):
    axis = next(a for a in chart.axes() if isinstance(a, QBarCategoryAxis))
    series = next(s for s in chart.series() if isinstance(s, QAbstractBarSeries))
    bars = series.barSets()[0]
    return {axis.categories()[i]: bars.at(i) for i in range(bars.count())}

bad = 0
for row in (0, 4, 7):
    w.toolbar.compound_list.setCurrentRow(row); tour.pump(2.0)
    compound = w.toolbar.compound_list.currentItem().text()
    ta = w.toolbar.total_abundance
    side = pairs(ta.chart_view.chart())
    truth = {n: P(use_legacy_integration=w.use_legacy_integration).get_compound_total_area(n, compound) for n in side}
    scale = max(truth.values()) / max(side.values())
    off = [n for n in side if abs(side[n] * scale - truth[n]) > 0.03 * max(truth.values())]
    ta._show_popup_chart(); tour.pump(0.5)
    pop = pairs(popups[-1].chart); pscale = max(truth.values()) / max(pop.values())
    poff = [n for n in pop if abs(pop[n] * pscale - truth[n]) > 0.03 * max(truth.values())]
    print("    misses:", [(n, round(side[n]*scale), round(truth[n])) for n in off])
    print(f"{compound}: sidebar {len(side)-len(off)}/{len(side)} right, popup {len(pop)-len(poff)}/{len(pop)} right")
    bad += len(off) + len(poff)
print("MISMATCHES", bad)
sys.exit(1 if bad else 0)
