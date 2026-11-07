from typing import List

import numpy as np
from PySide6.QtCharts import (
    QAbstractBarSeries,
    QBarCategoryAxis,
    QBarSet,
    QChart,
    QChartView,
    QHorizontalBarSeries,
    QHorizontalStackedBarSeries,
    QValueAxis,
)
from PySide6.QtCore import QEvent, QMargins, QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from manic.models.analysis import IonRole
from manic.ui.channel_chips import ChannelChipRow, identity_key_chips
from manic.ui.chart_header import HeaderName
from manic.ui.chart_style import (
    AXIS_LABEL_PX,
    BarRows,
    abundance_scale,
    bar_row_at,
    fit_category_names,
    scale_text,
    set_nice_ticks,
    style_axis,
    style_chart,
    text_style,
    ui_font,
)
from manic.ui.colors import (
    QUALIFIER_GREEN,
    QUALIFIER_GREY,
    QUALIFIER_RED,
    ChannelTraceStyle,
    label_colors,
)
from manic.ui.identity_chart import (
    STATUS_MARKS,
    IdentityGridBinding,
    add_identity_grid,
    identity_cell_tooltip,
    identity_chart_height,
    identity_cells,
    identity_column_headers,
    identity_unassessed_note,
)
from manic.ui.theme import FONT_SIZE_TITLE, color
from manic.ui import theme
from manic.validation.unlabelled_identity import IdentityAssessmentSet, QualifierStatus

# Every sample gets this much height so its name is never elided.
ROW_HEIGHT = 26
# Sample names, bar-end values and the value axis: a step above the summary panel's 10 px.
VALUE_PX = 12
# The chart margins above and below the rows; the axis text is pinned outside.
_AXIS_SPACE = 16


def identity_status_counts(identity: IdentityAssessmentSet) -> dict[str, int]:
    """Qualifier cells per key entry: Validated, Failed, and everything else."""
    counts = {"Validated": 0, "Failed": 0, "Not assessed": 0}
    for sample in identity.samples:
        for qualifier in identity_cells(sample):
            if qualifier.status is QualifierStatus.VALIDATED:
                counts["Validated"] += 1
            elif qualifier.status is QualifierStatus.FAILED:
                counts["Failed"] += 1
            else:
                counts["Not assessed"] += 1
    return counts


def identity_key_html(identity: IdentityAssessmentSet, *, swatches: bool = True) -> str:
    """Each state's colour, cell mark, name and count, for a chart with no QC key nearby.

    Without ``swatches`` it is a tally beside the grid's QC key, which already names the
    states: each mark that occurs and its count ("✓ 16  ✕ 2  ? 4").
    """
    counts = identity_status_counts(identity)
    present = {q.status for sample in identity.samples for q in identity_cells(sample)}
    # Every grey cell's mark, so the key accounts for each mark in the grid.
    grey_marks = " ".join(
        mark for status, mark in STATUS_MARKS.items()
        if status in present
        and status not in (QualifierStatus.VALIDATED, QualifierStatus.FAILED)
    )
    parts = []
    for qcolor, mark, name in (
        (QUALIFIER_GREEN, STATUS_MARKS[QualifierStatus.VALIDATED], "Validated"),
        (QUALIFIER_RED, STATUS_MARKS[QualifierStatus.FAILED], "Failed"),
        (QUALIFIER_GREY, grey_marks, "Not assessed"),
    ):
        mark = f"{mark.replace(' ', '&nbsp;')}&nbsp;" if mark else ""
        if swatches:
            swatch = f'<span style="color:{qcolor.name()};">&#9632;</span>&nbsp;'
            parts.append(f"{swatch}{mark}{name}&nbsp;<b>{counts[name]}</b>")
        elif counts[name]:
            parts.append(f"{mark}<b>{counts[name]}</b>")
    # Counts are cells, not samples; the unit leads so it is read first.
    unit, gap = ("Qualifier cells&nbsp;", " ") if swatches else ("Qualifier cells", "&nbsp;&nbsp; ")
    # Each entry stays whole, so a narrow key wraps between entries.
    return gap.join(f'<span style="white-space:nowrap">{part}</span>' for part in (unit, *parts))


IDENTITY_KEY_TOOLTIP = "Counts are qualifier cells: one per sample for each qualifier ion."


