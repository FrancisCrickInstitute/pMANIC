"""
Tests for UI number and value formatting utilities.

Tests formatting logic used to display values in the integration window
and other UI components.
"""

from dataclasses import replace
import pytest
from PySide6.QtCharts import (
    QCategoryAxis,
    QChart,
    QValueAxis,
)
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit
import numpy as np
from types import SimpleNamespace

from manic.processors.chromatographic_peak_deconvolution import (
    ChannelDeconvolution,
    ChannelDeconvolutionBundle,
    EICChromatographicPeakDeconvolutionResult,
    deconvolve_eic,
)
from manic.processors.display_deconvolution import plot_display
from manic.processors.tile_y_scale import YScalePolicy, y_axis_from_max
from manic.ui.colors import (
    QUALIFIER_GREEN,
    QUALIFIER_GREY,
    QUALIFIER_RED,
    ChannelTraceStyle,
    channel_trace_styles,
    dark_red_colour,
    label_colors,
)
from manic.ui.integration_window_widget import (
    IntegrationWindow,
    toolbar_decimal_text_is_allowed,
)
from manic.ui.summary_panel import SummaryPanel
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
    qualifier_pair,
)


@pytest.fixture
def integration_window(qapp):
    """Create IntegrationWindow instance for testing."""
    window = IntegrationWindow()
    yield window
    window.deleteLater()


def test_unlabelled_summary_shows_abundance_under_identity(qapp):
    panel = SummaryPanel(AnalysisMode.UNLABELLED)
    toolbar = Toolbar(AnalysisMode.UNLABELLED)
    try:
        assert panel.isotopologue_ratios.isHidden()
        assert not panel.total_abundance.isHidden()
        assert not panel.targeted_qc.isHidden()
        layout = panel.layout()
        assert 0 <= layout.indexOf(panel.targeted_qc) < layout.indexOf(panel.total_abundance)
        assert toolbar.integration.findChild(QLabel, "reference_rt_note") is None
    finally:
        panel.deleteLater()
        toolbar.deleteLater()


def test_labelled_summary_keeps_abundance_under_ratios(qapp):
    panel = SummaryPanel(AnalysisMode.LABELLED)
    try:
        assert not panel.isotopologue_ratios.isHidden()
        assert not panel.total_abundance.isHidden()
        assert panel.targeted_qc.isHidden()
        layout = panel.layout()
        assert 0 <= layout.indexOf(panel.isotopologue_ratios) < layout.indexOf(panel.total_abundance)
    finally:
        panel.deleteLater()


def test_y_scale_options_labelled_only_and_exclusive(qapp):
    labelled = Toolbar(AnalysisMode.LABELLED)
    unlabelled = Toolbar(AnalysisMode.UNLABELLED)
    try:
        selected = labelled.selected_peak_yscale_action
        shared = labelled.shared_yscale_action
        assert selected is not None
        assert unlabelled.selected_peak_yscale_action is None

        selected.trigger()
        assert selected.isChecked()
        assert not shared.isChecked()
        shared.trigger()
        assert shared.isChecked()
        assert not selected.isChecked()
        shared.trigger()
        assert not shared.isChecked()
        assert not selected.isChecked()
    finally:
        labelled.deleteLater()
        unlabelled.deleteLater()


def test_set_y_scale_policy_replots_only_on_change(qapp, monkeypatch):
    view = GraphView()
    replots = []
    monkeypatch.setattr(view, "_replot_current", lambda: replots.append(1))
    try:
        view.set_y_scale_policy(YScalePolicy.SHARED_EXTRACT)
        assert replots == [1]
        view.set_y_scale_policy(YScalePolicy.SHARED_EXTRACT)
        assert replots == [1]
    finally:
        view.deleteLater()


def test_selected_peak_yscale_follows_compound_deconvolution(qapp, monkeypatch):
    toolbar = Toolbar(AnalysisMode.LABELLED)
    checkbox = toolbar.selected_peak_yscale_action
    emitted = []
    toolbar.y_scale_policy_changed.connect(emitted.append)
    try:
        checkbox.trigger()
        assert checkbox.isChecked()
        emitted.clear()

        monkeypatch.setattr(
            "manic.ui.left_toolbar.read_compound",
            lambda _name: SimpleNamespace(
                deconvolution_level="off",
                baseline_correction=0,
            ),
        )
        toolbar.update_compound_list(["Glucose"])
        assert checkbox.isEnabled() is False
        assert checkbox.isChecked() is False
        assert emitted == [YScalePolicy.PER_TILE_EXTRACT]

        monkeypatch.setattr(
            "manic.ui.left_toolbar.read_compound",
            lambda _name: SimpleNamespace(
                deconvolution_level="4",
                baseline_correction=0,
            ),
        )
        toolbar.update_compound_list(["Glucose"])
        assert checkbox.isEnabled() is True
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
    host._assess_identities = MainWindow._assess_identities.__get__(host)

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


