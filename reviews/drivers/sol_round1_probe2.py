import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path('/Users/couttsj/Documents/_code/pythonMANIC')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
spec = importlib.util.spec_from_file_location('ui_tour', ROOT / 'scripts/ui_tour.py')
tour_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tour_module)
from PySide6.QtCore import QSettings, Qt, QPoint, QPointF, QMimeData, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QMessageBox, QPushButton, QFileDialog, QLabel, QLineEdit, QAbstractSpinBox, QComboBox, QCheckBox, QRadioButton
from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.ui.main_window import MainWindow
from manic.ui.add_compound_dialog import AddCompoundDialog
from manic.ui.dialog_kit import MARKED_ROLE
from manic.utils.utils import apply_app_stylesheet

database.DB_FILE = OUT / 'probe.db'
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(OUT / 'settings'))
app = QApplication(sys.argv)
app.setApplicationName('MANIC review')
app.setOrganizationName('MANIC isolated review round 1')
apply_app_stylesheet(app)
database.init_db()
MainWindow._check_for_updates = lambda self: None
tour = tour_module.Tour(app, OUT, (1600,1000))
results = {}
modals = []
menus = []

def save(widget, name):
    tour.pump(.25)
    widget.grab().save(str(OUT / (name + '.png')))

def menu_info(menu):
    return [{'text':a.text(), 'enabled':a.isEnabled(), 'checked':a.isChecked(), 'shortcut':a.shortcut().toString(), 'submenu':menu_info(a.menu()) if a.menu() else None} for a in menu.actions() if not a.isSeparator()]

def modal_capture(widget):
    widget.show()
    tour.pump(.4)
    name = type(widget).__name__
    modals.append({'class':name, 'title':widget.windowTitle()})
    save(widget, 'live_' + name)
    widget.close()
    return int(QDialog.Rejected)

def menu_capture(menu,*args,**kwargs):
    menus.append(menu_info(menu))
    menu.popup(args[0] if args else QPoint(100,100))
    save(menu,'live_list_context_' + str(len(menus)))
    menu.close()
    return None

QDialog.exec = modal_capture
QMessageBox.exec = modal_capture
QMenu.exec = menu_capture

def step(name, action):
    try:
        results[name] = action()
        print(name, json.dumps(results[name],default=str), flush=True)
    except Exception:
        results[name] = {'ERROR':traceback.format_exc()}
        print(name, results[name], flush=True)
    (OUT / 'probe_results.json').write_text(json.dumps(results,indent=2,default=str))

def active(window):
    window.raise_()
    window.activateWindow()
    app.setActiveWindow(window)
    tour.pump(.2)

