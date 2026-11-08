"""
Comprehensive visualization dialog for mass spectrometry data analysis.

Provides integrated visualization of chromatographic and spectral data:
1. Extracted Ion Chromatogram (EIC) with integration boundary visualization
2. Total Ion Chromatogram (TIC) with compound retention time indicators
3. Mass spectrum at the specified retention time point

Features responsive layout adaptation and professional scientific notation.
"""

import logging
import sys
from collections.abc import Callable, Sequence

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from manic.constants import (
    DETAILED_DIALOG_HEIGHT,
    DETAILED_DIALOG_SCREEN_RATIO,
    DETAILED_DIALOG_WIDTH,
    DETAILED_TIC_HEIGHT,
    MS_TIME_TOLERANCE,
    PLOT_GUIDELINE_WIDTH,
    PLOT_LINE_WIDTH,
    PLOT_STEM_WIDTH,
)
from manic.io.cdf_data_extractor import ensure_ms_data_for_time
from manic.io.compound_reader import read_compound_with_session
from manic.io.tic_reader import read_tic
from manic.processors.display_deconvolution import PlotDisplay, plot_display
from manic.processors.eic_processing import get_eics_for_compound
from manic.processors.integration import compute_linear_baseline
from manic.validation.unlabelled_identity import quantifier_apex_time
from manic.models.analysis import IonRole
from manic.models.sample_fit_type import get_sample_fit_types
from manic.ui.channel_labels import channel_legend_label, has_defined_channel
from manic.ui.colors import (
    channel_trace_styles,
    label_colors,
    steel_blue_colour,
)
from manic.validation.unlabelled_identity import IdentitySampleAssessment, QualifierStatus
from manic.ui.chart_header import HeaderName
from manic.ui.chart_style import text_style
from manic.ui.graphs import tile_caption
from manic.ui.identity_chart import STATUS_LABELS
from manic.ui.icon_button import segmented
from manic.ui.matplotlib_plot_widget import CompactNavigationToolbar, MatplotlibPlotWidget
from manic.ui import theme
from manic.ui.theme import COLORS, FONT_SIZE_TITLE

logger = logging.getLogger(__name__)
# Secondary legend entries, in key order: (label, line style, alpha, width as drawn), by treatment.
TRACE_KEY = {
    "raw": ("Raw signal", "solid", 0.4, 1.0),
    "component": ("Other fitted peak", "dotted", 0.6, 1.2),
    "baseline": ("Baseline", "dashed", 1.0, 1.2),
}
PLOT_TITLES = ("Extracted ion chromatogram", "Total ion chromatogram", "Mass spectrum")
# m/z either side of a labelled compound's isotopologues that the spectrum opens on.
SPECTRUM_CLUSTER_MARGIN = 20


def _rgba(qcolor, alpha: float) -> str:
    return f"rgba({qcolor.red()},{qcolor.green()},{qcolor.blue()},{alpha})"


def _show_empty(plot: MatplotlibPlotWidget, title: str) -> None:
    """Draws the empty state now, so the previous sample's traces never stay under it."""
    plot.clear_plot()
    plot.set_title(title)
    # Not finalize_plot: a failed plot may have failed there.
    plot.canvas.draw_idle()


