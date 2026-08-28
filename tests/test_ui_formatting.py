"""
Tests for UI number and value formatting utilities.

Tests formatting logic used to display values in the integration window
and other UI components.
"""

from dataclasses import replace
import pytest
from PySide6.QtCharts import QChart, QScatterSeries, QValueAxis
from PySide6.QtCore import QPointF, Qt
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
from manic.processors.display_deconvolution import plot_display
from manic.ui.colors import (
    QUALIFIER_GREEN,
    QUALIFIER_RED,
    channel_trace_styles,
    label_colors,
)
from manic.ui.identity_chart import identity_cell_tooltip

from manic.ui.integration_window_widget import IntegrationWindow
from manic.ui.left_toolbar import Toolbar
from manic.ui.graphs import GraphView
from manic.ui.main_window import MainWindow
from manic.ui.chart_popup_dialog import ChartPopupDialog
from manic.ui.targeted_qc_widget import TargetedQcWidget
from manic.models.analysis import AnalysisMode, IonChannel, IonRole
from manic.validation.unlabelled_identity import (
    IdentityAssessmentSet,
    IdentityQcResult,
    IdentitySampleAssessment,
    IdentityStatus,
    QualifierRatioResult,
    QualifierStatus,
    qualifier_pair,
)


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for UI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_nic_toggle_updates_preview_state_without_processing_data():
    labels = []
    ratio_states = []
    graph_states = []
    window = SimpleNamespace(
        nat_abundance_toggle=SimpleNamespace(
            isChecked=lambda: True,
            setText=labels.append,
        ),
        toolbar=SimpleNamespace(
            isotopologue_ratios=SimpleNamespace(
                set_use_corrected=ratio_states.append
            ),
            get_selected_compound=lambda: None,
            get_selected_samples=lambda: [],
        ),
        graph_view=SimpleNamespace(set_use_corrected=graph_states.append),
    )

    MainWindow.toggle_natural_abundance_correction(window)

    assert labels == ["Preview Natural Abundance Correction: On"]
    assert ratio_states == [True]
    assert graph_states == [True]


def test_legacy_integration_toggle_leaves_nic_preview_alone():
    graph_states = []
    window = SimpleNamespace(
        legacy_integration_toggle=SimpleNamespace(
            isChecked=lambda: True,
            setText=lambda text: None,
        ),
        use_legacy_integration=False,
        _create_message_box=lambda *args: SimpleNamespace(exec=lambda: None),
        graph_view=SimpleNamespace(set_use_corrected=graph_states.append),
        toolbar=SimpleNamespace(
            get_selected_compound=lambda: None,
            get_selected_samples=lambda: [],
        ),
    )

    MainWindow.toggle_legacy_integration_mode(window)

    assert window.use_legacy_integration is True
    assert graph_states == []


@pytest.fixture
def integration_window(qapp):
    """Create IntegrationWindow instance for testing."""
    window = IntegrationWindow()
    yield window
    window.deleteLater()


def test_unlabelled_toolbar_shows_abundance_under_identity(qapp):
    toolbar = Toolbar(AnalysisMode.UNLABELLED)
    try:
        assert toolbar.isotopologue_ratios.isHidden()
        assert not toolbar.total_abundance.isHidden()
        assert not toolbar.targeted_qc.isHidden()
        layout = toolbar.targeted_qc.parentWidget().layout()
        identity_index = layout.indexOf(toolbar.targeted_qc)
        abundance_index = layout.indexOf(toolbar.total_abundance)
        assert 0 <= identity_index < abundance_index
        assert toolbar.integration.findChild(QLabel, "reference_rt_note") is None
    finally:
        toolbar.deleteLater()


