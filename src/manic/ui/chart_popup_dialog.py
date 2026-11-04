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
from PySide6.QtCore import QEvent, QMargins, QMetaMethod, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QCursor, QPainter, QPen
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
    QToolTip,
    QVBoxLayout,
)

from manic.ui.channel_chips import ChannelChipRow, identity_key_chips
from manic.ui.chart_style import (
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
    abundance_colour,
    label_colors,
)
from manic.ui.identity_chart import (
    IdentityGridBinding,
    add_identity_grid,
    identity_cell_tooltip,
    show_identity_tooltip,
)
from manic.ui.theme import FONT_SIZE_TITLE, color
from manic.ui import theme
from manic.validation.unlabelled_identity import IdentityAssessmentSet, QualifierStatus

# Every sample gets this much height so its name is never elided.
ROW_HEIGHT = 22
# Room for the value axis, its title and the chart margins.
_AXIS_SPACE = 64


def identity_status_counts(identity: IdentityAssessmentSet) -> dict[str, int]:
    """Qualifier cells per key entry: Validated, Failed, and everything else."""
    counts = {"Validated": 0, "Failed": 0, "No verdict": 0}
    for sample in identity.samples:
        for qualifier in sample.qualifiers:
            if qualifier.status is QualifierStatus.VALIDATED:
                counts["Validated"] += 1
            elif qualifier.status is QualifierStatus.FAILED:
                counts["Failed"] += 1
            else:
                counts["No verdict"] += 1
    return counts


def identity_key_html(identity: IdentityAssessmentSet | None = None) -> str:
    counts = identity_status_counts(identity) if identity is not None else None
    parts = []
    for qcolor, name in (
        (QUALIFIER_GREEN, "Validated"),
        (QUALIFIER_RED, "Failed"),
        (QUALIFIER_GREY, "No verdict"),
    ):
        count = "" if counts is None else f"&nbsp;<b>{counts[name]}</b>"
        parts.append(f'<span style="color:{qcolor.name()};">&#9632;</span>&nbsp;{name}{count}')
    # Counts are cells, not samples; the unit leads so it is read first.
    unit = "" if counts is None else "Qualifier cells&nbsp;&nbsp;"
    return unit + "&nbsp;&nbsp;&nbsp;".join(parts)


_NO_VERDICT_STATES = {
    QualifierStatus.ABSENT: "absent",
    QualifierStatus.NOT_ASSESSED: "not assessed",
    QualifierStatus.UNAVAILABLE: "unavailable",
}


def identity_key_tooltip(identity: IdentityAssessmentSet) -> str:
    """What the key counts, and which states the grey cells hold."""
    grey = {status: 0 for status in _NO_VERDICT_STATES}
    for sample in identity.samples:
        for qualifier in sample.qualifiers:
            if qualifier.status in grey:
                grey[qualifier.status] += 1
    breakdown = ", ".join(
        f"{grey[status]} {label}" for status, label in _NO_VERDICT_STATES.items()
    )
    return (
        "Counts are qualifier cells: one per sample for each qualifier ion.\n"
        f"No verdict (grey): {breakdown}."
    )


def bar_value_text(value: float) -> str:
    """A bar's value in the axis unit at fixed precision: '0.91', '<0.01', or '—' for none."""
    if not np.isfinite(value) or value == 0:
        return "—"
    if abs(value) < 0.005:
        return "<0.01"
    return f"{value:.2f}"


class _BackedText(QGraphicsSimpleTextItem):
    """Text on a panel-coloured patch, so a gridline never strikes through it."""

    def paint(self, painter, option, widget=None):
        painter.fillRect(self.boundingRect(), color("surface"))
        super().paint(painter, option, widget)


