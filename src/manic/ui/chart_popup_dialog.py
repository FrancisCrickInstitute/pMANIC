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
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QCursor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
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
    return "&nbsp;&nbsp;&nbsp;".join(parts)


class ChartPopupDialog(QDialog):
    """Modal dialog showing an enlarged version of toolbar charts with sample names visible."""

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

        self.setWindowTitle(f"{title} — MANIC")
        self.setModal(True)

        # Set window icon (same as main window)
        self._set_window_icon(parent)

        self._setup_ui(title, compound_name or (identity.compound_name if identity else ""))
        self._populate_chart()
        self._fit_to_rows()

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
        hint = QLabel(
            "Hover a cell for details" if self.chart_type == "identity"
            else "Hover a bar for its value"
        )
        theme.style(hint, text_style("text_tertiary", 11))
        footer.addWidget(hint)
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
        bar_set.setLabelColor(color("text_secondary"))
        bar_set.setLabelFont(ui_font(10))

        # Calculate scaling for display
        max_abundance = float(np.max(self.data)) if len(self.data) > 0 else 1.0
        scale_exp = int(np.floor(np.log10(max_abundance))) if max_abundance > 0 else 0
        scale_factor = 10**scale_exp if scale_exp != 0 else 1
        self._total_abundance_scale_factor = float(scale_factor)

        # Add scaled abundance values
        for abundance in self.data:
            scaled_abundance = abundance / scale_factor
            bar_set.append(scaled_abundance)

        bar_set.hovered.connect(
            lambda status, index, bs=bar_set: self._on_total_abundance_bar_hover(
                bs, status, index
            )
        )

        bar_series.append(bar_set)
        bar_series.setLabelsVisible(True)
        bar_series.setLabelsPosition(QAbstractBarSeries.LabelsOutsideEnd)
        bar_series.setLabelsFormat("@value")
        bar_series.setLabelsPrecision(3)
        self.chart.addSeries(bar_series)

        # Setup axes with sample names visible
        self._setup_total_abundance_axes(max_abundance, scale_exp, scale_factor)

        # Attach series to axes
        bar_series.attachAxis(self.chart.axes(Qt.Horizontal)[0])
        bar_series.attachAxis(self.chart.axes(Qt.Vertical)[0])

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

        QToolTip.showText(
            QCursor.pos(),
            f"{sample_name}\nTotal: {scaled_value:.3g}",
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

        # Sample names bottom to top, matching QtCharts' category order.
        reversed_names = list(reversed(self.sample_names))
        y_axis = self._sample_axis(reversed_names)

        # Value axis on top so it stays in view while a long list scrolls.
        self.chart.addAxis(x_axis, Qt.AlignTop)
        self.chart.addAxis(y_axis, Qt.AlignLeft)

        self._hover_categories = list(reversed_names)

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
