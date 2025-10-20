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

from manic.io.compound_reader import read_compound_with_session
from manic.io.ms_reader import read_ms_at_time
from manic.io.tic_reader import read_tic
from manic.processors.eic_processing import get_eics_for_compound
from manic.ui.colors import label_colors  # Import the same colors as main window
from manic.ui.matplotlib_plot_widget import MatplotlibPlotWidget
from manic.constants import (
    DETAILED_DIALOG_WIDTH,
    DETAILED_DIALOG_HEIGHT,
    DETAILED_DIALOG_SCREEN_RATIO,
    DETAILED_EIC_HEIGHT,
    DETAILED_TIC_HEIGHT,
    DETAILED_MS_HEIGHT,
    MS_TIME_TOLERANCE,
    PLOT_LINE_WIDTH,
    PLOT_STEM_WIDTH,
    GUIDELINE_ALPHA,
    PLOT_GUIDELINE_WIDTH,
)

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

    def __init__(self, compound_name: str, sample_name: str, parent=None):
        super().__init__(parent)
        self.compound_name = compound_name
        self.sample_name = sample_name

        # Initialize data containers
        self.eic_data = None
        self.tic_data = None
        self.ms_data = None
        self.compound_info = None

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
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)  # Enable maximize button
        # Platform-adaptive sizing for better cross-platform experience
        # Try to get screen where parent window is located, fall back to primary screen
        if self.parent():
            screen = QApplication.screenAt(self.parent().geometry().center())
        else:
            screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry() if screen else None
        
        if sys.platform == "win32":
            # Windows: Account for title bar, taskbar, and DPI scaling
            width = min(DETAILED_DIALOG_WIDTH, int(screen_rect.width() * 0.85) if screen_rect else DETAILED_DIALOG_WIDTH)
            height = min(DETAILED_DIALOG_HEIGHT + 150, int(screen_rect.height() * 0.85) if screen_rect else DETAILED_DIALOG_HEIGHT)
        elif sys.platform == "darwin":
            # macOS: Account for menu bar and dock
            width = min(DETAILED_DIALOG_WIDTH, int(screen_rect.width() * 0.9) if screen_rect else DETAILED_DIALOG_WIDTH)
            height = min(DETAILED_DIALOG_HEIGHT, int(screen_rect.height() * 0.85) if screen_rect else DETAILED_DIALOG_HEIGHT)
        else:
            # Linux: Conservative sizing
            width = min(DETAILED_DIALOG_WIDTH, int(screen_rect.width() * 0.85) if screen_rect else DETAILED_DIALOG_WIDTH)
            height = min(DETAILED_DIALOG_HEIGHT, int(screen_rect.height() * 0.85) if screen_rect else DETAILED_DIALOG_HEIGHT)
        
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
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # Allow horizontal scroll if needed
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
        min_plot_height = min(200, int(screen_rect.height() * 0.15) if screen_rect else 200)
        
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
        splitter.setSizes([DETAILED_EIC_HEIGHT, DETAILED_TIC_HEIGHT, DETAILED_MS_HEIGHT])
        
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
            if not self.compound_info:
                self._show_error("Failed to load compound information")
                return

            # Extract Extracted Ion Chromatogram data (mandatory)
            self._load_eic_data()

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
            eics = get_eics_for_compound(self.compound_name, [self.sample_name])
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
                retention_time = self.compound_info.retention_time
                self.ms_data = read_ms_at_time(
                    self.sample_name, retention_time, tolerance=MS_TIME_TOLERANCE
                )

                if self.ms_data:
                    logger.debug(
                        f"✓ MS data loaded from DB: {self.sample_name} at {self.ms_data.time:.3f} min ({len(self.ms_data.mz)} peaks)"
                    )
                else:
                    logger.info(
                        f"No MS data in DB for {self.sample_name} at {retention_time:.3f} min (will show empty plot)"
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

            # Render primary EIC trace
            if self.eic_data.intensity.ndim == 1:
                # Single isotopologue: apply primary color scheme
                qcolor = label_colors[0]
                color = f"#{qcolor.red():02x}{qcolor.green():02x}{qcolor.blue():02x}"
                self.eic_plot.plot_line(
                    self.eic_data.time,
                    self.eic_data.intensity,
                    color=color,
                    width=PLOT_LINE_WIDTH,
                    name=f"{self.compound_name} EIC",
                )
            else:
                # Multiple isotopologues: apply consistent color palette
                for i in range(
                    min(self.eic_data.intensity.shape[0], len(label_colors))
                ):
                    # Convert QColor to RGB string for plot_line
                    qcolor = label_colors[i]
                    color = (
                        f"#{qcolor.red():02x}{qcolor.green():02x}{qcolor.blue():02x}"
                    )
                    self.eic_plot.plot_line(
                        self.eic_data.time,
                        self.eic_data.intensity[i, :],
                        color=color,
                        width=PLOT_LINE_WIDTH,
                        name=f"M+{i}",
                    )

            # Calculate and display integration boundaries
            rt = self.compound_info.retention_time
            left_bound = rt - self.compound_info.loffset
            right_bound = rt + self.compound_info.roffset

            # Render integration boundary markers with transparency
            self.eic_plot.add_vertical_line(
                left_bound, color=f"rgba(255,0,0,{GUIDELINE_ALPHA})", width=PLOT_GUIDELINE_WIDTH, style="dashed"
            )
            self.eic_plot.add_vertical_line(
                right_bound, color=f"rgba(255,0,0,{GUIDELINE_ALPHA})", width=PLOT_GUIDELINE_WIDTH, style="dashed"
            )
            self.eic_plot.add_vertical_line(
                rt, color=f"rgba(0,0,0,{GUIDELINE_ALPHA})", width=PLOT_GUIDELINE_WIDTH, style="dotted"
            )

            # Execute batch rendering for performance
            self.eic_plot.finalize_plot()

            # Record retention time values for diagnostics
            logger.debug(
                f"EIC plot - RT: {rt:.3f}, Left: {left_bound:.3f}, Right: {right_bound:.3f}"
            )

        except Exception as e:
            logger.error(f"Failed to plot EIC: {e}")

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
                    rt, color=f"rgba(255,0,0,{GUIDELINE_ALPHA})", width=PLOT_GUIDELINE_WIDTH, style="solid"
                )

            # Execute batch rendering for performance
            self.tic_plot.finalize_plot()

        except Exception as e:
            logger.error(f"Failed to plot TIC: {e}")
            self.tic_plot.set_title("Total Ion Chromatogram (error loading data)")

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
                self.ms_data.mz, self.ms_data.intensity, color="darkblue", width=PLOT_STEM_WIDTH
            )

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
            info_parts.append(f"Retention Time: {rt:.3f} min")
            info_parts.append(f"m/z: {self.compound_info.mass0:.4f}")

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
            if hasattr(self, 'eic_plot') and self.eic_plot:
                self.eic_plot.cleanup()
            
            if hasattr(self, 'tic_plot') and self.tic_plot:
                self.tic_plot.cleanup()
            
            if hasattr(self, 'ms_plot') and self.ms_plot:
                self.ms_plot.cleanup()
            
            # Clear data references
            self.eic_data = None
            self.tic_data = None
            self.ms_data = None
            self.compound_info = None
            
            logger.debug(f"Cleaned up plots for {self.compound_name}/{self.sample_name}")
            
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
