import numpy as np

# matplotlib's Qt backend needs the QApplication first, so imports wait for qapp.


def _spectrum(qapp, own_mz=()):
    from manic.ui.matplotlib_plot_widget import MatplotlibPlotWidget

    widget = MatplotlibPlotWidget("Mass Spectrum", "m/z", "Intensity")
    mz = np.array([73.02, 147.0, 173.97, 174.99, 175.98, 177.0, 207.01, 280.99, 300.0])
    intensity = np.array([3e4, 2e4, 8e5, 1.3e6, 7e5, 2e5, 1e4, 1e4, 4e5])
    widget.plot_stems(mz, intensity)
    widget.label_peaks(mz, intensity, own_mz=own_mz)
    widget.finalize_plot()
    widget.resize(900, 300)
    widget.show()
    for _ in range(5):
        qapp.processEvents()
        widget.canvas.draw()
    return widget


def test_spectrum_labels_own_ions_first_and_never_the_baseline(qapp):
    widget = _spectrum(qapp, own_mz=(174.0, 175.0, 176.0, 177.0))
    try:
        # The own ions crowd one column at full range, so only the tallest
        # shows; baseline peaks (73.02, 147.00, 207.01, 280.99) never do.
        assert widget.visible_peak_labels() == ["174.99", "300.00"]
        widget.ax.set_xlim(172.0, 179.0)
        widget.canvas.draw()
        widget.canvas.draw()
        assert widget.visible_peak_labels() == ["174.99", "173.97", "175.98", "177.00"]
    finally:
        widget.cleanup()
        widget.deleteLater()


def test_live_scheme_switch_repaints_spectrum_label_boxes(qapp):
    from matplotlib.colors import to_hex

    from manic.ui import theme

    widget = _spectrum(qapp, own_mz=(174.0,))
    try:
        theme.notifier.changed.emit(theme.set_dark(True))
        boxes = {to_hex(label.get_bbox_patch().get_facecolor()) for label in widget._peak_labels}
        assert boxes == {theme.COLORS["surface"].lower()}
    finally:
        theme.notifier.changed.emit(theme.set_dark(False))
        widget.cleanup()
        widget.deleteLater()
