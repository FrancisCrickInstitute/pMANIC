from PySide6.QtWidgets import QWidget

from manic.models.analysis import AnalysisMode
from manic.ui.plot_tile import PlotTile
from manic.validation.peak_verdict import PeakReview, PeakVerdict

from conftest import _make_window


class FakeChart:
    def __init__(self, sample: str, container: QWidget):
        self.sample_name = sample
        self.compound_name = "Cmp"
        self.is_selected = False
        self._container = container

    def parent(self) -> QWidget:
        return self._container

    def set_selected(self, selected: bool) -> None:
        self.is_selected = selected


def _window_with_plots(monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    view = window.graph_view
    charts = {}
    for sample in ("A", "B", "C"):
        container = PlotTile(QWidget())
        chart = FakeChart(sample, container)
        container.chart_view = chart
        charts[sample] = chart
    view._current_plots = list(charts.values())
    view.apply_peak_verdicts({"A": PeakVerdict.FAIL, "B": PeakVerdict.PASS})
    view.peak_review_changed.disconnect(window.on_peak_review_changed)
    emitted = []
    view.peak_review_changed.connect(lambda c, s, r: emitted.append((c, sorted(s), r)))
    return window, charts, emitted


def test_review_menu_names_its_targets_and_acts_on_them(qapp, monkeypatch):
    window, charts, emitted = _window_with_plots(monkeypatch)
    view = window.graph_view
    try:
        window._sync_review_menu()
        assert not window.inspect_action.isEnabled()
        assert not window.reject_peak_action.isEnabled()
        assert not window.review_fit_menu.isEnabled()
        assert not window.show_only_selected_action.isEnabled()

        view.select_samples(["A", "B"])
        assert window.reject_peak_action.text() == "Mark 2 Peaks as Bad"
        # Only A is below threshold, so only A can be accepted.
        assert window.accept_peak_action.text() == "Accept Peak (Below Threshold)"
        assert window.accept_peak_action.isEnabled()
        assert window.show_only_selected_action.text() == "Show Only 2 Selected Samples"
        assert window.inspect_action.text() == "Inspect A..."
        window.review_menu.aboutToShow.emit()
        assert window.review_fit_menu.title() == "Curve Fit for 2 Samples"
        assert "Use Compound Setting" in [a.text() for a in window.review_fit_menu.actions()]

        window.reject_peak_action.trigger()
        assert emitted == [("Cmp", ["A", "B"], PeakReview.REJECTED)]
        window.accept_peak_action.trigger()
        assert emitted[-1] == ("Cmp", ["A"], PeakReview.ACCEPTED)

        view.clear_selection()
        view._focus_index = 1
        window._sync_review_menu()
        assert window.reject_peak_action.text() == "Mark Peak as Bad"
        assert window.inspect_action.text() == "Inspect B..."
        assert not window.accept_peak_action.isEnabled()
    finally:
        window.close()


def test_deconvolution_status_opens_its_settings_page(qapp, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        window.deconvolution_indicator_label.click()
        assert window.settings_window.isVisible()
        assert window.settings_window.heading.text() == "Deconvolution"
    finally:
        if window.settings_window is not None:
            window.settings_window.close()
        window.close()
