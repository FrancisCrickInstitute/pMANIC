from types import SimpleNamespace

import numpy as np
import pytest
from matplotlib.backend_bases import MouseEvent
from matplotlib.colors import to_hex

# matplotlib's Qt backend needs the QApplication first, so UI imports wait for qapp.

SPECTRUM_MZ = np.array([73.02, 147.0, 173.97, 174.99, 175.98, 177.0, 207.01, 280.99, 300.0])
SPECTRUM_INTENSITY = np.array([3e4, 2e4, 8e5, 1.3e6, 7e5, 2e5, 1e4, 1e4, 4e5])
OWN_IONS = (174.0, 175.0, 176.0, 177.0)


@pytest.fixture
def dialog(qapp, monkeypatch):
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    dialog = DetailedPlotDialog("Pyruvate", "Bio_001")
    yield dialog
    dialog.deleteLater()


@pytest.fixture
def spectrum(qapp):
    """Draws the test spectrum, labelled as the dialog labels it, at 900 x 300."""
    from manic.ui.matplotlib_plot_widget import MatplotlibPlotWidget

    widgets = []

    def draw(own_mz=(), own_names=None, size=(900, 300)):
        widget = MatplotlibPlotWidget("Mass Spectrum", "m/z", "Intensity")
        widgets.append(widget)
        widget.plot_stems(SPECTRUM_MZ, SPECTRUM_INTENSITY)
        widget.label_peaks(SPECTRUM_MZ, SPECTRUM_INTENSITY, own_mz=own_mz, own_names=own_names)
        widget.finalize_plot()
        widget.setMinimumHeight(140)  # as the detailed view allows on a short screen
        widget.resize(*size)
        widget.show()
        for _ in range(5):
            qapp.processEvents()
            widget.canvas.draw()
        return widget

    yield draw
    for widget in widgets:
        widget.cleanup()
        widget.deleteLater()


def _shown_labels(widget) -> list[str]:
    return sorted(text.get_text() for text in widget.ax.texts if text.get_visible())


def _zoom_to_cluster(widget) -> None:
    widget.ax.set_xlim(172.0, 179.0)
    widget.canvas.draw()
    widget.canvas.draw()


def _zoomed_plots(dialog):
    plots = (dialog.eic_plot, dialog.tic_plot, dialog.ms_plot)
    for plot in plots:
        plot.plot_line(np.array([0.0, 10.0]), np.array([0.0, 5.0]), color="#000000")
        plot.ax.set_xlim(4.0, 5.0)
    return plots


def _click(plot, *, dblclick=False) -> None:
    x, y = plot.ax.transAxes.transform((0.5, 0.5))
    MouseEvent("button_press_event", plot.canvas, x, y, button=1, dblclick=dblclick)._process()
    MouseEvent("button_release_event", plot.canvas, x, y, button=1)._process()


def test_one_toolbar_pans_zooms_and_resets_all_three_charts(qapp, dialog):
    plots = (dialog.eic_plot, dialog.tic_plot, dialog.ms_plot)
    toolbar = dialog.nav_toolbar
    toolbar.pan_btn.click()
    assert [plot.mode() for plot in plots] == ["pan", "pan", "pan"]
    toolbar.zoom_btn.click()
    assert [plot.mode() for plot in plots] == ["zoom", "zoom", "zoom"]
    assert not toolbar.pan_btn.isChecked()

    # Tick labels of very different widths on each chart.
    for plot, top in zip(plots, (123456.0, 1.0, 5.0)):
        plot.plot_line(np.array([0.0, 10.0]), np.array([0.0, top]), color="#000000")
        plot.finalize_plot()
        plot.ax.set_xlim(4.0, 5.0)
    dialog.show()
    qapp.processEvents()
    for plot in plots:
        plot.canvas.draw()
    assert len({plot.ax.get_window_extent().x0 for plot in plots}) == 1

    toolbar.home_btn.click()
    assert [plot.mode() for plot in plots] == ["", "", ""]
    assert not toolbar.zoom_btn.isChecked()
    assert all(plot.ax.get_xlim()[0] < 0.0 and plot.ax.get_xlim()[1] > 10.0 for plot in plots)


@pytest.mark.parametrize("mode", ["", "pan", "zoom"])
def test_double_click_resets_only_that_chart(qapp, dialog, mode):
    if mode:
        getattr(dialog.nav_toolbar, f"{mode}_btn").click()
    eic, tic, ms = _zoomed_plots(dialog)
    dialog.show()
    qapp.processEvents()
    for plot in (eic, tic, ms):
        plot.canvas.draw()

    _click(tic, dblclick=True)
    assert tic.ax.get_xlim()[0] < 0.0 and tic.ax.get_xlim()[1] > 10.0
    assert eic.ax.get_xlim() == ms.ax.get_xlim() == (4.0, 5.0)

    _click(eic)
    assert eic.ax.get_xlim() == (4.0, 5.0)


def test_context_menu_resets_only_that_chart(dialog):
    eic, tic, ms = _zoomed_plots(dialog)
    menu = ms.context_menu()
    assert [action.text() for action in menu.actions()] == ["Reset This Chart"]
    menu.actions()[0].trigger()
    assert ms.ax.get_xlim()[0] < 0.0
    assert eic.ax.get_xlim() == tic.ax.get_xlim() == (4.0, 5.0)

    # Pan and Zoom own the right button, so no menu interrupts their drag.
    dialog.nav_toolbar.zoom_btn.click()
    assert eic.context_menu() is None