# Same meaning as on the grid tiles: dashed steel blue bounds the
# integration window, solid grey marks the target tR or m/z.
class DetailedPlotDialog(QDialog):
    """
    Modal dialog for detailed compound-sample visualization.

    Provides comprehensive analytical views with:
    - Enhanced EIC visualization with integration boundary display
    - TIC overlay with precise retention time marking
    - Mass spectrum extraction at compound retention time
    - Professional zoom and pan controls for data exploration
    - Responsive layout with scroll support for various screen sizes
    """

    def __init__(
        self,
        compound_name: str,
        sample_name: str,
        parent=None,
        use_corrected: bool = False,
        *,
        samples: Sequence[str] = (),
        identity_for: Callable[[str], IdentitySampleAssessment | None] = lambda _name: None,
    ):
        """``samples`` is the grid's order, which the previous/next sample buttons follow."""
        super().__init__(parent)
        self.compound_name = compound_name
        self.sample_name = sample_name
        self.use_corrected = use_corrected
        self._samples = list(samples) or [sample_name]
        self._identity_for = identity_for
        self.identity = identity_for(sample_name)
        self._channel_styles = ()
        # Which TRACE_KEY treatments the chromatogram drew.
        self._treatments: set[str] = set()

        self.eic_data = None
        self.tic_data = None
        self.ms_data = None
        self.compound_info = None
        self.observed_rt = None
        self._eic_plot_error = None

        self._setup_ui()
        self._show_sample_name()
        self._load_data()

    def step_sample(self, step: int) -> None:
        """Show the previous (-1) or next (1) sample in the grid's order, if there is one."""
        index = self._samples.index(self.sample_name) + step
        if not 0 <= index < len(self._samples):
            return
        self.sample_name = self._samples[index]
        self.identity = self._identity_for(self.sample_name)
        self.eic_data = self.tic_data = self.ms_data = self.compound_info = None
        self.observed_rt = None
        self._eic_plot_error = None
        for plot, title in zip((self.eic_plot, self.tic_plot, self.ms_plot), PLOT_TITLES):
            plot.set_title(title)
        self._show_sample_name()
        self._load_data()

    def _show_sample_name(self) -> None:
        self.setWindowTitle(f"{self.compound_name} in {self.sample_name} — MANIC")
        # A sample's fit override, as its grid caption names it.
        fit_type = get_sample_fit_types(self.compound_name).get((self.compound_name, self.sample_name))
        self.sample_label.setText(tile_caption(f"in {self.sample_name}", fit_type))
        self.sample_label.setAccessibleName(self.sample_name)
        index = self._samples.index(self.sample_name)
        self.previous_sample.setEnabled(index > 0)
        self.next_sample.setEnabled(index < len(self._samples) - 1)

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setModal(True)

        self.setSizeGripEnabled(True)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowMaximizeButtonHint
        )
        if self.parent():
            screen = QApplication.screenAt(self.parent().geometry().center())
        else:
            screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry() if screen else None

        if sys.platform == "win32":
            width = min(
                DETAILED_DIALOG_WIDTH,
                int(screen_rect.width() * 0.85)
                if screen_rect
                else DETAILED_DIALOG_WIDTH,
            )
            height = min(
                DETAILED_DIALOG_HEIGHT + 150,
                int(screen_rect.height() * 0.85)
                if screen_rect
                else DETAILED_DIALOG_HEIGHT,
            )
        elif sys.platform == "darwin":
            width = min(
                DETAILED_DIALOG_WIDTH,
                int(screen_rect.width() * 0.9)
                if screen_rect
                else DETAILED_DIALOG_WIDTH,
            )
            height = min(
                DETAILED_DIALOG_HEIGHT,
                int(screen_rect.height() * 0.85)
                if screen_rect
                else DETAILED_DIALOG_HEIGHT,
            )
        else:
            width = min(
                DETAILED_DIALOG_WIDTH,
                int(screen_rect.width() * 0.85)
                if screen_rect
                else DETAILED_DIALOG_WIDTH,
            )
            height = min(
                DETAILED_DIALOG_HEIGHT,
                int(screen_rect.height() * 0.85)
                if screen_rect
                else DETAILED_DIALOG_HEIGHT,
            )

        self.resize(width, height)

        min_width = min(600, int(screen_rect.width() * 0.5) if screen_rect else 600)
        min_height = min(500, int(screen_rect.height() * 0.4) if screen_rect else 500)
        self.setMinimumSize(min_width, min_height)

        if screen_rect:
            screen_width = screen_rect.width()
            screen_height = screen_rect.height()

            if screen_width >= 2560:
                width_ratio = 0.95
                height_ratio = 0.95
            elif screen_width >= 1920:
                width_ratio = 0.92
                height_ratio = 0.92
            else:
                width_ratio = DETAILED_DIALOG_SCREEN_RATIO
                height_ratio = DETAILED_DIALOG_SCREEN_RATIO

            max_width = int(screen_width * width_ratio)
            max_height = int(screen_height * height_ratio)
            self.setMaximumSize(max_width, max_height)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        title_label = HeaderName(self.compound_name, min_chars=12)
        theme.style(title_label, text_style("text", FONT_SIZE_TITLE, 600))
        self.sample_label = HeaderName(min_chars=14)
        theme.style(self.sample_label, text_style("text_secondary", FONT_SIZE_TITLE))
        header_layout.addWidget(title_label)
        header_layout.addWidget(self.sample_label)
        header_layout.addSpacing(4)
        header_layout.addWidget(self._build_sample_steps())
        header_layout.addStretch()
        layout.addLayout(header_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.NoFrame)
        theme.style(
            scroll_area,
            "QScrollArea { background: @surface; border: 1px solid @border; border-radius: 8px; }",
        )

        scroll_area.setMinimumSize(400, 300)
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        scroll_widget = QWidget()
        theme.style(scroll_widget, "background-color: @surface;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        self.eic_plot = MatplotlibPlotWidget(
            title=PLOT_TITLES[0],
            x_label="Time (min)",
            y_label="Intensity",
        )
        # Minimums leave room for a title, ticks and axis labels and no more, so all
        # three charts fit together in a short window; only a shorter one scrolls.
        self.eic_plot.setMinimumHeight(200)
        self.eic_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.eic_plot)
        # The TIC and spectrum share one row under the chromatogram, so all three
        # charts are in view together, even on a short screen.
        supporting = QSplitter(Qt.Horizontal)
        supporting.setChildrenCollapsible(False)
        splitter.addWidget(supporting)

        self.tic_plot = MatplotlibPlotWidget(
            title=PLOT_TITLES[1],
            x_label="Time (min)",
            y_label="Total intensity",
        )
        self.tic_plot.setMinimumHeight(140)
        self.tic_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        supporting.addWidget(self.tic_plot)

        self.ms_plot = MatplotlibPlotWidget(
            title=PLOT_TITLES[2], x_label="m/z", y_label="Intensity"
        )
        self.ms_plot.setMinimumHeight(140)
        self.ms_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        supporting.addWidget(self.ms_plot)

        # One toolbar for all three charts, in the title row.
        self.nav_toolbar = CompactNavigationToolbar(
            (self.eic_plot, self.tic_plot, self.ms_plot)
        )
        header_layout.addWidget(self.nav_toolbar)

        # The chromatogram is what is inspected; it gets three fifths of the height.
        splitter.setSizes([3 * DETAILED_TIC_HEIGHT, 2 * DETAILED_TIC_HEIGHT])
        for index, stretch in enumerate((3, 2)):
            splitter.setStretchFactor(index, stretch)

        scroll_layout.addWidget(splitter)

        scroll_area.setWidget(scroll_widget)

        layout.addWidget(scroll_area)

        info_layout = QHBoxLayout()
        self.info_label = QLabel("Loading…")
        theme.style(self.info_label, text_style("text_secondary", 11))
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label, stretch=1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setAutoDefault(False)
        info_layout.addWidget(close_btn)

        layout.addLayout(info_layout)

        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

    def _build_sample_steps(self) -> QWidget:
        """Previous and next sample, one segmented control; the arrow keys do the same."""
        buttons = []
        for name, glyph, step, key in (
            ("Previous sample", "‹", -1, Qt.Key_Left),
            ("Next sample", "›", 1, Qt.Key_Right),
        ):
            button = QToolButton()
            button.setText(glyph)
            button.setAccessibleName(name)
            button.setToolTip(f"{name} ({QKeySequence(key).toString(QKeySequence.NativeText)})")
            button.clicked.connect(lambda _checked=False, step=step: self.step_sample(step))
            QShortcut(QKeySequence(key), self, lambda step=step: self.step_sample(step))
            buttons.append(button)
        self.previous_sample, self.next_sample = buttons
        box = segmented(*buttons)
        if len(self._samples) <= 1:
            box.hide()  # never shown before it has a parent
        return box

    def _load_data(self):
        """Load all required data for the plots."""
        try:
            self.compound_info = read_compound_with_session(
                self.compound_name, self.sample_name
            )
            if not self.compound_info:
                self._show_error("Failed to load compound information")
                return

            self._channel_styles = channel_trace_styles(
                self.compound_info.analysis_channels,
                self.identity,
            )

            self._load_eic_data()
            if (
                self.eic_data is not None
                and self.compound_info.is_unlabelled_target
            ):
                self.observed_rt = quantifier_apex_time(
                    self.eic_data.time,
                    self.eic_data.intensity,
                    self.compound_info.channel_count,
                    expected_rt=self.compound_info.retention_time,
                    loffset=self.compound_info.loffset,
                    roffset=self.compound_info.roffset,
                )

            self._load_tic_data()

            self._load_ms_data()

            self._plot_eic()
            self._plot_tic()
            self._plot_ms()

            self._update_info_label()

            if not self.eic_data:
                self._show_error(
                    "No EIC data available for this compound-sample combination"
                )

        except Exception as e:
            logger.error(f"Failed to load data for detailed view: {e}")
            self._show_error(f"Failed to load data: {str(e)}")

    def _load_eic_data(self):
        """Load EIC data for the compound-sample combination."""
        try:
            eics = get_eics_for_compound(
                self.compound_name, [self.sample_name], use_corrected=False
            )
            if eics:
                self.eic_data = eics[0]
                logger.debug(f"Loaded EIC data: {len(self.eic_data.time)} points")
            else:
                logger.warning(
                    f"No EIC data found for {self.compound_name}/{self.sample_name}"
                )
                self.eic_data = None

        except Exception as e:
            logger.error(f"Failed to load EIC data: {e}")
            self.eic_data = None

    def _load_tic_data(self):
        """Load TIC data for the sample."""
        try:
            self.tic_data = read_tic(self.sample_name)
            if self.tic_data:
                logger.debug(
                    f"✓ TIC data loaded from DB: {self.sample_name} ({len(self.tic_data.time)} points)"
                )
            else:
                logger.info(
                    f"No TIC data in DB for {self.sample_name} (will show empty plot)"
                )

        except Exception as e:
            logger.error(f"Failed to load TIC data: {e}")
            self.tic_data = None

    def _load_ms_data(self):
        """Load MS data at the compound's retention time."""
        try:
            if self.compound_info:
                retention_time = (
                    self.observed_rt
                    if self.observed_rt is not None
                    else self.compound_info.retention_time
                )
                self.ms_data = ensure_ms_data_for_time(
                    self.sample_name,
                    retention_time,
                    tolerance=MS_TIME_TOLERANCE,
                )

                if self.ms_data:
                    logger.debug(
                        f"✓ MS data ready for {self.sample_name} at {self.ms_data.time:.3f} min ({len(self.ms_data.mz)} peaks)"
                    )
                else:
                    logger.info(
                        f"No MS data available for {self.sample_name} at {retention_time:.3f} min (will show empty plot)"
                    )

        except Exception as e:
            logger.error(f"Failed to load MS data: {e}")
            self.ms_data = None

    def _plot_eic(self):
        """Plot the EIC data with integration boundaries."""
        if not self.eic_data or not self.compound_info:
            _show_empty(self.eic_plot, "Extracted ion chromatogram (no data)")
            return

        self._eic_plot_error = None
        self._treatments = set()
        try:
            self.eic_plot.clear_plot()
            prepared = None
            try:
                prepared = plot_display(
                    self.eic_data.time,
                    self.eic_data.intensity,
                    self.compound_info,
                    use_corrected=self.use_corrected,
                )
                self._plot_eic_traces(prepared)
            except Exception as display_error:
                logger.error(f"Display deconvolution failed: {display_error}")
                prepared = PlotDisplay(
                    display=None,
                    intensity=np.asarray(self.eic_data.intensity, dtype=np.float64),
                    includes_raw_underlay=False,
                )
                self._plot_trace_matrix(prepared.intensity, selected=True)
                if not self.eic_plot.data_lines:
                    self._eic_plot_error = str(display_error)
            if not self.eic_plot.data_lines:
                self._plot_trace_matrix(self.eic_data.intensity, selected=True)
            if self.eic_plot.data_lines:
                self._eic_plot_error = None

            rt = self.compound_info.retention_time
            left_bound = rt - self.compound_info.loffset
            right_bound = rt + self.compound_info.roffset

            for edge in (left_bound, right_bound):
                self.eic_plot.add_vertical_line(
                    edge, color=_rgba(steel_blue_colour, 0.85), width=PLOT_GUIDELINE_WIDTH, style="dashed"
                )
            self.eic_plot.add_vertical_line(
                rt, color=COLORS["text_secondary"], width=PLOT_GUIDELINE_WIDTH, style="solid"
            )

            try:
                self._add_baseline_lines(left_bound, right_bound, prepared)
            except Exception as baseline_error:
                logger.error(f"Failed to draw baseline lines: {baseline_error}")

            # After the channels, so the faint, dotted and dashed lines are named too.
            for treatment, (label, style, alpha, width) in TRACE_KEY.items():
                if treatment in self._treatments:
                    self.eic_plot.add_key_entry(label, style=style, alpha=alpha, width=width)
            # Above the plot, under its title, so it never covers a trace.
            self.eic_plot.show_legend()

            self.eic_plot.finalize_plot()

            logger.debug(
                f"EIC plot - RT: {rt:.3f}, Left: {left_bound:.3f}, Right: {right_bound:.3f}"
            )

        except Exception as e:
            logger.error(f"Failed to plot EIC: {e}")
            self._eic_plot_error = str(e)
            _show_empty(self.eic_plot, "Extracted ion chromatogram (plot failed)")

    def _add_baseline_lines(self, left_bound: float, right_bound: float, prepared):
        if not self.compound_info or not self.eic_data:
            return

        baseline_flag = getattr(self.compound_info, "baseline_correction", 0)
        if not baseline_flag:
            return

        display = prepared.display
        if display is not None and display.bundle.shows_model_overlays(
            independent_channels=getattr(self.compound_info, "is_unlabelled_target", False)
        ):
            drew_baseline = False
            baseline_intensity = prepared.baseline_intensity()
            draw_matrix = (
                baseline_intensity
                if baseline_intensity.ndim > 1
                else baseline_intensity.reshape(1, -1)
            )
            for channel in display.bundle.channels:
                if channel.result.model is None:
                    continue
                selected_trace = np.asarray(
                    draw_matrix[channel.index], dtype=np.float64
                ).reshape(-1)
                trace_mask = np.asarray(channel.result.selected_mask, dtype=bool).reshape(-1)
                if not np.any(trace_mask):
                    continue
                baseline_result = compute_linear_baseline(
                    self.eic_data.time[trace_mask], selected_trace[trace_mask]
                )
                if baseline_result is None:
                    continue
                td_base, baseline_y = baseline_result
                qcolor = self._style_color(channel.index)
                color = f"#{qcolor.red():02x}{qcolor.green():02x}{qcolor.blue():02x}"
                baseline_x = np.array([td_base[0], td_base[-1]])
                baseline_y_vals = np.array([baseline_y[0], baseline_y[-1]])
                self.eic_plot.plot_line(
                    baseline_x,
                    baseline_y_vals,
                    color=color,
                    width=1.2,
                    name="",
                    style="dashed",
                )
                self._treatments.add("baseline")
                drew_baseline = True
            if drew_baseline:
                return

        mask = (self.eic_data.time > left_bound) & (self.eic_data.time < right_bound)
        if not np.any(mask):
            return

        td_win = self.eic_data.time[mask]
        draw_intensity = prepared.intensity

        if draw_intensity.ndim == 1:
            idata_win = draw_intensity[mask]
            baseline_result = compute_linear_baseline(td_win, idata_win)
            if baseline_result is not None:
                td_base, baseline_y = baseline_result
                baseline_x = np.array([td_base[0], td_base[-1]])
                baseline_y_vals = np.array([baseline_y[0], baseline_y[-1]])
                self.eic_plot.plot_line(
                    baseline_x,
                    baseline_y_vals,
                    color=COLORS["text_secondary"],
                    width=1.2,
                    name="",
                    style="dashed",
                )
                self._treatments.add("baseline")
        else:
            for i in range(draw_intensity.shape[0]):
                idata_win = draw_intensity[i, mask]
                baseline_result = compute_linear_baseline(td_win, idata_win)
                if baseline_result is not None:
                    td_base, baseline_y = baseline_result
                    qcolor = self._style_color(i)
                    color = (
                        f"#{qcolor.red():02x}{qcolor.green():02x}{qcolor.blue():02x}"
                    )
                    baseline_x = np.array([td_base[0], td_base[-1]])
                    baseline_y_vals = np.array([baseline_y[0], baseline_y[-1]])
                    self.eic_plot.plot_line(
                        baseline_x,
                        baseline_y_vals,
                        color=color,
                        width=1.2,
                        name="",
                        style="dashed",
                    )
                    self._treatments.add("baseline")

    def _plot_model_component(
        self,
        model,
        component_index: int,
        *,
        selected: bool,
        color_index: int | None = None,
    ):
        """Draw one fitted component over the integration or fit window."""
        multi_trace = self.eic_data.intensity.ndim > 1
        t_left, t_right = (
            (model.integration_left, model.integration_right)
            if selected
            else (model.fit_left, model.fit_right)
        )
        if not (t_right > t_left):
            return

        grid = np.linspace(t_left, t_right, 256)
        values = model.evaluate(grid, component_index)
        matrix = values if values.ndim > 1 else values.reshape(1, -1)
        for i, row in enumerate(matrix):
            series_index = color_index if color_index is not None else i
            qcolor = (
                self._style_color(series_index) if multi_trace else label_colors[0]
            )
            if selected:
                color = _rgba(qcolor, 1.0)
                self.eic_plot.plot_line(
                    grid,
                    row,
                    color=color,
                    width=PLOT_LINE_WIDTH,
                    name=self._channel_label(series_index) if multi_trace else "",
                    style=self._mpl_line_style(series_index),
                )
            else:
                color = _rgba(qcolor, 0.38)
                self.eic_plot.plot_line(
                    grid, row, color=color, width=1.2, name="", style="dotted"
                )
                self._treatments.add("component")

    def _plot_eic_traces(self, prepared):
        display = prepared.display
        bundle = None if display is None else display.bundle
        draw_intensity = prepared.intensity

        if bundle is None or not bundle.shows_model_overlays(
            independent_channels=getattr(self.compound_info, "is_unlabelled_target", False)
        ):
            self._plot_trace_matrix(draw_intensity, selected=True)
            return

        self._plot_trace_matrix(self.eic_data.intensity, selected=False, alpha=0.32)
        self._treatments.add("raw")
        if not prepared.includes_raw_underlay:
            self._plot_trace_matrix(draw_intensity, selected=True)
            return

        unfitted_indices: list[int] = []
        for channel in bundle.channels:
            model = channel.result.model
            if model is None:
                if not channel.result.empty:
                    unfitted_indices.append(channel.index)
                continue
            self._plot_model_component(
                model, model.selected_index, selected=True, color_index=channel.index
            )
            for component_index in range(model.n_components):
                if component_index == model.selected_index:
                    continue
                self._plot_model_component(
                    model, component_index, selected=False, color_index=channel.index
                )
        if unfitted_indices:
            self._plot_trace_matrix(
                self.eic_data.intensity,
                selected=True,
                channel_indices=tuple(unfitted_indices),
            )

    def _plot_trace_matrix(
        self,
        intensity: np.ndarray,
        *,
        selected: bool,
        alpha: float = 1.0,
        channel_indices: tuple[int, ...] | None = None,
    ):
        matrix = intensity if intensity.ndim > 1 else intensity.reshape(1, -1)
        multi_trace = intensity.ndim > 1
        time = np.asarray(self.eic_data.time, dtype=np.float64)
        for i, trace in enumerate(matrix):
            if channel_indices is not None and i not in channel_indices:
                continue
            qcolor = self._style_color(i) if multi_trace else label_colors[0]
            color = _rgba(qcolor, alpha)
            self.eic_plot.plot_line(
                time,
                trace,
                color=color,
                width=PLOT_LINE_WIDTH if selected else 1.0,
                name=self._channel_label(i) if selected and multi_trace else "",
                style=self._mpl_line_style(i) if multi_trace else "solid",
            )

    def _style_color(self, index: int):
        if 0 <= index < len(self._channel_styles):
            return self._channel_styles[index].color
        return label_colors[index % len(label_colors)]

    def _mpl_line_style(self, index: int) -> str:
        if 0 <= index < len(self._channel_styles):
            if self._channel_styles[index].line_style == Qt.DashDotLine:
                return "dashdot"
        return "solid"

    def _channel_label(self, channel_index: int) -> str:
        if not has_defined_channel(self.compound_info, channel_index):
            return ""
        label = channel_legend_label(self.compound_info, channel_index)
        if self.identity is None:
            return label
        channels = self.compound_info.analysis_channels
        if channel_index >= len(channels):
            return label
        channel = channels[channel_index]
        if channel.role is not IonRole.QUALIFIER:
            return label
        status = self.identity.qualifiers.for_ordinal(channel.ordinal).status
        # One name for every grey state; the Identity popup chips give the reason.
        if status not in (QualifierStatus.VALIDATED, QualifierStatus.FAILED):
            status = QualifierStatus.NOT_ASSESSED
        return f"{label} ({STATUS_LABELS[status]})"

    def _plot_tic(self):
        """Plot the TIC data with retention time marker."""
        if not self.tic_data:
            _show_empty(self.tic_plot, "Total ion chromatogram (no data)")
            return

        try:
            self.tic_plot.clear_plot()

            self.tic_plot.plot_line(
                self.tic_data.time,
                self.tic_data.intensity,
                color=COLORS["text_secondary"],
                width=1.4,
                name="Total ion chromatogram",
            )

            if self.compound_info:
                rt = self.compound_info.retention_time
                self.tic_plot.add_vertical_line(
                    rt, color=COLORS["text_secondary"], width=PLOT_GUIDELINE_WIDTH, style="solid"
                )

            self.tic_plot.finalize_plot()

        except Exception as e:
            logger.error(f"Failed to plot TIC: {e}")
            _show_empty(self.tic_plot, "Total ion chromatogram (plot failed)")

    def _plot_ms(self):
        """Plot the mass spectrum data."""
        if not self.ms_data:
            _show_empty(self.ms_plot, "Mass spectrum (no data)")
            return

        try:
            self.ms_plot.clear_plot()

            channels = self.compound_info.analysis_channels if self.compound_info else ()
            isotopologues = bool(channels) and all(
                channel.role is IonRole.ISOTOPOLOGUE for channel in channels
            )
            # Isotopologue stems in their trace colours, so the cluster stands out of the scan.
            self.ms_plot.plot_stems(
                self.ms_data.mz,
                self.ms_data.intensity,
                color=COLORS["text_tertiary" if isotopologues else "text"],
                width=PLOT_STEM_WIDTH,
                highlight=[
                    (channel.mz, self._style_color(i).name()) for i, channel in enumerate(channels)
                ] if isotopologues else (),
            )

            self.ms_plot.label_peaks(
                self.ms_data.mz,
                self.ms_data.intensity,
                own_mz=[channel.mz for channel in channels],
                own_names=[f"M+{channel.ordinal}" for channel in channels] if isotopologues else None,
            )
            if isotopologues:
                # The cluster is a few m/z wide; at full scan it is one sliver.
                masses = [channel.mz for channel in channels]
                self.ms_plot.show_x_range(min(masses) - SPECTRUM_CLUSTER_MARGIN, max(masses) + SPECTRUM_CLUSTER_MARGIN)

            # The target m/z, faint and behind its stem, so the stem's height still reads.
            if self.compound_info:
                self.ms_plot.add_vertical_line(
                    self.compound_info.mass0,
                    color=COLORS["border_strong"],
                    width=PLOT_GUIDELINE_WIDTH,
                    style="solid",
                    behind=True,
                )

            self.ms_plot.finalize_plot()

        except Exception as e:
            logger.error(f"Failed to plot MS: {e}")
            _show_empty(self.ms_plot, "Mass spectrum (plot failed)")

    def _update_info_label(self):
        """tR, the observed apex and the integration window: what the EIC is read against."""
        info_parts = []

        if self.compound_info:
            rt = self.compound_info.retention_time
            info_parts.append(f"tR {rt:.3f} min")
            if self.observed_rt is not None:
                info_parts.append(f"observed apex {self.observed_rt:.3f} min")
            info_parts.append(
                f"integration {rt - self.compound_info.loffset:.3f}–"
                f"{rt + self.compound_info.roffset:.3f} min"
            )

        if self._eic_plot_error:
            info_parts.insert(0, f"EIC plot failed: {self._eic_plot_error}")
        info_text = "  ·  ".join(info_parts) if info_parts else "No data available"
        self.info_label.setText(info_text)

    def _show_error(self, message: str):
        """Show error message to user."""
        msg_box = QMessageBox(
            QMessageBox.Warning, "Error", message, QMessageBox.Ok, self
        )
        msg_box.exec()

        self.info_label.setText(f"Error: {message}")

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def cleanup_plots(self):
        """Clean up all matplotlib resources from plot widgets."""
        try:
            if hasattr(self, "eic_plot") and self.eic_plot:
                self.eic_plot.cleanup()

            if hasattr(self, "tic_plot") and self.tic_plot:
                self.tic_plot.cleanup()

            if hasattr(self, "ms_plot") and self.ms_plot:
                self.ms_plot.cleanup()

            if getattr(self, "nav_toolbar", None) is not None:
                self.nav_toolbar.cleanup()

            self.eic_data = None
            self.tic_data = None
            self.ms_data = None
            self.compound_info = None

            logger.debug(
                f"Cleaned up plots for {self.compound_name}/{self.sample_name}"
            )

        except Exception as e:
            logger.error(f"Error during plot cleanup: {e}")

    def closeEvent(self, event):
        """Handle dialog close event with proper cleanup."""
        self.cleanup_plots()
        super().closeEvent(event)

    def reject(self):
        """Override reject to ensure cleanup when dialog is cancelled."""
        self.cleanup_plots()
        super().reject()

    def accept(self):
        """Override accept to ensure cleanup when dialog is accepted."""
        self.cleanup_plots()
        super().accept()
