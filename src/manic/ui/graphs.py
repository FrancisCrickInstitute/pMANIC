import logging
import math
from collections.abc import Iterable
from typing import Dict, List, Optional, Sequence, Set

import numpy as np
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QEvent, QMargins, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QRubberBand,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from manic.io.compound_reader import read_compound_with_session
from manic.models.sample_fit_type import FIT_TYPE_LABELS, get_sample_fit_types
from manic.processors.eic_processing import get_eics_for_compound
from manic.processors.display_deconvolution import (
    plot_display,
)
from manic.processors.tile_y_scale import (
    TileScaleInput,
    YAxisScale,
    YScalePolicy,
    axes_for_tiles,
)
from manic.processors.integration import compute_linear_baseline
from manic.utils.timer import measure_time

from manic.validation.peak_verdict import PeakReview, PeakVerdict
from manic.validation.unlabelled_identity import (
    IdentityAssessmentSet,
    IdentitySampleAssessment,
    QualifierStatus,
)

from .channel_chips import CHIP_HEIGHT, ChannelChipRow
from .channel_labels import channel_legend_label, has_defined_channel
from .chart_header import HeaderName
from .chart_style import set_nice_ticks, style_axis, style_chart, text_style, ui_font
from .icon_button import icon_button, segmented
from .identity_chart import identity_cells, identity_unassessed_note, qualifier_gap_note
from .colors import (
    QUALIFIER_GREEN,
    QUALIFIER_GREY,
    QUALIFIER_RED,
    ChannelTraceStyle,
    channel_trace_styles,
    dark_red_colour,
    label_colors,
    legend_trace_styles,
    steel_blue_colour,
)
from .sidebar_widgets import ElidedLabel, shortcut_text
from .plot_tile import (
    LARGE_TILE,
    MIN_TILE,
    TILE_GAP,
    PlotTile,
    grid_columns,
    tile_badges,
    tile_text_size,
)
from .theme import FONT_SIZE_TITLE, color
from manic.ui import theme

logger = logging.getLogger(__name__)

PLOT_Y_AXIS_HEADROOM = 1.05



def _minutes(value: float) -> str:
    # Same rounding as the sidebar's tR field.
    return f"{float(value):.3f}".rstrip("0").rstrip(".") or "0"


def retention_time_text(values: Iterable[float]) -> str:
    """'tR 7.09' for the grid title, or 'tR 7.05–7.12' when samples differ."""
    values = [float(v) for v in values if v is not None]
    if not values:
        return ""
    low, high = min(values), max(values)
    if abs(high - low) < 1e-6:
        return f"tR {_minutes(low)}"
    return f"tR {_minutes(low)}–{_minutes(high)}"


def tile_caption(sample_name: str, fit_type: str | None) -> str:
    if not fit_type:
        return sample_name
    return f"{sample_name}  ·  {FIT_TYPE_LABELS.get(fit_type, fit_type)}"


def qc_key_html(identity: IdentityAssessmentSet | None) -> str:
    """'Qualifier QC: ● Validated ● Not assessed' for the trace colours this compound's samples
    show; empty when no qualifier can be checked, where the gap note explains the grey traces."""
    if identity is None or identity_unassessed_note(identity) is not None:
        return ""
    shown = {q.status for sample in identity.samples for q in identity_cells(sample)}
    checked = {QualifierStatus.VALIDATED, QualifierStatus.FAILED}
    entries = [
        (qcolor, name)
        for qcolor, name, present in (
            (QUALIFIER_GREEN, "Validated", QualifierStatus.VALIDATED in shown),
            (QUALIFIER_RED, "Failed", QualifierStatus.FAILED in shown),
            (QUALIFIER_GREY, "Not assessed", bool(shown - checked)),
        )
        if present
    ]
    return "Qualifier QC:&nbsp;&nbsp;" + "&nbsp;&nbsp;".join(
        f'<span style="color:{qcolor.name()};">●</span>&nbsp;{name}' for qcolor, name in entries
    )


class ClickableChartView(QChartView):
    """Custom QChartView that can be selected"""

    clicked = Signal(object)
    right_clicked = Signal(object, object)  # view, global position
    double_clicked = Signal(object)

    def __init__(self, chart, sample_name, compound_name="", parent=None):
        super().__init__(chart, parent)
        self.sample_name = sample_name
        self.compound_name = compound_name
        self.is_selected = False
        self._swallow_release = False
        self.setRenderHint(QPainter.Antialiasing)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFrameShape(QFrame.NoFrame)
        # Transparent so the card's verdict tint shows through.
        self.setBackgroundBrush(Qt.NoBrush)
        self.viewport().setAutoFillBackground(False)
        self.setCursor(Qt.PointingHandCursor)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            # The release that ends a double-click must not toggle selection again.
            self._swallow_release = True
            self.double_clicked.emit(self)
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        # The release that ends a double-click can be lost to the dialog it opened.
        self._swallow_release = False
        if event.button() == Qt.LeftButton:
            self.m_pressPos = event.position().toPoint()
        elif event.button() == Qt.RightButton:
            self.right_clicked.emit(self, event.globalPosition())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._swallow_release:
            self._swallow_release = False
        elif event.button() == Qt.LeftButton and hasattr(self, "m_pressPos"):
            dist = (event.position().toPoint() - self.m_pressPos).manhattanLength()
            if dist < QApplication.startDragDistance():
                self.clicked.emit(self)
        super().mouseReleaseEvent(event)

    def set_selected(self, selected: bool):
        """Set the selection state and update appearance"""
        self.is_selected = selected
        self.update_appearance()

    def update_appearance(self):
        tile = self.parentWidget()
        if isinstance(tile, PlotTile):
            tile.refresh_selection()


def _fit_time_ticks(chart: QChart) -> None:
    """Time ticks as dense as the tile's plot width allows without labels touching."""
    axis = chart.axes(Qt.Horizontal)[0]
    set_nice_ticks(
        axis, axis.min(), axis.max(), max_ticks=2.5, decimals=2, plot_px=chart.plotArea().width()
    )


def _review_command_text(
    review: PeakReview | None, plots, set_text: str, clear_text: str
) -> str:
    """"Accept Bio_004 (Below Threshold)" or "Accept 2 Peaks (Below Threshold)" while it
    sets the review, "Clear Acceptance (Bio_004)" once every target already has it."""
    if len(plots) == 1:
        target = next(iter(plots)).sample_name
    else:
        target = f"{len(plots)} Peaks" if plots else "Peak"
    if review is None and plots:
        return f"{clear_text} ({target})"
    return set_text.format(target)


def _show_shortcut(action, sequence) -> None:
    """Label a context-menu action with the grid key that does the same thing.

    The grid handles the key itself, so the menu shortcut is display-only.
    """
    action.setShortcut(QKeySequence(sequence))
    action.setShortcutContext(Qt.WidgetShortcut)
    action.setShortcutVisibleInContextMenu(True)


class _ScaleMenuButton(QToolButton):
    """Checked while a scale toggle is on; only its menu changes the scale."""

    def nextCheckState(self) -> None:
        pass


