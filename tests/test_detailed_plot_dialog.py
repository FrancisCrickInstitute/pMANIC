from types import SimpleNamespace

import numpy as np
import pytest

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


def test_stepping_to_a_sample_with_no_tic_or_spectrum_draws_their_no_data_state(qapp, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from manic.io.compound_reader import Compound
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    time = np.linspace(0.8, 1.2, 81)
    peak = 1e6 * np.exp(-0.5 * ((time - 1.0) / 0.02) ** 2)
    compound = Compound(
        compound_name="Cmp", retention_time=1.0, loffset=0.1, roffset=0.1, mass0=217.0, label_atoms=0
    )
    module = "manic.ui.detailed_plot_dialog"
    monkeypatch.setattr(f"{module}.read_compound_with_session", lambda *_a: compound)
    monkeypatch.setattr(
        f"{module}.get_eics_for_compound",
        lambda name, samples, **_k: [
            SimpleNamespace(sample_name=s, compound_name=name, time=time, intensity=np.vstack([peak]))
            for s in samples
        ],
    )
    monkeypatch.setattr(
        f"{module}.read_tic",
        lambda sample: SimpleNamespace(time=time, intensity=peak) if sample == "S1" else None,
    )
    monkeypatch.setattr(
        f"{module}.ensure_ms_data_for_time",
        lambda sample, *_a, **_k: SimpleNamespace(
            time=1.0, mz=np.array([200.0, 217.0, 230.0]), intensity=np.array([1e5, 2e5, 1e4])
        ) if sample == "S1" else None,
    )
    dialog = DetailedPlotDialog("Cmp", "S1", samples=["S1", "S2"])
    try:
        dialog.show()
        QTest.qWait(150)
        drawn = {}
        for plot in (dialog.tic_plot, dialog.ms_plot):
            plot.canvas.mpl_connect(
                "draw_event",
                lambda _e, ax=plot.ax: drawn.__setitem__(
                    ax.get_title(loc="left"), len(ax.lines) + len(ax.collections)
                ),
            )
        QTest.mouseClick(dialog.next_sample, Qt.LeftButton)
        QTest.qWait(150)
        assert drawn == {"Total ion chromatogram (no data)": 0, "Mass spectrum (no data)": 0}
    finally:
        dialog.close()
        dialog.deleteLater()


def test_closing_with_a_draw_queued_prints_no_traceback(qapp, dialog, capsys):
    from manic.models.analysis import IonChannel, IonRole

    dialog.ms_data = SimpleNamespace(mz=SPECTRUM_MZ, intensity=SPECTRUM_INTENSITY)
    dialog.compound_info = SimpleNamespace(
        analysis_channels=[IonChannel(mz, IonRole.ISOTOPOLOGUE, ordinal=i) for i, mz in enumerate(OWN_IONS)],
        mass0=174.0,
    )
    dialog._plot_ms()
    dialog.show()
    qapp.processEvents()
    capsys.readouterr()
    dialog.ms_plot.canvas.draw_idle()
    dialog.close()
    for _ in range(5):
        qapp.processEvents()
    assert "Traceback" not in capsys.readouterr().err