def drop(window,path):
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(str(path))])
    enter = QDragEnterEvent(QPoint(900,450),Qt.CopyAction,md,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(window,enter)
    event = QDropEvent(QPointF(900,450),Qt.CopyAction,md,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(window,event)
    return {'enter':enter.isAccepted(),'drop':event.isAccepted()}

def shortcuts():
    active(w)
    w.graph_view.setFocus()
    QTest.keyClick(w,Qt.Key_F,Qt.ControlModifier)
    tour.pump(.15)
    f = w.toolbar.compound_filter
    focused = f.hasFocus()
    QTest.keyClicks(f,'valine')
    tour.pump(.2)
    visible = [w.toolbar.compound_list.item(i).text() for i in range(w.toolbar.compound_list.count()) if not w.toolbar.compound_list.isRowHidden(i)]
    QTest.keyClick(f,Qt.Key_Return)
    tour.pump(.5)
    picked = w.selected_compound_name()
    QTest.keyClick(w,Qt.Key_BracketRight,Qt.ControlModifier)
    tour.pump(.5)
    next_name = w.selected_compound_name()
    QTest.keyClick(w,Qt.Key_BracketLeft,Qt.ControlModifier)
    tour.pump(.5)
    prev_name = w.selected_compound_name()
    save(w,'live_compound_filter')
    f.clear()
    return {'cmd_f_focus':focused,'visible':visible,'enter_picked':picked,'cmd_right':next_name,'cmd_left':prev_name}

def display_menu():
    active(w)
    rows=[]
    for action,checkbox in w.display_actions:
        before=checkbox.isChecked()
        action.trigger()
        tour.pump(.4)
        rows.append({'name':action.text(),'enabled':action.isEnabled(),'before':before,'after':checkbox.isChecked(),'menu_matches':action.isChecked()==checkbox.isChecked()})
        if checkbox.isChecked()!=before:
            action.trigger()
            tour.pump(.4)
    w.toolbar.display_section.set_expanded(True)
    w.toolbar.inspector.ensureWidgetVisible(w.toolbar.display_section)
    save(w,'live_display_controls')
    w.toolbar.display_section.set_expanded(False)
    w.toolbar.inspector.verticalScrollBar().setValue(0)
    return rows

def grid_keys():
    active(w)
    graph=w.graph_view
    graph.clear_selection()
    view=graph._current_plots[0]
    QTest.mouseClick(view.viewport(),Qt.LeftButton,pos=view.viewport().rect().center())
    tour.pump(.2)
    clicked={'selected':graph.get_selected_samples(),'focus':type(app.focusWidget()).__name__}
    QTest.keyClick(app.focusWidget(),Qt.Key_Right)
    QTest.keyClick(app.focusWidget(),Qt.Key_Space)
    tour.pump(.25)
    right={'index':graph._focus_index,'selected':graph.get_selected_samples()}
    QTest.keyClick(app.focusWidget(),Qt.Key_Down)
    QTest.keyClick(app.focusWidget(),Qt.Key_Space)
    tour.pump(.25)
    down={'index':graph._focus_index,'selected':graph.get_selected_samples()}
    save(w,'live_grid_keyboard')
    before=len(modals)
    QTest.keyClick(app.focusWidget(),Qt.Key_Return)
    tour.pump(.3)
    enter=modals[before:]
    active(w)
    graph.setFocus()
    QTest.keyClick(graph,Qt.Key_A,Qt.ControlModifier)
    n_all=len(graph.get_selected_samples())
    QTest.keyClick(graph,Qt.Key_Escape)
    return {'clicked':clicked,'right_space':right,'down_space':down,'enter':enter,'select_all_count':n_all,'escape_count':len(graph.get_selected_samples()),'scope':w.toolbar.integration.apply_btn.text() if hasattr(w.toolbar.integration,'apply_btn') else [b.text() for b in w.toolbar.integration.findChildren(QPushButton)]}

def double_click():
    active(w)
    view=w.graph_view._current_plots[0]
    before=len(modals)
    QTest.mouseDClick(view.viewport(),Qt.LeftButton,pos=view.viewport().rect().center())
    tour.pump(.3)
    return {'opened':modals[before:]}

def plot_menu():
    active(w)
    graph=w.graph_view
    view=graph._current_plots[0]
    graph.select_only_plot(view)
    QTest.mouseClick(view.viewport(),Qt.RightButton,pos=view.viewport().rect().center())
    tour.pump(.2)
    menu=graph._active_context_menu
    info=menu_info(menu)
    save(menu,'live_plot_context')
    focus=next(a for a in menu.actions() if a.text()=='Show Only Selected Samples')
    focus.trigger()
    menu.close()
    tour.pump(.5)
    shown=graph.get_current_samples()
    w.show_all_samples_action.trigger()
    tour.pump(.5)
    return {'items':info,'focused_samples':shown,'show_all_count':len(graph.get_current_samples())}

def list_menus():
    active(w)
    w.toolbar.samples_section.set_expanded(True)
    tour.pump(.2)
    for widget in (w.toolbar.compound_list,w.toolbar.sample_list):
        point=widget.visualItemRect(widget.item(0)).center()
        widget.customContextMenuRequested.emit(point)
    save(w,'live_samples_expanded')
    return menus

def integration_controls():
    t=w.toolbar.integration
    widgets=[{'type':type(x).__name__,'name':x.objectName(),'text':x.text() if hasattr(x,'text') else '', 'enabled':x.isEnabled(),'visible':x.isVisible()} for x in t.findChildren(QWidget) if isinstance(x,(QLineEdit,QPushButton))]
    return widgets

def settings():
    active(w)
    w.settings_action.trigger()
    tour.pump(.4)
    s=w.settings_window
    page=s.page_named('Mass Tolerance')
    s.page_list.setCurrentRow(s._pages.index(page))
    page.spin.setValue(page.spin.value()+.01)
    tour.pump(.2)
    save(s,'live_settings_dirty_mass')
    s.page_list.setCurrentRow(len(s._pages)-1)
    tour.pump(.2)
    save(s,'live_settings_dirty_other')
    pending=s.pending_label.text()
    marked=s.page_list.item(0).data(MARKED_ROLE)
    save_enabled=s.save_button.isEnabled()
    s.pending_label.linkActivated.emit('0')
    tour.pump(.2)
    back=s.stack.currentIndex()
    QTest.mouseClick(s.reset_button,Qt.LeftButton)
    fields={p.title:[{'type':type(x).__name__,'name':x.objectName(),'enabled':x.isEnabled()} for x in p.findChildren(QWidget) if isinstance(x,(QAbstractSpinBox,QComboBox,QCheckBox,QRadioButton))] for p in s._pages}
    s.hide()
    return {'pending_after_switch':pending,'mass_marked':marked,'save_other_page':save_enabled,'link_return_index':back,'pending_after_discard':s.pending_label.text(),'pages':fields}

def add_validation():
    active(w)
    rows=[]
    for mode in (AnalysisMode.LABELLED,AnalysisMode.UNLABELLED):
        d=AddCompoundDialog(w,analysis_mode=mode,taken_names=['Pyruvate'])
        d.show()
        active(d)
        add=next(b for b in d.findChildren(QPushButton) if b.text()=='Add compound')
        QTest.mouseClick(add,Qt.LeftButton)
        tour.pump(.2)
        first={'message':d.validation_message,'focus':app.focusWidget() is d.compound_name,'error_inline':any(l.isVisible() and l.text()==d.validation_message for l in d.findChildren(QLabel))}
        d.compound_name.setText('Pyruvate')
        d.retention_time.setValue(4.5)
        if mode is AnalysisMode.LABELLED:
            d.mass0.setValue(174)
        else:
            d.quantifier_mz.setValue(174)
            d.qualifier1_mz.setValue(99)
        QTest.mouseClick(add,Qt.LeftButton)
        tour.pump(.2)
        duplicate=d.validation_message
        save(d,'live_add_invalid_' + mode.value)
        d.compound_name.setText('Review test compound')
        cleared=d.validation_message
        QTest.mouseClick(add,Qt.LeftButton)
        tour.pump(.2)
        rows.append({'mode':mode.value,'empty':first,'duplicate':duplicate,'clears_on_edit':cleared,'valid_result':d.result(),'size':[d.width(),d.height()],'screen':[d.screen().availableGeometry().width(),d.screen().availableGeometry().height()]})
        d.close()
    return rows

def resize_and_scroll():
    active(w)
    rows=[]
    for size in ((1280,800),(1024,650)):
        w.resize(*size)
        tour.pump(.5)
        rows.append({'window':[w.width(),w.height()],'shape':w.graph_view._grid_shape,'plot_size':[w.graph_view._current_plots[0].parent().width(),w.graph_view._current_plots[0].parent().height()]})
        save(w,'live_' + str(size[0]))
    w.resize(1600,1000)
    tour.pump(.3)
    graph=w.graph_view
    graph.setFocus()
    graph._focus_index=0
    for _ in range(len(graph._current_plots)-1):
        QTest.keyClick(graph,Qt.Key_Right)
    tour.pump(.2)
    rows.append({'last_focus':graph._focused_plot().sample_name,'scroll':graph._scroll.verticalScrollBar().value()})
    return rows

def unlabelled():
    global w
    w=tour_module.make_window(tour,AnalysisMode.UNLABELLED)
    active(w)
    list_drop=drop(w,tour_module.UNLABELLED / 'compounds.csv')
    tour.pump(.2)
    raw=drop(w,tour_module.UNLABELLED)
    tour.wait_for(lambda:w.cdf_data_loaded)
    tour.pump(.7)
    w.toolbar.compound_list.setCurrentRow(2)
    tour.pump(.7)
    w.toolbar.targeted_qc.header.expand_button.click()
    w.toolbar.total_abundance.header.expand_button.click()
    w.settings_action.trigger()
    tour.pump(.2)
    pages=[p.title for p in w.settings_window._pages]
    w.settings_window.hide()
    save(w,'live_unlabelled')
    return {'list_drop':list_drop,'raw_drop':raw,'settings_pages':pages,'menus':[{'menu':a.text(),'items':menu_info(a.menu())} for a in w.menuBar().actions() if a.menu()]}

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer
QMenu.exec = lambda menu,*a,**k: menus.append(menu_info(menu))
QMenu.exec_ = QMenu.exec
w = tour_module.make_window(tour,AnalysisMode.LABELLED)
active(w)
tour_module.load(tour,tour_module.LABELLED)
step('list_context_menus',list_menus)
step('integration_controls',integration_controls)
step('settings_dirty_pages',settings)
step('add_inline_validation',add_validation)
step('resize_reflow',resize_and_scroll)
step('unlabelled_drop_and_controls',unlabelled)
active(w)
w.toolbar.compound_filter.setText('valine')
tour.pump(.2)
w.toolbar.compound_list.setCurrentRow(2)

def observe():
    focus=app.focusWidget()
    value={'compound':w.selected_compound_name(),'focus_type':type(focus).__name__,'focus_name':focus.objectName() if focus else None,'filter':w.toolbar.compound_filter.text(),'selected':w.graph_view.get_selected_samples(),'active':w.isActiveWindow(),'modal':type(app.activeModalWidget()).__name__,'pages': [p.title for p in w.settings_window._pages] if w.settings_window else None}
    (OUT/'live_state.json').write_text(json.dumps(value,indent=2))
    command=OUT/'command.py'
    if command.exists():
        code=command.read_text()
        command.unlink()
        try:
            exec(code,globals())
        except Exception:
            print(traceback.format_exc(),flush=True)
timer=QTimer()
timer.timeout.connect(observe)
timer.start(500)
print('READY_FOR_NATIVE',flush=True)
app.exec()