def test_labelled_toolbar_keeps_abundance_under_ratios(qapp):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    try:
        assert not toolbar.isotopologue_ratios.isHidden()
        assert not toolbar.total_abundance.isHidden()
        assert toolbar.targeted_qc.isHidden()
        layout = toolbar.total_abundance.parentWidget().layout()
        ratio_index = layout.indexOf(toolbar.isotopologue_ratios)
        abundance_index = layout.indexOf(toolbar.total_abundance)
        assert 0 <= ratio_index < abundance_index
    finally:
        toolbar.deleteLater()


def test_refresh_mode_charts_shares_one_provider(monkeypatch):
    created = []

    class CountingProvider:
        def __init__(self, use_legacy_integration=False):
            created.append(self)

        def assess_unlabelled_identities(self, compound_name, sample_names):
            return SimpleNamespace(compound_name=compound_name, samples=tuple(sample_names))

    monkeypatch.setattr("manic.ui.main_window.DataProvider", CountingProvider)

    seen_qc = []
    seen_abundance = []
    host = SimpleNamespace(
        analysis_mode=AnalysisMode.UNLABELLED,
        use_legacy_integration=False,
        graph_view=SimpleNamespace(get_current_samples=lambda: ["S1"]),
        _update_targeted_qc=lambda identity: seen_qc.append(identity),
        _update_total_abundance=lambda compound, provider=None: seen_abundance.append(
            provider
        ),
    )

    MainWindow._refresh_mode_charts(host, "Target", ["S1"])

    assert len(created) == 1
    assert seen_qc[0].compound_name == "Target"
    assert seen_abundance == created


def _qion() -> IonChannel:
    return IonChannel(217.0, IonRole.QUANTIFIER)


def _v1(*, expected: float | None = 0.4, tolerance: float | None = 0.25) -> IonChannel:
    return IonChannel(
        147.0,
        IonRole.QUALIFIER,
        ordinal=1,
        expected_ratio=expected,
        ratio_tolerance=tolerance,
    )


def _v2(*, expected: float | None = 0.2, tolerance: float | None = 0.25) -> IonChannel:
    return IonChannel(
        73.0,
        IonRole.QUALIFIER,
        ordinal=2,
        expected_ratio=expected,
        ratio_tolerance=tolerance,
    )


def _identity_snapshot(channels, *sample_rows) -> IdentityAssessmentSet:
    samples = []
    for sample_name, qc, error in sample_rows:
        samples.append(
            IdentitySampleAssessment(
                sample_name,
                qc,
                qualifier_pair(channels, qc, error=error),
                error,
            )
        )
    return IdentityAssessmentSet("Target", channels, tuple(samples))


def _supported_qc(channels, *passed: bool) -> IdentityQcResult:
    qualifiers = [channel for channel in channels if channel.role is IonRole.QUALIFIER]
    return IdentityQcResult(
        status=IdentityStatus.SUPPORTED,
        quantifier_area=100.0,
        observed_rt=1.23,
        rt_error=0.03,
        rt_passed=True,
        qualifier_ratios=tuple(
            QualifierRatioResult(channel, 0.41 if channel.ordinal == 1 else 0.21, flag)
            for channel, flag in zip(qualifiers, passed)
        ),
        reasons=(),
    )


def test_targeted_qc_identity_chart_renders_two_cells(qapp):
    channels = (_qion(), _v1())
    identity = _identity_snapshot(
        channels, ("S1", _supported_qc(channels, True), None)
    )
    widget = TargetedQcWidget()
    try:
        widget.update_results(identity)
        assert widget.ion_legend.text() == "Target  Q ion m/z 217  V ion 1 m/z 147"
        assert "●" not in widget.ion_legend.text()
        assert widget.chart.title() == "Identity"
        assert widget.chart.legend().isVisible()
        assert widget._binding is not None
        assert widget._binding.cell_at(QPointF(1, 1)).qualifier.status is QualifierStatus.VALIDATED
        assert widget._binding.cell_at(QPointF(2, 1)).qualifier.status is QualifierStatus.ABSENT
        x_labels = widget.chart.axes(Qt.Horizontal)[0].categoriesLabels()
        y_labels = widget.chart.axes(Qt.Vertical)[0].categoriesLabels()
        assert x_labels == ["V1", "V2"]
        assert y_labels == ["S1"]
        widget.clear()
        assert widget._identity is None
        assert widget.chart.series() == []
        assert widget.ion_legend.isHidden()
    finally:
        widget.deleteLater()


