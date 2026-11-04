import numpy as np
from matplotlib.backend_bases import MouseEvent

# matplotlib's Qt backend needs the QApplication first, so imports wait for qapp.


def _dialog(monkeypatch):
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    return DetailedPlotDialog("Pyruvate", "Bio_001")


def _zoomed_plots(dialog):
    plots = (dialog.eic_plot, dialog.tic_plot, dialog.ms_plot)
    for plot in plots:
        plot.plot_line(np.array([0.0, 10.0]), np.array([0.0, 5.0]), color="#000000")
        plot.ax.set_xlim(4.0, 5.0)
    return plots


def test_double_click_resets_only_that_chart(qapp, monkeypatch):
    dialog = _dialog(monkeypatch)
    try:
        eic, tic, ms = _zoomed_plots(dialog)
        MouseEvent("button_press_event", tic.canvas, 50, 50, button=1, dblclick=True)._process()
        assert tic.ax.get_xlim()[0] < 0.0 and tic.ax.get_xlim()[1] > 10.0
        assert eic.ax.get_xlim() == ms.ax.get_xlim() == (4.0, 5.0)

        MouseEvent("button_press_event", eic.canvas, 50, 50, button=1)._process()
        assert eic.ax.get_xlim() == (4.0, 5.0)
    finally:
        dialog.deleteLater()


def test_context_menu_resets_only_that_chart(qapp, monkeypatch):
    dialog = _dialog(monkeypatch)
    try:
        eic, tic, ms = _zoomed_plots(dialog)
        menu = ms.context_menu()
        assert [action.text() for action in menu.actions()] == ["Reset This Chart"]
        menu.actions()[0].trigger()
        assert ms.ax.get_xlim()[0] < 0.0
        assert eic.ax.get_xlim() == tic.ax.get_xlim() == (4.0, 5.0)

        # Pan and Zoom own the right button, so no menu interrupts their drag.
        dialog.nav_toolbar.zoom_btn.click()
        assert eic.context_menu() is None
    finally:
        dialog.deleteLater()


def test_reset_all_names_its_scope(qapp, monkeypatch):
    dialog = _dialog(monkeypatch)
    try:
        assert dialog.nav_toolbar.home_btn.text() == "↻ Reset all"
        assert "Double-click a chart" in dialog.nav_toolbar.home_btn.toolTip()
    finally:
        dialog.deleteLater()
