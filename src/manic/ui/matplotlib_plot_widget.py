"""Matplotlib plot widget for the detailed view, with a shared pan/zoom toolbar."""

import logging

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backend_bases import _Mode
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.colors import to_hex, to_rgba, to_rgba_array
from matplotlib.figure import Figure
from matplotlib.transforms import offset_copy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QMenu, QToolButton, QVBoxLayout, QWidget

from manic.ui import theme
from manic.ui.theme import COLORS

from manic.constants import (
    PLOT_AXIS_SPINE_WIDTH,
    PLOT_DPI,
    PLOT_FIGURE_HEIGHT,
    PLOT_FIGURE_WIDTH,
    PLOT_GRID_LINEWIDTH,
    PLOT_GUIDELINE_WIDTH,
    PLOT_LINE_WIDTH,
    PLOT_MARGIN_BOTTOM,
    PLOT_MARGIN_LEFT,
    PLOT_MARGIN_RIGHT,
    PLOT_MARGIN_TOP,
    PLOT_MIN_HEIGHT,
    PLOT_STEM_WIDTH,
    PLOT_TITLE_PADDING,
    SCIENTIFIC_NOTATION_THRESHOLD,
    TOOLBAR_MAX_HEIGHT,
)

matplotlib.use("Qt5Agg")


def _points(px: float) -> float:
    """Matplotlib points for a size in logical px, at the figure's DPI."""
    return px * 72 / PLOT_DPI


# The detailed view is for reading values, so its text is two steps above the grid's.
PLOT_TICK_FONTSIZE = _points(13)
PLOT_LABEL_FONTSIZE = _points(14)
PLOT_TITLE_FONTSIZE = _points(15)
matplotlib.rcParams["figure.dpi"] = PLOT_DPI
matplotlib.rcParams["figure.autolayout"] = False
matplotlib.rcParams["axes.unicode_minus"] = False
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

    # Read every colour before writing any: a figure and its patch share one facecolor,
    # and remapping it twice turns dark surface into white, then into light on_accent.
    updates = []
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
                updates.append((setter, swap(value)))
            except (TypeError, ValueError):
                continue
    for setter, value in updates:
        try:
            setter(value)
        except (TypeError, ValueError):
            continue


logger = logging.getLogger(__name__)

# Above the tallest stem in view; each peak label then gets the room it needs on top.
STEM_HEADROOM = 1.05
# Space under a legend for the axis multiplier, in logical px.
LEGEND_LIFT_PX = 20

# The detailed view's small toggles, in the grid's segmented-control shape.
_TOGGLE_QSS = """
QToolButton {
    font-size: 11px; color: @text_secondary;
    background: @surface; border: 1px solid @border_strong;
    border-radius: 6px; padding: 2px 9px; min-height: 18px;
}
QToolButton:hover { background: @surface_hover; }
QToolButton:checked {
    color: @text; background: @accent_soft; border-color: @accent;
    font-weight: 600;
}
"""