def test_identity_chart_click_emits_sample_name(qapp):
    channels = (_qion(), _v1())
    identity = _identity_snapshot(
        channels, ("S1", _supported_qc(channels, True), None)
    )
    widget = TargetedQcWidget()
    activated = []
    widget.sample_activated.connect(activated.append)
    try:
        widget.update_results(identity)
        widget._on_cell_clicked(QPointF(2, 1))
        assert activated == ["S1"]
    finally:
        widget.deleteLater()


def test_identity_chart_popup_shows_sample_names(qapp):
    channels = (_qion(), _v1(), _v2())
    fail_v2 = IonChannel(
        73.0, IonRole.QUALIFIER, ordinal=2, expected_ratio=0.2, ratio_tolerance=0.25
    )
    fail_qc = IdentityQcResult(
        status=IdentityStatus.REVIEW_REQUIRED,
        quantifier_area=100.0,
        observed_rt=1.2,
        rt_error=0.0,
        rt_passed=True,
        qualifier_ratios=(
            QualifierRatioResult(channels[1], 0.41, True),
            QualifierRatioResult(fail_v2, 0.80, False),
        ),
        reasons=(),
    )
    identity = _identity_snapshot(
        channels,
        ("S1", _supported_qc(channels, True, True), None),
        ("S2", fail_qc, None),
    )
    dialog = ChartPopupDialog.for_identity(identity)
    try:
        assert dialog.chart.title() == "Identity"
        assert dialog.chart.legend().isVisible()
        assert "Target" in dialog.ion_legend.text()
        assert "●" not in dialog.ion_legend.text()
        y_labels = dialog.chart.axes(Qt.Vertical)[0].categoriesLabels()
        x_labels = dialog.chart.axes(Qt.Horizontal)[0].categoriesLabels()
        assert set(y_labels) == {"S1", "S2"}
        assert x_labels == ["V1", "V2"]
        assert dialog._identity_binding is not None
        s1_v1 = dialog._identity_binding.cell_at(QPointF(1, 2))
        s2_v2 = dialog._identity_binding.cell_at(QPointF(2, 1))
        assert s1_v1.sample_name == "S1"
        assert s1_v1.qualifier.status is QualifierStatus.VALIDATED
        assert s2_v2.sample_name == "S2"
        assert s2_v2.qualifier.status is QualifierStatus.FAILED
        labels = [series.name() for series in dialog.chart.series()]
        assert "Validated" in labels
        assert "Failed" in labels
        assert "No verdict" in labels
        assert all(isinstance(series, QScatterSeries) for series in dialog.chart.series())
    finally:
        dialog.deleteLater()


def test_identity_cell_tooltip_explains_absent_and_unassessed():
    channels = (_qion(), _v1())
    missing_q = IdentityQcResult(
        status=IdentityStatus.NOT_DETECTED,
        quantifier_area=0.0,
        observed_rt=None,
        rt_error=None,
        rt_passed=None,
        qualifier_ratios=(QualifierRatioResult(channels[1], None, None),),
        reasons=("Q ion was not detected above the assessment floor",),
    )
    snapshot = _identity_snapshot(
        channels,
        ("S1", missing_q, None),
        ("S2", None, "EIC file is missing"),
    )
    absent = snapshot.for_sample("S1").qualifiers.v2
    from manic.ui.identity_chart import IdentityCell

    assert "not in the method" in identity_cell_tooltip(IdentityCell("S1", absent))
    not_assessed = snapshot.for_sample("S1").qualifiers.v1
    assert "Q ion was not detected" in identity_cell_tooltip(
        IdentityCell("S1", not_assessed)
    )
    unavailable = snapshot.for_sample("S2").qualifiers.v1
    assert "EIC file is missing" in identity_cell_tooltip(
        IdentityCell("S2", unavailable)
    )


