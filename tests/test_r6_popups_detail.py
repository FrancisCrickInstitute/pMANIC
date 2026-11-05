from types import SimpleNamespace

import numpy as np
from matplotlib.backend_bases import MouseEvent

from manic.models.analysis import IonChannel, IonRole
from manic.validation.unlabelled_identity import QualifierStatus

# matplotlib's Qt backend needs the QApplication first, so UI imports wait for qapp.

Q_ION = IonChannel(174.0, IonRole.QUANTIFIER)
UNSET = IonChannel(248.0, IonRole.QUALIFIER, ordinal=1)


def test_detailed_legend_names_qualifier_states_in_words(qapp, monkeypatch):
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    dialog = DetailedPlotDialog("Glycine", "MM_01")
    try:
        dialog.compound_info = SimpleNamespace(analysis_channels=(Q_ION, UNSET))
        dialog.identity = SimpleNamespace(
            qualifiers=SimpleNamespace(
                for_ordinal=lambda _ordinal: SimpleNamespace(status=QualifierStatus.NOT_ASSESSED)
            )
        )
        assert dialog._channel_label(1) == "Qualifier ion 1 m/z 248 (not assessed)"
    finally:
        dialog.deleteLater()


def _spectrum(qapp):
    from manic.ui.matplotlib_plot_widget import MatplotlibPlotWidget

    widget = MatplotlibPlotWidget("Mass Spectrum", "m/z", "Intensity")
    mz = np.array([73.02, 147.0, 173.97, 174.99, 175.98, 177.0, 207.01, 280.99, 300.0])
    intensity = np.array([3e4, 2e4, 8e5, 1.3e6, 7e5, 2e5, 1e4, 1e4, 4e5])
    widget.plot_stems(mz, intensity)
    widget.label_peaks(
        mz, intensity, own_mz=(174.0, 175.0, 176.0, 177.0), own_names=("M+0", "M+1", "M+2", "M+3")
    )
    widget.finalize_plot()
    widget.resize(900, 300)
    widget.show()
    for _ in range(5):
        qapp.processEvents()
        widget.canvas.draw()
    return widget


def test_isotopologues_are_named_together_at_full_range_and_apart_when_zoomed(qapp):
    widget = _spectrum(qapp)
    try:
        assert widget.visible_peak_labels() == ["M+0…M+3", "300.00"]
        label, bracket = widget._cluster
        assert bracket.get_visible()
        renderer = widget.canvas.get_renderer()
        last_stem = widget.ax.transData.transform((177.0, 0))[0]
        # Beside the cluster, so the name sits on none of its stems.
        assert label.get_window_extent(renderer).x0 > last_stem + 2
        widget.ax.set_xlim(172.0, 179.0)
        widget.canvas.draw()
        widget.canvas.draw()
        assert widget.visible_peak_labels() == [
            "M+1  174.99", "M+0  173.97", "M+2  175.98", "M+3  177.00"
        ]
        assert not bracket.get_visible()
    finally:
        widget.cleanup()
        widget.deleteLater()


def test_reset_gesture_is_in_the_tooltip_and_double_click_resets_while_panning(qapp, monkeypatch):
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    dialog = DetailedPlotDialog("Pyruvate", "Bio_001")
    try:
        dialog.show()
        qapp.processEvents()
        assert "Double-click a chart to reset only that chart" in dialog.nav_toolbar.home_btn.toolTip()
        for button in (dialog.nav_toolbar.pan_btn, dialog.nav_toolbar.zoom_btn):
            button.click()
            plot = dialog.tic_plot
            plot.plot_line(np.array([0.0, 10.0]), np.array([0.0, 5.0]), color="#000000")
            plot.ax.set_xlim(4.0, 5.0)
            plot.canvas.draw()
            x, y = plot.ax.transAxes.transform((0.5, 0.5))
            MouseEvent("button_press_event", plot.canvas, x, y, button=1, dblclick=True)._process()
            MouseEvent("button_release_event", plot.canvas, x, y, button=1)._process()
            assert plot.ax.get_xlim()[0] < 0.0 and plot.ax.get_xlim()[1] > 10.0, button.text()
    finally:
        dialog.deleteLater()