class ChartPopupDialog(QDialog):
    """Modal dialog showing an enlarged version of toolbar charts with sample names visible.

    ``data`` and ``sample_names`` run bottom to top, as the sidebar charts
    draw them, so every popup reads top-down in grid order. Clicking a sample
    row, or Enter on the row picked with the arrow keys, emits
    ``sample_activated`` and closes the popup, once something listens.
    """

    sample_activated = Signal(str)

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
    ):
        super().__init__(parent)
        self.chart_type = chart_type
        self.data = data
        self.sample_names = sample_names
        self.hover_notes = hover_notes
        self._identity = identity

        self._hover_categories: list[str] | None = None
        self._hover_notes: list[str] | None = None
        self._identity_binding: IdentityGridBinding | None = None
        self._total_abundance_scale_factor: float = 1.0
        self._total_abundance_scale_exp: int = 0
        self._value_labels: list[tuple[QGraphicsSimpleTextItem, float, int]] = []
        self._current_row: int | None = None

        self.setWindowTitle(f"{title} — MANIC")
        self.setModal(True)

        # Set window icon (same as main window)
        self._set_window_icon(parent)

        self._setup_ui(title, compound_name or (identity.compound_name if identity else ""))
        self._populate_chart()
        self._fit_to_rows()
        self._row_marker = QGraphicsRectItem(self.chart)
        self._row_marker.setBrush(Qt.NoBrush)
        self._row_marker.setZValue(100)
        self._row_marker.hide()
        self.chart.plotAreaChanged.connect(self._place_row_marker)
        self.chart_view.viewport().setMouseTracking(True)
        self.chart_view.viewport().installEventFilter(self)

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

        self.compound_title = QLabel(compound_name or title)
        theme.style(self.compound_title, text_style("text", FONT_SIZE_TITLE, 600))
        count = len(self.sample_names)
        subtitle = title if compound_name else ""
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
        self.chart_view.setStyleSheet("background: transparent;")
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setWidget(self.chart_view)
        theme.style(
            self._scroll,
            "QScrollArea { background: @surface; border: 1px solid @border; border-radius: 8px; }",
        )
        layout.addWidget(self._scroll, stretch=1)

        self.status_legend = QLabel("")
        self.status_legend.setTextFormat(Qt.RichText)
        theme.style(self.status_legend, text_style("text_secondary", 12))
        self.status_legend.hide()

        footer = QHBoxLayout()
        footer.addWidget(self.status_legend)
        footer.addStretch()
        hover = {
            "identity": "Hover a cell for details",
            "isotopologue_ratios": "Hover a bar for its value",
        }.get(self.chart_type, "")
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
        self.chart_view.setMinimumHeight(rows * ROW_HEIGHT + _AXIS_SPACE)
        screen = self.screen() or QApplication.primaryScreen()
        max_height = int(screen.availableGeometry().height() * 0.85) if screen else 900
        chrome = 150 + (30 if self.ion_legend.isVisibleTo(self) else 0)
        self.resize(820, min(max_height, rows * ROW_HEIGHT + _AXIS_SPACE + chrome))

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
        bar_set.setColor(abundance_colour)
        bar_set.setBorderColor(abundance_colour)

        # Calculate scaling for display
        max_abundance = float(np.max(self.data)) if len(self.data) > 0 else 1.0
        scale_exp = int(np.floor(np.log10(max_abundance))) if max_abundance > 0 else 0
        scale_factor = 10**scale_exp if scale_exp != 0 else 1
        self._total_abundance_scale_factor = float(scale_factor)
        self._total_abundance_scale_exp = scale_exp

        scaled = [float(abundance) / scale_factor for abundance in self.data]
        for value in scaled:
            bar_set.append(value)

        bar_set.hovered.connect(
            lambda status, index, bs=bar_set: self._on_total_abundance_bar_hover(
                bs, status, index
            )
        )

        bar_series.append(bar_set)
        self.chart.addSeries(bar_series)

        # Setup axes with sample names visible
        self._setup_total_abundance_axes(max_abundance, scale_exp, scale_factor)

        # Attach series to axes
        bar_series.attachAxis(self.chart.axes(Qt.Horizontal)[0])
        bar_series.attachAxis(self.chart.axes(Qt.Vertical)[0])
        self._add_value_labels(bar_series, scaled)

    def _add_value_labels(self, series: QHorizontalBarSeries, values: list[float]) -> None:
        """Value text past each bar end. QtCharts' own labels can only print raw numbers."""
        for index, value in enumerate(values):
            item = _BackedText(bar_value_text(value), self.chart)
            item.setFont(ui_font(10))
            # Above QtCharts' gridlines, which sit over plain chart children.
            item.setZValue(50)
            self._value_labels.append((item, value if np.isfinite(value) else 0.0, index))
        self._value_series = series
        self._recolour_value_labels()
        self.chart.plotAreaChanged.connect(self._place_value_labels)
        theme.notifier.changed.connect(self._recolour_value_labels)
        self._place_value_labels()

    def _recolour_value_labels(self, *_args) -> None:
        for item, _value, _index in self._value_labels:
            item.setBrush(color("text_secondary"))
            item.update()

    def _place_value_labels(self, *_args) -> None:
        for item, value, index in self._value_labels:
            end = self.chart.mapToPosition(QPointF(max(value, 0.0), index), self._value_series)
            height = item.boundingRect().height()
            item.setPos(end.x() + 4, end.y() - height / 2)

    def value_label_texts(self) -> list[str]:
        """Value labels top to bottom, as the rows read."""
        return [item.text() for item, _value, _index in reversed(self._value_labels)]

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

            bar_set.hovered.connect(
                lambda status, index, bs=bar_set: self._on_stacked_bar_segment_hover(
                    bs, status, index
                )
            )
            stacked_series.append(bar_set)

        self.chart.addSeries(stacked_series)

        # Setup axes
        self._setup_isotopologue_axes()

        if num_isotopologues > 1:
            self.ion_legend.set_channels(labels, styles)

        # Attach series to axes
        stacked_series.attachAxis(self.chart.axes(Qt.Horizontal)[0])
        stacked_series.attachAxis(self.chart.axes(Qt.Vertical)[0])

    def _create_identity_chart(self):
        if self._identity is None or not self._identity.samples:
            return

        labels, styles = identity_key_chips(self._identity.channels)
        self.ion_legend.set_channels(labels, styles)
        self._identity_binding = add_identity_grid(
            self.chart, self._identity.samples, label_font_size=11
        )
        self.status_legend.setText(identity_key_html(self._identity))
        self.status_legend.setToolTip(identity_key_tooltip(self._identity))
        self.status_legend.show()
        for bar_set in self._identity_binding.bar_sets:
            bar_set.hovered.connect(
                lambda status, index, bound=bar_set: self._on_identity_cell_hover(
                    bound, status, index
                )
            )

    def _on_identity_cell_hover(
        self, bar_set: QBarSet, status: bool, index: int
    ) -> None:
        if (
            not status
            or self._identity_binding is None
            or index < 0
            or index >= bar_set.count()
            or bar_set.at(index) <= 0
        ):
            QToolTip.hideText()
            return
        cell = self._identity_binding.cell_for(bar_set)
        if cell is None:
            QToolTip.hideText()
            return
        show_identity_tooltip(self.chart_view, identity_cell_tooltip(cell))

    def closeEvent(self, event) -> None:
        QToolTip.hideText()
        super().closeEvent(event)

    def _sample_name_for_hover_index(self, index: int) -> str | None:
        if index < 0:
            return None

        if self._hover_categories is None:
            return None

        if index >= len(self._hover_categories):
            return None

        return self._hover_categories[index]

    def _on_stacked_bar_segment_hover(
        self, bar_set: QBarSet, status: bool, index: int
    ) -> None:
        if not status:
            QToolTip.hideText()
            return

        sample_name = self._sample_name_for_hover_index(index)
        if sample_name is None:
            return

        ratio = float(bar_set.at(index))
        percent = ratio * 100.0
        mx_label = bar_set.label()

        QToolTip.showText(
            QCursor.pos(),
            f"{sample_name}\n{mx_label}: {percent:.1f}%",
            self.chart_view,
        )

    def _on_total_abundance_bar_hover(
        self, bar_set: QBarSet, status: bool, index: int
    ) -> None:
        if not status:
            QToolTip.hideText()
            return

        sample_name = self._sample_name_for_hover_index(index)
        if sample_name is None:
            return

        scaled_value = float(bar_set.at(index))
        unit = scale_text(self._total_abundance_scale_exp)

        QToolTip.showText(
            QCursor.pos(),
            f"{sample_name}\nTotal abundance: {bar_value_text(scaled_value)} {unit}".rstrip(),
            self.chart_view,
        )

    def _sample_axis(self, names: list[str]) -> QBarCategoryAxis:
        axis = QBarCategoryAxis()
        axis.append(names)
        style_axis(axis)
        axis.setLabelsFont(ui_font(11))
        axis.setLabelsColor(color("text"))
        axis.setLineVisible(False)
        # Every row is tall enough for its name, so never shorten it to "…".
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
        x_axis.setTitleText(
            f"Total abundance  {scale_text(scale_exp)}" if scale_exp else "Total abundance"
        )

        y_axis = self._sample_axis(list(self.sample_names))

        # Value axis on top so it stays in view while a long list scrolls.
        self.chart.addAxis(x_axis, Qt.AlignTop)
        self.chart.addAxis(y_axis, Qt.AlignLeft)

        self._hover_categories = list(self.sample_names)

    def _setup_isotopologue_axes(self):
        """Setup axes for isotopologue chart."""
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)

        x_axis = QValueAxis()
        x_axis.setRange(0, 1.0)
        x_axis.setLabelFormat("%.1f")
        style_axis(x_axis, grid=True)
        x_axis.setTickCount(6)
        x_axis.setTitleText("Isotopologue ratio")

        y_axis = self._sample_axis(list(self.sample_names))
        self._hover_categories = list(self.sample_names)

        # Value axis on top so it stays in view while a long list scrolls.
        self.chart.addAxis(x_axis, Qt.AlignTop)
        self.chart.addAxis(y_axis, Qt.AlignLeft)

    def row_names(self) -> list[str]:
        """Sample names top to bottom, as the rows read."""
        axis = next(
            (a for a in self.chart.axes(Qt.Vertical) if isinstance(a, QBarCategoryAxis)), None
        )
        return list(reversed(axis.categories())) if axis is not None else []

    def _rows_active(self) -> bool:
        return bool(self.row_names()) and self.isSignalConnected(
            QMetaMethod.fromSignal(self.sample_activated)
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._rows_active():
            self._hint.setText(
                " · ".join(p for p in (self._hover_hint, "Click a sample to show its plot") if p)
            )
            self.chart_view.viewport().setCursor(Qt.PointingHandCursor)

    def _row_at(self, viewport_pos) -> int | None:
        series = self.chart.series()
        if not series:
            return None
        point = self.chart.mapFromScene(self.chart_view.mapToScene(viewport_pos))
        area = self.chart.plotArea()
        if not (area.top() <= point.y() <= area.bottom()) or point.x() > area.right():
            return None
        category = round(self.chart.mapToValue(point, series[0]).y())
        rows = len(self.row_names())
        return rows - 1 - category if 0 <= category < rows else None

    def set_current_row(self, row: int | None) -> None:
        self._current_row = row
        self._place_row_marker()

    def _place_row_marker(self, *_args) -> None:
        series = self.chart.series()
        if self._current_row is None or not series:
            self._row_marker.hide()
            return
        category = len(self.row_names()) - 1 - self._current_row
        top = self.chart.mapToPosition(QPointF(0, category + 0.5), series[0]).y()
        bottom = self.chart.mapToPosition(QPointF(0, category - 0.5), series[0]).y()
        area = self.chart.plotArea()
        self._row_marker.setRect(QRectF(2, top, area.right() - 2, bottom - top))
        self._row_marker.setPen(QPen(color("accent"), 1.5))
        self._row_marker.show()
        centre = self.chart_view.mapFromScene(self._row_marker.sceneBoundingRect().center())
        self._scroll.ensureVisible(centre.x(), centre.y(), 0, int(bottom - top))

    def activate_row(self, row: int) -> None:
        names = self.row_names()
        if not self._rows_active() or not 0 <= row < len(names):
            return
        self.sample_activated.emit(names[row])
        self.accept()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.chart_view.viewport() and self._rows_active():
            if event.type() == QEvent.MouseMove:
                row = self._row_at(event.position().toPoint())
                if row is not None and row != self._current_row:
                    self.set_current_row(row)
            elif (
                event.type() == QEvent.MouseButtonRelease
                and event.button() == Qt.LeftButton
            ):
                row = self._row_at(event.position().toPoint())
                if row is not None:
                    self.activate_row(row)
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:
        rows = len(self.row_names())
        if self._rows_active() and rows:
            key = event.key()
            if key in (Qt.Key_Down, Qt.Key_Up):
                step = 1 if key == Qt.Key_Down else -1
                start = -1 if step == 1 else rows
                current = start if self._current_row is None else self._current_row
                self.set_current_row(min(max(current + step, 0), rows - 1))
                return
            if key in (Qt.Key_Return, Qt.Key_Enter) and self._current_row is not None:
                self.activate_row(self._current_row)
                return
        super().keyPressEvent(event)