def test_channel_trace_styles_keep_q_steel_blue_and_solid():
    channels = (_qion(), _v1(), _v2())
    identity = _identity_snapshot(
        channels, ("S1", _supported_qc(channels, True, False), None)
    )
    styles = channel_trace_styles(channels, identity.for_sample("S1"))

    assert styles[0].color == label_colors[0]
    assert styles[0].line_style == Qt.SolidLine
    assert styles[1].color == QUALIFIER_GREEN
    assert styles[1].line_style == Qt.SolidLine
    assert styles[2].color == QUALIFIER_RED
    assert styles[2].line_style == Qt.DashDotLine


def test_channel_trace_styles_colour_v2_by_ordinal():
    channels = (_qion(), _v2())
    qc = IdentityQcResult(
        status=IdentityStatus.REVIEW_REQUIRED,
        quantifier_area=100.0,
        observed_rt=1.2,
        rt_error=0.0,
        rt_passed=True,
        qualifier_ratios=(QualifierRatioResult(channels[1], 0.80, False),),
        reasons=(),
    )
    identity = _identity_snapshot(channels, ("S1", qc, None))
    styles = channel_trace_styles(channels, identity.for_sample("S1"))

    assert len(styles) == 2
    assert styles[0].color == label_colors[0]
    assert styles[1].color == QUALIFIER_RED
    assert styles[1].line_style == Qt.DashDotLine
    assert styles[1].color != label_colors[1]


def test_channel_trace_styles_labelled_palette_unchanged():
    channels = (
        IonChannel(174.0, IonRole.ISOTOPOLOGUE, ordinal=0),
        IonChannel(175.0, IonRole.ISOTOPOLOGUE, ordinal=1),
        IonChannel(176.0, IonRole.ISOTOPOLOGUE, ordinal=2),
    )
    styles = channel_trace_styles(channels, None)
    assert [style.color for style in styles] == label_colors[:3]
    assert all(style.line_style == Qt.SolidLine for style in styles)


def test_graph_unlabelled_traces_use_status_pens(qapp):
    channels = (_qion(), _v2())
    qc = IdentityQcResult(
        status=IdentityStatus.REVIEW_REQUIRED,
        quantifier_area=100.0,
        observed_rt=1.2,
        rt_error=0.0,
        rt_passed=True,
        qualifier_ratios=(QualifierRatioResult(channels[1], 0.80, False),),
        reasons=(),
    )
    identity = _identity_snapshot(channels, ("S1", qc, None))
    styles = channel_trace_styles(channels, identity.for_sample("S1"))
    time = np.linspace(0.0, 1.0, 8)
    intensity = np.vstack([np.ones(time.size), np.full(time.size, 2.0)])
    view = GraphView()
    try:
        chart = QChart()
        x_axis = QValueAxis()
        y_axis = QValueAxis()
        chart.addAxis(x_axis, Qt.AlignBottom)
        chart.addAxis(y_axis, Qt.AlignLeft)
        view._add_trace_series(
            chart,
            x_axis,
            y_axis,
            time,
            intensity,
            1.0,
            selected=True,
            raw_context=False,
            channel_styles=styles,
        )
        pens = [series.pen() for series in chart.series()]
        assert pens[0].color().getRgb()[:3] == label_colors[0].getRgb()[:3]
        assert pens[0].style() == Qt.SolidLine
        assert pens[1].color().getRgb()[:3] == QUALIFIER_RED.getRgb()[:3]
        assert pens[1].style() == Qt.DashDotLine
    finally:
        view.deleteLater()


