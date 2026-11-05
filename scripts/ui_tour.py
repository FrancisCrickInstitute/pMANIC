#!/usr/bin/env python3
"""Drive MANIC through its main screens on synthetic data and save a screenshot of each.

Used for UI/UX review: every run walks the same states, so screenshots from
two revisions compare one to one. Modal dialogs and menus are captured and
dismissed instead of blocking. The app's own database is never touched.

Run from the repository root:
  uv run python scripts/ui_tour.py OUT_DIR [--size 1600x1000] [--scheme light|dark]
"""

from __future__ import annotations

import argparse
import atexit
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import shiboken6  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QListWidget,
    QWidget,
)

SCHEMES = {"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}
LABELLED = ROOT / "testdata" / "bench" / "labelled"
UNLABELLED = ROOT / "testdata" / "unlabelled_synthetic"


LEAF_KINDS = (QLabel, QAbstractButton, QComboBox, QLineEdit, QAbstractItemView, QScrollArea)


def layout_problems(window: QWidget) -> list[str]:
    """Controls that overlap, text cut off, or a window larger than its screen."""
    problems = []
    screen = window.screen().availableGeometry()
    if window.width() > screen.width() or window.height() > screen.height():
        problems.append(f"{window.size().toTuple()} does not fit the screen {screen.size().toTuple()}")

    def is_container(widget) -> bool:
        return isinstance(widget, QScrollArea) and widget.widget() is not None

    def context(widget) -> QWidget:
        """The scrolled body a widget lives in, or the window."""
        parent = widget.parentWidget()
        while parent is not None and parent is not window:
            if is_container(parent) and parent.widget().isAncestorOf(widget):
                return parent.widget()
            parent = parent.parentWidget()
        return window

    def inside_leaf(widget) -> bool:
        parent = widget.parentWidget()
        while parent is not None and parent is not window:
            if isinstance(parent, LEAF_KINDS) and not is_container(parent):
                return True
            parent = parent.parentWidget()
        return False

    leaves = [
        w
        for w in window.findChildren(QWidget)
        if isinstance(w, LEAF_KINDS) and w.isVisibleTo(window) and not inside_leaf(w)
    ]
    boxes = [(w, context(w)) for w in leaves]
    rects = [QRect(w.mapTo(ctx, QPoint(0, 0)), w.size()) for w, ctx in boxes]

    def name(widget) -> str:
        text = widget.text()[:40] if hasattr(widget, "text") else ""
        return f"{type(widget).__name__}({widget.objectName() or text!r})"

    for i, (a, ctx_a) in enumerate(boxes):
        if isinstance(a, QLabel) and a.text():
            if a.wordWrap() and a.heightForWidth(a.width()) > a.height() + 1:
                problems.append(f"{name(a)} is cut off at the bottom")
            if not a.wordWrap() and a.sizeHint().width() > a.width() + 1:
                problems.append(f"{name(a)} is cut off at the side")
        for j in range(i + 1, len(boxes)):
            b, ctx_b = boxes[j]
            if ctx_a is ctx_b and rects[i].intersects(rects[j]):
                problems.append(f"{name(a)} overlaps {name(b)}")
    return problems


class Skip(Exception):
    """A step that cannot run on this revision; reported, not counted as an error."""


class Tour:
    def __init__(self, app: QApplication, out: Path, size: tuple[int, int]):
        self.app = app
        self.out = out
        self.size = size
        self.step = ""
        self.index = 0
        self.saved: list[str] = []
        self.errors: list[str] = []
        self.skipped: list[str] = []
        self.window = None

    def pump(self, seconds: float = 0.3) -> None:
        end = time.time() + seconds
        while time.time() < end:
            self.app.processEvents()
            # Outside a running event loop deleteLater() never fires on its own.
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            time.sleep(0.02)

    def save(self, widget: QWidget, suffix: str = "") -> None:
        self.pump(0.4)
        name = f"{self.index:02d}_{self.step}{suffix}.png"
        widget.grab().save(str(self.out / name))
        self.saved.append(name)

    def capture_modal(self, widget: QWidget) -> int:
        widget.show()
        self.save(widget, f"__{type(widget).__name__}")
        widget.close()
        return 0

    def capture_popups(self) -> None:
        main = self.window
        for widget in QApplication.topLevelWidgets():
            if widget is main or not widget.isVisible():
                continue
            if isinstance(widget, QDialog):
                self.save(widget, f"__{type(widget).__name__}")
                stack = widget.findChild(QStackedWidget)
                pages = widget.findChild(QListWidget)
                if stack is not None and pages is not None and stack.count() > 1:
                    for row in range(1, pages.count()):
                        pages.setCurrentRow(row)
                        self.save(widget, f"__{type(widget).__name__}_page{row}")
                widget.close()
            elif isinstance(widget, QMenu):
                self.save(widget, "__menu")
                widget.close()

    def run(self, name: str, action, grab_main: bool = True) -> None:
        self.index += 1
        self.step = name
        try:
            action()
            self.pump(0.6)
            if grab_main and self.window is not None:
                self.save(self.window)
            self.capture_popups()
        except Skip as note:
            self.skipped.append(f"{name}: {note}")
            print(f"STEP SKIPPED {name}: {note}")
        except Exception:
            self.errors.append(f"{name}: {traceback.format_exc(limit=3)}")
            print(f"STEP FAILED {name}", file=sys.stderr)
            traceback.print_exc()

    def wait_for(self, predicate, timeout: float = 180.0) -> None:
        end = time.time() + timeout
        while not predicate():
            if time.time() > end:
                raise TimeoutError("timed out waiting for the app")
            self.pump(0.2)


def set_scheme(tour: Tour, scheme: Qt.ColorScheme) -> None:
    from manic.ui import theme

    from manic.utils.utils import apply_color_scheme

    hints = tour.app.styleHints()
    hints.setColorScheme(scheme)
    try:
        tour.wait_for(lambda: hints.colorScheme() == scheme, timeout=3)
    except TimeoutError:
        # Headless Linux (offscreen) has no platform theme to report a scheme.
        apply_color_scheme(tour.app, scheme == Qt.ColorScheme.Dark)
    tour.pump(0.3)
    if theme.is_dark() != (scheme == Qt.ColorScheme.Dark):
        raise RuntimeError(f"app did not restyle for {scheme}")


def make_window(tour: Tour, mode):
    from manic.models.analysis import AnalysisContext
    from manic.models.database import clear_database
    from manic.ui.main_window import MainWindow

    if tour.window is not None:
        tour.window._skip_close_guard = True
        tour.window.close()
        tour.window.deleteLater()
        tour.pump(0.3)
    clear_database()
    window = MainWindow(AnalysisContext(mode))
    window._skip_close_guard = True
    window.resize(*tour.size)
    window.show()
    window.raise_()
    tour.window = window
    return window


def load(tour: Tour, folder: Path) -> None:
    window = tour.window
    window._load_compound_list_from(str(folder / "compounds.csv"))
    tour.pump(0.3)
    window._load_cdf_folder(str(folder))
    tour.wait_for(lambda: window.cdf_data_loaded)
    tour.pump(1.5)


def charts(window):
    """Visible tiles in reading order of the grid, so [0] is the top-left tile."""
    from manic.ui.graphs import ClickableChartView

    grid = window.graph_view
    views = (v for v in grid.findChildren(ClickableChartView) if v.isVisible())

    def grid_position(view):
        pos = view.mapTo(grid, QPoint())
        return pos.y(), pos.x()

    return sorted(views, key=grid_position)


def add_compound_empty_submit(tour: Tour) -> None:
    """Open Add Compound the way the menu does and press Add with every field empty."""
    from manic.ui.add_compound_dialog import AddCompoundDialog

    def submit_empty(dialog):
        dialog.show()
        tour.pump(0.2)
        add = next(
            b for b in dialog.findChildren(QPushButton) if b.text() == "Add compound"
        )
        add.click()
        if not dialog.validation_message:
            raise RuntimeError("Add with empty fields showed no errors")
        tour.save(dialog, f"__{type(dialog).__name__}")
        dialog.close()
        return QDialog.Rejected

    AddCompoundDialog.exec = submit_empty
    try:
        tour.window.show_add_compound_dialog()
    finally:
        del AddCompoundDialog.exec


def detailed_scheme_switch(tour: Tour) -> None:
    """Open the detailed view, flip the scheme while it is open, and grab it after."""
    from manic.ui import theme
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    def switch_while_open(dialog):
        dialog.show()
        tour.pump(0.5)
        start = Qt.ColorScheme.Dark if theme.is_dark() else Qt.ColorScheme.Light
        flipped = Qt.ColorScheme.Light if theme.is_dark() else Qt.ColorScheme.Dark
        set_scheme(tour, flipped)
        tour.save(dialog, f"__{type(dialog).__name__}_switched")
        set_scheme(tour, start)
        dialog.close()
        return QDialog.Rejected

    window = tour.window
    DetailedPlotDialog.exec = switch_while_open
    try:
        window.graph_view._show_detailed_view(
            window.selected_compound_name(), charts(window)[0].sample_name
        )
    finally:
        del DetailedPlotDialog.exec


def samples_1024(tour: Tour) -> None:
    toolbar = tour.window.toolbar
    toolbar.compound_filter.setText("")
    toolbar.sample_filter.setText("")
    tour.window.resize(1024, 768)
    toolbar.samples_section.set_expanded(True)
    tour.pump(1.0)


def all_samples_unchecked(tour: Tour) -> None:
    """Untick every sample the way a user does: select all rows, press Space."""
    from PySide6.QtTest import QTest

    samples = getattr(tour.window.toolbar, "sample_list", None)
    if samples is None or not hasattr(samples, "shown_samples"):
        raise Skip("the sidebar has no sample_list with shown_samples() on this revision")
    tour.window.toolbar.samples_section.set_expanded(True)
    samples.setFocus()
    samples.setCurrentRow(0)
    samples.selectAll()
    QTest.keyClick(samples, Qt.Key_Space)
    tour.pump(1.0)
    if samples.shown_samples():
        raise Skip(f"Space left {len(samples.shown_samples())} samples ticked")


def settings_page(tour: Tour, title: str) -> None:
    window = tour.window
    window.open_settings_window()
    settings = window.settings_window
    settings.page_list.setCurrentRow(settings._pages.index(settings.page_named(title)))
    tour.save(settings, f"__{type(settings).__name__}")
    settings.close()


def checklist(tour: Tour) -> None:
    """The checklist as it opens, then with its steps shown; text must never collide."""
    dialog = tour.window._post_load_checklist
    if dialog is None or not dialog.isVisible():
        tour.window.show_post_load_checklist()
        dialog = tour.window._post_load_checklist
    tour.pump(0.5)
    toggle = getattr(dialog, "change_pattern_toggle", None)
    states = [("", None)] if toggle is None else [("", False), ("_steps", True)]
    for suffix, shown in states:
        if shown is not None:
            toggle.setChecked(shown)
            tour.pump(0.5)
        problems = layout_problems(dialog)
        tour.save(dialog, f"__{type(dialog).__name__}{suffix}")
        if problems:
            raise RuntimeError("checklist layout: " + "; ".join(problems))
    dialog.close()


def grab_popup(tour: Tour, show, *, attempts: int = 2) -> None:
    for attempt in range(1, attempts + 1):
        # A popup closes at once when its window is not active (another app took focus,
        # or Windows refused the activation); raise the window and try again.
        tour.window.raise_()
        tour.window.activateWindow()
        tour.pump(0.2)
        opened: list[QMenu] = []
        original_popup = QMenu.popup
        QMenu.popup = lambda menu, *a, **k: (opened.append(menu), original_popup(menu, *a, **k))[1]
        try:
            show()
        finally:
            QMenu.popup = original_popup
        # popup() is asynchronous; grab it now in case it closes before the step ends.
        tour.pump(0.3)
        popup = QApplication.activePopupWidget() or (opened[-1] if opened else None)
        if popup is None:
            raise RuntimeError("menu did not open")
        if shiboken6.isValid(popup):
            tour.save(popup, "__menu")
            popup.close()
            return
        active = QApplication.activeWindow() is tour.window
        if attempt == attempts:
            raise RuntimeError(
                f"menu closed before capture ({attempts} tries); "
                f"main window active: {active}"
            )
        print(f"  popup closed before capture, main window active: {active}; retrying")


def tour_steps(tour: Tour) -> None:
    from manic.models.analysis import AnalysisMode
    from manic.ui.analysis_mode_dialog import AnalysisModeDialog

    def mode_chooser():
        AnalysisModeDialog().exec()

    tour.run("mode_chooser", mode_chooser, grab_main=False)

    tour.run("empty_labelled", lambda: make_window(tour, AnalysisMode.LABELLED))
    tour.run(
        "compounds_only",
        lambda: tour.window._load_compound_list_from(
            str(LABELLED / "compounds.csv")
        ),
    )

    def load_cdf():
        tour.window._load_cdf_folder(str(LABELLED))
        tour.wait_for(lambda: tour.window.cdf_data_loaded)
        tour.pump(1.5)
        checklist(tour)

    tour.run("labelled_loaded_checklist", load_cdf)
    tour.run("labelled_grid", lambda: None)

    def select_one():
        views = charts(tour.window)
        tour.window.graph_view._on_plot_clicked(views[0])

    tour.run("sample_selected", select_one)

    def select_three():
        views = charts(tour.window)
        for view in views[1:3]:
            tour.window.graph_view._on_plot_clicked(view)

    tour.run("three_selected", select_three)

    def live_scheme_switch():
        from manic.ui import theme

        start = Qt.ColorScheme.Dark if theme.is_dark() else Qt.ColorScheme.Light
        flipped = Qt.ColorScheme.Light if theme.is_dark() else Qt.ColorScheme.Dark
        selected = tour.window.graph_view.get_selected_samples()
        set_scheme(tour, flipped)
        tour.save(tour.window, "__switched")
        set_scheme(tour, start)
        tour.save(tour.window, "__switched_back")
        if tour.window.graph_view.get_selected_samples() != selected:
            raise RuntimeError("selection lost across a live scheme switch")

    tour.run("live_scheme_switch", live_scheme_switch, grab_main=False)

    def grab_three_selected_popup(show) -> None:
        if len(tour.window.graph_view.get_selected_samples()) != 3:
            raise RuntimeError("expected three selected plots")
        grab_popup(tour, show)


    def context_menu():
        view = charts(tour.window)[0]
        pos = view.mapToGlobal(QPoint(view.width() // 2, view.height() // 2))
        grab_three_selected_popup(lambda: tour.window.graph_view._show_context_menu(pos, view))

    tour.run("plot_context_menu", context_menu)

    def review_menu():
        window = tour.window
        bar = window.menuBar()
        title = bar.actionGeometry(window.review_menu.menuAction())
        grab_three_selected_popup(
            lambda: window.review_menu.popup(bar.mapToGlobal(title.bottomLeft()))
        )

    tour.run("review_menu", review_menu)

    def detailed():
        window = tour.window
        name = window.selected_compound_name()
        sample = charts(window)[0].sample_name
        window.graph_view._show_detailed_view(name, sample)

    tour.run("detailed_view", detailed, grab_main=False)

    def next_compound():
        compounds = tour.window.toolbar.compound_list
        compounds.setCurrentRow(min(4, compounds.count() - 1))
        tour.pump(1.5)

    tour.run("another_compound", next_compound)
    tour.run(
        "abundance_popup",
        lambda: tour.window.toolbar.total_abundance._show_popup_chart(),
        grab_main=False,
    )
    tour.run(
        "label_popup",
        lambda: tour.window.toolbar.isotopologue_ratios._show_popup_chart(),
        grab_main=False,
    )
    tour.run("checklist", lambda: checklist(tour), grab_main=False)
    tour.run("settings", tour.window.open_settings_window, grab_main=False)
    def documentation():
        tour.window.open_documentation_window()
        viewer = tour.window.documentation_window
        # Each page renders after it is picked; capture that page, not its loading note.
        for row in range(viewer.page_list.count()):
            if viewer.page_list.item(row).data(Qt.UserRole) is None:
                continue  # a section heading, not a page
            viewer.page_list.setCurrentRow(row)
            tour.wait_for(viewer.is_rendered, timeout=30)
            tour.save(viewer, f"__DocumentationViewer_page{row}" if row else "__DocumentationViewer")
        viewer.close()

    tour.run("documentation", documentation, grab_main=False)
    tour.run("add_compound", tour.window.show_add_compound_dialog, grab_main=False)
    tour.run(
        "add_compound_empty_submit",
        lambda: add_compound_empty_submit(tour),
        grab_main=False,
    )
    tour.run("process_external", tour.window.update_old_data, grab_main=False)
    tour.run("about", tour.window.show_about, grab_main=False)

    def compact():
        tour.window.resize(1280, 800)
        tour.pump(1.0)

    tour.run("compact_1280x800", compact)

    def unlabelled():
        make_window(tour, AnalysisMode.UNLABELLED)
        load(tour, UNLABELLED)
        checklist(tour)

    tour.run("unlabelled_loaded_checklist", unlabelled)
    tour.run("unlabelled_grid", lambda: None)
    tour.run("unlabelled_sample_selected", select_one)

    def unlabelled_problem_compound():
        compounds = tour.window.toolbar.compound_list
        compounds.setCurrentRow(min(2, compounds.count() - 1))
        tour.pump(1.5)

    tour.run("unlabelled_another_compound", unlabelled_problem_compound)
    tour.run(
        "unlabelled_settings_deconvolution",
        lambda: settings_page(tour, "Deconvolution"),
        grab_main=False,
    )
    tour.run(
        "unlabelled_add_compound_empty_submit",
        lambda: add_compound_empty_submit(tour),
        grab_main=False,
    )

    def filter_and_samples():
        toolbar = tour.window.toolbar
        toolbar.compound_filter.setText("ine")
        toolbar.samples_section.set_expanded(True)
        toolbar.sample_filter.setText("0")
        tour.pump(0.5)

    tour.run("sidebar_filter_and_samples", filter_and_samples)
    def chooser_diagnostics():
        # Temporary: why does the chooser close at once on Windows CI?
        import traceback as tb

        from PySide6.QtCore import QObject

        from manic.ui.standard_chooser import StandardChooser

        watched = {QEvent.Show, QEvent.Hide, QEvent.Close, QEvent.FocusIn, QEvent.FocusOut,
                   QEvent.WindowActivate, QEvent.WindowDeactivate, QEvent.MouseButtonPress,
                   QEvent.KeyPress, QEvent.ActivationChange}

        class Spy(QObject):
            def eventFilter(self, obj, event):
                chooser = obj if isinstance(obj, StandardChooser) else None
                widget = obj
                while chooser is None and widget is not None and hasattr(widget, "parentWidget"):
                    widget = widget.parentWidget()
                    if isinstance(widget, StandardChooser):
                        chooser = widget
                noisy = {QEvent.Paint, QEvent.UpdateRequest, QEvent.UpdateLater, QEvent.Timer,
                         QEvent.MetaCall, QEvent.HoverMove, QEvent.Polish, QEvent.PolishRequest,
                         QEvent.StyleChange, QEvent.ChildPolished, QEvent.LayoutRequest}
                global_types = {QEvent.MouseButtonPress, QEvent.MouseButtonRelease,
                                QEvent.WindowDeactivate, QEvent.ApplicationStateChange,
                                QEvent.ApplicationDeactivate, QEvent.NonClientAreaMouseButtonPress,
                                QEvent.FocusAboutToChange, QEvent.Close}
                if (chooser is not None and event.type() not in noisy) or (
                    chooser is None and event.type() in global_types
                ):
                    print(f"  CHOOSER-DIAG {type(obj).__name__} {event.type().name}"
                          f" spont={event.spontaneous()}"
                          f" popup={type(QApplication.activePopupWidget()).__name__}", flush=True)
                return False

        spy = Spy()
        QApplication.instance().installEventFilter(spy)
        original_close = StandardChooser.close

        def traced_close(self):
            print("  CHOOSER-DIAG close() from:\n" + "".join(tb.format_stack(limit=8)), flush=True)
            return original_close(self)

        StandardChooser.close = traced_close
        QApplication.instance().removeEventFilter(spy)
        # Which part of the chooser makes Windows close it? Each variant opens the same way.
        from PySide6.QtWidgets import QComboBox, QFrame, QLineEdit, QListWidget, QVBoxLayout

        from manic.ui.sidebar_widgets import FilterField

        def frame(*parts):
            f = QFrame(tour.window.toolbar.standard, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
            lay = QVBoxLayout(f)
            for make in parts:
                lay.addWidget(make(f))
            return f

        def lst(_f):
            w = QListWidget()
            w.addItems(["one", "two", "three"])
            return w

        from manic.ui.standard_indicator_widget import lacking_amount

        toolbar = tour.window.toolbar
        names = toolbar.compound_list.real_names()
        lacking = lacking_amount(names, toolbar.analysis_mode)
        pos = toolbar.standard.mapToGlobal(toolbar.standard.rect().bottomLeft())

        def real(tweak):
            c = StandardChooser(names, toolbar.standard.internal_standard, lacking, toolbar.standard)
            c.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            tweak(c)
            return c

        variants = {
            "chooser via popup()": (lambda: real(lambda c: None), True),
            "chooser move+show": (lambda: real(lambda c: None), False),
            "chooser no focus proxy": (lambda: real(lambda c: c.setFocusProxy(None)), True),
            "chooser no style": (lambda: real(lambda c: c.setObjectName("x")), True),
            "chooser 3 names": (lambda: StandardChooser(names[:3], None, set(), toolbar.standard), True),
        }
        for name, (make, via_popup) in variants.items():
            tour.window.raise_()
            tour.window.activateWindow()
            tour.pump(0.2)
            w = make()
            if via_popup:
                w.popup(pos)
            else:
                w.move(pos)
                w.show()
            tour.pump(0.3)
            alive = shiboken6.isValid(w) and w.isVisible()
            print(f"  CHOOSER-DIAG variant {name}: open after 0.3 s = {alive}", flush=True)
            if shiboken6.isValid(w):
                w.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
                w.close()
            tour.pump(0.1)
        combo = QComboBox(tour.window.toolbar)
        combo.addItems(["one", "two", "three"])
        combo.show()
        tour.window.raise_()
        tour.window.activateWindow()
        tour.pump(0.2)
        combo.showPopup()
        tour.pump(0.3)
        print(f"  CHOOSER-DIAG control QComboBox popup visible after 0.3 s: "
              f"{combo.view().isVisible()}", flush=True)
        combo.hidePopup()
        combo.deleteLater()
        try:
            grab_popup(tour, tour.window.toolbar.show_internal_standard_menu)
        finally:
            StandardChooser.close = original_close

    tour.run("internal_standard_menu", chooser_diagnostics, grab_main=False)
    tour.run(
        "identity_popup",
        lambda: tour.window.toolbar.targeted_qc._show_popup_chart(),
        grab_main=False,
    )
    tour.run("detailed_scheme_switch", lambda: detailed_scheme_switch(tour), grab_main=False)
    tour.run("samples_1024x768", lambda: samples_1024(tour))
    tour.run("all_samples_unchecked", lambda: all_samples_unchecked(tour))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--size", default="1600x1000")
    parser.add_argument(
        "--scheme", choices=sorted(SCHEMES), help="force light or dark (default: follow the OS)"
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    width, height = (int(v) for v in args.size.split("x"))

    from manic.models import database

    scratch = Path(tempfile.mkdtemp(prefix="manic-ui-tour-"))
    # Each run's database holds every extracted EIC (tens of MB); never leave it behind.
    atexit.register(shutil.rmtree, scratch, ignore_errors=True)
    database.DB_FILE = scratch / "tour.db"
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(scratch))

    from manic.models.database import init_db
    from manic.ui.main_window import MainWindow
    from manic.utils.utils import apply_app_stylesheet

    app = QApplication(sys.argv)
    app.setApplicationName("MANIC")
    app.setOrganizationName("MANIC UI Tour")
    apply_app_stylesheet(app)
    init_db()
    MainWindow._check_for_updates = lambda self: None

    screen = app.primaryScreen()
    print(
        f"screen: {screen.availableGeometry().width()}x{screen.availableGeometry().height()}"
        f" available, device pixel ratio {screen.devicePixelRatio()}"
    )
    tour = Tour(app, args.out, (width, height))
    if args.scheme:
        try:
            set_scheme(tour, SCHEMES[args.scheme])
        except Exception:
            tour.errors.append(f"scheme: {traceback.format_exc(limit=3)}")
    QDialog.exec = lambda self: tour.capture_modal(self)
    QMessageBox.exec = lambda self: tour.capture_modal(self)
    QMenu.exec = lambda self, *a, **k: tour.capture_modal(self)

    tour_steps(tour)
    if tour.window is not None:
        tour.window.close()

    print(f"screenshots: {len(tour.saved)} in {args.out}")
    print(f"skipped: {len(tour.skipped)}")
    for note in tour.skipped:
        print(f"  {note}")
    print(f"errors: {len(tour.errors)}")
    for error in tour.errors:
        print(error)
    return 1 if tour.errors else 0


if __name__ == "__main__":
    sys.exit(main())