class CompactNavigationToolbar(QWidget):
    """Reset all, and a Pan/Zoom toggle; each mode applies to every plot.

    Double-click a single plot, or right-click it, to reset only that plot.
    """

    def __init__(self, plots, parent=None):
        super().__init__(parent)
        self.plots = list(plots)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        theme.style(
            self,
            _TOGGLE_QSS
            + """
            QToolButton#chartPan {
                border-top-right-radius: 0; border-bottom-right-radius: 0;
                border-right: none;
            }
            QToolButton#chartZoom {
                border-top-left-radius: 0; border-bottom-left-radius: 0;
            }
            """,
        )

        self.home_btn = QToolButton()
        self.home_btn.setText("↻ Reset all")
        self.home_btn.setToolTip(
            "Return all three charts to their opening view. Double-click a chart to reset only that chart."
        )
        self.home_btn.clicked.connect(self._reset_view)
        layout.addWidget(self.home_btn)

        modes = QHBoxLayout()
        modes.setContentsMargins(0, 0, 0, 0)
        modes.setSpacing(0)
        self.pan_btn = QToolButton()
        self.pan_btn.setObjectName("chartPan")
        self.pan_btn.setText("Pan")
        self.pan_btn.setToolTip("Drag any chart to pan it")
        self.pan_btn.setCheckable(True)
        self.pan_btn.clicked.connect(self._on_pan)
        modes.addWidget(self.pan_btn)

        self.zoom_btn = QToolButton()
        self.zoom_btn.setObjectName("chartZoom")
        self.zoom_btn.setText("Zoom")
        self.zoom_btn.setToolTip("Drag a rectangle on any chart to zoom it")
        self.zoom_btn.setCheckable(True)
        self.zoom_btn.clicked.connect(self._on_zoom)
        modes.addWidget(self.zoom_btn)
        layout.addLayout(modes)

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
    """One matplotlib axes with themed text, scientific-notation ticks and peak labels."""

    def __init__(
        self, title: str = "", x_label: str = "", y_label: str = "", parent=None
    ):
        super().__init__(parent)
        self.title = title
        self.x_label = x_label
        self.y_label = y_label

        self.data_lines = []
        self._last_stem_data = None
        # The stems' x range at full scan, and the one the chart opens on and resets to.
        self._full_x: tuple[float, float] | None = None
        self._home_x: tuple[float, float] | None = None
        # The y range last fitted to the stems; while it stands, labels get headroom.
        self._fitted_ylim: tuple[float, float] | None = None
        self.full_scan_button: QToolButton | None = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI with matplotlib figure."""
        _apply_theme_rc()
        theme.style(self, "background-color: @surface;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.figure = Figure(
            figsize=(PLOT_FIGURE_WIDTH, PLOT_FIGURE_HEIGHT),
            dpi=PLOT_DPI,
            facecolor=COLORS["surface"],
            edgecolor=COLORS["surface"],
        )
        self.canvas = FigureCanvas(self.figure)
        theme.style(self.canvas, "background-color: @surface; border: none;")

        self.ax = self.figure.add_subplot(111, facecolor=COLORS["surface"])
        self.figure.subplots_adjust(
            left=PLOT_MARGIN_LEFT,
            right=PLOT_MARGIN_RIGHT,
            top=PLOT_MARGIN_TOP,
            bottom=PLOT_MARGIN_BOTTOM,
        )

        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self.ax.spines["left"].set_linewidth(PLOT_AXIS_SPINE_WIDTH)
        self.ax.spines["bottom"].set_linewidth(PLOT_AXIS_SPINE_WIDTH)

        self._set_axes_title(self.title)
        self.ax.set_xlabel(self.x_label, fontsize=PLOT_LABEL_FONTSIZE)
        self.ax.set_ylabel(self.y_label, fontsize=PLOT_LABEL_FONTSIZE)

        self.ax.grid(
            True, color=COLORS["grid_line"], linestyle="-", linewidth=PLOT_GRID_LINEWIDTH
        )
        self.ax.tick_params(labelsize=PLOT_TICK_FONTSIZE)

        theme.notifier.changed.connect(self._on_theme_changed)

        # Matplotlib's own toolbar drives pan and zoom; a shared
        # CompactNavigationToolbar presses its buttons.
        self.nav = NavigationToolbar(self.canvas, self)
        self.nav.setVisible(False)
        self._reset_peak_labels()
        self._legend_entries = None
        self.canvas.mpl_connect("resize_event", self._fit_margins)
        self.canvas.mpl_connect("draw_event", self._on_draw)
        self.canvas.mpl_connect("button_press_event", self._reset_on_double_click)
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.canvas)

        self.setMinimumHeight(PLOT_MIN_HEIGHT)

    def clear_plot(self):
        """Clear all data from the plot."""
        self.ax.clear()
        self.data_lines = []
        self.ax.set_facecolor(COLORS["surface"])
        self._reset_peak_labels()
        self._legend_entries = None
        self._fitted_ylim = None
        self._set_axes_title(self.title)
        self.ax.set_xlabel(self.x_label, fontsize=PLOT_LABEL_FONTSIZE)
        self.ax.set_ylabel(self.y_label, fontsize=PLOT_LABEL_FONTSIZE)
        self.ax.grid(
            True, color=COLORS["grid_line"], linestyle="-", linewidth=PLOT_GRID_LINEWIDTH
        )
        self.ax.tick_params(labelsize=PLOT_TICK_FONTSIZE)

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
            x_data = np.asarray(x_data, dtype=np.float64)
            y_data = np.asarray(y_data, dtype=np.float64)

            mask = np.isfinite(x_data) & np.isfinite(y_data)
            x_data = x_data[mask]
            y_data = y_data[mask]

            if len(x_data) == 0:
                logger.warning(f"No valid data to plot for '{name}'")
                return

            self.data_lines.append((x_data, y_data))

            if color.startswith("rgba"):
                import re

                match = re.match(r"rgba\((\d+),(\d+),(\d+),([\d.]+)\)", color)
                if match:
                    r, g, b, a = match.groups()
                    color = (int(r) / 255, int(g) / 255, int(b) / 255, float(a))
            elif color.startswith("#"):
                pass  # matplotlib handles hex colors natively

            self.ax.plot(
                x_data,
                y_data,
                color=color,
                linewidth=width,
                linestyle=style,
                label=name if name else None,
            )[0]

            self.ax.relim()
            self.ax.autoscale_view()

            if np.max(np.abs(y_data)) > SCIENTIFIC_NOTATION_THRESHOLD:
                self.ax.ticklabel_format(axis="y", style="scientific", scilimits=(0, 0))
                self.ax.yaxis.get_offset_text().set_fontsize(PLOT_TICK_FONTSIZE)

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
            x_data = np.asarray(x_data, dtype=np.float64)
            y_data = np.asarray(y_data, dtype=np.float64)

            mask = (y_data > 0) & np.isfinite(x_data) & np.isfinite(y_data)
            x_data = x_data[mask]
            y_data = y_data[mask]

            if len(x_data) == 0:
                logger.warning("No valid MS data to plot")
                self._last_stem_data = None
                return

            self._last_stem_data = (x_data, y_data)

            markerline, stemlines, baseline = self.ax.stem(x_data, y_data, basefmt=" ")

            markerline.set_color(color)
            markerline.set_markersize(0)  # Hide markers
            stemlines.set_color(color)
            stemlines.set_linewidth(width)

            x_min, x_max = float(x_data.min()), float(x_data.max())
            x_padding = (x_max - x_min) * 0.05 if x_max > x_min else 10.0
            self._full_x = self._home_x = (max(0.0, x_min - x_padding), x_max + x_padding)
            self._fit_stems(*self._full_x)

            y_max = float(np.max(y_data))
            if y_max > SCIENTIFIC_NOTATION_THRESHOLD:
                self.ax.ticklabel_format(axis="y", style="scientific", scilimits=(0, 0))
                self.ax.yaxis.get_offset_text().set_fontsize(PLOT_TICK_FONTSIZE)

            # Defer canvas update for batch rendering

        except Exception as e:
            logger.error(f"Failed to plot stems: {e}")

    def _fit_stems(self, low: float, high: float) -> None:
        """Show m/z ``low``..``high``, with the stems there filling the height."""
        self.ax.set_xlim(low, high)
        x_data, y_data = self._last_stem_data
        inside = y_data[(x_data >= low) & (x_data <= high)]
        top = float(inside.max()) if inside.size else float(y_data.max())
        self.ax.set_ylim(0.0, top * STEM_HEADROOM)
        self._fitted_ylim = self.ax.get_ylim()

    def show_x_range(self, low: float, high: float) -> None:
        """Open, and reset, on the stems in ``low``..``high``; a Full scan toggle shows them all."""
        if self._last_stem_data is None:
            return
        self._home_x = (low, high)
        self._fit_stems(low, high)
        if self.full_scan_button is None:
            button = QToolButton(self.canvas)
            button.setText("Full scan")
            button.setCheckable(True)
            button.setToolTip(f"Show the whole scan; the chart opens on m/z {low:.0f}–{high:.0f}")
            theme.style(button, _TOGGLE_QSS)
            button.toggled.connect(self._show_full_scan)
            self.full_scan_button = button
            button.show()

    def _show_full_scan(self, full: bool) -> None:
        self._fit_stems(*(self._full_x if full else self._home_x))
        self.canvas.draw_idle()

    def _place_full_scan_button(self) -> None:
        """At the right end of the title row, centred on the title."""
        button = self.full_scan_button
        button.adjustSize()
        box = self.ax.title.get_window_extent(self.canvas.get_renderer())
        logical = self.canvas.height() / self.figure.bbox.height
        # 2 px above the box's middle, which its descenders pull down.
        centre = self.canvas.height() - (box.y0 + box.y1) / 2 * logical - 2
        button.move(self.canvas.width() - button.width() - 16, max(0, round(centre - button.height() / 2)))

    def add_vertical_line(
        self,
        x_position: float,
        color: str = "red",
        width: int = PLOT_GUIDELINE_WIDTH,
        style: str = "solid",
        *,
        behind: bool = False,
    ):
        """
        Add a vertical line at specified position.

        Args:
            x_position: X coordinate for line
            color: Line color
            width: Line width
            style: Line style (solid, dashed, dotted)
            behind: Draw under the data and gridlines, so it never hides a stem's height
        """
        try:
            if color.startswith("rgba"):
                import re

                match = re.match(r"rgba\((\d+),(\d+),(\d+),([\d.]+)\)", color)
                if match:
                    r, g, b, a = match.groups()
                    color = (int(r) / 255, int(g) / 255, int(b) / 255, float(a))

            linestyle = "-"
            if style == "dashed":
                linestyle = "--"
            elif style == "dotted":
                linestyle = ":"
            elif style == "dashdot":
                linestyle = "-."

            self.ax.axvline(
                x=x_position,
                color=color,
                linewidth=width,
                linestyle=linestyle,
                alpha=None if not isinstance(color, tuple) else color[3],
                zorder=0.5 if behind else None,
            )

            # Defer canvas update for batch rendering

        except Exception as e:
            logger.error(f"Failed to add vertical line: {e}")

    def add_key_entry(self, label: str, *, style: str, alpha: float, width: float) -> None:
        """A legend entry, in the neutral ink, for a way of drawing traces rather than a trace."""
        self.ax.plot(
            [], [], color=COLORS["text_secondary"], linestyle=style, alpha=alpha,
            linewidth=width, label=label,
        )

    def show_legend(self) -> None:
        """Key the named traces above the axes, wrapped to the plot's width.

        Its rows are laid out, and room made for them, on every resize.
        """
        handles, labels = self.ax.get_legend_handles_labels()
        self._legend_entries = (handles, labels) if labels else None

    def _wrap_legend(self, width: float) -> float:
        """Lay the legend out in as many columns as ``width`` px holds; its height in px."""
        if self._legend_entries is None:
            return 0.0
        handles, labels = self._legend_entries
        style = {
            "loc": "lower left",
            "bbox_to_anchor": (0, 1),
            # Above the axis multiplier ("×10⁵"), which sits on the axes' top-left corner.
            "bbox_transform": offset_copy(self.ax.transAxes, fig=self.figure, y=_points(LEGEND_LIFT_PX), units="points"),
            "fontsize": PLOT_LABEL_FONTSIZE,
            "frameon": False,
            "borderaxespad": 0,
            "borderpad": 0,
            "handlelength": 1.6,
            "columnspacing": 1.2,
        }
        renderer = self.canvas.get_renderer()
        logical = self.canvas.get_width_height()[0] / self.figure.bbox.width

        def px(artist):
            return artist.get_window_extent(renderer).width * logical

        legend = self.ax.legend(handles, labels, ncol=len(labels), **style)
        font_px = PLOT_LABEL_FONTSIZE * PLOT_DPI / 72
        spacing = style["columnspacing"] * font_px
        # Each entry is its handle, matplotlib's default 0.8 em text pad, its text and a gap.
        entry = max(px(text) for text in legend.get_texts()) + (style["handlelength"] + 0.8) * font_px + spacing
        columns = max(1, min(len(labels), int((width + spacing) // entry)))
        rows = -(-len(labels) // columns)
        # Matplotlib fills columns top to bottom; reorder so entries read across, M+0 first.
        order = [row * columns + col for col in range(columns) for row in range(rows) if row * columns + col < len(labels)]
        legend = self.ax.legend(
            [handles[i] for i in order], [labels[i] for i in order], ncol=columns, **style
        )
        return legend.get_window_extent(renderer).height * logical

    def _on_theme_changed(self, remap: dict) -> None:
        if self.figure is None:
            return
        _apply_theme_rc()
        remap_figure_colors(self.figure, remap)
        # A text's background box is not one of the figure's children.
        for label in self._all_peak_labels():
            label.get_bbox_patch().set_facecolor(COLORS["surface"])
        self.ax.tick_params(colors=COLORS["border_strong"], labelcolor=COLORS["text_secondary"])
        self.ax.grid(True, color=COLORS["grid_line"])
        self.canvas.draw_idle()

    def set_title(self, title: str):
        """Update the plot title."""
        self.title = title
        self._set_axes_title(title)
        # Don't draw yet

    def _set_axes_title(self, title: str, legend_px: float = 0.0) -> None:
        pad = PLOT_TITLE_PADDING + 4
        if legend_px:
            pad = _points(LEGEND_LIFT_PX + legend_px + 10)
        self.ax.set_title(title, loc="left", fontsize=PLOT_TITLE_FONTSIZE, pad=pad)

    def _fit_margins(self, _event=None) -> None:
        """Fixed pixel margins, so axes line up across plots of any width.

        A legend gets its own rows between the title and the axes.
        """
        width, height = self.canvas.get_width_height()
        if width < 100 or height < 100:
            return
        left, right = 72, 16
        legend_px = self._wrap_legend(width - left - right)
        self._set_axes_title(self.title, legend_px)
        top = 38 + (LEGEND_LIFT_PX + legend_px - 2 if legend_px else 0)
        self.figure.subplots_adjust(
            left=left / width, right=1 - right / width, top=1 - top / height, bottom=46 / height
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

    def _reset_on_double_click(self, event) -> None:
        if event.dblclick and event.button == 1:
            self.reset_view()

    def context_menu(self) -> QMenu | None:
        # Pan and Zoom use the right button themselves; a menu would swallow
        # the release and leave their drag running.
        if self.mode():
            return None
        menu = QMenu(self)
        menu.setAttribute(Qt.WA_DeleteOnClose)
        reset = menu.addAction("Reset This Chart")
        reset.setToolTip("Or double-click the chart")
        reset.triggered.connect(self.reset_view)
        return menu

    def _show_context_menu(self, pos) -> None:
        menu = self.context_menu()
        if menu is not None:
            menu.popup(self.canvas.mapToGlobal(pos))

    def mode(self) -> str:
        return {_Mode.PAN: "pan", _Mode.ZOOM: "zoom"}.get(self.nav.mode, "")

    def reset_view(self) -> None:
        """Fit the view to the drawn data, or a spectrum to the range it opened on.

        Matplotlib's nav-stack home can become unstable in Qt embed cases,
        especially for stem plots, so limits come from the stored data.
        """
        try:
            if self._last_stem_data is not None:
                if self.full_scan_button is not None and self.full_scan_button.isChecked():
                    self.full_scan_button.setChecked(False)  # fits the opening range
                else:
                    self._fit_stems(*self._home_x)
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

    def _reset_peak_labels(self) -> None:
        # Own ions first, tallest first, then the other peaks.
        self._peak_labels = []
        self._own_count = 0
        # One label and bracket over a run of isotopologues too close to name apart.
        self._cluster = None

    def _all_peak_labels(self) -> list:
        own, others = self._peak_labels[: self._own_count], self._peak_labels[self._own_count :]
        return own + ([self._cluster[0]] if self._cluster else []) + others

    def _peak_label(
        self, text: str, x: float, y: float, *, own: bool, rise: float, side: float = 0
    ):
        return self.ax.annotate(
            text,
            (x, y),
            xytext=(side, rise),
            textcoords="offset points",
            ha="left" if side else "center",
            va="center" if side else "bottom",
            fontsize=PLOT_TICK_FONTSIZE,
            color=COLORS["text"] if own else COLORS["text_secondary"],
            fontweight="semibold" if own else "normal",
            annotation_clip=True,
            # Opaque so a guide line through the label never cuts it.
            bbox={"boxstyle": "square,pad=0.15", "fc": COLORS["surface"], "ec": "none"},
        )

    def label_peaks(
        self,
        x_data,
        y_data,
        *,
        own_mz=(),
        own_names=None,
        limit: int = 5,
        min_fraction: float = 0.05,
        decimals: int = 2,
    ) -> None:
        """Label the compound's own ions (``own_mz``), then up to ``limit`` of
        the tallest other peaks. Peaks below ``min_fraction`` of the tallest
        are baseline and stay unlabelled. Where labels would share a column,
        own ions win over others, and the tallest own ion over the rest.

        With ``own_names`` (one per ``own_mz``, such as "M+1"), each own label
        leads with its name, and own ions too close to label one by one are
        named together by a bracket above them, such as "M+0…M+3"."""
        x_data = np.asarray(x_data, dtype=np.float64)
        y_data = np.asarray(y_data, dtype=np.float64)
        keep = (y_data > 0) & np.isfinite(x_data) & np.isfinite(y_data)
        x_data, y_data = x_data[keep], y_data[keep]
        if not len(y_data):
            return
        floor = min_fraction * float(np.max(y_data))
        names = list(own_names) if own_names is not None else [None] * len(own_mz)
        own: dict[int, str | None] = {}
        for mz, name in zip(own_mz, names):
            nearest = int(np.argmin(np.abs(x_data - mz)))
            # Channels sit 1 Da apart: half that finds a channel's peak
            # without taking its neighbour's.
            if abs(x_data[nearest] - mz) <= 0.5 and y_data[nearest] >= floor and nearest not in own:
                own[nearest] = name
        others = [
            int(index) for index in np.argsort(y_data)[::-1]
            if y_data[index] >= floor and index not in own
        ][:limit]
        for index in sorted(own, key=lambda index: -y_data[index]):
            value = f"{x_data[index]:.{decimals}f}"
            text = f"{own[index]}  {value}" if own[index] else value
            # Clear of the stem top, so the label never sits on its bar.
            self._peak_labels.append(
                self._peak_label(text, x_data[index], y_data[index], own=True, rise=4)
            )
        self._own_count = len(self._peak_labels)
        for index in others:
            self._peak_labels.append(
                self._peak_label(
                    f"{x_data[index]:.{decimals}f}", x_data[index], y_data[index], own=False, rise=2
                )
            )
        named = sorted(index for index in own if own[index])
        if len(named) > 1:
            left, right = x_data[named[0]], x_data[named[-1]]
            top = max(y_data[index] for index in named)
            bracket = self.ax.plot(
                [left, right], [top, top],
                color=COLORS["text_secondary"], linewidth=PLOT_GUIDELINE_WIDTH,
                transform=offset_copy(self.ax.transData, fig=self.figure, y=3, units="points"),
            )[0]
            # Centred above the bracket, which sits over the tallest bar, so on no stem.
            label = self._peak_label(
                f"{own[named[0]]}…{own[named[-1]]}", (left + right) / 2, top, own=True, rise=6
            )
            self._cluster = (label, bracket)

    def _on_draw(self, _event=None) -> None:
        if self.full_scan_button is not None:
            self._place_full_scan_button()
        if not self._peak_labels:
            return
        before = [label.get_visible() for label in self._all_peak_labels()]
        refit = self._make_label_headroom()
        self._declutter_peak_labels()
        if refit or before != [label.get_visible() for label in self._all_peak_labels()]:
            # Settles in one more draw: the same layout gives the same answer.
            self.canvas.draw_idle()

    def _make_label_headroom(self) -> bool:
        """While the stems are fitted, raise the top until each label in view fits under it.

        The room is in pixels, so a short chart keeps its labels. True if the range moved.
        """
        if self._fitted_ylim is None or self.ax.get_ylim() != self._fitted_ylim:
            return False  # the user panned or zoomed
        renderer = self.canvas.get_renderer()
        area = self.ax.get_window_extent(renderer)
        low, high = self.ax.get_xlim()
        x_data, y_data = self._last_stem_data
        inside = y_data[(x_data >= low) & (x_data <= high)]
        top = float(inside.max()) * STEM_HEADROOM if inside.size else self._fitted_ylim[1]
        for label in self._all_peak_labels():
            x, y = label.xy
            if not low <= x <= high:
                continue
            label.set_visible(True)  # hidden text measures as an empty box
            above = label.get_window_extent(renderer).y1 - self.ax.transData.transform((x, y))[1]
            room = area.height - above - 2
            if room > 0:
                top = max(top, y * area.height / room)
        if abs(top - self._fitted_ylim[1]) <= 1e-3 * top:
            return False
        self.ax.set_ylim(0.0, top)
        self._fitted_ylim = self.ax.get_ylim()
        return True

    def _declutter_peak_labels(self) -> None:
        renderer = self.canvas.get_renderer()
        area = self.ax.get_window_extent(renderer)
        placed = []

        def span(label):
            """The label's column if it fits the plot and no placed label's column, else None."""
            label.set_visible(True)  # hidden text measures as an empty box
            box = label.get_window_extent(renderer)
            # One label per column: a label stacked above a neighbour's is
            # ambiguous about which stem it names.
            column = (box.x0 - 4, box.x1 + 4)
            fits = (
                box.y1 <= area.y1 + 1
                and box.x0 >= area.x0 - 1
                and box.x1 <= area.x1 + 1
                and not any(column[0] < right and left < column[1] for left, right in placed)
            )
            return column if fits else None

        own = self._peak_labels[: self._own_count]
        if self._cluster is not None:
            label, bracket = self._cluster
            columns = [span(item) for item in own]
            apart = all(columns) and not any(
                a[0] < b[1] and b[0] < a[1]
                for i, a in enumerate(columns) for b in columns[i + 1 :]
            )
            column = None if apart else span(label)
            for item, item_column in zip(own, columns):
                item.set_visible(apart)
                if apart:
                    placed.append(item_column)
            label.set_visible(column is not None)
            bracket.set_visible(column is not None)
            if column is not None:
                placed.append(column)
            rest = self._peak_labels[self._own_count :]
        else:
            rest = self._peak_labels  # tallest own first, so they win
        for label in rest:
            column = span(label)
            if column is not None:
                placed.append(column)
            label.set_visible(column is not None)

    def finalize_plot(self):
        """Finalize plot after all data is added - single draw call for speed."""
        self.ax.grid(True, color=COLORS["grid_line"], linestyle="-", linewidth=PLOT_GRID_LINEWIDTH)
        self._fit_margins()

        if "time" in self.x_label.lower() or "min" in self.x_label.lower():
            from matplotlib.ticker import FormatStrFormatter

            self.ax.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))

        self.canvas.draw()

    def cleanup(self):
        """Properly cleanup matplotlib resources to prevent memory leaks."""
        try:
            if hasattr(self, "ax") and self.ax:
                self.ax.clear()
                self.ax = None

            if hasattr(self, "figure") and self.figure:
                self.figure.clear()
                plt.close(self.figure)
                self.figure = None

            if hasattr(self, "canvas") and self.canvas:
                self.canvas = None

            if getattr(self, "nav", None) is not None:
                self.nav = None
            self._reset_peak_labels()

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