class GraphView(QWidget):
    """
    A grid of QtCharts tiles, one per sample, with data from the
    processors/io stack.
    """

    selection_changed = Signal(list)  # List of selected sample names
    peak_review_changed = Signal(str, list, object)
    sample_fit_type_changed = Signal(str, list, object)
    focus_selected_requested = Signal(list)
    show_all_samples_requested = Signal()
    settings_requested = Signal()
    # A documentation link, "file.md#section".
    guide_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        outer_layout = QVBoxLayout(self)
        outer_layout.setSpacing(0)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.setFocusPolicy(Qt.StrongFocus)

        header = QHBoxLayout()
        header.setContentsMargins(6, 6, 6, 0)
        header.setSpacing(8)
        # The two panel buttons bracket the header, each beside the panel it opens; the
        # window wires them to View > Show Sidebar and Show Summary.
        self.sidebar_button = icon_button("sidebarButton", "sidebar_panel.svg", "Sidebar")
        self.summary_button = icon_button("summaryButton", "summary_panel.svg", "Summary")
        for button in (self.sidebar_button, self.summary_button):
            button.setCheckable(True)
        self._header_button(self.sidebar_button)
        header.addWidget(self.sidebar_button)
        self.compound_title = HeaderName(min_chars=10)
        theme.style(self.compound_title, text_style("text", FONT_SIZE_TITLE, 600))
        self.compound_title.hide()
        header.addWidget(self.compound_title)
        # "tR 7.09", plus "· 3 of 30 selected" once plots are picked; the Samples
        # section already gives the total.
        self.selection_summary = ElidedLabel()
        theme.style(self.selection_summary, text_style("text_secondary", 12))
        self.selection_summary.setToolTip(
            f"Click a plot to select it. {shortcut_text('Ctrl+A')} selects all, Esc clears, "
            "arrow keys move, Space toggles, Enter opens the detailed view."
        )
        header.addWidget(self.selection_summary, stretch=1)
        # The plots' y-scale, mirrored from View > Shared Y-Scale and Scale to Selected Peak.
        self.shared_y_button = QToolButton()
        self.shared_y_button.setObjectName("sharedYButton")
        self.shared_y_button.setText("Shared Y")
        self.peak_scale_button = QToolButton()
        self.peak_scale_button.setObjectName("peakScaleButton")
        self.peak_scale_button.setText("Scale to peak")
        for button in (self.shared_y_button, self.peak_scale_button):
            button.setCheckable(True)
            button.setFocusPolicy(Qt.TabFocus)
        self._view_controls = segmented(self.shared_y_button, self.peak_scale_button)
        header.addWidget(self._view_controls)
        # On a narrow grid the two fold into one Scale menu, so the header keeps one row.
        self.scale_menu_button = _ScaleMenuButton()
        self.scale_menu_button.setObjectName("scaleMenuButton")
        self.scale_menu_button.setCheckable(True)
        self.scale_menu_button.setPopupMode(QToolButton.InstantPopup)
        self.scale_menu_button.setFocusPolicy(Qt.TabFocus)
        scale_menu = QMenu(self.scale_menu_button)
        scale_menu.setToolTipsVisible(True)
        self._scale_choices = []
        for button in (self.shared_y_button, self.peak_scale_button):
            action = scale_menu.addAction(button.text())
            action.setCheckable(True)
            action.triggered.connect(button.click)
            self._scale_choices.append((action, button))
            button.toggled.connect(self._sync_scale_menu)
        self._sync_scale_menu()
        scale_menu.aboutToShow.connect(self._sync_scale_menu)
        self.scale_menu_button.setMenu(scale_menu)
        self._scale_menu = segmented(self.scale_menu_button)
        self._scale_menu.hide()
        header.addWidget(self._scale_menu)
        self._header_row = header
        self.settings_button = icon_button("settingsButton", "settings_gear.svg", "Settings")
        self.settings_button.clicked.connect(self.settings_requested.emit)
        for button in (self.settings_button, self.summary_button):
            self._header_button(button)
            header.addWidget(button)
        outer_layout.addLayout(header)

        self.qc_key = QLabel()
        self.qc_key.setTextFormat(Qt.RichText)
        self.qc_key.setFixedHeight(CHIP_HEIGHT)
        theme.style(self.qc_key, text_style("text_secondary", 11))
        self.qc_key.hide()
        self._qc_key_wanted = False
        theme.notifier.changed.connect(self._recolour_qc_key)
        # The key stays beside the traces it colours; the Summary's Identity panel carries
        # the qualifier note while it is open.
        self.summary_button.toggled.connect(self._show_qc_text)
        # Legend entries and the QC key wrap onto a second row instead of truncating.
        self.channel_legend = ChannelChipRow(trailing=self.qc_key)
        legend_row = QHBoxLayout()
        legend_row.setContentsMargins(TILE_GAP + 2, 4, 6, 2)
        legend_row.addWidget(self.channel_legend)
        outer_layout.addLayout(legend_row)
        self.qc_note = QLabel()
        self.qc_note.setTextFormat(Qt.RichText)
        self.qc_note.setWordWrap(True)
        self.qc_note.setContentsMargins(TILE_GAP + 2, 0, 6, 2)
        theme.style(self.qc_note, text_style("text_secondary", 11))
        self.qc_note.linkActivated.connect(self.guide_requested)
        self.qc_note.hide()
        outer_layout.addWidget(self.qc_note)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setFocusPolicy(Qt.NoFocus)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self._scroll.viewport().setAutoFillBackground(False)
        self._scroll.viewport().installEventFilter(self)
        grid_host = QWidget()
        grid_host.setAutoFillBackground(False)
        grid_host.setStyleSheet("background: transparent;")
        self._scroll.setWidget(grid_host)
        outer_layout.addWidget(self._scroll, stretch=1)

        self._layout = QGridLayout(grid_host)
        self._layout.setSpacing(TILE_GAP)
        self._layout.setContentsMargins(TILE_GAP, 4, TILE_GAP, TILE_GAP)
        # Two large tiles side by side at the least, whatever sits beside the grid.
        self.setMinimumWidth(
            2 * LARGE_TILE[0]
            + 3 * TILE_GAP
            + self._scroll.verticalScrollBar().sizeHint().width()
        )
        self._grid_shape: tuple[int, int] = (1, 0)
        self._text_size = tile_text_size(*MIN_TILE)
        self._focus_index: int | None = None

        self._selected_plots: Set[ClickableChartView] = set()

        self._current_plots: List[ClickableChartView] = []

        self._current_compound: str = ""
        self._current_samples: List[str] = []
        self._sample_fit_types: Dict[tuple[str, str], str] = {}

        self.use_corrected = False
        self._prepared_displays = {}

        self._identity: IdentityAssessmentSet | None = None

        self._y_scale_policy = YScalePolicy.PER_TILE_EXTRACT
        self._last_validation_data: Dict[str, PeakVerdict] | None = None

        # Track max grid dimensions we've used, so we can reliably reset
        # stretch/min-size for any historical rows/cols when the grid shrinks.
        self._max_rows_seen = 0
        self._max_cols_seen = 0

        # Maintains reusable chart containers to avoid expensive creation/destruction cycles
        self._container_pool: List[
            QWidget
        ] = []
        self._available_containers: List[QWidget] = []

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._update_graph_sizes)

        self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self._drag_origin = None
        self._is_dragging = False

        self.installEventFilter(self)
        self._tr_text = ""
        self.selection_changed.connect(self._update_selection_summary)

    @staticmethod
    def _header_button(button: QToolButton) -> None:
        button.setAccessibleName(button.toolTip())
        button.setProperty("variant", "ghost")
        button.setIconSize(button.iconSize() * 0.9)
        button.setFixedSize(28, 28)
        button.setFocusPolicy(Qt.NoFocus)

    def _apply_text_size(self, tile: PlotTile) -> None:
        tick_px, caption_px = self._text_size
        if tile.text_size() == self._text_size:
            return
        tile.set_text_size(tick_px, caption_px)
        for axis in tile.chart_view.chart().axes():
            axis.setLabelsFont(ui_font(tick_px))
        _fit_time_ticks(tile.chart_view.chart())

    def _update_selection_summary(self, *_args) -> None:
        total = len(self._current_plots)
        selected = len(self._selected_plots)
        count = f"{selected} of {total} selected" if total and selected else ""
        self.selection_summary.setText(" · ".join(p for p in (self._tr_text, count) if p))
        # A long compound name elides before it hides the tR.
        self.selection_summary.setMinimumWidth(
            self.selection_summary.fontMetrics().horizontalAdvance(self._tr_text)
        )

    def eventFilter(self, obj, event):
        """
        Event filter to handle rubberband selection across child widgets.
        """
        if event.type() == QEvent.Resize and obj is self._scroll.viewport():
            self._resize_timer.start(60)
            return False
        if event.type() == QEvent.MouseButtonPress:
            me = event
            if me.button() == Qt.LeftButton:
                self._drag_origin = self.mapFromGlobal(me.globalPosition().toPoint())
                self._is_dragging = False
            # Always return False to let children process press events (e.g. for click detection)
            return False

        elif event.type() == QEvent.MouseMove:
            me = event
            if not (me.buttons() & Qt.LeftButton):
                return False

            if self._handle_drag_move(me):
                return True

        elif event.type() == QEvent.MouseButtonRelease:
            me = event
            if me.button() != Qt.LeftButton:
                return False

            if self._handle_drag_release(me):
                return True

        return super().eventFilter(obj, event)

    def _handle_drag_move(self, me):
        """Handle mouse move events for drag selection"""
        if self._drag_origin is None:
            return False

        current_pos = self.mapFromGlobal(me.globalPosition().toPoint())

        if not self._is_dragging:
            if (
                current_pos - self._drag_origin
            ).manhattanLength() < QApplication.startDragDistance():
                return False

            self._is_dragging = True
            self._rubber_band.setGeometry(
                QRect(self._drag_origin, current_pos).normalized()
            )
            self._rubber_band.show()
        else:
            rect = QRect(self._drag_origin, current_pos).normalized()
            self._rubber_band.setGeometry(rect)
            self._update_selection_from_rubberband(rect)

        return True

    def _handle_drag_release(self, me):
        """Handle mouse release events for drag selection"""
        if not self._is_dragging:
            self._drag_origin = None
            return False

        self._rubber_band.hide()

        final_pos = self.mapFromGlobal(me.globalPosition().toPoint())
        rect = QRect(self._drag_origin, final_pos).normalized()
        self._update_selection_from_rubberband(rect)

        selected_samples = [plot.sample_name for plot in self._selected_plots]
        self.selection_changed.emit(selected_samples)

        self._drag_origin = None
        self._is_dragging = False
        return True

    def _update_selection_from_rubberband(self, band_rect: QRect):
        """Update selection based on rubberband geometry"""
        modifiers = QApplication.keyboardModifiers()
        is_additive = bool(modifiers & (Qt.ControlModifier | Qt.ShiftModifier))

        for container in self._current_plots:
            chart_container = container.parent()
            if not chart_container:
                continue

            # Map the container rect into GraphView coordinates; the grid lives in an
            # inner host widget.
            top_left = chart_container.mapTo(self, chart_container.rect().topLeft())
            container_rect = QRect(top_left, chart_container.size())

            if band_rect.intersects(container_rect):
                if not container.is_selected:
                    container.set_selected(True)
                    self._selected_plots.add(container)
            elif not is_additive:
                if container.is_selected:
                    container.set_selected(False)
                    self._selected_plots.discard(container)

    def set_use_corrected(self, use_corrected: bool):
        """Set whether to use natural abundance corrected data."""
        self.use_corrected = use_corrected
        logger.info(
            f"GraphView set to use {'corrected' if use_corrected else 'uncorrected'} data"
        )

    def plot_compound(
        self,
        compound_name: str,
        samples: List[str],
        validation_data: Dict[str, PeakVerdict] = None,
        *,
        identity: IdentityAssessmentSet | None = None,
    ) -> None:
        """
        Build one mini-plot per active sample for the selected *compound*.
        """

        if identity is not None and identity.compound_name != compound_name:
            identity = None
        self._identity = identity
        note = qualifier_gap_note(identity) if identity is not None else None
        self.qc_note.setText(note or "")
        self._show_qc_text()

        # Re-plotting the same compound (a fit or scale change) keeps selection and focus.
        same_compound = compound_name == self._current_compound
        kept_selection = self.get_selected_samples() if same_compound else []
        focused = self._focused_plot() if same_compound else None
        kept_focus = focused.sample_name if focused is not None else None

        self._clear_layout()
        self._set_title(compound_name)
        if not samples:
            self._hide_unused_tiles()
            self._hide_legend()
            self._update_selection_summary()
            return

        self._current_compound = compound_name
        self._current_samples = samples
        self._sample_fit_types = get_sample_fit_types(compound_name)

        with measure_time("get_eics_from_db"):
            eics = get_eics_for_compound(
                compound_name, samples, use_corrected=False
            )

        num = len(eics)
        if num == 0:
            self._hide_unused_tiles()
            self._hide_legend()
            return

        self._last_validation_data = validation_data

        prepared_displays = []
        scale_inputs: list[TileScaleInput] = []
        retention_times = []
        for eic in eics:
            compound = read_compound_with_session(eic.compound_name, eic.sample_name)
            retention_times.append(compound.retention_time)
            prepared = plot_display(
                eic.time,
                eic.intensity,
                compound,
                use_corrected=self.use_corrected,
            )
            prepared_displays.append(prepared)
            scale_inputs.append(
                TileScaleInput(
                    prepared=prepared,
                    raw_intensity=eic.intensity,
                    independent_channels=compound.is_unlabelled_target,
                )
            )
        self._prepared_displays = {
            (eic.sample_name, eic.compound_name): prepared
            for eic, prepared in zip(eics, prepared_displays)
        }
        tile_axes = axes_for_tiles(self._y_scale_policy, scale_inputs)
        self._tr_text = retention_time_text(retention_times)

        self._update_channel_legend(compound_name, eics)

        with measure_time("build_plots_and_add_to_layout"):
            plot_containers = [
                self._get_container_from_pool(
                    eic,
                    verdict=validation_data.get(eic.sample_name, PeakVerdict.PASS)
                    if validation_data
                    else PeakVerdict.PASS,
                    axis_scale=axis_scale,
                )
                for eic, axis_scale in zip(eics, tile_axes, strict=True)
            ]

            self._current_plots = [
                container.chart_view for container in plot_containers
            ]

            # Reused tiles stay visible: hiding and re-showing them costs a
            # synchronous relayout of every card. Nothing paints until the
            # event loop runs, so there is no flash either way.
            self._place_tiles(force=True)
            for container in plot_containers:
                if container.isHidden():
                    container.show()
            self._hide_unused_tiles()

        if same_compound:
            names = [plot.sample_name for plot in self._current_plots]
            self._focus_index = names.index(kept_focus) if kept_focus in names else None
            for plot in self._current_plots:
                if plot.sample_name in kept_selection:
                    plot.set_selected(True)
                    self._selected_plots.add(plot)
        elif self._focus_index is not None and self._focus_index >= num:
            self._focus_index = None
        self._paint_focus()
        self._update_selection_summary()
        self._layout.activate()
        if same_compound and self.get_selected_samples() != kept_selection:
            self.selection_changed.emit(self.get_selected_samples())

        self._prepared_displays.clear()

    def _hide_unused_tiles(self) -> None:
        for container in self._available_containers:
            container.hide()

    def _grid_viewport(self) -> tuple[int, int]:
        margins = self._layout.contentsMargins()
        viewport = self._scroll.viewport()
        return (
            viewport.width() - margins.left() - margins.right(),
            viewport.height() - margins.top() - margins.bottom(),
        )

    def _place_tiles(self, force: bool = False) -> None:
        """Lay the current tiles out as large as fits every one on screen; when even the
        smallest readable tiles cannot all fit, scroll at the large size instead."""
        tiles = [plot.parent() for plot in self._current_plots]
        width, height = self._grid_viewport()
        shape = grid_columns(
            len(tiles), width, height, min_width=MIN_TILE[0], min_height=MIN_TILE[1]
        )
        if shape[1]:  # Scrolling anyway, so small tiles buy no overview: scroll large ones.
            shape = grid_columns(
                len(tiles), width, height, min_width=LARGE_TILE[0], min_height=LARGE_TILE[1]
            )
        cols, row_height = shape
        rows = math.ceil(len(tiles) / cols) if tiles else 0
        text_size = tile_text_size(
            (width - TILE_GAP * (cols - 1)) / cols,
            row_height or (height - TILE_GAP * (rows - 1)) / max(rows, 1),
        )
        if text_size != self._text_size:
            self._text_size = text_size
            for tile in self._container_pool:
                self._apply_text_size(tile)
        if not force and shape == self._grid_shape:
            return
        self._grid_shape = shape
        self._max_rows_seen = max(self._max_rows_seen, rows)
        self._max_cols_seen = max(self._max_cols_seen, cols)
        for tile in tiles:
            self._layout.removeWidget(tile)
        for i in range(max(self._max_rows_seen, self._layout.rowCount())):
            self._layout.setRowStretch(i, 0)
            self._layout.setRowMinimumHeight(i, 0)
        for i in range(max(self._max_cols_seen, self._layout.columnCount())):
            self._layout.setColumnStretch(i, 0)
            self._layout.setColumnMinimumWidth(i, 0)
        for i, tile in enumerate(tiles):
            self._layout.addWidget(tile, i // cols, i % cols)
        for col in range(cols):
            self._layout.setColumnStretch(col, 1)
        for row in range(rows):
            self._layout.setRowStretch(row, 1)
            self._layout.setRowMinimumHeight(row, row_height)

    def select_sample(self, sample_name: str) -> bool:
        """Select, focus and scroll to the plot for ``sample_name``; False if not shown."""
        for index, plot in enumerate(self._current_plots):
            if plot.sample_name == sample_name:
                self.select_only_plot(plot)
                self._focus_on(index)
                return True
        return False

    def set_y_scale_policy(self, policy: YScalePolicy):
        if policy is self._y_scale_policy:
            return
        self._y_scale_policy = policy
        self._replot_current()

    def _replot_current(self) -> None:
        """Re-plot the current compound/samples after a display toggle."""
        if self._current_compound and self._current_samples:
            self.plot_compound(
                self._current_compound,
                self._current_samples,
                self._last_validation_data,
                identity=self._identity,
            )

    def _hide_legend(self) -> None:
        self.channel_legend.hide()
        self._qc_key_wanted = False
        self.qc_note.clear()
        self._show_qc_text()

    def _recolour_qc_key(self, *_args) -> None:
        if self._qc_key_wanted:
            self.qc_key.setText(qc_key_html(self._identity))

    def _show_qc_text(self, *_args) -> None:
        self.qc_key.setVisible(self._qc_key_wanted)
        self.qc_note.setVisible(bool(self.qc_note.text()) and not self.summary_button.isChecked())

    def _set_title(self, compound_name: str) -> None:
        self._tr_text = ""
        self.compound_title.setText(compound_name)
        self.compound_title.setVisible(bool(compound_name))
        self._fit_header()

    def _update_channel_legend(self, compound_name: str, eics) -> None:
        """One legend entry per plotted channel above the grid, in both analysis modes."""
        if not eics:
            self._hide_legend()
            return
        try:
            compound = read_compound_with_session(compound_name, None)
            intensity = eics[0].intensity
            multi_trace = getattr(intensity, "ndim", 1) > 1
            n_traces = intensity.shape[0] if multi_trace else 1
            channels = compound.analysis_channels[: n_traces]
            if not channels:
                self._hide_legend()
                return
            unlabelled = getattr(compound, "is_unlabelled_target", False)
            self.channel_legend.set_channels(
                [channel_legend_label(compound, i) for i in range(len(channels))],
                legend_trace_styles(
                    channels, unlabelled=unlabelled, multi_trace=multi_trace
                ),
            )
            key = qc_key_html(self._identity) if unlabelled and multi_trace else ""
            self.qc_key.setText(key)
            self._qc_key_wanted = bool(key)
            self._show_qc_text()
        except LookupError:
            self._hide_legend()
        except Exception:
            logger.exception("Failed to update channel colour key")
            self._hide_legend()

    def _on_plot_clicked(self, clicked_plot: ClickableChartView):
        """Handle plot click - toggle selection"""
        if clicked_plot in self._current_plots:
            self._focus_index = self._current_plots.index(clicked_plot)
            self._paint_focus()
        if clicked_plot.is_selected:
            self._selected_plots.discard(clicked_plot)
            clicked_plot.set_selected(False)
        else:
            self._selected_plots.add(clicked_plot)
            clicked_plot.set_selected(True)

        selected_samples = [plot.sample_name for plot in self._selected_plots]
        self.selection_changed.emit(selected_samples)

    def _focused_plot(self) -> ClickableChartView | None:
        if self._focus_index is None or self._focus_index >= len(self._current_plots):
            return None
        return self._current_plots[self._focus_index]

    def _paint_focus(self) -> None:
        show = self.hasFocus()
        for index, plot in enumerate(self._current_plots):
            tile = plot.parent()
            if isinstance(tile, PlotTile):
                tile.set_focused(show and index == self._focus_index)

    def _move_focus(self, delta: int) -> None:
        count = len(self._current_plots)
        if self._focus_index is None:
            self._focus_on(0)
        elif 0 <= self._focus_index + delta < count:
            self._focus_on(self._focus_index + delta)
        else:
            self._focus_on(self._focus_index)

    def _focus_on(self, index: int) -> None:
        # A pending re-flow after a resize would move the tile after we scroll to it.
        if self._resize_timer.isActive():
            self._resize_timer.stop()
            self._update_graph_sizes()
            QApplication.sendPostedEvents(None, QEvent.LayoutRequest)
        self._focus_index = index
        self._paint_focus()
        tile = self._current_plots[index].parent()
        if isinstance(tile, QWidget):
            self._scroll.ensureWidgetVisible(tile, 0, TILE_GAP)

    def _needs_review(self, plot: ClickableChartView) -> bool:
        """A badge with no verdict yet: Accepted and Marked bad close a tile's review."""
        tile = plot.parent()
        return (
            isinstance(tile, PlotTile)
            and bool(tile.badges())
            and tile.verdict not in (PeakVerdict.ACCEPTED, PeakVerdict.REJECTED)
        )

    def has_flagged(self) -> bool:
        return any(self._needs_review(plot) for plot in self._current_plots)

    def focus_flagged(self, step: int) -> bool:
        """Focus and select only the next (``step`` 1) or previous (-1) tile that needs
        review, wrapping, so A and B judge that tile; False if none does."""
        count = len(self._current_plots)
        start = self._focus_index if self._focus_index is not None else (-1 if step > 0 else count)
        for offset in range(1, count + 1):
            index = (start + step * offset) % count
            plot = self._current_plots[index]
            if self._needs_review(plot):
                self.setFocus(Qt.ShortcutFocusReason)
                self._focus_on(index)
                self.select_only_plot(plot)
                return True
        return False

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._paint_focus()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._paint_focus()

    def keyPressEvent(self, event):
        if not self._current_plots:
            super().keyPressEvent(event)
            return
        key = event.key()
        cols = self._grid_shape[0]
        moves = {Qt.Key_Left: -1, Qt.Key_Right: 1, Qt.Key_Up: -cols, Qt.Key_Down: cols}
        if event.matches(QKeySequence.SelectAll):
            self.select_all_plots()
        elif key == Qt.Key_Escape:
            self.clear_selection()
        elif key in moves and not event.modifiers() & ~Qt.KeypadModifier:
            self._move_focus(moves[key])
        elif key == Qt.Key_Space and self._focused_plot() is not None:
            self._on_plot_clicked(self._focused_plot())
        elif key in (Qt.Key_Return, Qt.Key_Enter) and self._focused_plot() is not None:
            self.inspect_plot(self._focused_plot())
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def _on_plot_right_clicked(self, clicked_plot: ClickableChartView, global_pos):
        """Handle right-click on plot - show consolidated context menu"""
        try:
            self._show_context_menu(global_pos.toPoint(), clicked_plot)
        except Exception as e:
            logger.error(f"Failed to show context menu: {e}")

    def _show_context_menu(self, global_pos, clicked_plot=None):
        """Plot context menu; Inspect and Select Only need a right-clicked plot."""

        if hasattr(self, "_active_context_menu") and self._active_context_menu:
            self._active_context_menu.close()

        context_menu = QMenu(self)
        self._active_context_menu = context_menu

        context_menu.setAttribute(Qt.WA_DeleteOnClose)
        context_menu.aboutToHide.connect(self._on_context_menu_closed)

        # Same groups and order as the Review menu, which main_window builds.
        inspect_action = context_menu.addAction("Inspect Sample...")
        _show_shortcut(inspect_action, QKeySequence(Qt.Key_Return))
        context_menu.addSeparator()

        select_all_action = context_menu.addAction("Select All Plots")
        select_all_action.triggered.connect(self.select_all_plots)
        _show_shortcut(select_all_action, QKeySequence.SelectAll)

        deselect_all_action = context_menu.addAction("Deselect All")
        deselect_all_action.triggered.connect(self.clear_selection)
        _show_shortcut(deselect_all_action, QKeySequence(Qt.Key_Escape))

        select_only_action = context_menu.addAction("Select Only This Sample")
        if clicked_plot is not None:
            select_only_action.triggered.connect(
                lambda: self.select_only_plot(clicked_plot)
            )
        else:
            select_only_action.setEnabled(False)
            select_only_action.setToolTip("Right-click a specific plot")

        show_only_action = context_menu.addAction("Show Only Selected Samples")
        show_only_action.triggered.connect(lambda: self.show_only_samples(clicked_plot))

        show_all_action = context_menu.addAction("Show All Samples")
        show_all_action.triggered.connect(
            lambda: self.show_all_samples_requested.emit()
        )

        context_menu.addSeparator()
        accept_action = context_menu.addAction("Accept Peak (Below Threshold)")
        reject_action = context_menu.addAction("Mark Peak as Bad")
        _show_shortcut(accept_action, QKeySequence(Qt.Key_A))
        _show_shortcut(reject_action, QKeySequence(Qt.Key_B))
        fit_menu = context_menu.addMenu("Curve Fit")
        self.update_review_actions(
            clicked_plot,
            inspect=inspect_action,
            show_only=show_only_action,
            accept=accept_action,
            reject=reject_action,
            fit_menu=fit_menu,
        )
        if clicked_plot is None:
            inspect_action.setToolTip("Right-click a specific plot to inspect it")
        else:
            inspect_action.triggered.connect(lambda: self.inspect_plot(clicked_plot))
            accept_action.triggered.connect(
                lambda: self.toggle_peak_review(clicked_plot, PeakReview.ACCEPTED)
            )
            reject_action.triggered.connect(
                lambda: self.toggle_peak_review(clicked_plot, PeakReview.REJECTED)
            )

        context_menu.popup(global_pos)

    def has_plots(self) -> bool:
        return bool(self._current_plots)

    def review_lead(self) -> ClickableChartView | None:
        """The plot the Review menu acts from: the focused plot if it is selected,
        else the first selected plot, else the focused plot."""
        selected = [plot for plot in self._current_plots if plot in self._selected_plots]
        focused = self._focused_plot()
        if selected:
            return focused if focused in selected else selected[0]
        return focused

    def update_review_actions(
        self,
        lead: ClickableChartView | None,
        *,
        inspect: QAction,
        show_only: QAction,
        accept: QAction,
        reject: QAction,
        fit_menu: QMenu,
    ) -> None:
        """Label, enable and check the review commands for `lead`.

        The plot context menu and the Review menu both call this, so their
        target counts and states always agree. `lead` None disables the
        commands that need a plot.
        """
        inspect.setEnabled(lead is not None)
        inspect.setText(
            f"Inspect {lead.sample_name}..." if lead is not None else "Inspect Sample..."
        )

        show_only.setEnabled(bool(self._selected_plots))
        shown = len(self._focus_sample_names(lead))
        if not self._selected_plots:
            show_only.setText("Show Only Selected Samples")
        elif lead is not None and lead not in self._selected_plots:
            show_only.setText("Show Only This Sample")
        elif shown == 1:
            show_only.setText("Show Only Selected Sample")
        else:
            show_only.setText(f"Show Only {shown} Selected Samples")

        fit_count = 1
        accept_review: PeakReview | None = PeakReview.ACCEPTED
        reject_review: PeakReview | None = PeakReview.REJECTED
        accept_plots = reject_plots = set()
        if lead is not None:
            accept_review, accept_plots = self._peak_review_targets(lead, PeakReview.ACCEPTED)
            reject_review, reject_plots = self._peak_review_targets(lead, PeakReview.REJECTED)
            fit_count = len(self._curve_fit_targets(lead))
        # The label names what the command does; a checkmark could not show a mixed group.
        accept.setCheckable(False)
        accept.setEnabled(bool(accept_plots))
        accept.setText(
            _review_command_text(
                accept_review, accept_plots, "Accept {} (Below Threshold)", "Clear Acceptance"
            )
        )
        reject.setCheckable(False)
        reject.setEnabled(lead is not None)
        reject.setText(
            _review_command_text(reject_review, reject_plots, "Mark {} as Bad", "Clear Bad Mark")
        )

        for group in fit_menu.findChildren(QActionGroup):
            group.deleteLater()
        fit_menu.clear()
        fit_menu.setTitle(
            f"Curve Fit for {fit_count} Samples" if fit_count > 1 else "Curve Fit"
        )
        fit_menu.setEnabled(lead is not None)
        if lead is not None:
            self._populate_curve_fit_menu(fit_menu, lead)

    def inspect_plot(self, plot: ClickableChartView) -> None:
        self._show_detailed_view(plot.compound_name, plot.sample_name)

    def show_only_samples(self, plot: ClickableChartView | None) -> None:
        """Show only the selection, or only `plot` when it is not selected."""
        self.focus_selected_requested.emit(self._focus_sample_names(plot))

    def _verdict_for_plot(self, plot: ClickableChartView) -> PeakVerdict:
        container = plot.parent()
        return getattr(container, "verdict", PeakVerdict.PASS)

    def _review_for_plot(self, plot: ClickableChartView) -> PeakReview | None:
        verdict = self._verdict_for_plot(plot)
        if verdict is PeakVerdict.ACCEPTED:
            return PeakReview.ACCEPTED
        if verdict is PeakVerdict.REJECTED:
            return PeakReview.REJECTED
        return None

    def _peak_review_targets(
        self, clicked_plot: ClickableChartView, review: PeakReview
    ) -> tuple[PeakReview | None, set[ClickableChartView]]:
        """The review a menu command sets, and the plots it sets it on.

        Accept only reaches below-threshold peaks. While any eligible peak
        lacks `review` the command sets it on those; once all have it, the
        command clears it from all of them.
        """
        plots = (
            self._selected_plots
            if clicked_plot in self._selected_plots
            else {clicked_plot}
        )
        if review is PeakReview.ACCEPTED:
            plots = {
                plot
                for plot in plots
                if self._verdict_for_plot(plot) in (PeakVerdict.FAIL, PeakVerdict.ACCEPTED)
            }
        missing = {plot for plot in plots if self._review_for_plot(plot) is not review}
        return (review, missing) if missing else (None, plots)

    def toggle_peak_review(
        self, clicked_plot: ClickableChartView, review: PeakReview
    ) -> None:
        new_review, plots = self._peak_review_targets(clicked_plot, review)
        sample_names = [plot.sample_name for plot in plots]
        self.peak_review_changed.emit(
            clicked_plot.compound_name, sample_names, new_review
        )

    def _curve_fit_targets(self, clicked_plot: ClickableChartView):
        return (
            self._selected_plots
            if clicked_plot in self._selected_plots
            else {clicked_plot}
        )

    def _populate_curve_fit_menu(
        self, fit_menu: QMenu, clicked_plot: ClickableChartView
    ) -> None:
        plots = self._curve_fit_targets(clicked_plot)
        current_values = {
            self._sample_fit_types.get((plot.compound_name, plot.sample_name))
            for plot in plots
        }
        common = next(iter(current_values)) if len(current_values) == 1 else object()
        group = QActionGroup(fit_menu)
        group.setExclusive(True)
        inherit_action = fit_menu.addAction("Use Compound Setting")
        inherit_action.setCheckable(True)
        inherit_action.setChecked(common is None)
        inherit_action.triggered.connect(
            lambda: self._emit_sample_fit_type(clicked_plot, None)
        )
        group.addAction(inherit_action)
        for value, label in FIT_TYPE_LABELS.items():
            action = fit_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(common == value)
            action.triggered.connect(
                lambda _checked=False, fit=value: self._emit_sample_fit_type(
                    clicked_plot, fit
                )
            )
            group.addAction(action)

    def _emit_sample_fit_type(
        self, clicked_plot: ClickableChartView, fit_type: str | None
    ) -> None:
        sample_names = [plot.sample_name for plot in self._curve_fit_targets(clicked_plot)]
        self.sample_fit_type_changed.emit(
            clicked_plot.compound_name, sample_names, fit_type
        )

    def apply_peak_verdicts(self, validation_data: Dict[str, PeakVerdict]) -> None:
        self._last_validation_data = validation_data
        for chart_view in self._current_plots:
            container = chart_view.parent()
            if container is None:
                continue
            verdict = validation_data.get(chart_view.sample_name, PeakVerdict.PASS)
            self._apply_validation_styling(container, verdict)

    def _on_context_menu_closed(self):
        """Handle context menu cleanup when it closes."""
        self._active_context_menu = None

    def _show_detailed_view(self, compound_name: str, sample_name: str):
        """Show detailed plot dialog for compound-sample combination"""
        try:
            from manic.ui.detailed_plot_dialog import DetailedPlotDialog

            dialog = DetailedPlotDialog(
                compound_name=compound_name,
                sample_name=sample_name,
                parent=self,
                use_corrected=self.use_corrected,
                samples=[plot.sample_name for plot in self._current_plots],
                identity_for=self._sample_identity,
            )
            dialog.exec()

        except Exception as e:
            logger.error(
                f"Failed to show detailed view for {compound_name}/{sample_name}: {e}"
            )
            QMessageBox.warning(self, "Detailed view", str(e))

    def get_selected_samples(self) -> List[str]:
        """Get list of currently selected sample names"""
        return [
            plot.sample_name
            for plot in self._current_plots
            if plot in self._selected_plots
        ]

    def get_current_compound(self) -> str:
        """Get the currently displayed compound"""
        return self._current_compound

    def get_current_samples(self) -> List[str]:
        """Get the list of all currently displayed samples"""
        return self._current_samples.copy()

    def clear_selection(self):
        """Clear all plot selections"""
        for plot in self._selected_plots:
            plot.set_selected(False)
        self._selected_plots.clear()
        self.selection_changed.emit([])

    def select_only_plot(self, plot: ClickableChartView):
        """Select only the provided plot, deselecting all others."""
        if plot is None:
            return

        if plot not in self._current_plots:
            return

        if (
            len(self._selected_plots) == 1
            and plot in self._selected_plots
            and plot.is_selected
        ):
            return

        for selected_plot in list(self._selected_plots):
            selected_plot.set_selected(False)
        self._selected_plots.clear()

        plot.set_selected(True)
        self._selected_plots.add(plot)
        self.selection_changed.emit([plot.sample_name])

    def clear_all_plots(self, force_destroy: bool = True):
        """Clear all plots from the graph view

        Args:
            force_destroy: If True, completely destroy widgets (slower but prevents artifacts).
                          If False, use pooling (faster but may have visual artifacts).
        """
        self.clear_selection()
        self._current_compound = ""
        self._current_samples = []
        self._identity = None
        self._hide_legend()
        self._set_title("")
        self._clear_layout(force_destroy=force_destroy)
        self._hide_unused_tiles()
        self._update_selection_summary()

        # Force immediate update to prevent visual artifacts
        self.update()
        self.repaint()
        QApplication.processEvents()

    def select_all_plots(self):
        """Select all currently displayed plots"""
        for plot in self._current_plots:
            if not plot.is_selected:
                plot.set_selected(True)
                self._selected_plots.add(plot)

        self.selection_changed.emit(self.get_selected_samples())

    def select_samples(self, names: Iterable[str]) -> None:
        wanted = set(names)
        self._selected_plots.clear()
        for plot in self._current_plots:
            if plot.sample_name in wanted:
                plot.set_selected(True)
                self._selected_plots.add(plot)
            elif plot.is_selected:
                plot.set_selected(False)
        self.selection_changed.emit(self.get_selected_samples())

    def _focus_sample_names(self, clicked_plot) -> list[str]:
        if clicked_plot is not None and clicked_plot not in self._selected_plots:
            return [clicked_plot.sample_name]
        return self.get_selected_samples()

    def contextMenuEvent(self, event):
        """
        Handle right-click context menu for plot selection.

        This method is automatically called by Qt when:
        - User right-clicks anywhere in the graph window
        - User presses the context menu key on keyboard
        - User performs platform-specific context menu gesture

        Qt's QWidget base class automatically detects right-click events
        and converts them to context menu events, then calls this override.
        """
        if not self._current_plots:
            return

        # Qt fires contextMenuEvent as well as the chart view's right-click signal;
        # hit-test the cursor so either path gets the plot under it.
        clicked_plot = self._plot_at_global_pos(event.globalPos())
        self._show_context_menu(event.globalPos(), clicked_plot=clicked_plot)

    def _plot_at_global_pos(self, global_pos):
        """Return the plot whose area contains the given global position."""
        for plot in self._current_plots:
            try:
                top_left = plot.mapToGlobal(plot.rect().topLeft())
                if QRect(top_left, plot.size()).contains(global_pos):
                    return plot
            except RuntimeError:
                continue
        return None

    def refresh_plots_with_session_data(
        self,
        validation_data: Optional[Dict[str, PeakVerdict]] = None,
        *,
        identity: IdentityAssessmentSet | None = None,
    ):
        """
        Refresh the current plots using session data where available.

        This method rebuilds all current plots, using session activity data
        where it exists, while preserving the current plot selection state.

        Args:
            validation_data: Optional dictionary mapping sample names to validation status
                           (True=valid, False=invalid) for visual styling.
        """
        if not self._current_compound or not self._current_samples:
            logger.warning("Cannot refresh plots: no current compound or samples")
            return

        selected_sample_names = {plot.sample_name for plot in self._selected_plots}

        try:
            with measure_time("refresh_plots_with_session_data"):
                self._selected_plots.clear()

                self.plot_compound(
                    self._current_compound,
                    self._current_samples,
                    validation_data,
                    identity=identity,
                )

                self.select_samples(selected_sample_names)
                restored_count = len(self._selected_plots)

                logger.info(
                    f"Refreshed {len(self._current_plots)} plots for '{self._current_compound}' "
                    f"with session data. Restored {restored_count} selections."
                )

        except Exception as e:
            logger.error(f"Failed to refresh plots with session data: {e}")
            try:
                selected_samples = [plot.sample_name for plot in self._selected_plots]
                self.selection_changed.emit(selected_samples)
            except Exception as e:
                pass  # Don't cascade failures

    def _get_container_from_pool(
        self,
        eic,
        verdict: PeakVerdict = PeakVerdict.PASS,
        *,
        axis_scale: YAxisScale,
    ) -> QWidget:
        """A pooled tile redrawn with ``eic``, or a new one when the pool is empty.

        Tiles are reused rather than deleted, which keeps Qt's parent-child
        ownership intact; the grid layout decides when they show."""
        if self._available_containers:
            container = self._available_containers.pop()
            self._update_container_data(container, eic, verdict, axis_scale=axis_scale)
            return container
        else:
            container = self._create_plot_container(eic, verdict, axis_scale=axis_scale)
            self._container_pool.append(container)
            return container

    def _create_plot_container(
        self,
        eic,
        verdict: PeakVerdict = PeakVerdict.PASS,
        *,
        axis_scale: YAxisScale,
    ) -> QWidget:
        """A new tile, connected and filtered once for its whole pooled life."""
        chart_view = self._build_plot(eic, axis_scale=axis_scale)

        container = PlotTile(chart_view)
        self._apply_text_size(container)
        caption = container.caption
        container.set_caption(self._tile_caption_for(eic))
        container.set_scale(axis_scale.scale_exp)

        chart_view.clicked.connect(self._on_plot_clicked)
        chart_view.right_clicked.connect(self._on_plot_right_clicked)
        chart_view.double_clicked.connect(self.inspect_plot)

        self._apply_validation_styling(container, verdict)

        # Rubber-band selection; a chart view's mouse events arrive on its viewport.
        container.installEventFilter(self)
        chart_view.installEventFilter(self)
        chart_view.viewport().installEventFilter(self)
        caption.installEventFilter(self)

        return container

    def _tile_caption_for(self, eic) -> str:
        fit_type = self._sample_fit_types.get((eic.compound_name, eic.sample_name))
        return tile_caption(eic.sample_name, fit_type)

    def _update_container_data(
        self,
        container: QWidget,
        eic,
        verdict: PeakVerdict = PeakVerdict.PASS,
        *,
        axis_scale: YAxisScale,
    ):
        chart_view = container.chart_view
        chart_view.chart().removeAllSeries()
        container.set_caption("")

        chart_view.set_selected(False)

        # Reset container sizing to clear any cached geometry from previous use
        # This is critical when widgets are moved to a different row/col
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        container.setMinimumSize(0, 0)
        chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        chart_view.setMinimumSize(0, 0)

        self._update_chart_data(chart_view, eic, axis_scale=axis_scale)

        container.set_caption(self._tile_caption_for(eic))
        container.set_scale(axis_scale.scale_exp)
        self._apply_validation_styling(container, verdict)

    def _update_chart_data(
        self,
        chart_view: ClickableChartView,
        eic,
        *,
        axis_scale: YAxisScale,
    ):
        """Redraw a reused chart's series on the axes it keeps."""
        chart = chart_view.chart()
        try:
            chart_view.sample_name = eic.sample_name
            chart_view.compound_name = eic.compound_name
            chart_view.set_selected(False)
            chart.removeAllSeries()
            axes = chart.axes()
            if len(axes) > 1:
                self._draw_eic(chart, axes[0], axes[1], eic, axis_scale)
        except Exception as e:
            # A failed redraw must not break the rest of the grid.
            logger.error(f"Error updating chart data: {e}")

    def _return_containers_to_pool(self):
        """Empty every current tile and return it to the pool for reuse."""
        for plot in self._current_plots:
            plot.set_selected(False)
            plot.chart().removeAllSeries()
            plot.chart().setTitle("")
            plot.update()

            container = plot.parent()
            while container and not hasattr(container, "chart_view"):
                container = container.parent()

            if container and container in self._container_pool:
                if hasattr(container, "caption"):
                    container.caption.setText("")
                    container.caption.update()

                self._available_containers.append(container)

        self._current_plots.clear()
        self._selected_plots.clear()

    def _build_plot(
        self, eic, axis_scale: YAxisScale
    ) -> ClickableChartView:
        """Create a ClickableChartView with EIC data and guide lines."""
        chart = QChart()
        style_chart(chart, QMargins(2, 2, 4, 0))
        # The card's fill, tinted for a peak verdict, runs under the traces too.
        chart.setPlotAreaBackgroundVisible(False)

        x_axis = QValueAxis()
        y_axis = QValueAxis()
        style_axis(x_axis)
        style_axis(y_axis, grid=True)
        chart.addAxis(x_axis, Qt.AlignBottom)
        chart.addAxis(y_axis, Qt.AlignLeft)
        # The tile's width settles after layout and on every resize.
        chart.plotAreaChanged.connect(lambda _area, c=chart: _fit_time_ticks(c))
        self._draw_eic(chart, x_axis, y_axis, eic, axis_scale)
        return ClickableChartView(chart, eic.sample_name, eic.compound_name)

    def _draw_eic(self, chart, x_axis, y_axis, eic, axis_scale: YAxisScale) -> None:
        """Traces, ranges, tR guides and baselines of one tile, on axes it already has."""
        compound = read_compound_with_session(eic.compound_name, eic.sample_name)
        prepared = self._plot_display_for(eic, compound)
        scale_factor = axis_scale.scale_factor
        scaled_y_max = axis_scale.scaled_max
        channel_styles = self._channel_styles_for(compound, eic.sample_name)
        self._add_eic_series(
            chart,
            x_axis,
            y_axis,
            eic.time,
            eic.intensity,
            compound,
            scale_factor,
            prepared=prepared,
            channel_styles=channel_styles,
        )

        # The x range is the actual EIC extract, so it reflects the tR window.
        self._set_tile_ranges(x_axis, y_axis, eic.time, scaled_y_max)
        _fit_time_ticks(chart)
        self._add_tile_guides(chart, x_axis, y_axis, compound, scaled_y_max)
        self._add_baseline_lines(
            chart,
            x_axis,
            y_axis,
            eic.time,
            eic.intensity,
            compound,
            scale_factor,
            prepared=prepared,
            channel_styles=channel_styles,
        )

    def _set_tile_ranges(self, x_axis, y_axis, eic_time, scaled_y_max) -> None:
        x_min = float(np.min(eic_time))
        x_max = float(np.max(eic_time))
        x_axis.setRange(x_min, x_max)
        y_max = scaled_y_max * PLOT_Y_AXIS_HEADROOM
        y_axis.setRange(0, y_max)
        set_nice_ticks(y_axis, 0, y_max, max_ticks=2)

    def _add_tile_guides(self, chart, x_axis, y_axis, compound, scaled_y_max) -> None:
        """Solid line at the expected tR, dashed lines at the integration window."""
        rt = compound.retention_time
        self._add_guide_line(
            chart, x_axis, y_axis, rt, 0, scaled_y_max,
            color("text_secondary"), role="rt", width=1.0,
        )
        for edge in (rt - compound.loffset, rt + compound.roffset):
            self._add_guide_line(
                chart, x_axis, y_axis, edge, 0, scaled_y_max,
                steel_blue_colour, dashed=True, role="window", width=1.0,
            )

    def _add_guide_line(
        self,
        chart,
        x_axis,
        y_axis,
        x_pos,
        y_start,
        y_end,
        color,
        dashed=False,
        *,
        role: str | None = None,
        width: float = 1.2,
    ):
        """Add a vertical guide line to the chart."""
        line_series = QLineSeries()
        line_series.append(x_pos, y_start)
        line_series.append(x_pos, y_end)
        if role:
            line_series.setProperty("guide_role", role)
        pen = QPen(color, width)
        if dashed:
            pen.setStyle(Qt.DashLine)
        line_series.setPen(pen)
        chart.addSeries(line_series)
        line_series.attachAxis(x_axis)
        line_series.attachAxis(y_axis)
        return line_series

    def _add_baseline_lines(
        self,
        chart,
        x_axis,
        y_axis,
        eic_time: np.ndarray,
        eic_intensity: np.ndarray,
        compound,
        scale_factor: float,
        prepared,
        channel_styles: Sequence[ChannelTraceStyle] | None = None,
    ):
        baseline_flag = getattr(compound, "baseline_correction", 0)
        if not baseline_flag:
            return

        logger.debug(f"Drawing baseline lines for {compound.compound_name}")

        l_boundary = compound.retention_time - compound.loffset
        r_boundary = compound.retention_time + compound.roffset
        mask = (eic_time > l_boundary) & (eic_time < r_boundary)

        display = prepared.display
        if display is not None and display.bundle.shows_model_overlays(
            independent_channels=getattr(compound, "is_unlabelled_target", False)
        ):
            drew_baseline = False
            baseline_intensity = prepared.baseline_intensity()
            draw_matrix = (
                baseline_intensity
                if baseline_intensity.ndim > 1
                else baseline_intensity.reshape(1, -1)
            )
            raw_matrix = np.asarray(eic_intensity, dtype=np.float64).reshape(
                draw_matrix.shape
            )
            # One failed ion sends every non-empty ion to raw in-window scans in integration.
            model_areas = display.bundle.uses_model_areas()
            for channel in display.bundle.channels:
                if channel.result.empty:
                    continue
                if not model_areas:
                    selected_trace = raw_matrix[channel.index]
                    trace_mask = mask
                else:
                    selected_trace = np.asarray(
                        draw_matrix[channel.index], dtype=np.float64
                    ).reshape(-1)
                    trace_mask = np.asarray(
                        channel.result.selected_mask, dtype=bool
                    ).reshape(-1)
                if not np.any(trace_mask):
                    continue
                baseline_result = compute_linear_baseline(
                    eic_time[trace_mask], selected_trace[trace_mask]
                )
                if baseline_result is None:
                    continue
                td_base, baseline_y = baseline_result
                baseline_y_scaled = (
                    baseline_y / scale_factor if scale_factor != 0 else baseline_y
                )
                style = self._style_at(
                    channel_styles,
                    channel.index,
                    multi_trace=eic_intensity.ndim > 1,
                )
                qcolor = style.color
                baseline_series = QLineSeries()
                baseline_series.append(td_base[0], baseline_y_scaled[0])
                baseline_series.append(td_base[-1], baseline_y_scaled[-1])
                baseline_pen = QPen(qcolor, 1.2)
                baseline_pen.setStyle(Qt.DashLine)
                baseline_series.setPen(baseline_pen)
                chart.addSeries(baseline_series)
                baseline_series.attachAxis(x_axis)
                baseline_series.attachAxis(y_axis)
                drew_baseline = True
            if drew_baseline:
                return

        if not np.any(mask):
            return

        td_win = eic_time[mask]
        draw_intensity = prepared.intensity
        multi_trace = draw_intensity.ndim > 1

        if multi_trace:
            for i, intensity_trace in enumerate(draw_intensity):
                idata_win = intensity_trace[mask]
                baseline_result = compute_linear_baseline(td_win, idata_win)
                if baseline_result is not None:
                    td_base, baseline_y = baseline_result
                    baseline_y_scaled = (
                        baseline_y / scale_factor if scale_factor != 0 else baseline_y
                    )

                    baseline_series = QLineSeries()
                    baseline_series.append(td_base[0], baseline_y_scaled[0])
                    baseline_series.append(td_base[-1], baseline_y_scaled[-1])

                    style = self._style_at(channel_styles, i, multi_trace=True)
                    baseline_pen = QPen(style.color, 1.2)
                    baseline_pen.setStyle(Qt.DashLine)
                    baseline_series.setPen(baseline_pen)
                    chart.addSeries(baseline_series)
                    baseline_series.attachAxis(x_axis)
                    baseline_series.attachAxis(y_axis)
        else:
            idata_win = draw_intensity[mask]
            baseline_result = compute_linear_baseline(td_win, idata_win)
            if baseline_result is not None:
                td_base, baseline_y = baseline_result
                baseline_y_scaled = (
                    baseline_y / scale_factor if scale_factor != 0 else baseline_y
                )

                baseline_series = QLineSeries()
                baseline_series.append(td_base[0], baseline_y_scaled[0])
                baseline_series.append(td_base[-1], baseline_y_scaled[-1])

                baseline_pen = QPen(dark_red_colour, 1.2)
                baseline_pen.setStyle(Qt.DashLine)
                baseline_series.setPen(baseline_pen)
                chart.addSeries(baseline_series)
                baseline_series.attachAxis(x_axis)
                baseline_series.attachAxis(y_axis)

    def _add_model_component_series(
        self,
        chart,
        x_axis,
        y_axis,
        model,
        component_index: int,
        *,
        multi_trace: bool,
        scale_factor: float,
        selected: bool,
        color_index: int | None = None,
        channel_styles: Sequence[ChannelTraceStyle] | None = None,
    ):
        """Draw one fitted component over the integration or fit window."""
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
            style = self._style_at(
                channel_styles, series_index, multi_trace=multi_trace
            )
            qcolor = style.color
            if selected:
                pen = QPen(QColor(qcolor), 2.2)
                pen.setStyle(style.line_style)
            else:
                overlay_color = QColor(qcolor)
                overlay_color.setAlpha(95)
                pen = QPen(overlay_color, 1.2)
                pen.setStyle(Qt.DotLine)

            scaled = row / scale_factor if scale_factor != 0 else row
            finite = np.isfinite(scaled)
            if not np.any(finite):
                continue
            series = QLineSeries()
            series.appendNp(
                np.ascontiguousarray(grid[finite], dtype=np.float64),
                np.ascontiguousarray(scaled[finite], dtype=np.float64),
            )
            series.setPen(pen)
            chart.addSeries(series)
            series.attachAxis(x_axis)
            series.attachAxis(y_axis)

    def _sample_identity(self, sample_name: str) -> IdentitySampleAssessment | None:
        if self._identity is None:
            return None
        try:
            return self._identity.for_sample(sample_name)
        except KeyError:
            return None

    def _channel_styles_for(self, compound, sample_name: str) -> tuple[ChannelTraceStyle, ...]:
        return channel_trace_styles(
            compound.analysis_channels,
            self._sample_identity(sample_name),
        )

    def _style_at(
        self,
        channel_styles: Sequence[ChannelTraceStyle] | None,
        index: int,
        *,
        multi_trace: bool,
    ) -> ChannelTraceStyle:
        if channel_styles is not None and 0 <= index < len(channel_styles):
            return channel_styles[index]
        if multi_trace:
            return ChannelTraceStyle(
                label_colors[index % len(label_colors)], Qt.SolidLine
            )
        return ChannelTraceStyle(dark_red_colour, Qt.SolidLine)

    def _plot_display_for(self, eic, compound):
        prepared = self._prepared_displays.pop(
            (eic.sample_name, eic.compound_name), None
        )
        if prepared is not None:
            return prepared
        return plot_display(
            eic.time,
            eic.intensity,
            compound,
            use_corrected=self.use_corrected,
        )

    def _add_eic_series(
        self,
        chart,
        x_axis,
        y_axis,
        eic_time: np.ndarray,
        eic_intensity: np.ndarray,
        compound,
        scale_factor: float,
        prepared,
        channel_styles: Sequence[ChannelTraceStyle] | None = None,
    ):
        display = prepared.display
        bundle = None if display is None else display.bundle
        draw_intensity = prepared.intensity

        if bundle is None or not bundle.shows_model_overlays(
            independent_channels=getattr(compound, "is_unlabelled_target", False)
        ):
            self._add_trace_series(
                chart,
                x_axis,
                y_axis,
                eic_time,
                draw_intensity,
                scale_factor,
                selected=False,
                raw_context=False,
                compound=compound,
                channel_styles=channel_styles,
            )
            return

        if not prepared.includes_raw_underlay:
            self._add_trace_series(
                chart,
                x_axis,
                y_axis,
                eic_time,
                eic_intensity,
                scale_factor,
                selected=False,
                raw_context=True,
                compound=compound,
                channel_styles=channel_styles,
            )
            self._add_trace_series(
                chart,
                x_axis,
                y_axis,
                eic_time,
                draw_intensity,
                scale_factor,
                selected=True,
                raw_context=False,
                compound=compound,
                channel_styles=channel_styles,
            )
            return

        multi_trace = eic_intensity.ndim > 1
        self._add_trace_series(
            chart,
            x_axis,
            y_axis,
            eic_time,
            eic_intensity,
            scale_factor,
            selected=False,
            raw_context=True,
            raw_is_evidence=all(
                channel.result.model is None and channel.result.empty
                for channel in bundle.channels
            ),
            compound=compound,
            channel_styles=channel_styles,
        )
        unfitted_indices: list[int] = []
        for channel in bundle.channels:
            model = channel.result.model
            if model is None:
                if not channel.result.empty:
                    unfitted_indices.append(channel.index)
                continue
            self._add_model_component_series(
                chart,
                x_axis,
                y_axis,
                model,
                model.selected_index,
                multi_trace=multi_trace,
                scale_factor=scale_factor,
                selected=True,
                color_index=channel.index,
                channel_styles=channel_styles,
            )
            for component_index in range(model.n_components):
                if component_index == model.selected_index:
                    continue
                self._add_model_component_series(
                    chart,
                    x_axis,
                    y_axis,
                    model,
                    component_index,
                    multi_trace=multi_trace,
                    scale_factor=scale_factor,
                    selected=False,
                    color_index=channel.index,
                    channel_styles=channel_styles,
                )
        if unfitted_indices:
            self._add_trace_series(
                chart,
                x_axis,
                y_axis,
                eic_time,
                eic_intensity,
                scale_factor,
                selected=True,
                raw_context=False,
                compound=compound,
                channel_styles=channel_styles,
                channel_indices=tuple(unfitted_indices),
            )

    def _add_trace_series(
        self,
        chart,
        x_axis,
        y_axis,
        eic_time: np.ndarray,
        eic_intensity: np.ndarray,
        scale_factor: float,
        *,
        selected: bool,
        raw_context: bool,
        raw_is_evidence: bool = False,
        selected_mask: np.ndarray | None = None,
        compound=None,
        channel_styles: Sequence[ChannelTraceStyle] | None = None,
        channel_indices: tuple[int, ...] | None = None,
    ):
        matrix = eic_intensity if eic_intensity.ndim > 1 else eic_intensity.reshape(1, -1)
        mask_matrix = None
        if selected_mask is not None:
            mask_matrix = (
                selected_mask
                if selected_mask.ndim > 1
                else selected_mask.reshape(1, -1)
            )

        multi_trace = eic_intensity.ndim > 1
        for i, trace in enumerate(matrix):
            if channel_indices is not None and i not in channel_indices:
                continue
            if multi_trace:
                style = self._style_at(channel_styles, i, multi_trace=True)
                qcolor = style.color
                line_style = style.line_style
            else:
                qcolor = dark_red_colour
                line_style = Qt.SolidLine
            pen_color = QColor(qcolor)
            if raw_is_evidence:
                # Nothing was fitted, so the raw trace is what the reviewer inspects.
                pen_color.setAlpha(190)
                width = 1.5
            elif raw_context:
                pen_color.setAlpha(75)
                width = 1.0
            else:
                width = 2.2 if selected else 2.0

            pen = QPen(pen_color, width)
            pen.setStyle(line_style)
            series = QLineSeries()
            scaled_trace = trace / scale_factor if scale_factor != 0 else trace
            keep = np.isfinite(scaled_trace)
            if mask_matrix is not None:
                keep &= np.asarray(mask_matrix[i, :], dtype=bool)
            if np.any(keep):
                xs = np.ascontiguousarray(eic_time[keep], dtype=np.float64)
                ys = np.ascontiguousarray(scaled_trace[keep], dtype=np.float64)
                series.appendNp(
                    np.ascontiguousarray(xs, dtype=np.float64),
                    np.ascontiguousarray(ys, dtype=np.float64),
                )
            series.setPen(pen)
            if (
                not raw_context
                and multi_trace
                and has_defined_channel(compound, i)
            ):
                series.setName(channel_legend_label(compound, i))
            chart.addSeries(series)
            series.attachAxis(x_axis)
            series.attachAxis(y_axis)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_header()
        self._resize_timer.start(60)

    def minimumSizeHint(self) -> QSize:
        # The header folds its scale toggles (see _fit_header), so only the grid's two columns bound the width.
        return QSize(self.minimumWidth(), super().minimumSizeHint().height())

    def _fit_header(self) -> None:
        """The two scale toggles while the header row fits them whole, else the Scale menu."""
        row = self._header_row
        folding = (self.selection_summary, self._view_controls, self._scale_menu)
        shown = [
            widget
            for widget in (row.itemAt(i).widget() for i in range(row.count()))
            if widget is not None and widget not in folding and not widget.isHidden()
        ]
        margins = row.contentsMargins()
        # Room for a whole selection line at any count, so it never elides or moves them.
        summary = self.selection_summary.fontMetrics().horizontalAdvance(
            "tR 00.00 · 000 of 000 selected"
        )
        need = (
            margins.left()
            + margins.right()
            + sum(widget.sizeHint().width() for widget in shown)
            + self._view_controls.sizeHint().width()
            + summary
            + row.spacing() * (len(shown) + 1)
        )
        wide = need <= self.width()
        self._view_controls.setVisible(wide)
        self._scale_menu.setVisible(not wide)

    def _sync_scale_menu(self, *_args) -> None:
        """The menu mirrors the toggles; its button names the one that is on."""
        for action, button in self._scale_choices:
            action.setVisible(not button.isHidden())
            action.setEnabled(button.isEnabled())
            action.setChecked(button.isChecked())
            action.setToolTip(button.toolTip())
        active = next((b.text() for _a, b in self._scale_choices if b.isChecked()), None)
        self.scale_menu_button.setText(active or "Scale")
        self.scale_menu_button.setChecked(active is not None)
        self.scale_menu_button.setToolTip(
            f"Plot y-scale: {active or 'each plot to its own range'}"
        )

    def _update_graph_sizes(self) -> None:
        self._place_tiles()
        # Invalidate first, then activate to force recalculation
        self._layout.invalidate()
        self._layout.activate()
        self._layout.update()

        parent = self.parent()
        if parent:
            parent.updateGeometry()
            parent.update()

    def _apply_validation_styling(self, container: QWidget, verdict: PeakVerdict):
        container.verdict = verdict
        self._restyle_container(container)

    def _restyle_container(self, container: QWidget):
        verdict = getattr(container, "verdict", PeakVerdict.PASS)
        sample_name = getattr(container.chart_view, "sample_name", "")
        identity = self._sample_identity(sample_name)
        container.set_badges(tile_badges(verdict, identity))

    def _clear_layout(self, force_destroy: bool = False) -> None:
        if not self._layout:
            return

        if force_destroy:
            self._current_plots.clear()
            self._selected_plots.clear()

            while self._layout.count():
                item = self._layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()

            for container in self._container_pool:
                if container and container.parent():
                    container.setParent(None)
                container.deleteLater()

            self._container_pool.clear()
            self._available_containers.clear()
            self._max_rows_seen = 0
            self._max_cols_seen = 0
        else:
            self._return_containers_to_pool()
            while self._layout.count():
                item = self._layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    # Pooled containers stay (hidden) in the grid host: re-parenting
                    # them would re-polish every card on the next show.
                    if widget not in self._container_pool:
                        widget.deleteLater()

        # Recreating the layout causes a crash because the old layout
        # remains associated with the widget in ways that deleteLater()
        # doesn't handle immediately during the plot cycle.
        max_rows_to_reset = max(self._max_rows_seen, self._layout.rowCount())
        max_cols_to_reset = max(self._max_cols_seen, self._layout.columnCount())

        for i in range(max_cols_to_reset):
            self._layout.setColumnStretch(i, 0)
            self._layout.setColumnMinimumWidth(i, 0)
        for i in range(max_rows_to_reset):
            self._layout.setRowStretch(i, 0)
            self._layout.setRowMinimumHeight(i, 0)

        self.updateGeometry()
        self.update()