def test_graph_labelled_traces_keep_label_palette(qapp):
    channels = (
        IonChannel(174.0, IonRole.ISOTOPOLOGUE, ordinal=0),
        IonChannel(175.0, IonRole.ISOTOPOLOGUE, ordinal=1),
    )
    styles = channel_trace_styles(channels, None)
    time = np.linspace(0.0, 1.0, 8)
    intensity = np.vstack([np.ones(time.size), np.full(time.size, 2.0)])
    view = GraphView()
    try:
        chart = QChart()
        x_axis = QValueAxis()
        y_axis = QValueAxis()
        chart.addAxis(x_axis, Qt.AlignBottom)
        chart.addAxis(y_axis, Qt.AlignLeft)
        view._add_trace_series(
            chart,
            x_axis,
            y_axis,
            time,
            intensity,
            1.0,
            selected=True,
            raw_context=False,
            channel_styles=styles,
        )
        pens = [series.pen() for series in chart.series()]
        assert pens[0].color().getRgb()[:3] == label_colors[0].getRgb()[:3]
        assert pens[1].color().getRgb()[:3] == label_colors[1].getRgb()[:3]
        assert pens[0].style() == Qt.SolidLine
        assert pens[1].style() == Qt.SolidLine
    finally:
        view.deleteLater()


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
        is_unlabelled_target=False,
        analysis_channels=(
            IonChannel(174.0, IonRole.ISOTOPOLOGUE, ordinal=0),
            IonChannel(175.0, IonRole.ISOTOPOLOGUE, ordinal=1),
        ),
    )
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session",
        lambda *_args: compound,
    )
    view = GraphView()
    try:
        view._update_channel_legend("alanine", _multi_trace_eics(4))
        text = view.channel_legend.text()
        assert not view.channel_legend.isHidden()
        assert "M+0 m/z 174" in text
        assert "M+1 m/z 175" in text
        assert text.count("●") == 2
        assert "V ion" not in text
    finally:
        view.deleteLater()


def test_channel_legend_hides_for_unlabelled_target(qapp, monkeypatch):
    compound = SimpleNamespace(
        is_unlabelled_target=True,
        analysis_channels=(
            IonChannel(217.0, IonRole.QUANTIFIER),
            IonChannel(147.0, IonRole.QUALIFIER, ordinal=1),
        ),
    )
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session",
        lambda *_args: compound,
    )
    view = GraphView()
    try:
        view.channel_legend.show()
        view._update_channel_legend("Target", _multi_trace_eics(2))
        assert view.channel_legend.isHidden()
    finally:
        view.deleteLater()


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


def _empty_second_channel_bundle(time):
    bundle = _mixed_deconvolution_bundle(time)
    empty = replace(
        bundle.channels[1].result,
        selected=np.zeros(time.size),
        selected_center=None,
        empty=True,
    )
    return replace(
        bundle,
        channels=(
            bundle.channels[0],
            replace(bundle.channels[1], result=empty),
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
        "manic.processors.display_deconvolution.deconvolve_channel_matrix",
        lambda *args, **kwargs: _mixed_deconvolution_bundle(time),
    )
    view = GraphView()
    try:
        compound = _deconvolution_plot_compound(is_unlabelled_target=False)
        prepared = plot_display(time, intensity, compound, use_corrected=False)
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
            compound,
            1.0,
            prepared,
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
        "manic.processors.display_deconvolution.deconvolve_channel_matrix",
        lambda *args, **kwargs: _mixed_deconvolution_bundle(time),
    )
    view = GraphView()
    try:
        compound = _deconvolution_plot_compound(is_unlabelled_target=True)
        prepared = plot_display(time, intensity, compound, use_corrected=False)
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
            compound,
            1.0,
            prepared,
        )
        widths = {series.pen().widthF() for series in chart.series()}
        assert 2.2 in widths
    finally:
        view.deleteLater()