def missing_ratio_note(sample_name: str) -> str:
    """Hover text for a label-incorporation row with no bar."""
    return f"{sample_name}\nNo ratio: this sample has no integrated peak area for this compound."


def bar_value_text(value: float, *, precise: bool = False) -> str:
    """A bar's value in the axis unit: '0.91', '<0.01', '0', or '—' for no data.

    ``precise`` gives four significant figures, for the row being read.
    """
    if not np.isfinite(value):
        return "—"
    if value == 0:
        return "0"
    if precise:
        return f"{value:.4g}"
    if abs(value) < 0.005:
        return "<0.01"
    return f"{value:.2f}"


def percent_text(ratio: float) -> str:
    """'18.1%', '<0.1%' for a trace, '0%'; padded with figure spaces to one width."""
    percent = ratio * 100
    text = "0%" if percent == 0 else "<0.1%" if percent < 0.05 else f"{percent:.1f}%"
    return text.rjust(6, "\u2007")


def category_rect(chart: QChart, category: int) -> QRectF:
    """One category's row across the plot, in chart coordinates."""
    series = chart.series()[0]
    top = chart.mapToPosition(QPointF(0, category + 0.5), series).y()
    bottom = chart.mapToPosition(QPointF(0, category - 0.5), series).y()
    return QRectF(2, top, chart.plotArea().right() - 2, bottom - top)


def value_axis_ticks(axis: QValueAxis) -> list[tuple[float, str]]:
    """The (value, text) of each tick ``axis`` would label."""
    low, high = axis.min(), axis.max()
    if axis.tickType() == QValueAxis.TicksDynamic:
        values = np.arange(axis.tickAnchor(), high + axis.tickInterval() / 1e6, axis.tickInterval())
    else:
        values = np.linspace(low, high, axis.tickCount())
    return [(float(v), axis.labelFormat() % v) for v in values if low <= v <= high + 1e-9]


