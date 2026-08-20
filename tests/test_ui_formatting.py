"""
Tests for UI number and value formatting utilities.

Tests formatting logic used to display values in the integration window
and other UI components.
"""

import pytest
from PySide6.QtCharts import QChart, QValueAxis
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel
import sys
import numpy as np
from types import SimpleNamespace

from manic.processors.chromatographic_peak_deconvolution import (
    ChannelDeconvolution,
    ChannelDeconvolutionBundle,
    EICChromatographicPeakDeconvolutionResult,
    deconvolve_eic,
)
from manic.ui import graphs as graphs_module
from manic.ui.colors import label_colors

from manic.ui.integration_window_widget import IntegrationWindow
from manic.ui.left_toolbar import Toolbar
from manic.ui.graphs import GraphView
from manic.ui.main_window import MainWindow
from manic.ui.chart_popup_dialog import ChartPopupDialog
from manic.ui.targeted_qc_widget import RatioVerdict, TargetedQcWidget, ratio_verdict
from manic.models.analysis import AnalysisMode, IonChannel, IonRole
from manic.validation.unlabelled_identity import (
    IdentityQcResult,
    IdentityStatus,
    QualifierRatioResult,
)


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for UI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def integration_window(qapp):
    """Create IntegrationWindow instance for testing."""
    window = IntegrationWindow()
    yield window
    window.deleteLater()


def test_unlabelled_toolbar_hides_label_derived_summaries(qapp):
    toolbar = Toolbar(AnalysisMode.UNLABELLED)
    try:
        assert toolbar.isotopologue_ratios.isHidden()
        assert toolbar.total_abundance.isHidden()
        assert not toolbar.targeted_qc.isHidden()
        assert toolbar.integration.findChild(QLabel, "reference_rt_note") is None
    finally:
        toolbar.deleteLater()


def test_targeted_qc_identity_chart_records_observed_rt(qapp):
    v = IonChannel(
        147.0,
        IonRole.QUALIFIER,
        ordinal=1,
        expected_ratio=0.4,
        ratio_tolerance=0.2,
    )
    result = IdentityQcResult(
        status=IdentityStatus.SUPPORTED,
        quantifier_area=100.0,
        observed_rt=1.23,
        rt_error=0.03,
        rt_passed=True,
        qualifier_ratios=(QualifierRatioResult(v, 0.41, True),),
        reasons=(),
    )
    provider = SimpleNamespace(
        assess_unlabelled_identity=lambda _sample, _compound: result
    )
    widget = TargetedQcWidget()
    try:
        widget.update_results("Target", ["S1"], provider)
        assert [row.sample_name for row in widget._rows] == ["S1"]
        assert widget._rows[0].verdict is RatioVerdict.VALIDATED
        assert widget.chart.title() == "Identity"
        assert widget.chart.legend().isVisible()
        assert len(widget.chart.series()) == 1
        assert widget._rows[0].note == "V1  expected 0.400  ±20%  observed 0.410"
        widget.clear()
        assert widget._rows == []
        assert widget.chart.series() == []
    finally:
        widget.deleteLater()


def test_identity_chart_popup_shows_sample_names(qapp):
    dialog = ChartPopupDialog(
        chart_type="identity",
        title="Identity",
        data=["validated", "mismatch"],
        sample_names=["S1", "S2"],
    )
    try:
        assert dialog.chart.title() == "Identity"
        assert dialog.chart.legend().isVisible()
        y_axes = dialog.chart.axes(Qt.Vertical)
        assert y_axes
        categories = y_axes[0].categories()
        assert "S1" in categories
        assert "S2" in categories
        labels = [
            bar_set.label()
            for series in dialog.chart.series()
            for bar_set in series.barSets()
        ]
        assert "Validated" in labels
        assert "Partial" in labels
        assert "Fail" in labels
    finally:
        dialog.deleteLater()


