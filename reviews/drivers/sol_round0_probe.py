from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path('/Users/couttsj/Documents/_code/pythonMANIC')
OUT = Path(__file__).resolve().parent
STATE = OUT / 'runtime'
STATE.mkdir(exist_ok=True)
tempfile.tempdir = str(STATE)
os.environ['XDG_CACHE_HOME'] = str(STATE / 'cache')
os.environ['XDG_CONFIG_HOME'] = str(STATE / 'config')
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'src'))

spec = importlib.util.spec_from_file_location('ui_tour_review', ROOT / 'scripts/ui_tour.py')
tour_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tour_module)

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QMessageBox, QScrollArea, QToolTip
from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.ui.chart_popup_dialog import ChartPopupDialog
from manic.utils.utils import apply_app_stylesheet

database.DB_FILE = STATE / 'review.db'
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(STATE))
app = QApplication(sys.argv)
app.setApplicationName('MANIC review')
app.setOrganizationName('MANIC independent review')
apply_app_stylesheet(app)
database.init_db()
database.clear_database()
tour_module.MainWindow = None
from manic.ui.main_window import MainWindow
MainWindow._check_for_updates = lambda self: None

tour = tour_module.Tour(app, OUT, (1280, 800))
QDialog.exec = lambda self: tour.capture_modal(self)
QMessageBox.exec = lambda self: tour.capture_modal(self)
QMenu.exec = lambda self, *args: tour.capture_modal(self)
results = {}

def snap(name, widget):
    tour.pump(0.5)
    widget.grab().save(str(OUT / f'{name}.png'))

window = tour_module.make_window(tour, AnalysisMode.UNLABELLED)
snap('extra_empty', window)
results['empty'] = {
    'apply_enabled': window.toolbar.integration.apply_button.isEnabled(),
    'reset_enabled': window.toolbar.integration.restore_button.isEnabled(),
    'sample_list_height': window.toolbar.sample_list.height(),
    'compound_list_height': window.toolbar.compound_list.height(),
    'actions': [
        {'text': action.text(), 'shortcuts': [shortcut.toString() for shortcut in action.shortcuts()]}
        for action in window.findChildren(QAction) if action.text()
    ],
}

window.open_documentation_window()
docs = window.documentation_window
for attempt in range(10):
    tour.pump(1)
    state = []
    docs.web_view.page().runJavaScript('document.body ? document.body.innerText : ""', state.append)
    tour.wait_for(lambda: bool(state), timeout=5)
    if len(state[0] or '') > 100:
        break
results['docs'] = {'body_length': len(state[0] or ''), 'body_start': (state[0] or '')[:600], 'current_file': str(docs.current_file)}
snap('extra_documentation_waited', docs)
docs.close()

tour.index = 1
tour.step = 'extra_unlabelled_load_checklist'
tour_module.load(tour, tour_module.UNLABELLED)
window.toolbar.compound_list.setCurrentRow(2)
tour.pump(1)
snap('extra_valine_compact', window)
views = tour_module.charts(window)
results['loaded'] = {
    'sample_count': window.toolbar.sample_list.count(),
    'compound_count': window.toolbar.compound_list.count(),
    'sample_list_height': window.toolbar.sample_list.height(),
    'compound_list_height': window.toolbar.compound_list.height(),
    'tile_count': len(views),
    'first_tile_size': [views[0].width(), views[0].height()],
    'graph_focus_policy': str(window.graph_view.focusPolicy()),
    'tile_focus_policy': str(views[0].focusPolicy()),
}
first = views[0]
QTest.mouseClick(first.viewport(), Qt.LeftButton, Qt.NoModifier, first.viewport().rect().center())
tour.pump(0.3)
before = window.graph_view.get_selected_samples()
QTest.keyClick(first, Qt.Key_Right)
QTest.keyClick(first, Qt.Key_Space)
tour.pump(0.3)
results['keyboard_grid'] = {'after_click': before, 'after_right_space': window.graph_view.get_selected_samples()}
QTest.mouseClick(first.viewport(), Qt.LeftButton, Qt.NoModifier, first.viewport().rect().center())
tour.pump(0.3)
results['deselect'] = {'selected': window.graph_view.get_selected_samples(), 'integration_title': window.toolbar.integration.title(), 'sample_list_selected': len(window.toolbar.sample_list.selectedItems())}

qc = window.toolbar.targeted_qc
scroll = window.toolbar.findChild(QScrollArea)
scroll.ensureWidgetVisible(qc)
tour.pump(0.4)
chart = qc.chart
area = chart.plotArea()
samples = list(qc._identity.samples)
target = next((s for s in samples if s.sample_name == 'Sample_08_low_is'), samples[0])
display_index = list(reversed(samples)).index(target)
point = QPointF(area.left() + area.width()*0.25, area.bottom() - area.height()*(display_index+0.5)/len(samples))
local = qc.chart_view.mapFromScene(chart.mapToScene(point))
QTest.mouseMove(qc.chart_view.viewport(), local)
tour.pump(0.6)
results['qc_hover'] = {'tooltip': QToolTip.text(), 'target': target.sample_name}
snap('extra_qc_hover', window)
QTest.mouseClick(qc.chart_view.viewport(), Qt.LeftButton, Qt.NoModifier, local)
tour.pump(0.5)
results['qc_click_selection'] = window.graph_view.get_selected_samples()
popup = ChartPopupDialog.for_identity(qc._identity, parent=window)
popup.show()
snap('extra_identity_popup', popup)
popup.close()

window.graph_view.deselect_all_plots()
scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
tour.pump(0.5)
abundance = window.toolbar.total_abundance
popup = ChartPopupDialog('total_abundance', 'Total Abundance', abundance._current_abundances, abundance._current_sample_names, parent=window)
popup.show()
snap('extra_abundance_popup_default', popup)
results['abundance_popup'] = {'plot_area': [popup.chart.plotArea().x(), popup.chart.plotArea().y(), popup.chart.plotArea().width(), popup.chart.plotArea().height()], 'sample_names': popup.sample_names}
popup.resize(1100, 850)
snap('extra_abundance_popup_large', popup)
popup.close()

window.open_settings_window()
settings = window.settings_window
settings.page_named('Mass Tolerance').spin.setValue(0.21)
snap('extra_settings_dirty', settings)
settings.page_list.setCurrentRow(settings.page_list.count()-1)
snap('extra_settings_dirty_other_page', settings)
results['settings_hidden_dirty'] = {'mass_page_dirty': settings.page_named('Mass Tolerance').is_dirty(), 'current_page': settings.heading.text(), 'save_enabled': settings.save_button.isEnabled(), 'footer_hint': settings.hint_label.text()}
settings.page_list.setCurrentRow(0)
settings.reset_button.click()
settings.close()

window._skip_close_guard = True
window.close()
(OUT / 'probe_results.json').write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2), flush=True)
