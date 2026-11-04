"""
Matplotlib-based plot widget for enhanced data visualization.

This module provides a high-performance plotting widget using matplotlib
with optimized rendering and professional scientific notation support.
Key features include custom zoom controls, responsive layouts, and
efficient batch rendering for improved performance.
"""

import logging
from contextlib import contextmanager

# Configure matplotlib for Qt5 integration with performance optimizations
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backend_bases import _Mode
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.colors import to_hex, to_rgba, to_rgba_array
from matplotlib.figure import Figure
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QVBoxLayout, QWidget

from manic.ui import theme
from manic.ui.theme import COLORS

from manic.constants import (
    PLOT_AXIS_SPINE_WIDTH,
    PLOT_DPI,
    PLOT_FIGURE_HEIGHT,
    PLOT_FIGURE_WIDTH,
    PLOT_GRID_LINEWIDTH,
    PLOT_GUIDELINE_WIDTH,
    PLOT_LABEL_FONTSIZE,
    PLOT_LINE_WIDTH,
    PLOT_MARGIN_BOTTOM,
    PLOT_MARGIN_LEFT,
    PLOT_MARGIN_RIGHT,
    PLOT_MARGIN_TOP,
    PLOT_MIN_HEIGHT,
    PLOT_STEM_WIDTH,
    PLOT_TICK_FONTSIZE,
    PLOT_TITLE_FONTSIZE,
    PLOT_TITLE_PADDING,
    SCIENTIFIC_NOTATION_THRESHOLD,
    TOOLBAR_BUTTON_MARGIN,
    TOOLBAR_BUTTON_PADDING,
    TOOLBAR_MAX_HEIGHT,
    TOOLBAR_SPACING,
)

matplotlib.use("Qt5Agg")
# Configure matplotlib rendering parameters for optimal performance
matplotlib.rcParams["figure.dpi"] = PLOT_DPI  # Optimized DPI for responsive rendering
matplotlib.rcParams["figure.autolayout"] = (
    False  # Manual layout control for performance
)
matplotlib.rcParams["axes.unicode_minus"] = False  # Simplified minus sign rendering
# Match the app's system font (macOS, Windows, then matplotlib's own fallback).
matplotlib.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Segoe UI", "DejaVu Sans"],
        "axes.titleweight": "semibold",
        "legend.framealpha": 0.92,
        # Axis multiplier reads "×10⁶", as on the grid tiles, not "1e6".
        "axes.formatter.use_mathtext": True,
    }
)


def _apply_theme_rc() -> None:
    """Theme colours for artists matplotlib creates later (titles, legends, text)."""
    matplotlib.rcParams.update(
        {
            "text.color": COLORS["text"],
            "axes.edgecolor": COLORS["border_strong"],
            "axes.labelcolor": COLORS["text_secondary"],
            "axes.titlecolor": COLORS["text"],
            "xtick.color": COLORS["border_strong"],
            "ytick.color": COLORS["border_strong"],
            "xtick.labelcolor": COLORS["text_secondary"],
            "ytick.labelcolor": COLORS["text_secondary"],
            "legend.edgecolor": COLORS["border"],
            "legend.facecolor": COLORS["surface"],
        }
    )


def remap_figure_colors(figure: Figure, remap: dict[str, str]) -> None:
    """Move every drawn artist that used a token or data colour to the new scheme."""

    def swap(value):
        rgba = np.atleast_2d(to_rgba_array(value))
        out = rgba.copy()
        for row in out:
            new = remap.get(to_hex(row[:3]))
            if new is not None:
                row[:3] = to_rgba(new)[:3]
        return out if len(out) > 1 else tuple(out[0])

    for artist in figure.findobj():
        for prop in ("color", "facecolor", "edgecolor", "markeredgecolor", "markerfacecolor"):
            getter = getattr(artist, f"get_{prop}", None)
            setter = getattr(artist, f"set_{prop}", None)
            if getter is None or setter is None:
                continue
            try:
                value = getter()
                if len(np.atleast_1d(value)) == 0 or (isinstance(value, str) and value in ("none", "auto")):
                    continue
                setter(swap(value))
            except (TypeError, ValueError):
                continue