def test_ratio_verdict_maps_configured_v_over_q_checks():
    v = IonChannel(
        147.0,
        IonRole.QUALIFIER,
        ordinal=1,
        expected_ratio=0.4,
        ratio_tolerance=0.25,
    )
    match = IdentityQcResult(
        status=IdentityStatus.SUPPORTED,
        quantifier_area=100.0,
        observed_rt=1.2,
        rt_error=0.0,
        rt_passed=True,
        qualifier_ratios=(QualifierRatioResult(v, 0.41, True),),
        reasons=(),
    )
    mismatch = IdentityQcResult(
        status=IdentityStatus.REVIEW_REQUIRED,
        quantifier_area=100.0,
        observed_rt=1.2,
        rt_error=0.0,
        rt_passed=True,
        qualifier_ratios=(QualifierRatioResult(v, 0.70, False),),
        reasons=("V ion 1 ratio 0.700 is outside 0.400 ±25%",),
    )
    not_given = IdentityQcResult(
        status=IdentityStatus.NOT_ASSESSED,
        quantifier_area=100.0,
        observed_rt=1.2,
        rt_error=0.0,
        rt_passed=True,
        qualifier_ratios=(QualifierRatioResult(v, 0.41, None),),
        reasons=("Identity references are incomplete; signal is reported without confirmation",),
    )
    missing_q = IdentityQcResult(
        status=IdentityStatus.NOT_DETECTED,
        quantifier_area=0.0,
        observed_rt=None,
        rt_error=None,
        rt_passed=None,
        qualifier_ratios=(QualifierRatioResult(v, None, None),),
        reasons=("Q ion was not detected above the assessment floor",),
    )
    v2_pass = IonChannel(
        73.0,
        IonRole.QUALIFIER,
        ordinal=2,
        expected_ratio=0.2,
        ratio_tolerance=0.25,
    )
    v2_unchecked = IonChannel(73.0, IonRole.QUALIFIER, ordinal=2)
    both_pass = IdentityQcResult(
        status=IdentityStatus.SUPPORTED,
        quantifier_area=100.0,
        observed_rt=1.2,
        rt_error=0.0,
        rt_passed=True,
        qualifier_ratios=(
            QualifierRatioResult(v, 0.41, True),
            QualifierRatioResult(v2_pass, 0.21, True),
        ),
        reasons=(),
    )
    one_of_two = IdentityQcResult(
        status=IdentityStatus.REVIEW_REQUIRED,
        quantifier_area=100.0,
        observed_rt=1.2,
        rt_error=0.0,
        rt_passed=True,
        qualifier_ratios=(
            QualifierRatioResult(v, 0.41, True),
            QualifierRatioResult(v2_pass, 0.80, False),
        ),
        reasons=("V ion 2 ratio 0.800 is outside 0.200 ±25%",),
    )
    one_checked = IdentityQcResult(
        status=IdentityStatus.NOT_ASSESSED,
        quantifier_area=100.0,
        observed_rt=1.2,
        rt_error=0.0,
        rt_passed=True,
        qualifier_ratios=(
            QualifierRatioResult(v, 0.41, True),
            QualifierRatioResult(v2_unchecked, 0.21, None),
        ),
        reasons=("Identity references are incomplete; signal is reported without confirmation",),
    )
    assert ratio_verdict(match) is RatioVerdict.VALIDATED
    assert ratio_verdict(both_pass) is RatioVerdict.VALIDATED
    assert ratio_verdict(one_of_two) is RatioVerdict.PARTIAL
    assert ratio_verdict(one_checked) is RatioVerdict.PARTIAL
    assert ratio_verdict(mismatch) is RatioVerdict.MISMATCH
    assert ratio_verdict(not_given) is RatioVerdict.NOT_GIVEN
    assert ratio_verdict(missing_q) is RatioVerdict.NOT_GIVEN
    assert ratio_verdict(None) is RatioVerdict.NOT_GIVEN