def _horizontal_axes(chart):
    value_axes = [
        axis for axis in chart.axes(Qt.Horizontal) if type(axis) is QValueAxis
    ]
    category_axes = [
        axis for axis in chart.axes(Qt.Horizontal) if isinstance(axis, QCategoryAxis)
    ]
    return value_axes, category_axes


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
        widget.resize(300, 200)
        widget.show()
        for _ in range(5):
            qapp.processEvents()
        # Anywhere on the row, its name included, as on the Peak area bars beside it.
        chart, viewport = widget.chart, widget.chart_view.viewport()
        name_x = chart.plotArea().left() - 10
        row_y = chart.mapToPosition(QPointF(0, 0), chart.series()[0]).y()
        pos = QPointF(widget.chart_view.mapFromScene(chart.mapToScene(QPointF(name_x, row_y))))
        for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            QApplication.sendEvent(
                viewport,
                QMouseEvent(kind, pos, viewport.mapToGlobal(pos), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier),
            )
        assert activated == ["S1"]
    finally:
        widget.deleteLater()


def test_identity_chart_hover_maps_live_cell(qapp, monkeypatch):
    channels = (_qion(), _v1())
    identity = _identity_snapshot(
        channels,
        ("S1", _supported_qc(channels, True), None),
        ("S2", _supported_qc(channels, False), None),
    )
    shown = []
    hidden = []
    monkeypatch.setattr(
        "manic.ui.targeted_qc_widget.show_identity_tooltip",
        lambda _widget, text: shown.append(text),
    )
    monkeypatch.setattr(
        "manic.ui.targeted_qc_widget.QToolTip.hideText",
        lambda: hidden.append(True),
    )
    widget = TargetedQcWidget()
    try:
        widget.update_results(identity)
        s1_v1 = widget._binding.bar_sets[1]
        assert widget._binding.cell_for(s1_v1).sample_name == "S1"
        s1_v1.hovered.emit(True, 1)
        assert len(shown) == 1
        assert "S1" in shown[0]
        assert "Validated" in shown[0]
        shown.clear()
        hidden.clear()
        s1_v1.hovered.emit(True, 0)
        assert shown == []
        assert hidden == [True]
        hidden.clear()
        s1_v1.hovered.emit(False, 1)
        assert shown == []
        assert hidden == [True]
    finally:
        widget.deleteLater()


def test_identity_chart_popup_hover_maps_live_cell(qapp, monkeypatch):
    channels = (_qion(), _v1())
    identity = _identity_snapshot(
        channels, ("S1", _supported_qc(channels, True), None)
    )
    shown = []
    hidden = []
    monkeypatch.setattr(
        "manic.ui.chart_popup_dialog.show_identity_tooltip",
        lambda _widget, text: shown.append(text),
    )
    monkeypatch.setattr(
        "manic.ui.chart_popup_dialog.QToolTip.hideText",
        lambda: hidden.append(True),
    )
    dialog = ChartPopupDialog.for_identity(identity)
    try:
        v1_set = dialog._identity_binding.bar_sets[0]
        assert dialog._identity_binding.cell_for(v1_set).sample_name == "S1"
        v1_set.hovered.emit(True, 0)
        assert len(shown) == 1
        assert "S1" in shown[0]
        assert "Validated" in shown[0]
        shown.clear()
        hidden.clear()
        v1_set.hovered.emit(True, 1)
        assert shown == []
        assert hidden == [True]
    finally:
        dialog.deleteLater()


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
        _background_work_running=lambda _msg: False,
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
        _export_thread=None,
    )
    window_stub._running_background_thread = (
        lambda: MainWindow._running_background_thread(window_stub)
    )
    window_stub._background_work_running = (
        lambda message: MainWindow._background_work_running(window_stub, message)
    )

    MainWindow.new_analysis_session(window_stub, False)
    assert window_stub._thread is None