def test_unlabelled_empty_channel_is_not_redrawn_as_a_failed_trace(qapp, monkeypatch):
    time = np.linspace(4.0, 6.0, 81)
    intensity = np.vstack(
        [
            12.0 * np.exp(-0.5 * ((time - 5.0) / 0.08) ** 2),
            np.full(time.size, 3.0),
        ]
    )
    monkeypatch.setattr(
        "manic.processors.display_deconvolution.deconvolve_channel_matrix",
        lambda *args, **kwargs: _empty_second_channel_bundle(time),
    )
    view = GraphView()
    try:
        compound = _deconvolution_plot_compound(is_unlabelled_target=True)
        prepared = plot_display(time, intensity, compound, use_corrected=False)
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
            compound,
            1.0,
            prepared,
        )

        selected_series = [
            series for series in chart.series() if series.pen().widthF() == 2.2
        ]
        assert len(selected_series) == 1
    finally:
        view.deleteLater()


def test_unlabelled_mixed_bundle_detailed_plot_draws_fitted_ion(qapp, monkeypatch):
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
        "manic.processors.display_deconvolution.deconvolve_channel_matrix",
        lambda *args, **kwargs: _mixed_deconvolution_bundle(time),
    )
    dialog = DetailedPlotDialog("Target", "S1")
    drew_model = []
    try:
        dialog.compound_info = _deconvolution_plot_compound(is_unlabelled_target=True)
        dialog.eic_data = SimpleNamespace(time=time, intensity=intensity)
        prepared = plot_display(
            time, intensity, dialog.compound_info, use_corrected=False
        )
        dialog._plot_model_component = lambda *args, **kwargs: drew_model.append(True)
        dialog._plot_eic_traces(prepared)
        assert drew_model == [True]
    finally:
        dialog.deleteLater()


def _labelled_detail_compound(*, use_baseline=1, label_atoms=1):
    from manic.io.compound_reader import Compound

    return Compound(
        compound_name="glucose",
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        label_atoms=label_atoms,
        mass0=319.0,
        formula="C6H12O6",
        baseline_correction=use_baseline,
        deconvolution_level="4",
        deconvolution_fit_type="auto",
        deconvolution_noise_gate="balanced",
    )


def _labelled_detail_eic():
    time = np.linspace(0.0, 10.0, 201)
    intensity = np.vstack(
        [
            10.0 * np.exp(-0.5 * ((time - 7.0) / 0.25) ** 2),
            3.0 * np.exp(-0.5 * ((time - 7.0) / 0.25) ** 2),
        ]
    )
    return time, intensity


def test_detailed_eic_draws_when_higher_mn_are_empty(qapp, monkeypatch):
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    time = np.linspace(0.0, 10.0, 201)
    intensity = np.vstack(
        [
            10.0 * np.exp(-0.5 * ((time - 7.0) / 0.25) ** 2),
            np.zeros(time.size),
            np.zeros(time.size),
        ]
    )
    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    dialog = DetailedPlotDialog("glucose", "S1")
    try:
        dialog.compound_info = _labelled_detail_compound(label_atoms=2)
        dialog.eic_data = SimpleNamespace(time=time, intensity=intensity)
        dialog._plot_eic()
        assert dialog._eic_plot_error is None, dialog._eic_plot_error
        assert dialog.eic_plot.data_lines
        assert max(float(np.max(y)) for _x, y in dialog.eic_plot.data_lines) > 1.0
    finally:
        dialog.deleteLater()


