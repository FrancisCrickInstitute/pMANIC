"""
Shared color definitions for consistent styling across UI components.
"""

from dataclasses import dataclass
from typing import Mapping, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from manic.models.analysis import IonRole
from manic.ui import theme
from manic.ui.theme import contrast
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


# Every data colour above, with its light-scheme value. Consumers hold these
# QColor objects, so set_dark() retunes them in place.
_DATA_COLOURS = [
    steel_blue_colour,
    dark_red_colour,
    *label_colors,
    QUALIFIER_GREEN,
    QUALIFIER_RED,
    QUALIFIER_GREY,
]
_LIGHT_VALUES = [QColor(c) for c in _DATA_COLOURS]
_DARK_MIN_CONTRAST = 3.5


def _legible_on(base: QColor, background: QColor) -> QColor:
    """``base`` mixed toward white until it reads on ``background``; hue is kept."""
    for step in range(11):
        t = step / 10
        mixed = QColor.fromRgbF(*(v + (1 - v) * t for v in (base.redF(), base.greenF(), base.blueF())))
        if contrast(mixed, background) >= _DARK_MIN_CONTRAST:
            return mixed
    return mixed


def set_dark(dark: bool, plot_area: QColor) -> dict[str, str]:
    """Retune the data colours for a scheme; return old -> new hex for each."""
    remap = {}
    for qcolor, light in zip(_DATA_COLOURS, _LIGHT_VALUES):
        new = _legible_on(light, plot_area) if dark else light
        remap[qcolor.name()] = new.name()
        qcolor.setRgb(new.rgb())
    return remap


@dataclass(frozen=True, slots=True)
class VerdictColours:
    tint: QColor  # card fill
    pill: QColor  # badge fill
    text: QColor  # badge text


def _mix(under: QColor, over: QColor, opacity: float) -> QColor:
    """``over`` laid on ``under`` at ``opacity``, as an opaque colour."""
    return QColor.fromRgbF(
        *(u + (o - u) * opacity for u, o in zip(under.getRgbF()[:3], over.getRgbF()[:3]))
    )


def _readable(colour: QColor, background: QColor, *, lighter: bool) -> QColor:
    """``colour`` moved darker (or lighter) in its own hue until it reads at 4.5:1."""
    hue, sat, lightness, _ = colour.getHslF()
    while contrast(colour, background) < 4.5 and 0.0 < lightness < 1.0:
        lightness = min(1.0, lightness + 0.01) if lighter else max(0.0, lightness - 0.01)
        colour = QColor.fromHslF(hue, sat * (0.85 if not lighter else 1.0), lightness).toRgb()
    return colour


def _verdict_scheme(fill: str) -> tuple[VerdictColours, VerdictColours]:
    """(light, dark) colours for a workbook verdict fill, keeping its hue.

    The card is the workbook fill laid over the card surface as a soft wash (main
    painted it at about half opacity); the badge is a pastel pill of the fill with
    its own hue, deepened or lightened, as text.
    """
    wash = QColor(fill)
    light_surface, dark_surface = QColor(theme.LIGHT["surface"]), QColor(theme.DARK["surface"])
    light_card = _mix(light_surface, wash, 0.45)
    dark_card = _mix(dark_surface, wash, 0.16)
    dark_pill = _mix(dark_surface, wash, 0.28)
    return (
        VerdictColours(light_card, wash, _readable(wash, wash, lighter=False)),
        VerdictColours(dark_card, dark_pill, _readable(wash, dark_pill, lighter=True)),
    )


_VERDICT_COLOURS = {
    verdict: _verdict_scheme(fill) for verdict, fill in PEAK_VERDICT_FILL.items() if fill
}


def verdict_colours(verdict: PeakVerdict) -> VerdictColours | None:
    """Tile colours for a peak verdict in the active scheme; None for a clean pass."""
    pair = _VERDICT_COLOURS.get(verdict)
    return pair[theme.is_dark()] if pair else None


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
