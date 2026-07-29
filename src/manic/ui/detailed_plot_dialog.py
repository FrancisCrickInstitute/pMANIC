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

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from manic.constants import (
    DETAILED_DIALOG_HEIGHT,
    DETAILED_DIALOG_SCREEN_RATIO,
    DETAILED_DIALOG_WIDTH,
    DETAILED_EIC_HEIGHT,
    DETAILED_MS_HEIGHT,
    DETAILED_TIC_HEIGHT,
    GUIDELINE_ALPHA,
    MS_TIME_TOLERANCE,
    PLOT_GUIDELINE_WIDTH,
    PLOT_LINE_WIDTH,
    PLOT_STEM_WIDTH,
)
from manic.io.cdf_data_extractor import ensure_ms_data_for_time
from manic.io.compound_reader import read_compound, read_compound_with_session
from manic.io.tic_reader import read_tic
from manic.processors.chromatographic_peak_deconvolution import (
    chromatographic_peak_deconvolution_enabled,
    deconvolve_eic,
)
from manic.processors.eic_processing import get_eics_for_compound
from manic.processors.integration import compute_linear_baseline
from manic.validation.unlabelled_identity import quantifier_apex_time
from manic.ui.channel_labels import channel_legend_label
from manic.ui.colors import label_colors  # Import the same colors as main window
from manic.ui.matplotlib_plot_widget import MatplotlibPlotWidget
logger = logging.getLogger(__name__)


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
        normalize_targeted_traces: bool = False,
    ):
        super().__init__(parent)
        self.compound_name = compound_name
        self.sample_name = sample_name
        self.use_corrected = use_corrected  # Store the isotope correction flag
        self.normalize_targeted_traces = bool(normalize_targeted_traces)

        # Initialize data containers
        self.eic_data = None
        self.tic_data = None
        self.ms_data = None
        self.compound_info = None
        self.method_compound = None
        self.observed_rt = None

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle(
            f"Detailed View - {self.compound_name} ({self.sample_name})"
        )
        self.setModal(True)

        # Ensure the dialog is resizable on all platforms
        self.setSizeGripEnabled(True)  # Enable resize grip
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowMaximizeButtonHint
        )  # Enable maximize button
        # Platform-adaptive sizing for better cross-platform experience
        # Try to get screen where parent window is located, fall back to primary screen
        if self.parent():
            screen = QApplication.screenAt(self.parent().geometry().center())
        else:
            screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry() if screen else None

        if sys.platform == "win32":
            # Windows: Account for title bar, taskbar, and DPI scaling
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
            # macOS: Account for menu bar and dock
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
            # Linux: Conservative sizing
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

        # Set more reasonable minimum size for small screens (allow scrolling)
        min_width = min(600, int(screen_rect.width() * 0.5) if screen_rect else 600)
        min_height = min(500, int(screen_rect.height() * 0.4) if screen_rect else 500)
        self.setMinimumSize(min_width, min_height)

        # Set maximum size based on available screen space with adaptive ratio
        if screen_rect:
            # Use more generous ratios for larger screens
            screen_width = screen_rect.width()
            screen_height = screen_rect.height()

            # Adaptive ratio: more generous on larger screens
            if screen_width >= 2560:  # 4K+ monitors
                width_ratio = 0.95
                height_ratio = 0.95
            elif screen_width >= 1920:  # 1080p+ monitors
                width_ratio = 0.92
                height_ratio = 0.92
            else:  # Smaller monitors
                width_ratio = DETAILED_DIALOG_SCREEN_RATIO
                height_ratio = DETAILED_DIALOG_SCREEN_RATIO

            max_width = int(screen_width * width_ratio)
            max_height = int(screen_height * height_ratio)
            self.setMaximumSize(max_width, max_height)

        # Configure primary layout structure
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(5, 5, 5, 5)

        # Create header section with compound identification
        header_layout = QHBoxLayout()

        title_label = QLabel(
            f"<b>{self.compound_name}</b> in <i>{self.sample_name}</i>"
        )
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label)

        layout.addLayout(header_layout)

        # Initialize scrollable container for plot widgets
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )  # Allow horizontal scroll if needed
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Ensure scroll area can shrink to fit in small windows
        scroll_area.setMinimumSize(400, 300)  # Reasonable minimum for plot visibility
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Configure scroll area content widget
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: white;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(5, 5, 5, 5)

        # Initialize resizable splitter for plot arrangement
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        # Initialize Extracted Ion Chromatogram display
        self.eic_plot = MatplotlibPlotWidget(
            title="Extracted Ion Chromatogram",
            x_label="Time (min)",
            y_label="Intensity",
        )
        # Adaptive minimum heights for small screens
        min_plot_height = min(
            200, int(screen_rect.height() * 0.15) if screen_rect else 200
        )

        self.eic_plot.setMinimumHeight(min_plot_height)  # Adaptive minimum height
        self.eic_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.eic_plot)

        # Initialize Total Ion Chromatogram display
        self.tic_plot = MatplotlibPlotWidget(
            title="Total Ion Chromatogram",
            x_label="Time (min)",
            y_label="Total Intensity",
        )
        self.tic_plot.setMinimumHeight(min_plot_height)  # Adaptive minimum height
        self.tic_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.tic_plot)

        # Initialize Mass Spectrum display
        self.ms_plot = MatplotlibPlotWidget(
            title="Mass Spectrum", x_label="m/z", y_label="Intensity"
        )
        self.ms_plot.setMinimumHeight(min_plot_height)  # Adaptive minimum height
        self.ms_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.ms_plot)

        # Configure initial plot height proportions
        splitter.setSizes(
            [DETAILED_EIC_HEIGHT, DETAILED_TIC_HEIGHT, DETAILED_MS_HEIGHT]
        )

        # Add splitter to scroll layout
        scroll_layout.addWidget(splitter)

        # Set the scroll widget as the content of scroll area
        scroll_area.setWidget(scroll_widget)

        # Add scroll area to main layout
        layout.addWidget(scroll_area)

        # Create information display panel
        info_layout = QHBoxLayout()
        self.info_label = QLabel("Loading data...")
        self.info_label.setFont(QFont("Arial", 9))
        self.info_label.setStyleSheet("color: gray; padding: 5px;")
        info_layout.addWidget(self.info_label)
        info_layout.addStretch()

        # Display navigation control legend
        zoom_label = QLabel("<b>↻:</b> Reset | <b>✋:</b> Drag | <b>🔍:</b> Zoom")
        zoom_label.setFont(QFont("Arial", 9))
        zoom_label.setStyleSheet("color: gray; padding: 5px;")
        info_layout.addWidget(zoom_label)

        layout.addLayout(info_layout)

        # Configure dialog control buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        # Enable window maximization capability
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

    def _load_data(self):
        """Load all required data for the plots."""
        try:
            # Retrieve compound metadata from database
            self.compound_info = read_compound_with_session(
                self.compound_name, self.sample_name
            )
            self.method_compound = read_compound(self.compound_name)
            if not self.compound_info:
                self._show_error("Failed to load compound information")
                return

            # Extract Extracted Ion Chromatogram data (mandatory)
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

            # Retrieve Total Ion Chromatogram data (if available)
            self._load_tic_data()

            # Extract Mass Spectrum at retention time (if available)
            self._load_ms_data()

            # Render all available data visualizations
            self._plot_eic()
            self._plot_tic()
            self._plot_ms()

            # Update info label
            self._update_info_label()

            # Validate minimum data requirements
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
                self.compound_name, [self.sample_name], use_corrected=self.use_corrected
            )
            if eics:
                self.eic_data = eics[0]  # Get the first (and only) EIC
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
            self.eic_plot.clear_plot()
            self.eic_plot.set_title("Enhanced Extracted Ion Chromatogram (no data)")
            return

        try:
            # Reset plot area before rendering
            self.eic_plot.clear_plot()
            self._plot_eic_traces()

            # Calculate and display integration boundaries
            rt = self.compound_info.retention_time
            left_bound = rt - self.compound_info.loffset
            right_bound = rt + self.compound_info.roffset

            # Render integration boundary markers with transparency
            self.eic_plot.add_vertical_line(
                left_bound,
                color=f"rgba(255,0,0,{GUIDELINE_ALPHA})",
                width=PLOT_GUIDELINE_WIDTH,
                style="dashed",
            )
            self.eic_plot.add_vertical_line(
                right_bound,
                color=f"rgba(255,0,0,{GUIDELINE_ALPHA})",
                width=PLOT_GUIDELINE_WIDTH,
                style="dashed",
            )
            self.eic_plot.add_vertical_line(
                rt,
                color=f"rgba(0,0,0,{GUIDELINE_ALPHA})",
                width=PLOT_GUIDELINE_WIDTH,
                style="dotted",
            )
            self._add_targeted_reference_lines(self.eic_plot)

            # Add baseline lines if baseline correction is enabled
            self._add_baseline_lines(left_bound, right_bound)

            # Show mode-appropriate channel labels on the right side.
            self.eic_plot.show_legend(loc="upper right")

            # Execute batch rendering for performance
            self.eic_plot.finalize_plot()

            # Record retention time values for diagnostics
            logger.debug(
                f"EIC plot - RT: {rt:.3f}, Left: {left_bound:.3f}, Right: {right_bound:.3f}"
            )

        except Exception as e:
            logger.error(f"Failed to plot EIC: {e}")

    def _add_baseline_lines(self, left_bound: float, right_bound: float):
        """Add dashed baseline lines when baseline correction is enabled."""
        if not self.compound_info or not self.eic_data:
            return

        baseline_flag = getattr(self.compound_info, "baseline_correction", 0)
        if not baseline_flag:
            return

        if chromatographic_peak_deconvolution_enabled(getattr(self.compound_info, "deconvolution_level", "off")):
            result = deconvolve_eic(
                self.eic_data.time,
                self.eic_data.intensity,
                retention_time=self.compound_info.retention_time,
                loffset=self.compound_info.loffset,
                roffset=self.compound_info.roffset,
                stringency=getattr(self.compound_info, "deconvolution_level", "off"),
                fit_type=getattr(self.compound_info, "deconvolution_fit_type", "auto"),
                noise_gate=getattr(self.compound_info, "deconvolution_noise_gate", "balanced"),
            )
            selected_matrix = (
                result.selected
                if self.eic_data.intensity.ndim > 1
                else result.selected.reshape(1, -1)
            )
            mask_matrix = (
                result.selected_mask
                if self.eic_data.intensity.ndim > 1
                else result.selected_mask.reshape(1, -1)
            )
            drew_baseline = False
            for i, selected_trace in enumerate(selected_matrix):
                trace_mask = np.asarray(mask_matrix[i, :], dtype=bool)
                if not np.any(trace_mask):
                    continue
                baseline_result = compute_linear_baseline(
                    self.eic_data.time[trace_mask], selected_trace[trace_mask]
                )
                if baseline_result is None:
                    continue
                td_base, baseline_y = baseline_result
                qcolor = label_colors[i % len(label_colors)]
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
                drew_baseline = True
            if drew_baseline:
                return

        # Create window mask (strict boundaries like integration)
        mask = (self.eic_data.time > left_bound) & (self.eic_data.time < right_bound)
        if not np.any(mask):
            return

        td_win = self.eic_data.time[mask]

        if self.eic_data.intensity.ndim == 1:
            # Single trace - use dark red color
            idata_win = self.eic_data.intensity[mask]
            baseline_result = compute_linear_baseline(td_win, idata_win)
            if baseline_result is not None:
                td_base, baseline_y = baseline_result
                baseline_x = np.array([td_base[0], td_base[-1]])
                baseline_y_vals = np.array([baseline_y[0], baseline_y[-1]])
                self.eic_plot.plot_line(
                    baseline_x,
                    baseline_y_vals,
                    color="darkred",
                    width=1.2,
                    name="",
                    style="dashed",
                )
        else:
            # Multi-trace - draw baseline for each isotopologue with matching color
            for i in range(self.eic_data.intensity.shape[0]):
                idata_win = self.eic_data.intensity[i, mask]
                baseline_result = compute_linear_baseline(td_win, idata_win)
                if baseline_result is not None:
                    td_base, baseline_y = baseline_result
                    qcolor = label_colors[i % len(label_colors)]
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

    def _plot_model_component(self, model, component_index: int, *, selected: bool):
        """Draw one fitted component as the continuous model curve.

        This is the same smooth model integration uses, evaluated on a dense grid
        so the displayed peak and the exported area come from a single source.
        """
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
            qcolor = label_colors[i % len(label_colors)] if multi_trace else label_colors[0]
            if selected:
                color = f"rgba({qcolor.red()},{qcolor.green()},{qcolor.blue()},1.0)"
                self.eic_plot.plot_line(
                    grid,
                    row,
                    color=color,
                    width=PLOT_LINE_WIDTH,
                    name=self._channel_label(i) if multi_trace else "",
                )
            else:
                color = f"rgba({qcolor.red()},{qcolor.green()},{qcolor.blue()},0.38)"
                self.eic_plot.plot_line(
                    grid, row, color=color, width=1.2, name="", style="dotted"
                )

    def _plot_eic_traces(self):
        """Draw raw context plus selected/excluded chromatographic peak deconvolution components."""
        result = None
        if chromatographic_peak_deconvolution_enabled(getattr(self.compound_info, "deconvolution_level", "off")):
            result = deconvolve_eic(
                self.eic_data.time,
                self.eic_data.intensity,
                retention_time=self.compound_info.retention_time,
                loffset=self.compound_info.loffset,
                roffset=self.compound_info.roffset,
                stringency=getattr(self.compound_info, "deconvolution_level", "off"),
                fit_type=getattr(self.compound_info, "deconvolution_fit_type", "auto"),
                noise_gate=getattr(self.compound_info, "deconvolution_noise_gate", "balanced"),
            )

        model = result.model if result is not None else None
        if model is None:
            self._plot_trace_matrix(self.eic_data.intensity, selected=True)
            return

        self._plot_trace_matrix(self.eic_data.intensity, selected=False, alpha=0.32)
        self._plot_model_component(model, model.selected_index, selected=True)
        for component_index in range(model.n_components):
            if component_index == model.selected_index:
                continue
            self._plot_model_component(model, component_index, selected=False)

    def _plot_trace_matrix(
        self,
        intensity: np.ndarray,
        *,
        selected: bool,
        alpha: float = 1.0,
    ):
        matrix = intensity if intensity.ndim > 1 else intensity.reshape(1, -1)
        if (
            self.normalize_targeted_traces
            and self.compound_info is not None
            and self.compound_info.is_unlabelled_target
            and matrix.shape[0] > 1
        ):
            # Match OLD_MANIC's optional Scale ValIons view: all channels are
            # scaled to the Q-ion peak height for shape comparison only.
            matrix = np.asarray(matrix, dtype=np.float64).copy()
            finite_q = matrix[0, np.isfinite(matrix[0])]
            q_peak = float(np.max(finite_q)) if finite_q.size else 0.0
            if q_peak > 0:
                for index in range(1, matrix.shape[0]):
                    finite = matrix[index, np.isfinite(matrix[index])]
                    channel_peak = float(np.max(finite)) if finite.size else 0.0
                    if channel_peak > 0:
                        matrix[index] *= q_peak / channel_peak
        multi_trace = intensity.ndim > 1
        time = np.asarray(self.eic_data.time, dtype=np.float64)
        for i, trace in enumerate(matrix):
            qcolor = label_colors[i % len(label_colors)] if multi_trace else label_colors[0]
            color = f"rgba({qcolor.red()},{qcolor.green()},{qcolor.blue()},{alpha})"
            self.eic_plot.plot_line(
                time,
                trace,
                color=color,
                width=PLOT_LINE_WIDTH if selected else 1.0,
                name=self._channel_label(i) if selected and multi_trace else "",
            )

    def _channel_label(self, channel_index: int) -> str:
        """Return isotope or diagnostic-ion semantics for the legend."""
        return channel_legend_label(self.compound_info, channel_index)

    def _plot_tic(self):
        """Plot the TIC data with retention time marker."""
        if not self.tic_data:
            self.tic_plot.clear_plot()
            self.tic_plot.set_title("Total Ion Chromatogram (data not available)")
            return

        try:
            # Reset plot area before rendering
            self.tic_plot.clear_plot()

            # Render Total Ion Chromatogram trace
            self.tic_plot.plot_line(
                self.tic_data.time,
                self.tic_data.intensity,
                color="darkgreen",
                width=PLOT_LINE_WIDTH,
                name="Total Ion Chromatogram",
            )

            # Display retention time indicator with transparency
            if self.compound_info:
                rt = self.compound_info.retention_time
                self.tic_plot.add_vertical_line(
                    rt,
                    color=f"rgba(255,0,0,{GUIDELINE_ALPHA})",
                    width=PLOT_GUIDELINE_WIDTH,
                    style="solid",
                )
                self._add_targeted_reference_lines(self.tic_plot)

            # Execute batch rendering for performance
            self.tic_plot.finalize_plot()

        except Exception as e:
            logger.error(f"Failed to plot TIC: {e}")
            self.tic_plot.set_title("Total Ion Chromatogram (error loading data)")

    def _add_targeted_reference_lines(self, plot) -> None:
        """Method reference RT (dash-dot grey) and observed Q apex (magenta)."""
        if self.method_compound and self.compound_info.is_unlabelled_target:
            plot.add_vertical_line(
                self.method_compound.retention_time,
                color=f"rgba(100,100,100,{GUIDELINE_ALPHA})",
                width=PLOT_GUIDELINE_WIDTH,
                style="dashdot",
            )
        if self.observed_rt is not None:
            plot.add_vertical_line(
                self.observed_rt,
                color="#D946EF",
                width=1.8,
                style="solid",
            )

    def _plot_ms(self):
        """Plot the mass spectrum data."""
        if not self.ms_data:
            self.ms_plot.clear_plot()
            self.ms_plot.set_title("Mass Spectrum (data not available)")
            return

        try:
            # Reset plot area before rendering
            self.ms_plot.clear_plot()

            # Render mass spectrum as stem plot
            self.ms_plot.plot_stems(
                self.ms_data.mz,
                self.ms_data.intensity,
                color="darkblue",
                width=PLOT_STEM_WIDTH,
            )

            # Annotate the 8 most abundant peaks with their m/z values
            try:
                mz = np.asarray(self.ms_data.mz, dtype=np.float64)
                intensity = np.asarray(self.ms_data.intensity, dtype=np.float64)

                # Use the same basic filtering as plot_stems: positive and finite
                mask = (intensity > 0) & np.isfinite(mz) & np.isfinite(intensity)
                mz = mz[mask]
                intensity = intensity[mask]

                if mz.size > 0:
                    # Indices of the top N peaks by intensity
                    N = 8
                    if intensity.size > N:
                        top_idx = np.argsort(intensity)[-N:]
                    else:
                        top_idx = np.argsort(intensity)

                    # Sort selected peaks by m/z for a more orderly appearance (optional but nice)
                    top_idx = top_idx[np.argsort(mz[top_idx])]

                    for idx in top_idx:
                        x_val = float(mz[idx])
                        y_val = float(intensity[idx])
                        if y_val <= 0:
                            continue

                        # Position label slightly above the peak
                        y_label = y_val * 1.02
                        label = f"{x_val:.2f}"  # m/z with 2 decimal places

                        self.ms_plot.add_text(
                            x_val,
                            y_label,
                            label,
                            color="black",
                            ha="center",
                            va="bottom",
                        )
            except Exception as e:
                logger.error(f"Failed to annotate MS peaks: {e}")

            # Mark target m/z position with transparent indicator
            if self.compound_info:
                self.ms_plot.add_vertical_line(
                    self.compound_info.mass0,
                    color=f"rgba(255,0,0,{GUIDELINE_ALPHA})",
                    width=PLOT_GUIDELINE_WIDTH,
                    style="solid",
                )

            # Execute batch rendering for performance
            self.ms_plot.finalize_plot()

        except Exception as e:
            logger.error(f"Failed to plot MS: {e}")
            self.ms_plot.set_title("Mass Spectrum (error loading data)")

    def _update_info_label(self):
        """Update the information label with data summary."""
        info_parts = []

        if self.compound_info:
            rt = self.compound_info.retention_time
            if self.compound_info.is_unlabelled_target:
                reference_rt = (
                    self.method_compound.retention_time
                    if self.method_compound is not None
                    else rt
                )
                info_parts.append(f"Reference RT: {reference_rt:.3f} min")
                info_parts.append(f"Integration centre: {rt:.3f} min")
                if self.observed_rt is not None:
                    info_parts.append(f"Observed Q apex: {self.observed_rt:.3f} min")
                ions = ", ".join(
                    channel.label for channel in self.compound_info.analysis_channels
                )
                info_parts.append(ions)
            else:
                info_parts.append(f"Retention Time: {rt:.3f} min")
                info_parts.append(f"m/z: {self.compound_info.mass0:.4f}")
                if self.compound_info.label_atoms:
                    info_parts.append(
                        f"Isotopologues: M+0…M+{self.compound_info.label_atoms}"
                    )

        if self.eic_data:
            info_parts.append(f"EIC Points: {len(self.eic_data.time)}")

        if self.tic_data:
            info_parts.append(f"TIC Points: {len(self.tic_data.time)}")

        if self.ms_data:
            info_parts.append(f"MS Peaks: {len(self.ms_data.mz)}")

        info_text = " | ".join(info_parts) if info_parts else "No data available"
        self.info_label.setText(info_text)

    def _show_error(self, message: str):
        """Show error message to user."""
        msg_box = QMessageBox(
            QMessageBox.Warning, "Error", message, QMessageBox.Ok, self
        )
        msg_box.exec()

        # Display error message in information panel
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
            # Clean up each plot widget
            if hasattr(self, "eic_plot") and self.eic_plot:
                self.eic_plot.cleanup()

            if hasattr(self, "tic_plot") and self.tic_plot:
                self.tic_plot.cleanup()

            if hasattr(self, "ms_plot") and self.ms_plot:
                self.ms_plot.cleanup()

            # Clear data references
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
