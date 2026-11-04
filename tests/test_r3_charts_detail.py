from types import SimpleNamespace

import numpy as np

# Imported in the tests: matplotlib's Qt backend needs the QApplication first.


def _dialog(monkeypatch):
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    return DetailedPlotDialog("Pyruvate", "Bio_001")


def test_one_toolbar_pans_zooms_and_resets_all_three_charts(qapp, monkeypatch):
    dialog = _dialog(monkeypatch)
    plots = (dialog.eic_plot, dialog.tic_plot, dialog.ms_plot)
    try:
        toolbar = dialog.nav_toolbar
        toolbar.pan_btn.click()
        assert [plot.mode() for plot in plots] == ["pan", "pan", "pan"]
        toolbar.zoom_btn.click()
        assert [plot.mode() for plot in plots] == ["zoom", "zoom", "zoom"]
        assert not toolbar.pan_btn.isChecked()

        for plot in plots:
            plot.plot_line(np.array([0.0, 10.0]), np.array([0.0, 5.0]), color="#000000")
            plot.ax.set_xlim(4.0, 5.0)
        toolbar.home_btn.click()
        assert [plot.mode() for plot in plots] == ["", "", ""]
        assert not toolbar.zoom_btn.isChecked()
        assert all(plot.ax.get_xlim()[0] < 0.0 and plot.ax.get_xlim()[1] > 10.0 for plot in plots)
    finally:
        dialog.deleteLater()


def test_footer_separates_facts_with_dots(qapp, monkeypatch):
    dialog = _dialog(monkeypatch)
    try:
        dialog.compound_info = SimpleNamespace(
            retention_time=7.09, is_unlabelled_target=False, mass0=174.0, label_atoms=3
        )
        dialog.eic_data = SimpleNamespace(time=np.zeros(48))
        dialog.ms_data = SimpleNamespace(mz=np.zeros(17))
        dialog._update_info_label()
        assert dialog.info_label.text() == (
            "tR 7.090 min  ·  m/z 174.0000  ·  M+0…M+3  ·  48 EIC points  ·  17 MS peaks"
        )
    finally:
        dialog.deleteLater()


def _spectrum_widget(qapp, width: int):
    from manic.ui.matplotlib_plot_widget import MatplotlibPlotWidget

    widget = MatplotlibPlotWidget("Mass Spectrum", "m/z", "Intensity")
    mz = np.array([73.02, 147.0, 173.97, 174.99, 175.98, 177.0, 207.01, 280.99])
    intensity = np.array([3e4, 2e4, 8e5, 1.3e6, 7e5, 2e5, 1e4, 1e4])
    widget.plot_stems(mz, intensity)
    widget.label_peaks(mz, intensity)
    widget.finalize_plot()
    widget.resize(width, 300)
    widget.show()
    for _ in range(5):
        qapp.processEvents()
        widget.canvas.draw()
    return widget


def test_spectrum_labels_never_share_a_column(qapp):
    widget = _spectrum_widget(qapp, 900)
    try:
        assert widget.visible_peak_labels() == ["174.99"]
        widget.ax.set_xlim(172.0, 179.0)
        widget.canvas.draw()
        widget.canvas.draw()
        assert widget.visible_peak_labels() == ["174.99", "173.97", "175.98", "177.00"]
    finally:
        widget.cleanup()
        widget.deleteLater()


def test_detail_axes_line_up_whatever_the_tick_labels(qapp):
    from manic.ui.matplotlib_plot_widget import MatplotlibPlotWidget

    wide = MatplotlibPlotWidget("A", "x", "y")
    narrow = MatplotlibPlotWidget("B", "x", "y")
    try:
        wide.plot_line(np.array([0.0, 1.0]), np.array([0.0, 123456.0]), color="#000000")
        narrow.plot_line(np.array([0.0, 1.0]), np.array([0.0, 1.0]), color="#000000")
        for widget in (wide, narrow):
            widget.finalize_plot()
            widget.resize(800, 300)
            widget.show()
        qapp.processEvents()
        for widget in (wide, narrow):
            widget.canvas.draw()
        assert wide.ax.get_window_extent().x0 == narrow.ax.get_window_extent().x0 == 64
    finally:
        for widget in (wide, narrow):
            widget.cleanup()
            widget.deleteLater()