@pytest.mark.parametrize(
    "value,expected",
    [
        (9.77123456, "9.771"),
        (15.4567, "15.457"),
        (7.171234, "7.171"),
        (12.3456, "12.346"),
        (0.123456, "0.123"),
        (0.1, "0.1"),
        (0.456789, "0.457"),
        (0.999, "0.999"),
        (0, "0"),
        (0.0, "0"),
        (-0.0, "0"),
        (0.001, "0.001"),
        (0.001234, "0.001"),
        (0.0004567, "0"),
        (0.99995, "1"),
        (1.0001, "1"),
        (9.9995, "9.999"),
        (10.001, "10.001"),
        (123.456, "123.456"),
        (318.123, "318.123"),
        (999.999, "999.999"),
        (-9.77123, "-9.771"),
        (-0.1235, "-0.123"),
        (-15.4567, "-15.457"),
        (1.2345, "1.234"),
        (1.2346, "1.235"),
        (1.2344, "1.234"),
    ],
    ids=[
        "rt_9.771",
        "rt_15.457",
        "rt_7.171",
        "rt_12.346",
        "offset_0.123",
        "offset_0.1",
        "offset_0.457",
        "offset_0.999",
        "zero_int",
        "zero_float",
        "neg_zero",
        "small_0.001",
        "small_0.001234",
        "small_rounds_to_0",
        "boundary_0.99995",
        "boundary_1.0001",
        "boundary_9.9995",
        "boundary_10.001",
        "large_123.456",
        "large_318.123",
        "large_999.999",
        "neg_9.771",
        "neg_0.123",
        "neg_15.457",
        "edge_1.2345",
        "edge_1.2346",
        "edge_1.2344",
    ],
)
def test_format_number(integration_window, value, expected):
    assert integration_window._format_number(value) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1.234", True),
        ("7.1 - 7.567", True),
        ("", True),
        ("1.2345", False),
        ("7.1 - 7.5678", False),
    ],
    ids=[
        "three_decimals",
        "range_three_decimals",
        "empty",
        "fourth_decimal",
        "range_fourth_decimal",
    ],
)
def test_toolbar_decimal_text_is_allowed(text, expected):
    assert toolbar_decimal_text_is_allowed(text) is expected


class TestToolbarDecimalInput:
    def test_offset_field_refuses_a_fourth_decimal_digit(self, integration_window):
        edit = integration_window.findChild(QLineEdit, "lo_input")
        edit.insert("1.234")
        assert edit.text() == "1.234"
        edit.insert("5")
        assert edit.text() == "1.234"


@pytest.mark.parametrize(
    "values,expected",
    [
        ([9.77, 9.77, 9.77], "9.77"),
        ([9.77, 9.77000001, 9.76999999], "9.77"),
        ([9.5, 10.2], "9.5 - 10.2"),
        ([7.1, 7.5, 7.3, 7.8, 7.2], "7.1 - 7.8"),
        ([9.5, None, 10.2, None], "9.5 - 10.2"),
        ([None, None, None], ""),
        ([], ""),
        ([9.77123, 10.4567], "9.771 - 10.457"),
        ([0.123456, 0.456789], "0.123 - 0.457"),
        ([9.5, "invalid", 10.2], "9.5 - 10.2"),
    ],
    ids=[
        "identical",
        "float_noise",
        "two_value_range",
        "min_max",
        "none_filtered",
        "all_none",
        "empty",
        "three_decimals",
        "small_values",
        "invalid_filtered",
    ],
)
def test_format_range(integration_window, values, expected):
    assert integration_window._format_range(values) == expected


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


def test_channel_legend_unlabelled_chips_show_line_style_not_status_colour(
    qapp, monkeypatch
):
    compound = SimpleNamespace(
        is_unlabelled_target=True,
        analysis_channels=(
            IonChannel(217.0, IonRole.QUANTIFIER),
            IonChannel(147.0, IonRole.QUALIFIER, ordinal=1),
            IonChannel(73.0, IonRole.QUALIFIER, ordinal=2),
        ),
    )
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session",
        lambda *_args: compound,
    )
    view = GraphView()
    try:
        view._update_channel_legend("Target", _multi_trace_eics(3))
        assert not view.channel_legend.isHidden()
        assert view.channel_legend.labels() == [
            "Q ion m/z 217",
            "Qualifier ion 1 m/z 147",
            "Qualifier ion 2 m/z 73",
        ]
        styles = [chip.style for chip in view.channel_legend.chips()]
        assert styles[0] == ChannelTraceStyle(label_colors[0], Qt.SolidLine)
        assert styles[1] == ChannelTraceStyle(QUALIFIER_GREY, Qt.SolidLine)
        assert styles[2] == ChannelTraceStyle(QUALIFIER_GREY, Qt.DashDotLine)
        # The QC key stays beside the traces it colours while the Summary is open.
        assert not view.qc_key.isHidden()
        view.summary_button.setChecked(True)
        assert not view.qc_key.isHidden()
    finally:
        view.deleteLater()


def test_channel_legend_shows_a_single_trace_in_dark_red(qapp, monkeypatch):
    compound = SimpleNamespace(
        is_unlabelled_target=False,
        analysis_channels=(IonChannel(174.0, IonRole.ISOTOPOLOGUE, ordinal=0),),
    )
    monkeypatch.setattr(
        "manic.ui.graphs.read_compound_with_session",
        lambda *_args: compound,
    )
    view = GraphView()
    try:
        view._update_channel_legend(
            "alanine", [SimpleNamespace(intensity=np.ones(3, dtype=float))]
        )
        assert not view.channel_legend.isHidden()
        assert view.channel_legend.labels() == ["M+0 m/z 174"]
        assert view.channel_legend.chips()[0].style.color == dark_red_colour
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
        chart_view = view._build_plot(
            eic, axis_scale=y_axis_from_max(float(np.max(raw)))
        )
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
