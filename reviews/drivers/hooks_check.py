"""Popup rows activate plots and the checklist names the loaded compound list."""
import sys, tempfile
from pathlib import Path
ROOT = Path.cwd(); sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import ui_tour
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog, QLabel
from manic.models import database
scratch = Path(tempfile.mkdtemp()); database.DB_FILE = scratch / "t.db"
QSettings.setDefaultFormat(QSettings.IniFormat); QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(scratch))
from manic.models.database import init_db
from manic.models.analysis import AnalysisMode
from manic.ui.main_window import MainWindow
from manic.utils.utils import apply_app_stylesheet
app = QApplication([]); apply_app_stylesheet(app); init_db(); MainWindow._check_for_updates = lambda self: None
tour = ui_tour.Tour(app, scratch, (1600, 1000))
w = ui_tour.make_window(tour, AnalysisMode.LABELLED); ui_tour.load(tour, ui_tour.LABELLED)
popups = []
QDialog.exec = lambda self: (popups.append(self), self.show(), 0)[2]
w.toolbar.compound_list.setCurrentRow(0); tour.pump(1.5)
ok = True
for chart in (w.toolbar.total_abundance, w.toolbar.isotopologue_ratios):
    chart._show_popup_chart(); tour.pump(0.4)
    d = popups[-1]; names = d.row_names()
    active = d._rows_active()
    d.sample_activated.emit(names[4]); tour.pump(0.6)
    sel = w.graph_view.get_selected_samples()
    print(type(chart).__name__, "rows active:", active, "picked", names[4], "-> selected", sel)
    ok &= active and sel == [names[4]]
w.show_post_load_checklist(); tour.pump(0.5)
texts = " | ".join(l.text() for l in w._post_load_checklist.findChildren(QLabel))
named = "compounds.csv" in texts
print("checklist names compounds.csv:", named)
print("HOOKS OK" if ok and named else "HOOKS FAIL")