def test_new_session_ignores_qaction_checked_boolean(monkeypatch):
    """QAction.triggered(False) must open the chooser, not become mode=False."""
    monkeypatch.setattr(
        "manic.ui.analysis_mode_dialog.choose_analysis_mode",
        lambda _parent: None,
    )
    window_stub = SimpleNamespace(
        compound_data_loaded=False,
        cdf_data_loaded=False,
    )

    MainWindow.new_analysis_session(window_stub, False)


def test_new_session_ignores_deleted_import_thread(monkeypatch):
    monkeypatch.setattr(
        "manic.ui.analysis_mode_dialog.choose_analysis_mode",
        lambda _parent: None,
    )

    class DeadThread:
        def isRunning(self):
            raise RuntimeError(
                "Internal C++ object (PySide6.QtCore.QThread) already deleted."
            )

    window_stub = SimpleNamespace(
        compound_data_loaded=False,
        cdf_data_loaded=False,
        _thread=DeadThread(),
        _regen_thread=None,
        _mass_tol_thread=None,
    )

    MainWindow.new_analysis_session(window_stub, False)
    assert window_stub._thread is None


class TestSignificantFigures:
    """Test formatting numbers to 4 significant figures."""

    def test_normal_retention_times(self, integration_window):
        """Test typical retention time values."""
        assert integration_window._format_number(9.77123456) == "9.771"
        assert integration_window._format_number(15.4567) == "15.46"
        assert integration_window._format_number(7.171234) == "7.171"
        assert integration_window._format_number(12.3456) == "12.35"

    def test_small_offsets(self, integration_window):
        """Test small offset values (typically < 1)."""
        assert integration_window._format_number(0.123456) == "0.1235"
        assert integration_window._format_number(0.1) == "0.1"
        assert integration_window._format_number(0.456789) == "0.4568"
        assert integration_window._format_number(0.999) == "0.999"

    def test_zero_handling(self, integration_window):
        """Test zero and near-zero values."""
        assert integration_window._format_number(0) == "0"
        assert integration_window._format_number(0.0) == "0"
        assert integration_window._format_number(-0.0) == "0"

    def test_very_small_values(self, integration_window):
        """Test very small non-zero values."""
        assert integration_window._format_number(0.001) == "0.001"
        assert integration_window._format_number(0.001234) == "0.001234"
        assert integration_window._format_number(0.0004567) == "0.0004567"

    def test_boundary_values(self, integration_window):
        """Test values near rounding boundaries."""
        assert integration_window._format_number(0.99995) == "1"
        assert integration_window._format_number(1.0001) == "1"
        assert integration_window._format_number(9.9995) == "9.999"  # Keeps 4 sig figs
        assert integration_window._format_number(10.001) == "10"

    def test_large_values(self, integration_window):
        """Test larger values (e.g., mass values)."""
        assert integration_window._format_number(123.456) == "123.5"
        assert integration_window._format_number(318.123) == "318.1"
        assert integration_window._format_number(999.999) == "1000"

    def test_negative_values(self, integration_window):
        """Test negative values (shouldn't occur but test anyway)."""
        assert integration_window._format_number(-9.77123) == "-9.771"
        assert integration_window._format_number(-0.1235) == "-0.1235"
        assert integration_window._format_number(-15.4567) == "-15.46"

    def test_edge_case_precision(self, integration_window):
        """Test precise rounding behavior."""
        # Test that 4 sig figs is applied correctly
        assert integration_window._format_number(1.2345) == "1.234"
        assert integration_window._format_number(1.2346) == "1.235"  # Round up
        assert integration_window._format_number(1.2344) == "1.234"


