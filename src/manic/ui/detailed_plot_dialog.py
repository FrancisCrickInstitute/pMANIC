"""
Detailed plot dialog showing EIC, TIC, and MS plots.

Displays three interactive plots:
1. Enhanced EIC plot with integration boundaries
2. Total Ion Chromatogram with retention time marker
3. Mass spectrum at retention time
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
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

logger = logging.getLogger(__name__)


class DetailedPlotDialog(QDialog):
    """
    Modal dialog showing detailed plots for a compound-sample combination.

    Features:
    - Large EIC plot with integration boundaries highlighted
    - TIC plot with retention time marker
    - Mass spectrum at retention time
    - Interactive plots with zoom/pan capabilities
    """

    def __init__(self, compound_name: str, sample_name: str, parent=None):
        super().__init__(parent)
        self.compound_name = compound_name
        self.sample_name = sample_name

        # Data storage
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
        self.resize(1400, 1100)  # Larger default size
        self.setMinimumSize(800, 600)  # Smaller minimum to allow for smaller screens
        
        # Get screen geometry to set maximum size
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()
            self.setMaximumSize(int(screen_rect.width() * 0.95), int(screen_rect.height() * 0.95))

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(5, 5, 5, 5)

        # Header with compound/sample info
        header_layout = QHBoxLayout()

        title_label = QLabel(
            f"<b>{self.compound_name}</b> in <i>{self.sample_name}</i>"
        )
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label)

        layout.addLayout(header_layout)

        # Create scroll area for plots
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Container widget for the scroll area
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: white;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

        # Create splitter for resizable plots
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        # EIC Plot (top, larger)
        self.eic_plot = MatplotlibPlotWidget(
            title="Extracted Ion Chromatogram",
            x_label="Time (min)",
            y_label="Intensity",
        )
        self.eic_plot.setMinimumHeight(250)  # Minimum height for usability
        self.eic_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.eic_plot)

        # TIC Plot (middle)
        self.tic_plot = MatplotlibPlotWidget(
            title="Total Ion Chromatogram",
            x_label="Time (min)",
            y_label="Total Intensity",
        )
        self.tic_plot.setMinimumHeight(250)  # Minimum height for usability
        self.tic_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.tic_plot)

        # MS Plot (bottom)
        self.ms_plot = MatplotlibPlotWidget(
            title="Mass Spectrum", x_label="m/z", y_label="Intensity"
        )
        self.ms_plot.setMinimumHeight(200)  # Slightly smaller minimum for MS
        self.ms_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.ms_plot)

        # Set initial splitter sizes (TIC slightly taller than MS)
        splitter.setSizes([450, 450, 350])
        
        # Add splitter to scroll layout
        scroll_layout.addWidget(splitter)
        
        # Set the scroll widget as the content of scroll area
        scroll_area.setWidget(scroll_widget)
        
        # Add scroll area to main layout
        layout.addWidget(scroll_area)

        # Info panel
        info_layout = QHBoxLayout()
        self.info_label = QLabel("Loading data...")
        self.info_label.setFont(QFont("Arial", 9))
        self.info_label.setStyleSheet("color: gray; padding: 5px;")
        info_layout.addWidget(self.info_label)
        info_layout.addStretch()

        # Zoom instructions as a key
        zoom_label = QLabel("<b>↻:</b> Reset | <b>✋:</b> Drag | <b>🔍:</b> Zoom")
        zoom_label.setFont(QFont("Arial", 9))
        zoom_label.setStyleSheet("color: gray; padding: 5px;")
        info_layout.addWidget(zoom_label)

        layout.addLayout(info_layout)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        # Set window properties
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

    def _load_data(self):
        """Load all required data for the plots."""
        try:
            # Load compound information
            self.compound_info = read_compound_with_session(
                self.compound_name, self.sample_name
            )
            if not self.compound_info:
                self._show_error("Failed to load compound information")
                return

            # Load EIC data (required)
            self._load_eic_data()

            # Load TIC data (optional)
            self._load_tic_data()

            # Load MS data (optional)
            self._load_ms_data()

            # Plot all data (EIC is required, others show fallback if unavailable)
            self._plot_eic()
            self._plot_tic()
            self._plot_ms()

            # Update info label
            self._update_info_label()

            # Check if we have minimal data to show
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
                    self.sample_name, retention_time, tolerance=0.1
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
            # Clear any existing plot first
            self.eic_plot.clear_plot()

            # Plot the main EIC trace
            if self.eic_data.intensity.ndim == 1:
                # Single trace - use first label color (blue)
                qcolor = label_colors[0]
                color = f"#{qcolor.red():02x}{qcolor.green():02x}{qcolor.blue():02x}"
                self.eic_plot.plot_line(
                    self.eic_data.time,
                    self.eic_data.intensity,
                    color=color,
                    width=2,
                    name=f"{self.compound_name} EIC",
                )
            else:
                # Multiple traces (isotopologues) - use same colors as main window
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
                        width=2,
                        name=f"M+{i}",
                    )

            # Add integration boundaries
            rt = self.compound_info.retention_time
            left_bound = rt - self.compound_info.loffset
            right_bound = rt + self.compound_info.roffset

            # Add vertical lines for integration boundaries (thinner and semi-transparent)
            self.eic_plot.add_vertical_line(
                left_bound, color="rgba(255,0,0,0.5)", width=1, style="dashed"
            )
            self.eic_plot.add_vertical_line(
                right_bound, color="rgba(255,0,0,0.5)", width=1, style="dashed"
            )
            self.eic_plot.add_vertical_line(
                rt, color="rgba(0,0,0,0.5)", width=1, style="dotted"
            )

            # Finalize the plot
            self.eic_plot.finalize_plot()

            # Log the retention time for debugging
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
            # Clear any existing plot first
            self.tic_plot.clear_plot()

            # Plot TIC trace
            self.tic_plot.plot_line(
                self.tic_data.time,
                self.tic_data.intensity,
                color="darkgreen",
                width=2,
                name="Total Ion Chromatogram",
            )

            # Add retention time marker (thinner and semi-transparent)
            if self.compound_info:
                rt = self.compound_info.retention_time
                self.tic_plot.add_vertical_line(
                    rt, color="rgba(255,0,0,0.5)", width=1, style="solid"
                )

            # Finalize the plot
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
            # Clear any existing plot first
            self.ms_plot.clear_plot()

            # Use the stems method for MS data
            self.ms_plot.plot_stems(
                self.ms_data.mz, self.ms_data.intensity, color="darkblue", width=2
            )

            # Add red vertical line at the compound's m/z (thinner and semi-transparent)
            if self.compound_info:
                self.ms_plot.add_vertical_line(
                    self.compound_info.mass0,
                    color="rgba(255,0,0,0.5)",
                    width=1,
                    style="solid",
                )

            # Finalize the plot
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

        # Update info label
        self.info_label.setText(f"Error: {message}")

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
