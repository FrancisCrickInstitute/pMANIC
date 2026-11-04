"""Round 1 reviewer driver: checks new interactions and round-0 parity. Run from repo root."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path.cwd()
spec = importlib.util.spec_from_file_location("ui_tour", ROOT / "scripts" / "ui_tour.py")
ut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ut)

from PySide6.QtCore import QMimeData, QPoint, QPointF, QSettings, Qt, QUrl  # noqa
from PySide6.QtGui import QDropEvent, QDragEnterEvent  # noqa
from PySide6.QtTest import QTest  # noqa
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QMessageBox, QPushButton  # noqa

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.append(s)


def main():
    from manic.models import database

    scratch = Path(tempfile.mkdtemp(prefix="manic-r1-opus-"))
    database.DB_FILE = scratch / "tour.db"
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(scratch))
    from manic.models.database import init_db
    from manic.io.compound_reader import read_compound
    from manic.models.analysis import AnalysisMode
    from manic.ui.main_window import MainWindow
    from manic.utils.utils import apply_app_stylesheet

    app = QApplication(sys.argv)
    app.setApplicationName("MANIC")
    app.setOrganizationName("MANIC UI Tour")
    apply_app_stylesheet(app)
    init_db()
    MainWindow._check_for_updates = lambda self: None
    tour = ut.Tour(app, OUT, (1600, 1000))
    captured = []

    def cap(self, *a, **k):
        captured.append(type(self).__name__)
        tour.capture_modal(self)
        return 0

    QDialog.exec = cap
    QMessageBox.exec = cap
    QMenu.exec = lambda self, *a, **k: cap(self)

    def shot(name, widget=None):
        tour.index += 1
        tour.step = name
        tour.save(widget or tour.window)

    # ---- drag and drop on an empty window
    w = ut.make_window(tour, AnalysisMode.LABELLED)
    tour.pump(0.5)
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(str(ut.LABELLED / "compounds.csv"))])
    pos = QPointF(800, 500)
    enter = QDragEnterEvent(QPoint(800, 500), Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
    w.dragEnterEvent(enter)
    log("drop: dragEnter accepted =", enter.isAccepted())
    drop = QDropEvent(pos, Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
    w.dropEvent(drop)
    tour.pump(1.0)
    log("drop: compounds loaded =", w.compound_data_loaded, w.toolbar.compound_list.real_count())
    shot("after_drop_compounds")

    # status row clicks before raw data: raw-data row -> load request (patch action)
    hits = []
    w.load_cdf_action.triggered.connect(lambda *_: hits.append("cdf"))
    # don't actually open dialog: QFileDialog is static; patch
    from PySide6.QtWidgets import QFileDialog
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
    w.toolbar.loaded_data.raw_data_row.clicked.emit()
    tour.pump(0.3)
    log("status row 'Raw data' click triggers load action:", hits)

    # drop folder
    md2 = QMimeData()
    md2.setUrls([QUrl.fromLocalFile(str(ut.LABELLED))])
    w.dropEvent(QDropEvent(pos, Qt.CopyAction, md2, Qt.LeftButton, Qt.NoModifier))
    tour.wait_for(lambda: w.cdf_data_loaded)
    tour.pump(2.0)
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog) and widget.isVisible():
            widget.close()
    log("drop folder: raw loaded =", w.cdf_data_loaded)

    tb = w.toolbar
    comp = tb.get_selected_compound()
    log("baseline: compound", comp, "db =", read_compound(comp).baseline_correction,
        "checkbox =", tb.baseline_checkbox.isChecked(),
        "summary =", tb.display_section.summary.text())
    tb.display_section.set_expanded(True)
    tour.pump(0.5)
    shot("display_expanded")
    # switch compounds and come back
    for row in range(0, 5):
        tb.compound_list.setCurrentRow(row)
        tour.pump(1.2)
        c = tb.get_selected_compound()
        log("  compound", c, "db_baseline", read_compound(c).baseline_correction,
            "checkbox", tb.baseline_checkbox.isChecked(), "summary", tb.display_section.summary.text())
    # toggle shared y-scale then peak scale; summary consistency
    tb.shared_yscale_checkbox.click(); tour.pump(1.0)
    log("after shared click: shared", tb.shared_yscale_checkbox.isChecked(),
        "peak", tb.selected_peak_yscale_checkbox and tb.selected_peak_yscale_checkbox.isChecked(),
        "summary", tb.display_section.summary.text())
    if tb.selected_peak_yscale_checkbox and tb.selected_peak_yscale_checkbox.isEnabled():
        tb.selected_peak_yscale_checkbox.click(); tour.pump(1.0)
        log("after peak click: shared", tb.shared_yscale_checkbox.isChecked(),
            "peak", tb.selected_peak_yscale_checkbox.isChecked(),
            "summary", tb.display_section.summary.text())
        tb.selected_peak_yscale_checkbox.click(); tour.pump(1.0)
    else:
        log("peak scale checkbox disabled/absent")
    if tb.shared_yscale_checkbox.isChecked():
        tb.shared_yscale_checkbox.click(); tour.pump(1.0)
    tb.display_section.set_expanded(False)
    tb.compound_list.setCurrentRow(0)
    tour.pump(1.2)

    # ---- keyboard: Cmd+F (Ctrl in Qt on mac == Command)
    w.activateWindow(); tour.pump(0.3)
    QTest.keyClick(w, Qt.Key_F, Qt.ControlModifier); tour.pump(0.3)
    log("Cmd+F via keyClick: focus =", type(app.focusWidget()).__name__ if app.focusWidget() else None,
        app.focusWidget() is tb.compound_filter or app.focusWidget() in tb.compound_filter.findChildren(object))
    w.find_compound_action.trigger(); tour.pump(0.3)
    fw = app.focusWidget()
    log("find action trigger: focus widget", type(fw).__name__ if fw else None, getattr(fw, "objectName", lambda: "")())
    QTest.keyClicks(fw, "leu"); tour.pump(0.5)
    log("filter 'leu' count label:", tb.compound_count_label.text(), "current:", tb.get_selected_compound())
    QTest.keyClick(fw, Qt.Key_Down); tour.pump(0.8)
    log("Down in filter -> current:", tb.get_selected_compound(), "focus:", type(app.focusWidget()).__name__)
    QTest.keyClick(app.focusWidget(), Qt.Key_Return); tour.pump(1.5)
    log("Return -> current:", tb.get_selected_compound(), "focus:", type(app.focusWidget()).__name__)
    shot("filter_leu")
    # Cmd+] next within filter
    before = tb.get_selected_compound()
    QTest.keyClick(w, Qt.Key_BracketRight, Qt.ControlModifier); tour.pump(1.2)
    after_key = tb.get_selected_compound()
    w.next_compound_action.trigger(); tour.pump(1.2)
    after_action = tb.get_selected_compound()
    log("Cmd+] keyClick:", before, "->", after_key, "| action trigger ->", after_action)
    w.previous_compound_action.trigger(); tour.pump(1.2)
    log("Cmd+[ action ->", tb.get_selected_compound())
    # Esc in filter clears?
    tb.compound_filter.setFocus(); QTest.keyClick(tb.compound_filter, Qt.Key_Escape); tour.pump(0.3)
    log("Esc in filter: text=", repr(tb.compound_filter.text()), "count", tb.compound_count_label.text())
    tb.compound_filter.setText(""); tour.pump(0.3)
    tb.compound_list.setCurrentRow(0); tour.pump(1.2)

    # ---- grid keyboard
    gv = w.graph_view
    gv.setFocus(); tour.pump(0.3)
    log("grid focusPolicy", gv.focusPolicy(), "hasFocus", gv.hasFocus())
    QTest.keyClick(gv, Qt.Key_A, Qt.ControlModifier); tour.pump(0.8)
    log("Cmd+A selected:", len(gv.get_selected_samples()))
    shot("grid_select_all")
    QTest.keyClick(gv, Qt.Key_Escape); tour.pump(0.8)
    log("Esc selected:", len(gv.get_selected_samples()))
    QTest.keyClick(gv, Qt.Key_Right); QTest.keyClick(gv, Qt.Key_Right); QTest.keyClick(gv, Qt.Key_Down); tour.pump(0.5)
    fp = gv._focused_plot()
    log("arrows focused:", fp.sample_name if fp else None)
    QTest.keyClick(gv, Qt.Key_Space); tour.pump(0.8)
    log("Space selected:", gv.get_selected_samples())
    shot("grid_keyboard_focus")
    n = len(captured)
    QTest.keyClick(gv, Qt.Key_Return); tour.pump(1.5)
    log("Return opened:", captured[n:])
    # does clicking a tile with the mouse give the grid keyboard focus?
    w.toolbar.compound_filter.setFocus(); tour.pump(0.2)
    views = ut.charts(w)
    v = views[6]
    QTest.mouseClick(v.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(60, 60)); tour.pump(0.6)
    log("after mouse click on tile: focus", type(app.focusWidget()).__name__ if app.focusWidget() else None,
        "selected", gv.get_selected_samples())
    QTest.keyClick(app.focusWidget() or gv, Qt.Key_A, Qt.ControlModifier); tour.pump(0.6)
    log("Cmd+A after mouse click (focus wherever it is):", len(gv.get_selected_samples()))
    gv.clear_selection(); tour.pump(0.5)
    # double-click
    n = len(captured)
    QTest.mouseDClick(v.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(60, 60)); tour.pump(1.5)
    log("double-click opened:", captured[n:], "selected after dclick:", gv.get_selected_samples())
    gv.clear_selection(); tour.pump(0.5)

    # ---- sample list semantics: deselect one sample
    tb.samples_section.set_expanded(True); tour.pump(0.5)
    sl = tb.sample_list
    log("sample list selected:", len(sl.selectedItems()), "of", sl.count())
    sl.item(0).setSelected(False); tour.pump(1.5)
    log("after deselect first: summary", tb.samples_section.summary.text(), "grid count", len(ut.charts(w)))
    shot("samples_one_hidden")
    sl.item(0).setSelected(True); tour.pump(1.5)

    # compound list right-click menu
    cl = tb.compound_list
    item_rect = cl.visualItemRect(cl.item(1))
    cl._show_context_menu(item_rect.center()); tour.pump(0.4)
    popup = QApplication.activePopupWidget()
    if popup:
        tour.index += 1; tour.step = "compound_context"; tour.save(popup, "__menu"); popup.close()
    log("compound context captured:", [c for c in captured[-2:]])

    # density compact
    gv.set_density("compact"); tour.pump(1.5)
    shot("density_compact_1600")
    w.resize(1280, 800); tour.pump(1.5)
    shot("density_compact_1280")
    gv.set_density("comfortable"); tour.pump(1.0)
    w.resize(1024, 700); tour.pump(1.5)
    shot("narrow_1024x700")
    w.resize(1600, 1000); tour.pump(1.5)

    # ---- settings dirty
    w.open_settings_window(); tour.pump(0.6)
    sw = w.settings_window
    page = sw.page_named("Mass Tolerance")
    page.spin.setValue(page.spin.value() + 0.1); tour.pump(0.3)
    sw.page_list.setCurrentRow(5 if sw.page_list.count() > 5 else 1); tour.pump(0.4)
    shot("settings_dirty_other_page", sw)
    sw.page_list.setCurrentRow(0); tour.pump(0.4)
    shot("settings_dirty_page", sw)
    log("settings title:", sw.windowTitle(), "modified", sw.isWindowModified(),
        "save enabled", sw.save_button.isEnabled(), "pending:", sw.pending_label.text()[:120])
    log("save btn geom", sw.save_button.geometry().getRect(), "reset btn geom", sw.reset_button.geometry().getRect())
    sw._reset_current(); tour.pump(0.3)
    sw.close()

    # ---- add compound validation
    from manic.ui.add_compound_dialog import AddCompoundDialog
    d = AddCompoundDialog(w, AnalysisMode.LABELLED, taken_names={"Pyruvate"})
    d.show(); tour.pump(0.5)
    d._on_ok(); tour.pump(0.4)
    shot("add_compound_empty_submit", d)
    d.compound_name.setText("Pyruvate"); d.retention_time.setValue(5.0); d.mass0.setValue(100.0)
    d._on_ok(); tour.pump(0.4)
    shot("add_compound_duplicate", d)
    log("add compound validation message:", d.validation_message)
    d.close()

    # unlabelled identity popup + problem compound
    w2 = ut.make_window(tour, AnalysisMode.UNLABELLED)
    ut.load(tour, ut.UNLABELLED)
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog) and widget.isVisible():
            widget.close()
    w2.toolbar.compound_list.setCurrentRow(2); tour.pump(1.5)
    n = len(captured)
    w2.toolbar.targeted_qc._show_popup_chart(); tour.pump(0.8)
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog) and widget.isVisible():
            tour.index += 1; tour.step = "identity_popup"; tour.save(widget, "__" + type(widget).__name__); widget.close()
    shot("unlabelled_valine")
    views = ut.charts(w2)
    w2.graph_view._show_context_menu(views[16].mapToGlobal(QPoint(50, 50)), views[16]); tour.pump(0.4)
    popup = QApplication.activePopupWidget()
    if popup:
        tour.index += 1; tour.step = "unl_context"; tour.save(popup, "__menu"); popup.close()

    w2._skip_close_guard = True
    w2.close()
    (OUT / "log.txt").write_text("\n".join(LOG))
    return 0


if __name__ == "__main__":
    sys.exit(main())
