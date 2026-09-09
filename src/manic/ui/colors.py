"""
Shared color definitions for consistent styling across UI components.
"""

from dataclasses import dataclass
from typing import Mapping, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from manic.models.analysis import IonRole
from manic.validation.peak_verdict import PEAK_VERDICT_FILL, PeakVerdict
from manic.validation.unlabelled_identity import (
    QUALIFIER_OUTCOME_FILL,
    IdentitySampleAssessment,
    QualifierOutcome,
    QualifierStatus,
)

# Steel blue and dark red used in graphs
steel_blue_colour = QColor(70, 130, 180)
dark_red_colour = QColor(139, 0, 0)
selection_color = QColor(144, 238, 144, 50)  # Light green with transparency

# Colors for isotopologue labels (M+0, M+1, M+2, etc.)
# Used in both multi-trace plots and isotopologue ratio charts
label_colors = [
    QColor(31, 119, 180),    # blue - M+0
    QColor(255, 127, 14),    # orange - M+1  
    QColor(44, 160, 44),     # green - M+2
    QColor(214, 39, 40),     # red - M+3
    QColor(148, 103, 189),   # purple - M+4
    QColor(140, 86, 75),     # brown - M+5
    QColor(227, 119, 194),   # pink - M+6
    QColor(127, 127, 127),   # gray - M+7
    QColor(188, 189, 34),    # olive - M+8
    QColor(23, 190, 207),    # cyan - M+9
]

QUALIFIER_GREEN = QColor(QUALIFIER_OUTCOME_FILL[QualifierOutcome.PASS])
QUALIFIER_RED = QColor(QUALIFIER_OUTCOME_FILL[QualifierOutcome.FAIL])
QUALIFIER_GREY = QColor(QUALIFIER_OUTCOME_FILL[QualifierOutcome.NO_QUALIFIERS])


def peak_verdict_qcolor(verdict: PeakVerdict) -> QColor | None:
    fill = PEAK_VERDICT_FILL[verdict]
    if fill is None:
        return None
    return QColor(fill)

QUALIFIER_STATUS_COLORS: Mapping[QualifierStatus, QColor] = {
    QualifierStatus.ABSENT: QUALIFIER_GREY,
    QualifierStatus.VALIDATED: QUALIFIER_GREEN,
    QualifierStatus.FAILED: QUALIFIER_RED,
    QualifierStatus.NOT_ASSESSED: QUALIFIER_GREY,
    QualifierStatus.UNAVAILABLE: QUALIFIER_GREY,
}


@dataclass(frozen=True, slots=True)
class ChannelTraceStyle:
    color: QColor
    line_style: Qt.PenStyle


def _qualifier_line_style(ordinal: int) -> Qt.PenStyle:
    if ordinal == 2:
        return Qt.DashDotLine
    return Qt.SolidLine


def legend_trace_styles(
    channels: Sequence, *, unlabelled: bool, multi_trace: bool
) -> tuple[ChannelTraceStyle, ...]:
    """One representative style per channel for a colour key.

    Unlabelled qualifier traces take their colour from each sample's QC
    status, so the key shows them grey and lets the line style tell them
    apart. A single trace is drawn dark red regardless of channel.
    """
    if not multi_trace:
        return tuple(
            ChannelTraceStyle(dark_red_colour, Qt.SolidLine) for _channel in channels
        )
    if not unlabelled:
        return channel_trace_styles(channels, None)
    return tuple(
        ChannelTraceStyle(label_colors[0], Qt.SolidLine)
        if channel.role is IonRole.QUANTIFIER or int(channel.ordinal) == 0
        else ChannelTraceStyle(QUALIFIER_GREY, _qualifier_line_style(channel.ordinal))
        for channel in channels
    )


def channel_trace_styles(
    channels: Sequence,
    identity: IdentitySampleAssessment | None,
) -> tuple[ChannelTraceStyle, ...]:
    if identity is None:
        return tuple(
            ChannelTraceStyle(label_colors[index % len(label_colors)], Qt.SolidLine)
            for index, _channel in enumerate(channels)
        )

    styles = []
    for index, channel in enumerate(channels):
        if channel.role is IonRole.QUANTIFIER or int(channel.ordinal) == 0:
            styles.append(ChannelTraceStyle(label_colors[0], Qt.SolidLine))
            continue
        assessment = identity.qualifiers.for_ordinal(channel.ordinal)
        styles.append(
            ChannelTraceStyle(
                QUALIFIER_STATUS_COLORS[assessment.status],
                _qualifier_line_style(channel.ordinal),
            )
        )
    return tuple(styles)