logger = logging.getLogger(__name__)

STEM_HEADROOM = 1.18


@contextmanager
def matplotlib_cleanup():
    """Context manager to ensure matplotlib resources are properly cleaned up."""
    try:
        yield
    finally:
        # Force garbage collection of matplotlib objects
        import gc

        gc.collect()
        # Close any lingering figures
        plt.close("all")


class CompactNavigationToolbar(QWidget):
    """Reset, Pan and Zoom for a set of plots; each mode applies to every plot."""

    def __init__(self, plots, parent=None):
        super().__init__(parent)
        self.plots = list(plots)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TOOLBAR_SPACING)

        theme.style(
            self,
            f"""
            QToolButton {{
                border: 1px solid transparent;
                padding: {TOOLBAR_BUTTON_PADDING}px 10px;
                margin: {TOOLBAR_BUTTON_MARGIN}px;
                background-color: transparent;
                border-radius: 6px;
                color: @text_secondary;
                font-size: 12px;
            }}
            QToolButton:hover {{
                background-color: @surface_hover;
            }}
            QToolButton:checked {{
                background-color: @accent_soft;
                color: @accent;
            }}
            """,
        )

        self.home_btn = QToolButton()
        self.home_btn.setText("↻ Reset")
        self.home_btn.setToolTip("Fit all three charts to their data")
        self.home_btn.clicked.connect(self._reset_view)
        layout.addWidget(self.home_btn)

        self.pan_btn = QToolButton()
        self.pan_btn.setText("Pan")
        self.pan_btn.setToolTip("Drag any chart to pan it")
        self.pan_btn.setCheckable(True)
        self.pan_btn.clicked.connect(self._on_pan)
        layout.addWidget(self.pan_btn)

        self.zoom_btn = QToolButton()
        self.zoom_btn.setText("Zoom")
        self.zoom_btn.setToolTip("Drag a rectangle on any chart to zoom it")
        self.zoom_btn.setCheckable(True)
        self.zoom_btn.clicked.connect(self._on_zoom)
        layout.addWidget(self.zoom_btn)

        self.setMaximumHeight(TOOLBAR_MAX_HEIGHT)

    def _set_mode(self, mode: str) -> None:
        self.pan_btn.setChecked(mode == "pan")
        self.zoom_btn.setChecked(mode == "zoom")
        for plot in self.plots:
            plot.set_mode(mode)

    def _on_pan(self):
        self._set_mode("pan" if self.pan_btn.isChecked() else "")

    def _on_zoom(self):
        self._set_mode("zoom" if self.zoom_btn.isChecked() else "")

    def _reset_view(self):
        self._set_mode("")
        for plot in self.plots:
            plot.reset_view()

    def cleanup(self):
        self.plots = []


