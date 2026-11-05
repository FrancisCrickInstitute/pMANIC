from PySide6.QtWidgets import QSplitter

from manic.constants import PLOT_DPI


def _dialog(monkeypatch):
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    return DetailedPlotDialog("Pyruvate", "Bio_001")


def test_detailed_text_is_at_least_ten_pixels(qapp, monkeypatch):
    dialog = _dialog(monkeypatch)
    try:
        for plot in (dialog.eic_plot, dialog.tic_plot, dialog.ms_plot):
            tick = plot.ax.xaxis.get_major_ticks()[0].label1
            assert tick.get_fontsize() * PLOT_DPI / 72 >= 10
            assert plot.ax.xaxis.label.get_fontsize() > tick.get_fontsize()
    finally:
        dialog.deleteLater()


def test_the_chromatogram_gets_half_the_chart_height(qapp, monkeypatch):
    dialog = _dialog(monkeypatch)
    try:
        dialog.show()
        qapp.processEvents()
        eic, tic, ms = dialog.findChild(QSplitter).sizes()
        # Half when there is room; the others' minimums can take a little of it.
        assert eic > max(tic, ms) and eic >= 0.45 * (eic + tic + ms)
    finally:
        dialog.deleteLater()


def test_each_chart_keeps_room_for_its_title_and_axis_label(qapp, monkeypatch):
    dialog = _dialog(monkeypatch)
    try:
        for plot in (dialog.eic_plot, dialog.tic_plot, dialog.ms_plot):
            assert plot.minimumHeight() >= 140
    finally:
        dialog.deleteLater()