class TestRangeFormatting:
    """Test formatting value ranges for display."""

    def test_single_value_range(self, integration_window):
        """Test range when all values are identical."""
        values = [9.77, 9.77, 9.77]
        result = integration_window._format_range(values)
        assert result == "9.77"

    def test_single_value_with_float_error(self, integration_window):
        """Test range with values that are very close (floating point precision)."""
        values = [9.77, 9.77000001, 9.76999999]
        result = integration_window._format_range(values)
        # Should treat as single value (within 1e-6 tolerance)
        assert result == "9.77"

    def test_actual_range(self, integration_window):
        """Test range with different values."""
        values = [9.5, 10.2]
        result = integration_window._format_range(values)
        assert result == "9.5 - 10.2"

    def test_range_multiple_values(self, integration_window):
        """Test range with many values (should show min-max)."""
        values = [7.1, 7.5, 7.3, 7.8, 7.2]
        result = integration_window._format_range(values)
        assert result == "7.1 - 7.8"

    def test_range_with_none_values(self, integration_window):
        """Test range handling None values."""
        values = [9.5, None, 10.2, None]
        result = integration_window._format_range(values)
        # Should filter out None and show range
        assert result == "9.5 - 10.2"

    def test_range_all_none(self, integration_window):
        """Test range with all None values."""
        values = [None, None, None]
        result = integration_window._format_range(values)
        assert result == ""

    def test_empty_range(self, integration_window):
        """Test range with empty list."""
        values = []
        result = integration_window._format_range(values)
        assert result == ""

    def test_range_consistent_sig_figs(self, integration_window):
        """Test that both endpoints use 4 sig figs."""
        values = [9.77123, 10.4567]
        result = integration_window._format_range(values)
        # Both values should be formatted to 4 sig figs
        assert result == "9.771 - 10.46"

    def test_range_with_small_values(self, integration_window):
        """Test range with small offset-like values."""
        values = [0.123456, 0.456789]
        result = integration_window._format_range(values)
        assert result == "0.1235 - 0.4568"

    def test_range_invalid_values(self, integration_window):
        """Test range with non-numeric values."""
        values = [9.5, "invalid", 10.2]
        result = integration_window._format_range(values)
        # Should filter out invalid and show range of valid values
        assert result == "9.5 - 10.2"


class TestTRWindowFormatting:
    """Test tR window field formatting."""

    def test_tr_window_default_value(self, integration_window):
        """Test default tR window value formatting."""
        # Default is typically 0.2
        assert integration_window._format_number(0.2) == "0.2"

    def test_tr_window_custom_values(self, integration_window):
        """Test various tR window values."""
        assert integration_window._format_number(0.15) == "0.15"
        assert integration_window._format_number(0.25) == "0.25"
        assert integration_window._format_number(0.5) == "0.5"
        assert integration_window._format_number(1.0) == "1"


class TestFormattingConsistency:
    """Test formatting consistency across different contexts."""

    def test_same_value_formatted_identically(self, integration_window):
        """Test that same value formats the same way every time."""
        value = 9.77123
        result1 = integration_window._format_number(value)
        result2 = integration_window._format_number(value)
        assert result1 == result2
        assert result1 == "9.771"

    def test_range_endpoints_use_same_formatting(self, integration_window):
        """Test that range endpoints use same formatting as single values."""
        value1 = 9.77123
        value2 = 10.4567

        # Format as single values
        single1 = integration_window._format_number(value1)
        single2 = integration_window._format_number(value2)

        # Format as range
        range_result = integration_window._format_range([value1, value2])

        # Range should contain both formatted single values
        assert single1 in range_result
        assert single2 in range_result
        assert range_result == f"{single1} - {single2}"


def _multi_trace_eics(row_count: int):
    return [
        SimpleNamespace(
            intensity=np.ones((row_count, 3), dtype=float),
        )
    ]


def test_channel_legend_hides_when_compound_is_missing(qapp, monkeypatch):
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session",
        lambda *_args: (_ for _ in ()).throw(LookupError("alanine")),
    )
    view = GraphView()
    try:
        view.channel_legend.show()
        view._update_channel_legend("alanine", _multi_trace_eics(2))
        assert view.channel_legend.isHidden()
    finally:
        view.deleteLater()