class MatplotlibPlotWidget(QWidget):
    """
    Advanced scientific plotting widget with matplotlib backend.

    Provides professional-grade visualization capabilities including:
    - Integrated navigation controls for interactive exploration
    - Automatic scientific notation for large numerical ranges
    - High-precision line and marker positioning
    - Optimized batch rendering for performance
    - Responsive layout adaptation
    """

    def __init__(
        self, title: str = "", x_label: str = "", y_label: str = "", parent=None
    ):
        super().__init__(parent)
        self.title = title
        self.x_label = x_label
        self.y_label = y_label

        # Initialize data storage for plot management
        self.data_lines = []
        self._last_stem_data = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI with matplotlib figure."""
        _apply_theme_rc()
        theme.style(self, "background-color: @surface;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Initialize matplotlib figure with performance-optimized parameters
        self.figure = Figure(
            figsize=(PLOT_FIGURE_WIDTH, PLOT_FIGURE_HEIGHT),
            dpi=PLOT_DPI,
            facecolor=COLORS["surface"],
            edgecolor=COLORS["surface"],
        )
        self.canvas = FigureCanvas(self.figure)
        theme.style(self.canvas, "background-color: @surface; border: none;")

        # Configure subplot with optimized margin parameters
        self.ax = self.figure.add_subplot(111, facecolor=COLORS["surface"])
        self.figure.subplots_adjust(
            left=PLOT_MARGIN_LEFT,
            right=PLOT_MARGIN_RIGHT,
            top=PLOT_MARGIN_TOP,
            bottom=PLOT_MARGIN_BOTTOM,
        )

        # Configure minimal axis styling for clean appearance
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self.ax.spines["left"].set_linewidth(PLOT_AXIS_SPINE_WIDTH)
        self.ax.spines["bottom"].set_linewidth(PLOT_AXIS_SPINE_WIDTH)

        # Initialize plot labels and title
        self._set_axes_title(self.title)
        self.ax.set_xlabel(self.x_label, fontsize=PLOT_LABEL_FONTSIZE)
        self.ax.set_ylabel(self.y_label, fontsize=PLOT_LABEL_FONTSIZE)

        # Apply subtle grid styling for reference
        self.ax.grid(
            True, color=COLORS["grid_line"], linestyle="-", linewidth=PLOT_GRID_LINEWIDTH
        )
        self.ax.tick_params(labelsize=PLOT_TICK_FONTSIZE)

        theme.notifier.changed.connect(self._on_theme_changed)

        # Matplotlib's own toolbar drives pan and zoom; a shared
        # CompactNavigationToolbar presses its buttons.
        self.nav = NavigationToolbar(self.canvas, self)
        self.nav.setVisible(False)
        self._peak_labels = []
        self.canvas.mpl_connect("resize_event", self._fit_margins)
        self.canvas.mpl_connect("draw_event", self._declutter_peak_labels)

        layout.addWidget(self.canvas)

        # Define minimum widget dimensions
        self.setMinimumHeight(PLOT_MIN_HEIGHT)

    def clear_plot(self):
        """Clear all data from the plot."""
        self.ax.clear()
        self.data_lines = []
        self.ax.set_facecolor(COLORS["surface"])
        self._peak_labels = []
        self._set_axes_title(self.title)
        self.ax.set_xlabel(self.x_label, fontsize=PLOT_LABEL_FONTSIZE)
        self.ax.set_ylabel(self.y_label, fontsize=PLOT_LABEL_FONTSIZE)
        self.ax.grid(
            True, color=COLORS["grid_line"], linestyle="-", linewidth=PLOT_GRID_LINEWIDTH
        )
        self.ax.tick_params(labelsize=PLOT_TICK_FONTSIZE)

        # Restore axis styling configuration
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self.ax.spines["left"].set_linewidth(PLOT_AXIS_SPINE_WIDTH)
        self.ax.spines["bottom"].set_linewidth(PLOT_AXIS_SPINE_WIDTH)
        # Defer rendering until data is loaded

    def plot_line(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        color: str = "blue",
        width: int = PLOT_LINE_WIDTH,
        name: str = "",
        style: str = "solid",
    ):
        """
        Plot a line.

        Args:
            x_data: X coordinates
            y_data: Y coordinates
            color: Line color (matplotlib format)
            width: Line width
            name: Series name for legend
            style: Line style ('solid', 'dashed', 'dotted', 'dashdot')
        """
        try:
            # Ensure data is in numpy array format
            x_data = np.asarray(x_data, dtype=np.float64)
            y_data = np.asarray(y_data, dtype=np.float64)

            # Remove invalid data points
            mask = np.isfinite(x_data) & np.isfinite(y_data)
            x_data = x_data[mask]
            y_data = y_data[mask]

            if len(x_data) == 0:
                logger.warning(f"No valid data to plot for '{name}'")
                return

            # Store data for later reference
            self.data_lines.append((x_data, y_data))

            # Parse RGBA color format if provided
            if color.startswith("rgba"):
                import re

                match = re.match(r"rgba\((\d+),(\d+),(\d+),([\d.]+)\)", color)
                if match:
                    r, g, b, a = match.groups()
                    color = (int(r) / 255, int(g) / 255, int(b) / 255, float(a))
            elif color.startswith("#"):
                # Convert hex to matplotlib format
                pass  # matplotlib handles hex colors natively

            # Plot the line
            self.ax.plot(
                x_data,
                y_data,
                color=color,
                linewidth=width,
                linestyle=style,
                label=name if name else None,
            )[0]

            # Update axes limits
            self.ax.relim()
            self.ax.autoscale_view()

            # Use scientific notation for large numbers
            if np.max(np.abs(y_data)) > SCIENTIFIC_NOTATION_THRESHOLD:
                self.ax.ticklabel_format(axis="y", style="scientific", scilimits=(0, 0))
                self.ax.yaxis.get_offset_text().set_fontsize(8)

            # Defer canvas update for batch rendering

        except Exception as e:
            logger.error(f"Failed to plot line: {e}")

    def plot_stems(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        color: str = "darkblue",
        width: int = PLOT_STEM_WIDTH,
    ):
        """
        Plot vertical lines from zero (stem plot) for MS data.

        Args:
            x_data: X coordinates (m/z values)
            y_data: Y coordinates (intensities)
            color: Line color
            width: Line width
        """
        try:
            # Ensure data is in numpy array format
            x_data = np.asarray(x_data, dtype=np.float64)
            y_data = np.asarray(y_data, dtype=np.float64)

            # Filter out non-positive values
            mask = (y_data > 0) & np.isfinite(x_data) & np.isfinite(y_data)
            x_data = x_data[mask]
            y_data = y_data[mask]

            if len(x_data) == 0:
                logger.warning("No valid MS data to plot")
                self._last_stem_data = None
                return

            # Store stem data for robust reset behavior
            self._last_stem_data = (x_data, y_data)

            # Use matplotlib stem plot
            markerline, stemlines, baseline = self.ax.stem(x_data, y_data, basefmt=" ")

            # Set colors and widths
            markerline.set_color(color)
            markerline.set_markersize(0)  # Hide markers
            stemlines.set_color(color)
            stemlines.set_linewidth(width)

            # Ensure Y axis starts at 0, with room above the tallest peak for its label
            y_max = float(np.max(y_data))
            self.ax.set_ylim(0, y_max * STEM_HEADROOM)

            # Set X axis limits based on actual data range with small padding
            x_min, x_max = x_data.min(), x_data.max()
            x_padding = (x_max - x_min) * 0.05 if x_max > x_min else 10
            self.ax.set_xlim(max(0, x_min - x_padding), x_max + x_padding)

            # Use scientific notation for large numbers
            if y_max > SCIENTIFIC_NOTATION_THRESHOLD:
                self.ax.ticklabel_format(axis="y", style="scientific", scilimits=(0, 0))
                self.ax.yaxis.get_offset_text().set_fontsize(8)

            # Defer canvas update for batch rendering

        except Exception as e:
            logger.error(f"Failed to plot stems: {e}")

    def add_vertical_line(
        self,
        x_position: float,
        color: str = "red",
        width: int = PLOT_GUIDELINE_WIDTH,
        style: str = "solid",
    ):
        """
        Add a vertical line at specified position.

        Args:
            x_position: X coordinate for line
            color: Line color
            width: Line width
            style: Line style (solid, dashed, dotted)
        """
        try:
            # Parse RGBA color format if provided
            if color.startswith("rgba"):
                import re

                match = re.match(r"rgba\((\d+),(\d+),(\d+),([\d.]+)\)", color)
                if match:
                    r, g, b, a = match.groups()
                    color = (int(r) / 255, int(g) / 255, int(b) / 255, float(a))

            # Convert style to matplotlib format
            linestyle = "-"
            if style == "dashed":
                linestyle = "--"
            elif style == "dotted":
                linestyle = ":"
            elif style == "dashdot":
                linestyle = "-."

            # Add vertical line
            self.ax.axvline(
                x=x_position,
                color=color,
                linewidth=width,
                linestyle=linestyle,
                alpha=None if not isinstance(color, tuple) else color[3],
            )

            # Defer canvas update for batch rendering

        except Exception as e:
            logger.error(f"Failed to add vertical line: {e}")

    def show_legend(self, loc: str = "best", **kwargs):
        """
        Display a legend for the isotopologues.

        Args:
            loc: Legend location (matplotlib 'loc' parameter).
            **kwargs: Additional keyword arguments forwarded to ax.legend().
        """
        try:
            handles, labels = self.ax.get_legend_handles_labels()
            # Avoid creating an empty legend
            if not labels:
                return

            kwargs.setdefault("frameon", True)
            legend = self.ax.legend(loc=loc, fontsize=PLOT_LABEL_FONTSIZE, **kwargs)
            # Keep a reference if needed later (optional)
            self._legend = legend

        except Exception as e:
            logger.error(f"Failed to show legend: {e}")

    def add_text(
        self,
        x: float,
        y: float,
        text: str,
        color: str | None = None,
        ha: str = "center",
        va: str = "bottom",
        fontsize: int | None = None,
        rotation: float = 0.0,
        **kwargs,
    ):
        """
        Add a text annotation at (x, y) in data coordinates.

        Args:
            x: X position in data coordinates.
            y: Y position in data coordinates.
            text: Text string to render.
            color: Text color.
            ha: Horizontal alignment ('center', 'left', 'right').
            va: Vertical alignment ('bottom', 'center', 'top', ...).
            fontsize: Font size; defaults to slightly smaller than labels.
            rotation: Rotation angle in degrees.
            **kwargs: Additional matplotlib.text.Text kwargs.
        """
        try:
            if fontsize is None:
                fontsize = max(PLOT_LABEL_FONTSIZE - 1, 6)

            self.ax.text(
                x,
                y,
                text,
                color=color or COLORS["text"],
                ha=ha,
                va=va,
                fontsize=fontsize,
                rotation=rotation,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Failed to add text annotation: {e}")

    def _on_theme_changed(self, remap: dict) -> None:
        if self.figure is None:
            return
        _apply_theme_rc()
        remap_figure_colors(self.figure, remap)
        self.ax.tick_params(colors=COLORS["border_strong"], labelcolor=COLORS["text_secondary"])
        self.ax.grid(True, color=COLORS["grid_line"])
        self.canvas.draw_idle()

    def set_title(self, title: str):
        """Update the plot title."""
        self.title = title
        self._set_axes_title(title)
        # Don't draw yet

    def _set_axes_title(self, title: str) -> None:
        self.ax.set_title(
            title, loc="left", fontsize=PLOT_TITLE_FONTSIZE, pad=PLOT_TITLE_PADDING + 4
        )

    def _fit_margins(self, _event=None) -> None:
        """Fixed pixel margins, so axes line up across plots of any width."""
        width, height = self.canvas.get_width_height()
        if width < 100 or height < 100:
            return
        self.figure.subplots_adjust(
            left=64 / width, right=1 - 16 / width, top=1 - 34 / height, bottom=40 / height
        )

    def set_mode(self, mode: str) -> None:
        """'pan', 'zoom' or '' (neither), whatever the current mode is."""
        current = {_Mode.PAN: "pan", _Mode.ZOOM: "zoom"}.get(self.nav.mode, "")
        if current == mode:
            return
        if mode == "pan" or (current == "pan" and not mode):
            self.nav.pan()
        else:
            self.nav.zoom()

    def mode(self) -> str:
        return {_Mode.PAN: "pan", _Mode.ZOOM: "zoom"}.get(self.nav.mode, "")

    def reset_view(self) -> None:
        """Fit the view to the drawn data.

        Matplotlib's nav-stack home can become unstable in Qt embed cases,
        especially for stem plots, so limits come from the stored data.
        """
        try:
            if self._last_stem_data is not None:
                x_data, y_data = self._last_stem_data
                if len(x_data) == 0:
                    return
                x_min, x_max = float(np.min(x_data)), float(np.max(x_data))
                x_padding = (x_max - x_min) * 0.05 if x_max > x_min else 10.0
                self.ax.set_xlim(max(0.0, x_min - x_padding), x_max + x_padding)
                y_max = float(np.max(y_data))
                self.ax.set_ylim(0.0, y_max * STEM_HEADROOM if y_max > 0 else 1.0)
            elif self.data_lines:
                x_concat = np.concatenate([x for x, _y in self.data_lines])
                y_concat = np.concatenate([y for _x, y in self.data_lines])
                x_min, x_max = float(np.min(x_concat)), float(np.max(x_concat))
                y_min, y_max = float(np.min(y_concat)), float(np.max(y_concat))
                x_pad = (x_max - x_min) * 0.02 if x_max > x_min else 1.0
                y_pad = (y_max - y_min) * 0.05 if y_max > y_min else 1.0
                self.ax.set_xlim(x_min - x_pad, x_max + x_pad)
                self.ax.set_ylim(y_min - y_pad, y_max + y_pad)
            else:
                self.ax.relim()
                self.ax.autoscale_view()
            self.canvas.draw_idle()
        except Exception as e:
            logger.error(f"Failed to reset view: {e}")

    def label_peaks(self, x_data, y_data, *, limit: int = 8, decimals: int = 2) -> None:
        """Label up to ``limit`` of the tallest peaks; labels that would overlap
        a taller peak's label are hidden at draw time."""
        x_data = np.asarray(x_data, dtype=np.float64)
        y_data = np.asarray(y_data, dtype=np.float64)
        keep = (y_data > 0) & np.isfinite(x_data) & np.isfinite(y_data)
        x_data, y_data = x_data[keep], y_data[keep]
        for index in np.argsort(y_data)[::-1][:limit]:
            self._peak_labels.append(
                self.ax.annotate(
                    f"{x_data[index]:.{decimals}f}",
                    (x_data[index], y_data[index]),
                    xytext=(0, 2),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=PLOT_TICK_FONTSIZE,
                    color=COLORS["text_secondary"],
                    annotation_clip=True,
                    # Opaque so a guide line through the label never cuts it.
                    bbox={"boxstyle": "square,pad=0.15", "fc": COLORS["surface"], "ec": "none"},
                )
            )

    def visible_peak_labels(self) -> list[str]:
        return [label.get_text() for label in self._peak_labels if label.get_visible()]

    def _declutter_peak_labels(self, _event=None) -> None:
        if not self._peak_labels:
            return
        renderer = self.canvas.get_renderer()
        area = self.ax.get_window_extent(renderer)
        placed = []
        changed = False
        for label in self._peak_labels:  # tallest first, so they win
            was_visible = label.get_visible()
            label.set_visible(True)  # hidden text measures as an empty box
            box = label.get_window_extent(renderer)
            # One label per column: a label stacked above a neighbour's is
            # ambiguous about which stem it names.
            span = (box.x0 - 4, box.x1 + 4)
            show = (
                box.y1 <= area.y1 + 1
                and box.x0 >= area.x0 - 1
                and box.x1 <= area.x1 + 1
                and not any(span[0] < right and left < span[1] for left, right in placed)
            )
            if show:
                placed.append(span)
            label.set_visible(show)
            changed |= was_visible != show
        if changed:
            # Settles in one more draw: the same layout gives the same answer.
            self.canvas.draw_idle()

    def finalize_plot(self):
        """Finalize plot after all data is added - single draw call for speed."""
        self.ax.grid(True, color=COLORS["grid_line"], linestyle="-", linewidth=PLOT_GRID_LINEWIDTH)
        self._fit_margins()

        # For time axis, format nicely
        if "time" in self.x_label.lower() or "min" in self.x_label.lower():
            # Format x-axis to show clear decimal minutes
            from matplotlib.ticker import FormatStrFormatter

            self.ax.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))

        # Single draw call for all updates - much faster
        self.canvas.draw()

    def cleanup(self):
        """Properly cleanup matplotlib resources to prevent memory leaks."""
        try:
            # Clear the axes
            if hasattr(self, "ax") and self.ax:
                self.ax.clear()
                self.ax = None

            # Clear and close the figure
            if hasattr(self, "figure") and self.figure:
                self.figure.clear()
                plt.close(self.figure)
                self.figure = None

            # Clear canvas reference
            if hasattr(self, "canvas") and self.canvas:
                self.canvas = None

            if getattr(self, "nav", None) is not None:
                self.nav = None
            self._peak_labels = []

            # Clear data storage
            if hasattr(self, "data_lines"):
                self.data_lines = []

            logger.debug("Matplotlib resources cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during matplotlib cleanup: {e}")

    def closeEvent(self, event):
        """Handle widget close event."""
        self.cleanup()
        super().closeEvent(event)

    def __del__(self):
        """Destructor to ensure cleanup on deletion."""
        self.cleanup()