class PinnedAxis(QWidget):
    """A chart's top axis text, kept above the scroll area its rows move in.

    Each tick is drawn at the x its value maps to in ``view``'s chart, so the
    labels stay over their gridlines however far the rows are scrolled.
    """

    def __init__(self, view: QChartView, parent=None, *, font_px: int = AXIS_LABEL_PX):
        super().__init__(parent)
        self._view = view
        self._title = ""
        self._ticks: list[tuple[float, str]] = []
        self._font = ui_font(font_px)
        self._title_font = ui_font(11)
        view.chart().plotAreaChanged.connect(self.update)
        self.hide()

    def set_axis(self, title: str, ticks: list[tuple[float, str]]) -> None:
        self._title = title
        self._ticks = list(ticks)
        lines = max((text.count("\n") + 1 for _value, text in ticks), default=1)
        height = QFontMetrics(self._font).height() * lines + 4
        if title:
            height += QFontMetrics(self._title_font).height() + 2
        self.setFixedHeight(height)
        self.setVisible(bool(ticks))
        self.update()

    def title(self) -> str:
        return self._title

    def _x(self, value: float) -> int:
        chart = self._view.chart()
        point = chart.mapToScene(chart.mapToPosition(QPointF(value, 0), chart.series()[0]))
        window = self.window()
        return self.mapFrom(window, self._view.mapTo(window, self._view.mapFromScene(point))).x()

    def tick_positions(self) -> list[tuple[str, int]]:
        if not self._view.chart().series():
            return []
        return [(text, self._x(value)) for value, text in self._ticks]

    def paintEvent(self, _event) -> None:
        ticks = self.tick_positions()
        if not ticks:
            return
        painter = QPainter(self)
        painter.setPen(color("text_secondary"))
        y = 0
        if self._title:
            painter.setFont(self._title_font)
            line = QFontMetrics(self._title_font).height()
            left, right = ticks[0][1], ticks[-1][1]
            painter.drawText(QRect(left, 0, max(right - left, 1), line), Qt.AlignCenter, self._title)
            y = line + 2
        painter.setFont(self._font)
        metrics = QFontMetrics(self._font)
        for text, x in ticks:
            for number, line in enumerate(text.split("\n")):
                width = metrics.horizontalAdvance(line)
                left = min(max(x - width // 2, 0), self.width() - width)
                painter.drawText(QPoint(left, y + number * metrics.height() + metrics.ascent()), line)


class _BackedText(QGraphicsSimpleTextItem):
    """Text on a panel-coloured patch, so a gridline never strikes through it."""

    def paint(self, painter, option, widget=None):
        painter.fillRect(self.boundingRect(), color("surface"))
        super().paint(painter, option, widget)


class ChartPopupDialog(QDialog):
    """Modal dialog showing an enlarged version of toolbar charts with sample names visible.

    ``data`` and ``sample_names`` run bottom to top, as the summary panel's charts
    draw them, so every popup reads top-down in grid order. Clicking a sample
    row, or Enter on the row picked with the arrow keys, emits
    ``sample_activated`` and closes the popup, once something listens.
    """

    sample_activated = Signal(str)
    # A documentation link from the note, "file.md#section"; the popup closes first.
    guide_requested = Signal(str)

    def __init__(
        self,
        chart_type: str,
        title: str,
        data,
        sample_names: List[str],
        parent=None,
        *,
        hover_notes: list[str] | None = None,
        identity: IdentityAssessmentSet | None = None,
        compound_name: str = "",
        highlighted=(),
        quantity: str = "",
    ):
        super().__init__(parent)
        self.chart_type = chart_type
        self.data = data
        self.sample_names = sample_names
        self.hover_notes = hover_notes
        self._identity = identity
        # What the abundance bars measure, such as "Q-ion peak area".
        self._quantity = quantity
        # The grid's selected samples, filled in the accent as in the summary panel.
        self._highlighted = set(highlighted)

        # The ion key's (labels, styles); with a current row it reads that row's shares.
        self._ratio_key: tuple[list[str], list[ChannelTraceStyle]] | None = None
        self._hover_notes: list[str] | None = None
        self._identity_binding: IdentityGridBinding | None = None
        self._value_labels: list[tuple[QGraphicsSimpleTextItem, float, int]] = []
        self._current_row: int | None = None
        # Tooltip for each row that has nothing drawn, by category index.
        self._row_notes: dict[int, str] = {}

        self.setWindowTitle(f"{title} — MANIC")
        self.setModal(True)
        # exec() then deletes the popup as it returns. Left to Python, its row callbacks keep it
        # in a reference cycle the garbage collector clears while the dialog is still alive.
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Set window icon (same as main window)
        self._set_window_icon(parent)

        self._setup_ui(title, compound_name or (identity.compound_name if identity else ""))
        self._populate_chart()
        name_axis = self._name_axis()
        # Full names bottom to top, as the name axis holds them before _fit_names shortens them.
        self._category_names: list[str] = name_axis.categories() if name_axis is not None else []
        self._fit_to_rows()
        self._row_marker = QGraphicsRectItem(self.chart)
        self._row_marker.setBrush(Qt.NoBrush)
        self._row_marker.setZValue(100)
        self._row_marker.hide()
        self.chart.plotAreaChanged.connect(self._place_row_marker)
        self._rows = BarRows(
            self.chart,
            self.chart_view,
            lambda category: self.activate_row(len(self._category_names) - 1 - category),
            self._tip,
        )
        self.chart_view.viewport().installEventFilter(self)
        # Whichever of these has focus, the row keys still reach the rows.
        self._scroll.installEventFilter(self)
        self.chart_view.installEventFilter(self)

    @classmethod
    def for_identity(
        cls,
        identity: IdentityAssessmentSet,
        *,
        parent=None,
    ) -> "ChartPopupDialog":
        return cls(
            chart_type="identity",
            title="Identity",
            data=None,
            sample_names=[sample.sample_name for sample in identity.samples],
            parent=parent,
            identity=identity,
        )

    def _set_window_icon(self, parent_widget):
        """Set window icon by finding the main window."""
        # Walk up the parent hierarchy to find the main window
        widget = parent_widget
        while widget and widget.parent():
            widget = widget.parent()
            if hasattr(widget, '_get_logo_path'):
                logo_path = widget._get_logo_path()
                if logo_path:
                    from PySide6.QtGui import QIcon
                    self.setWindowIcon(QIcon(logo_path))
                break

    def _setup_ui(self, title: str, compound_name: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.compound_title = HeaderName(compound_name or title, min_chars=12)
        theme.style(self.compound_title, text_style("text", FONT_SIZE_TITLE, 600))
        count = len(self.sample_names)
        # An abundance popup's axis title already names its quantity.
        subtitle = title if compound_name and not self._quantity else ""
        subtitle = " · ".join(
            part for part in (subtitle, f"{count} sample{'s' if count != 1 else ''}") if part
        )
        self.subtitle = QLabel(subtitle)
        theme.style(self.subtitle, text_style("text_secondary", 12))
        header = QVBoxLayout()
        header.setSpacing(2)
        header.addWidget(self.compound_title)
        header.addWidget(self.subtitle)
        layout.addLayout(header)

        self.ion_legend = ChannelChipRow()
        layout.addWidget(self.ion_legend)

        self.chart = QChart()
        style_chart(self.chart, QMargins(8, 4, 16, 4))
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setFrameShape(QFrame.NoFrame)
        self.chart_view.setStyleSheet("QChartView { background: transparent; }")
        self.chart_view.setFocusPolicy(Qt.StrongFocus)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFocusPolicy(Qt.NoFocus)
        self._scroll.setWidget(self.chart_view)
        theme.style(
            self._scroll,
            "QScrollArea { background: @surface; border: 1px solid @border; border-radius: 8px; }",
        )
        self.pinned_axis = PinnedAxis(
            self.chart_view, font_px=11 if self.chart_type == "identity" else VALUE_PX
        )
        # Tight to the rows it labels, not a layout gap away.
        rows = QVBoxLayout()
        rows.setSpacing(2)
        rows.addWidget(self.pinned_axis)
        rows.addWidget(self._scroll, stretch=1)
        layout.addLayout(rows, stretch=1)
        self.empty_note = QLabel()
        self.empty_note.setWordWrap(True)
        self.empty_note.setTextFormat(Qt.RichText)
        self.empty_note.linkActivated.connect(self._open_guide)
        theme.style(self.empty_note, text_style("text_secondary", 13))
        self.empty_note.hide()
        layout.addWidget(self.empty_note)

        self.status_legend = QLabel("")
        self.status_legend.setTextFormat(Qt.RichText)
        theme.style(self.status_legend, text_style("text_secondary", 12))
        self.status_legend.hide()

        footer = QHBoxLayout()
        footer.addWidget(self.status_legend)
        footer.addStretch()
        hover = "Hover a cell for details" if self.chart_type == "identity" else ""
        self._hint = QLabel(hover)
        self._hover_hint = hover
        theme.style(self._hint, text_style("text_tertiary", 11))
        footer.addWidget(self._hint)
        close_button = QPushButton("Close")
        close_button.setAutoDefault(False)
        close_button.clicked.connect(self.accept)
        footer.addWidget(close_button)
        layout.addLayout(footer)

    def _fit_to_rows(self) -> None:
        rows = max(len(self.sample_names), 1)
        # Fixed, top-aligned: a short list keeps slim rows instead of slabs.
        self.chart_view.setFixedHeight(
            identity_chart_height(rows) if self.chart_type == "identity"
            else rows * ROW_HEIGHT + _AXIS_SPACE
        )
        self._scroll.setAlignment(Qt.AlignTop)
        screen = self.screen() or QApplication.primaryScreen()
        max_height = int(screen.availableGeometry().height() * 0.85) if screen else 900
        chrome = 150 + (30 if self.ion_legend.isVisibleTo(self) else 0)
        chrome += self.pinned_axis.height() if self.pinned_axis.isVisibleTo(self) else 0
        if self.empty_note.isVisibleTo(self):
            self.resize(640, 200)
            return
        self.resize(820, min(max_height, self.chart_view.height() + chrome))

    def _populate_chart(self):
        """Populate chart based on type and data."""
        if self.chart_type == "total_abundance":
            self._create_total_abundance_chart()
        elif self.chart_type == "isotopologue_ratios":
            self._create_isotopologue_chart()
        elif self.chart_type == "identity":
            self._create_identity_chart()

    def _create_total_abundance_chart(self):
        """Create enlarged total abundance chart with sample names on Y-axis."""
        if self.data is None or len(self.data) == 0:
            return

        bar_series = QHorizontalBarSeries()
        bar_series.setBarWidth(0.7)

        bar_set = QBarSet("Total Abundance")
        bar_set.setColor(color("text_tertiary"))
        bar_set.setPen(QPen(Qt.NoPen))

        max_abundance, scale_exp = abundance_scale(self.data)
        scale_factor = 10**scale_exp
        scaled = [float(abundance) / scale_factor for abundance in self.data]
        for value in scaled:
            bar_set.append(value if np.isfinite(value) else 0.0)
        bar_set.selectBars([i for i, name in enumerate(self.sample_names) if name in self._highlighted])
        self._abundance_bars = bar_set
        self._recolour_selection()
        theme.notifier.changed.connect(self._recolour_selection)

        # The row under the pointer or picked with the arrow keys reads at four
        # significant figures (see _refresh_value_labels), so no value tooltip.
        bar_series.append(bar_set)
        self.chart.addSeries(bar_series)

        # Setup axes with sample names visible
        self._setup_total_abundance_axes(max_abundance, scale_exp, scale_factor)

        # Attach series to axes
        bar_series.attachAxis(self.chart.axes(Qt.Horizontal)[0])
        bar_series.attachAxis(self.chart.axes(Qt.Vertical)[0])
        self._add_value_labels(bar_series, list(enumerate(scaled)))

    def _recolour_selection(self, *_args) -> None:
        # A scheme switch remaps bar colours, but not the selected colour.
        self._abundance_bars.setSelectedColor(color("accent"))

    def _add_value_labels(
        self, series: QAbstractBarSeries, values: list[tuple[int, float]]
    ) -> None:
        """Text past the bar end of each (category, value). QtCharts' own labels can only print raw numbers."""
        for index, value in values:
            item = _BackedText(bar_value_text(value), self.chart)
            item.setFont(ui_font(VALUE_PX))
            # Above QtCharts' gridlines, which sit over plain chart children.
            item.setZValue(50)
            self._value_labels.append((item, value, index))
        self._value_series = series
        self._refresh_value_labels()
        self.chart.plotAreaChanged.connect(self._place_value_labels)
        theme.notifier.changed.connect(self._refresh_value_labels)
        self._place_value_labels()

    def _refresh_value_labels(self, *_args) -> None:
        """Compact values, except the current row's, which reads in full in the text colour."""
        current = None if self._current_row is None else len(self.sample_names) - 1 - self._current_row
        for item, value, index in self._value_labels:
            item.setText(bar_value_text(value, precise=index == current))
            item.setBrush(color("text" if index == current else "text_secondary"))
            item.update()

    def _place_value_labels(self, *_args) -> None:
        for item, value, index in self._value_labels:
            end = self.chart.mapToPosition(QPointF(value if value > 0 else 0.0, index), self._value_series)
            height = item.boundingRect().height()
            item.setPos(end.x() + 4, end.y() - height / 2)

    def _create_isotopologue_chart(self):
        """Create enlarged isotopologue chart with sample names on Y-axis."""
        if self.data is None or len(self.data) == 0:
            return

        stacked_series = QHorizontalStackedBarSeries()
        stacked_series.setBarWidth(0.7)

        # Get number of isotopologues
        num_isotopologues = self.data.shape[1] if len(self.data.shape) > 1 else 1

        labels = []
        styles = []
        for i in range(num_isotopologues):
            bar_set = QBarSet(f"M+{i}")
            bar_colour = label_colors[i % len(label_colors)]
            bar_set.setColor(bar_colour)
            bar_set.setBorderColor(color("surface"))
            labels.append(bar_set.label())
            styles.append(ChannelTraceStyle(bar_colour, Qt.SolidLine))

            # Add ratio values for this isotopologue across all samples
            for sample_idx in range(len(self.sample_names)):
                if len(self.data.shape) > 1:
                    ratio = self.data[sample_idx, i]
                else:
                    ratio = 1.0 if i == 0 else 0.0  # Single trace case
                bar_set.append(ratio)
            stacked_series.append(bar_set)

        self.chart.addSeries(stacked_series)

        # Setup axes
        self._setup_isotopologue_axes()

        if num_isotopologues > 1:
            self._ratio_key = (labels, styles)
            self._refresh_ratio_key()

        # Attach series to axes
        stacked_series.attachAxis(self.chart.axes(Qt.Horizontal)[0])
        stacked_series.attachAxis(self.chart.axes(Qt.Vertical)[0])

        # A row with no ratio would otherwise be blank, with no bar to hover.
        totals = np.nansum(self.data, axis=1) if self.data.ndim > 1 else np.ones(len(self.data))
        empty = [index for index, total in enumerate(totals) if not total > 0]
        for index in empty:
            self._row_notes[index] = missing_ratio_note(self.sample_names[index])
        if empty:
            self._add_value_labels(stacked_series, [(index, np.nan) for index in empty])

    def _create_identity_chart(self):
        if self._identity is None or not self._identity.samples:
            return

        note = identity_unassessed_note(self._identity)
        if note is not None:
            # With no grid, the chips name what each qualifier is missing.
            self.ion_legend.set_channels(*identity_key_chips(self._identity.channels))
            self.empty_note.setText(note)
            self.empty_note.show()
            self._scroll.hide()
            self._hover_hint = ""
            self._hint.clear()
            return
        quantifier = next(
            (c.label for c in self._identity.channels if c.role is IonRole.QUANTIFIER), ""
        )
        count = len(self.sample_names)
        self.subtitle.setText(
            " · ".join(p for p in ("Identity", quantifier, f"{count} sample{'s' if count != 1 else ''}") if p)
        )
        self._identity_binding = add_identity_grid(
            self.chart, self._identity.samples, label_font_size=11
        )
        self.pinned_axis.set_axis("", identity_column_headers(self._identity.channels))
        self.status_legend.setText(identity_key_html(self._identity))
        self.status_legend.setToolTip(IDENTITY_KEY_TOOLTIP)
        self.status_legend.show()

    def _sample_axis(self, names: list[str]) -> QBarCategoryAxis:
        axis = QBarCategoryAxis()
        axis.append(names)
        style_axis(axis)
        axis.setLabelsFont(ui_font(VALUE_PX))
        axis.setLabelsColor(color("text"))
        axis.setLineVisible(False)
        # Long names are shortened in the middle instead (see _fit_names).
        axis.setTruncateLabels(False)
        return axis

    def _setup_total_abundance_axes(self, max_abundance: float, scale_exp: int, scale_factor: float):
        """Setup axes for total abundance chart."""
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)

        x_axis = QValueAxis()
        scaled_max = max_abundance / scale_factor
        # Extra room past the longest bar for its value label.
        x_axis.setRange(0, scaled_max * 1.15)
        style_axis(x_axis, grid=True)
        set_nice_ticks(x_axis, 0, scaled_max * 1.15, max_ticks=4)
        y_axis = self._sample_axis(list(self.sample_names))

        self.chart.addAxis(x_axis, Qt.AlignTop)
        self.chart.addAxis(y_axis, Qt.AlignLeft)
        scale = scale_text(scale_exp)
        title = scale
        if self._quantity:
            title = f"{self._quantity} ({scale})" if scale else self._quantity
        self._pin_value_axis(x_axis, title)

    def _pin_value_axis(self, axis: QValueAxis, title: str) -> None:
        """Gridlines stay in the scrolled chart; the tick text and unit move above it."""
        axis.setLabelsVisible(False)
        axis.setLineVisible(False)
        self.pinned_axis.set_axis(title, value_axis_ticks(axis))

    def _setup_isotopologue_axes(self):
        """Setup axes for isotopologue chart."""
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)

        x_axis = QValueAxis()
        x_axis.setRange(0, 1.0)
        x_axis.setLabelFormat("%.1f")
        style_axis(x_axis, grid=True)
        x_axis.setTickCount(6)

        y_axis = self._sample_axis(list(self.sample_names))

        self.chart.addAxis(x_axis, Qt.AlignTop)
        self.chart.addAxis(y_axis, Qt.AlignLeft)
        self._pin_value_axis(x_axis, "Isotopologue ratio")

    def _name_axis(self) -> QBarCategoryAxis | None:
        return next(
            (a for a in self.chart.axes(Qt.Vertical) if isinstance(a, QBarCategoryAxis)), None
        )

    def row_names(self) -> list[str]:
        """Full sample names top to bottom, as the rows read."""
        return list(reversed(self._category_names))

    def _fit_names(self) -> None:
        axis = self._name_axis()
        if axis is not None:
            fit_category_names(axis, self._category_names, self.chart_view.width())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.row_names():
            rows = "↑↓ to choose · Return or click to select its plot"
            self._hint.setText(" · ".join(p for p in (self._hover_hint, rows) if p))
            self.chart_view.viewport().setCursor(Qt.PointingHandCursor)
            self.chart_view.setFocus(Qt.OtherFocusReason)

    def _row_at(self, viewport_pos) -> int | None:
        category = bar_row_at(self.chart, self.chart_view, viewport_pos)
        return None if category is None else len(self.row_names()) - 1 - category

    def set_current_row(self, row: int | None) -> None:
        self._current_row = row
        self._place_row_marker()
        self._refresh_value_labels()
        self._refresh_ratio_key()

    def _refresh_ratio_key(self) -> None:
        """Each isotopologue chip gives the current row's percentage, as its bar shows."""
        if self._ratio_key is None:
            return
        labels, styles = self._ratio_key
        if self._current_row is not None:
            ratios = self.data[len(self.sample_names) - 1 - self._current_row]
            if np.nansum(ratios) > 0:
                labels = [f"{label}  {percent_text(ratio)}" for label, ratio in zip(labels, ratios)]
        self.ion_legend.set_channels(labels, styles)

    def _place_row_marker(self, *_args) -> None:
        if self._current_row is None or not self.chart.series():
            self._row_marker.hide()
            return
        rect = category_rect(self.chart, len(self.row_names()) - 1 - self._current_row)
        self._row_marker.setRect(rect)
        self._row_marker.setPen(QPen(color("accent"), 1.5))
        self._row_marker.show()
        centre = self.chart_view.mapFromScene(self._row_marker.sceneBoundingRect().center())
        self._scroll.ensureVisible(centre.x(), centre.y(), 0, int(rect.height()))

    def row_tip(self, row: int) -> str | None:
        """A row's tooltip (top to bottom): why it has nothing drawn, or its shortened name in full."""
        category = len(self._category_names) - 1 - row
        if category in self._row_notes:
            return self._row_notes[category]
        name = self._category_names[category]
        return name if self._name_axis().categories()[category] != name else None

    def _tip(self, category: int, value: QPointF) -> str | None:
        """Over an identity cell its detail; elsewhere on the row, its row tip."""
        cell = self._identity_binding.cell_at(value) if self._identity_binding else None
        if cell is not None:
            return identity_cell_tooltip(cell)
        return self.row_tip(len(self._category_names) - 1 - category)

    def _choose_row(self, row: int) -> None:
        """Make a row the keys picked current, with its tip shown at its name."""
        self.set_current_row(row)
        rect = self._row_marker.sceneBoundingRect()
        self._rows.refresh(self.chart_view.mapFromScene(rect.left(), rect.center().y()))

    def _open_guide(self, href: str) -> None:
        self.accept()
        self.guide_requested.emit(href)

    def activate_row(self, row: int) -> None:
        names = self.row_names()
        if not 0 <= row < len(names):
            return
        self.sample_activated.emit(names[row])
        self.accept()

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.KeyPress and obj in (self._scroll, self.chart_view):
            return self._row_key(event.key())
        if obj is self.chart_view and event.type() == QEvent.Resize:
            self._fit_names()
        if obj is self.chart_view.viewport() and event.type() == QEvent.MouseMove:
            row = self._row_at(event.position().toPoint())
            if row is not None and row != self._current_row:
                self.set_current_row(row)
        return super().eventFilter(obj, event)

    def _row_key(self, key: int) -> bool:
        """Move or activate the current row; False for a key rows do not use."""
        rows = len(self.row_names())
        if not rows:
            return False
        current = self._current_row
        if key in (Qt.Key_Down, Qt.Key_Up):
            step = 1 if key == Qt.Key_Down else -1
            start = -1 if step == 1 else rows
            self._choose_row(min(max((start if current is None else current) + step, 0), rows - 1))
        elif key in (Qt.Key_Home, Qt.Key_End):
            self._choose_row(0 if key == Qt.Key_Home else rows - 1)
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            # The first press shows which row Return would open.
            if current is None:
                self._choose_row(0)
            else:
                self.activate_row(current)
        else:
            return False
        return True

    def keyPressEvent(self, event) -> None:
        if not self._row_key(event.key()):
            super().keyPressEvent(event)