def test_channel_legend_hides_when_compound_read_fails(qapp, monkeypatch):
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session",
        lambda *_args: (_ for _ in ()).throw(ValueError("invalid ions")),
    )
    view = GraphView()
    try:
        view.channel_legend.show()
        view._update_channel_legend("alanine", _multi_trace_eics(2))
        assert view.channel_legend.isHidden()
    finally:
        view.deleteLater()


def test_channel_legend_names_only_defined_ions(qapp, monkeypatch):
    compound = SimpleNamespace(
        analysis_channels=(
            IonChannel(217.0, IonRole.QUANTIFIER),
            IonChannel(147.0, IonRole.QUALIFIER, ordinal=1),
        )
    )
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session",
        lambda *_args: compound,
    )
    view = GraphView()
    try:
        view._update_channel_legend("Target", _multi_trace_eics(4))
        text = view.channel_legend.text()
        assert not view.channel_legend.isHidden()
        assert "Q ion m/z 217" in text
        assert "V ion 1 m/z 147" in text
        assert text.count("●") == 2
        assert "M+" not in text
    finally:
        view.deleteLater()


def test_detailed_eic_plot_failure_updates_info_strip(qapp, monkeypatch):
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    dialog = DetailedPlotDialog("alanine", "S1")
    try:
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
        dialog._plot_eic_traces = lambda: (_ for _ in ()).throw(
            RuntimeError("guide draw failed")
        )
        dialog._plot_eic()
        dialog._update_info_label()
        text = dialog.info_label.text()
        assert text.startswith("EIC plot failed: guide draw failed")
        assert dialog.eic_plot.ax.get_title() == (
            "Enhanced Extracted Ion Chromatogram (plot failed)"
        )
    finally:
        dialog.deleteLater()


def test_one_d_model_overlay_uses_qualifier_color(qapp):
    time = np.linspace(0.0, 10.0, 201)
    peak = 10.0 * np.exp(-0.5 * ((time - 5.0) / 0.3) ** 2)
    result = deconvolve_eic(
        time,
        peak,
        retention_time=5.0,
        loffset=2.0,
        roffset=2.0,
        stringency="4",
    )
    assert result.model is not None
    assert result.model.was_1d

    view = GraphView()
    try:
        chart = QChart()
        x_axis = QValueAxis()
        y_axis = QValueAxis()
        chart.addAxis(x_axis, Qt.AlignBottom)
        chart.addAxis(y_axis, Qt.AlignLeft)
        view._add_model_component_series(
            chart,
            x_axis,
            y_axis,
            result.model,
            result.model.selected_index,
            multi_trace=True,
            scale_factor=1.0,
            selected=True,
            color_index=1,
        )
        drawn = {series.pen().color().getRgb()[:3] for series in chart.series()}
        qualifier = label_colors[1]
        quantifier = label_colors[0]
        assert (qualifier.red(), qualifier.green(), qualifier.blue()) in drawn
        assert (quantifier.red(), quantifier.green(), quantifier.blue()) not in drawn
    finally:
        view.deleteLater()


def _deconvolution_plot_compound(*, is_unlabelled_target=False):
    return SimpleNamespace(
        deconvolution_level="4",
        deconvolution_fit_type="auto",
        deconvolution_noise_gate="balanced",
        retention_time=5.0,
        loffset=0.4,
        roffset=0.4,
        is_unlabelled_target=is_unlabelled_target,
        compound_name="test",
        baseline_correction=0,
        analysis_channels=(),
    )