def test_detailed_eic_stays_visible_when_display_pipeline_fails(qapp, monkeypatch):
    from manic.ui import detailed_plot_dialog as dialog_module
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    time, intensity = _labelled_detail_eic()
    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    monkeypatch.setattr(
        dialog_module,
        "plot_display",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("display failed")),
    )
    dialog = DetailedPlotDialog("glucose", "S1")
    baseline_displays = []
    try:
        dialog.compound_info = _labelled_detail_compound()
        dialog.eic_data = SimpleNamespace(time=time, intensity=intensity)
        dialog._add_baseline_lines = (
            lambda _left, _right, prepared: baseline_displays.append(prepared)
        )
        dialog._plot_eic()
        dialog._update_info_label()
        assert dialog.eic_plot.data_lines
        assert dialog._eic_plot_error is None
        assert not dialog.info_label.text().startswith("EIC plot failed")
        assert max(float(np.max(y)) for _x, y in dialog.eic_plot.data_lines) > 1.0
        assert len(baseline_displays) == 1
        assert baseline_displays[0].display is None
        assert baseline_displays[0].intensity == pytest.approx(intensity)
    finally:
        dialog.deleteLater()


def test_detailed_eic_info_strip_reports_failure_when_plot_never_draws(qapp, monkeypatch):
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
        dialog.eic_plot.finalize_plot = lambda: (_ for _ in ()).throw(
            RuntimeError("finalize failed")
        )
        dialog._plot_eic()
        dialog._update_info_label()
        assert dialog.info_label.text().startswith("EIC plot failed: finalize failed")
        assert "plot failed" in dialog.eic_plot.ax.get_title()
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize("use_corrected", [False, True])
def test_detailed_eic_draws_labelled_traces(qapp, monkeypatch, use_corrected):
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    time, intensity = _labelled_detail_eic()
    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    dialog = DetailedPlotDialog("glucose", "S1", use_corrected=use_corrected)
    try:
        dialog.compound_info = _labelled_detail_compound()
        dialog.eic_data = SimpleNamespace(time=time, intensity=intensity)
        dialog._plot_eic()
        assert dialog._eic_plot_error is None, dialog._eic_plot_error
        assert dialog.eic_plot.data_lines
        assert max(float(np.max(y)) for _x, y in dialog.eic_plot.data_lines) > 1.0
    finally:
        dialog.deleteLater()


def _outside_window_pair():
    time = np.linspace(6.0, 8.5, 251)
    selected = 6.0 * np.exp(-0.5 * ((time - 7.0) / 0.08) ** 2)
    excluded = 40.0 * np.exp(-0.5 * ((time - 8.0) / 0.08) ** 2)
    return time, np.vstack([selected + excluded, 0.3 * selected + 0.3 * excluded])


def _outside_window_compound():
    from manic.io.compound_reader import Compound

    return Compound(
        compound_name="pyruvate",
        retention_time=7.0,
        loffset=0.3,
        roffset=0.3,
        label_atoms=1,
        mass0=174.0,
        formula="C6H12O6",
        baseline_correction=0,
        deconvolution_level="4",
        deconvolution_fit_type="auto",
        deconvolution_noise_gate="balanced",
    )


def _series_xy(series):
    points = series.points()
    return (
        np.array([point.x() for point in points], dtype=np.float64),
        np.array([point.y() for point in points], dtype=np.float64),
    )