@pytest.mark.parametrize("own_mz", [(), OWN_IONS], ids=["no own ions", "own ions"])
def test_spectrum_labels_own_ions_first_and_never_the_baseline(spectrum, own_mz):
    widget = spectrum(own_mz=own_mz)
    # The cluster's labels would share one column at full range, so only the
    # tallest shows; baseline peaks (73.02, 147.00, 207.01, 280.99) never do.
    assert _shown_labels(widget) == ["174.99", "300.00"]
    _zoom_to_cluster(widget)
    assert _shown_labels(widget) == ["173.97", "174.99", "175.98", "177.00"]


def test_isotopologues_are_named_together_at_full_range_and_apart_when_zoomed(spectrum):
    widget = spectrum(own_mz=OWN_IONS, own_names=("M+0", "M+1", "M+2", "M+3"))
    assert _shown_labels(widget) == ["300.00", "M+0…M+3"]
    label = next(text for text in widget.ax.texts if text.get_text() == "M+0…M+3")
    bracket = next(line for line in widget.ax.lines if list(line.get_ydata()) == [1.3e6, 1.3e6])
    assert bracket.get_visible()
    renderer = widget.canvas.get_renderer()
    tallest = widget.ax.transData.transform((174.99, 1.3e6))[1]
    # Above the bracket over the tallest bar, so the name sits on none of the stems.
    assert label.get_window_extent(renderer).y0 > tallest + 3

    _zoom_to_cluster(widget)
    assert _shown_labels(widget) == ["M+0  173.97", "M+1  174.99", "M+2  175.98", "M+3  177.00"]
    assert not bracket.get_visible()


def test_labelled_spectrum_opens_on_its_cluster_and_full_scan_is_one_toggle(qapp, dialog):
    from manic.models.analysis import IonChannel, IonRole

    dialog.ms_data = SimpleNamespace(mz=SPECTRUM_MZ, intensity=SPECTRUM_INTENSITY)
    dialog.compound_info = SimpleNamespace(
        analysis_channels=[IonChannel(mz, IonRole.ISOTOPOLOGUE, ordinal=i) for i, mz in enumerate(OWN_IONS)],
        mass0=174.0,
    )
    dialog._plot_ms()
    plot = dialog.ms_plot
    toggle = plot.full_scan_button
    assert plot.ax.get_xlim() == (154.0, 197.0) and not toggle.isChecked()
    toggle.click()
    low, high = plot.ax.get_xlim()
    assert low < 73.02 and high > 300.0
    # Reset all returns to the opening view, not the scan.
    dialog.nav_toolbar.home_btn.click()
    assert plot.ax.get_xlim() == (154.0, 197.0) and not toggle.isChecked()
    # The target m/z guide sits behind the stems.
    guide = next(line for line in plot.ax.lines if list(line.get_xdata()) == [174.0, 174.0])
    assert guide.get_zorder() < min(c.get_zorder() for c in plot.ax.collections)


@pytest.mark.parametrize("own_mz", [(174.99,), OWN_IONS], ids=["quantifier", "isotopologues"])
def test_a_short_spectrum_keeps_its_own_ion_labels_inside_the_plot(spectrum, own_mz):
    # The supporting row of a 921x581 detailed view.
    widget = spectrum(own_mz=own_mz, size=(440, 160))
    renderer = widget.canvas.get_renderer()
    [tallest] = [text for text in widget.ax.texts if text.get_text() == "174.99"]
    assert tallest.get_visible()
    assert tallest.get_window_extent(renderer).y1 <= widget.ax.get_window_extent(renderer).y1 + 1


def test_live_scheme_switch_repaints_spectrum_label_boxes(qapp, spectrum):
    from manic.utils.utils import apply_color_scheme

    widget = spectrum(own_mz=(174.0,))

    def boxes():
        return {to_hex(text.get_bbox_patch().get_facecolor()) for text in widget.ax.texts}

    try:
        apply_color_scheme(qapp, True)
        assert boxes() == {"#232529"}
        assert to_hex(widget.figure.get_facecolor()) == "#232529"
        apply_color_scheme(qapp, False)
        assert boxes() == {"#ffffff"}
        assert to_hex(widget.figure.get_facecolor()) == to_hex(widget.ax.get_facecolor()) == "#ffffff"
    finally:
        apply_color_scheme(qapp, False)
        qapp.setStyleSheet("")


def test_detailed_eic_info_strip_reports_failure_when_plot_never_draws(dialog):
    dialog.compound_info = SimpleNamespace(
        retention_time=5.0,
        loffset=0.1,
        roffset=0.1,
        is_unlabelled_target=False,
        mass0=116.0,
        label_atoms=0,
    )
    dialog.eic_data = SimpleNamespace(
        time=np.array([4.9, 5.0, 5.1]),
        intensity=np.array([1.0, 2.0, 1.0]),
    )
    dialog.eic_plot.finalize_plot = lambda: (_ for _ in ()).throw(RuntimeError("finalize failed"))
    dialog._plot_eic()
    dialog._update_info_label()
    assert dialog.info_label.text() == (
        "EIC plot failed: finalize failed  ·  tR 5.000 min  ·  integration 4.900–5.100 min"
    )
    assert dialog.eic_plot.ax.get_title(loc="left") == (
        "Extracted Ion Chromatogram (plot failed)"
    )