def _mixed_deconvolution_bundle(time):
    fitted = deconvolve_eic(
        time,
        12.0 * np.exp(-0.5 * ((time - 5.0) / 0.08) ** 2),
        retention_time=5.0,
        loffset=0.4,
        roffset=0.4,
        stringency="4",
    )
    assert fitted.model is not None
    failed = EICChromatographicPeakDeconvolutionResult(
        selected=np.full(time.size, 3.0),
        selected_mask=np.asarray(fitted.selected_mask, dtype=bool),
        excluded=[],
        excluded_masks=[],
        selected_center=5.0,
        component_centers=[5.0],
        model=None,
    )
    return ChannelDeconvolutionBundle(
        time=time,
        channels=(
            ChannelDeconvolution(index=0, result=fitted),
            ChannelDeconvolution(index=1, result=failed),
        ),
    )


def test_labelled_mixed_bundle_draws_scans_not_model_overlay(qapp, monkeypatch):
    time = np.linspace(4.0, 6.0, 81)
    intensity = np.vstack(
        [
            12.0 * np.exp(-0.5 * ((time - 5.0) / 0.08) ** 2),
            np.full(time.size, 3.0),
        ]
    )
    monkeypatch.setattr(
        graphs_module,
        "deconvolve_channel_matrix",
        lambda *args, **kwargs: _mixed_deconvolution_bundle(time),
    )
    view = GraphView()
    try:
        chart = QChart()
        x_axis = QValueAxis()
        y_axis = QValueAxis()
        chart.addAxis(x_axis, Qt.AlignBottom)
        chart.addAxis(y_axis, Qt.AlignLeft)
        view._add_eic_series(
            chart,
            x_axis,
            y_axis,
            time,
            intensity,
            _deconvolution_plot_compound(is_unlabelled_target=False),
            1.0,
        )
        widths = {series.pen().widthF() for series in chart.series()}
        assert 2.2 not in widths
        assert 2.0 in widths
    finally:
        view.deleteLater()


def test_unlabelled_mixed_bundle_draws_fitted_ion_overlay(qapp, monkeypatch):
    time = np.linspace(4.0, 6.0, 81)
    intensity = np.vstack(
        [
            12.0 * np.exp(-0.5 * ((time - 5.0) / 0.08) ** 2),
            np.full(time.size, 3.0),
        ]
    )
    monkeypatch.setattr(
        graphs_module,
        "deconvolve_channel_matrix",
        lambda *args, **kwargs: _mixed_deconvolution_bundle(time),
    )
    view = GraphView()
    try:
        chart = QChart()
        x_axis = QValueAxis()
        y_axis = QValueAxis()
        chart.addAxis(x_axis, Qt.AlignBottom)
        chart.addAxis(y_axis, Qt.AlignLeft)
        view._add_eic_series(
            chart,
            x_axis,
            y_axis,
            time,
            intensity,
            _deconvolution_plot_compound(is_unlabelled_target=True),
            1.0,
        )
        widths = {series.pen().widthF() for series in chart.series()}
        assert 2.2 in widths
    finally:
        view.deleteLater()


def test_unlabelled_mixed_bundle_detailed_plot_draws_fitted_ion(qapp, monkeypatch):
    from manic.ui import detailed_plot_dialog as dialog_module
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    time = np.linspace(4.0, 6.0, 81)
    intensity = np.vstack(
        [
            12.0 * np.exp(-0.5 * ((time - 5.0) / 0.08) ** 2),
            np.full(time.size, 3.0),
        ]
    )
    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    monkeypatch.setattr(
        dialog_module,
        "deconvolve_channel_matrix",
        lambda *args, **kwargs: _mixed_deconvolution_bundle(time),
    )
    dialog = DetailedPlotDialog("Target", "S1")
    drew_model = []
    try:
        dialog.compound_info = _deconvolution_plot_compound(is_unlabelled_target=True)
        dialog.eic_data = SimpleNamespace(time=time, intensity=intensity)
        dialog._plot_model_component = lambda *args, **kwargs: drew_model.append(True)
        dialog._plot_eic_traces()
        assert drew_model == [True]
    finally:
        dialog.deleteLater()