def test_corrected_preview_keeps_raw_context_on_graph_tile(qapp, monkeypatch):
    time, raw = _outside_window_pair()
    compound = _outside_window_compound()
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session",
        lambda *args, **kwargs: compound,
    )
    view = GraphView()
    view.use_corrected = True
    try:
        prepared = plot_display(time, raw, compound, use_corrected=True)
        assert prepared.display.bundle.shows_model_overlays(independent_channels=False)
        assert not prepared.includes_raw_underlay

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
            raw,
            compound,
            1.0,
            prepared,
        )

        faint = [
            series
            for series in chart.series()
            if series.pen().widthF() == 1.0 and series.pen().color().alpha() == 75
        ]
        solid = [series for series in chart.series() if series.pen().widthF() == 2.2]
        dotted = [
            series
            for series in chart.series()
            if series.pen().style() == Qt.DotLine
        ]
        assert faint
        assert solid
        assert not dotted

        faint_peak_times = []
        for series in faint:
            xs, ys = _series_xy(series)
            if ys.size:
                faint_peak_times.append(float(xs[int(np.argmax(ys))]))
        solid_peak_times = []
        for series in solid:
            xs, ys = _series_xy(series)
            if ys.size:
                solid_peak_times.append(float(xs[int(np.argmax(ys))]))
        assert any(abs(peak - 8.0) < 0.08 for peak in faint_peak_times)
        assert all(abs(peak - 7.0) < 0.08 for peak in solid_peak_times)

        eic = SimpleNamespace(
            time=time,
            intensity=raw,
            sample_name="sample_01",
            compound_name="pyruvate",
        )
        chart_view = view._build_plot(eic)
        plot_y = chart_view.chart().axes()[1]
        raw_max = float(np.max(raw))
        scale_factor = 10 ** int(np.floor(np.log10(raw_max)))
        assert plot_y.max() >= (raw_max / scale_factor) * 1.04
    finally:
        view.deleteLater()


def test_corrected_preview_keeps_raw_context_on_detailed_plot(qapp, monkeypatch):
    from manic.ui.detailed_plot_dialog import DetailedPlotDialog

    time, raw = _outside_window_pair()
    compound = _outside_window_compound()
    monkeypatch.setattr(DetailedPlotDialog, "_load_data", lambda self: None)
    dialog = DetailedPlotDialog("pyruvate", "sample_01", use_corrected=True)
    try:
        dialog.compound_info = compound
        dialog.eic_data = SimpleNamespace(time=time, intensity=raw)
        prepared = plot_display(time, raw, compound, use_corrected=True)
        assert prepared.display.bundle.shows_model_overlays(independent_channels=False)
        assert not prepared.includes_raw_underlay
        dialog._plot_eic_traces(prepared)

        faint = [
            line
            for line in dialog.eic_plot.ax.lines
            if line.get_linewidth() == 1.0
        ]
        solid = [
            line
            for line in dialog.eic_plot.ax.lines
            if line.get_linewidth() == 2
        ]
        dotted = [
            line
            for line in dialog.eic_plot.ax.lines
            if line.get_linestyle() == ":"
        ]
        assert faint
        assert solid
        assert not dotted

        faint_peak_times = [
            float(line.get_xdata()[int(np.argmax(line.get_ydata()))])
            for line in faint
            if np.asarray(line.get_ydata()).size
        ]
        solid_peak_times = [
            float(line.get_xdata()[int(np.argmax(line.get_ydata()))])
            for line in solid
            if np.asarray(line.get_ydata()).size
        ]
        assert any(abs(peak - 8.0) < 0.08 for peak in faint_peak_times)
        assert all(abs(peak - 7.0) < 0.08 for peak in solid_peak_times)
        assert max(float(np.max(y)) for _x, y in dialog.eic_plot.data_lines) > 30.0
    finally:
        dialog.deleteLater()


def test_preview_off_graph_tile_still_draws_model_overlay(qapp):
    time, raw = _outside_window_pair()
    compound = _outside_window_compound()
    view = GraphView()
    try:
        prepared = plot_display(time, raw, compound, use_corrected=False)
        assert prepared.includes_raw_underlay
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
            raw,
            compound,
            1.0,
            prepared,
        )
        solid = [series for series in chart.series() if series.pen().widthF() == 2.2]
        faint = [
            series
            for series in chart.series()
            if series.pen().widthF() == 1.0 and series.pen().color().alpha() == 75
        ]
        assert solid
        assert faint
        solid_peak_times = []
        for series in solid:
            xs, ys = _series_xy(series)
            if ys.size:
                solid_peak_times.append(float(xs[int(np.argmax(ys))]))
        assert all(abs(peak - 7.0) < 0.08 for peak in solid_peak_times)
    finally:
        view.deleteLater()
