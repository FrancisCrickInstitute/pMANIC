"""One sample's card in the plot grid: caption, QC badges, selection and focus outline."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from manic.ui.chart_style import AXIS_LABEL_PX, scale_text, text_style
from manic.ui.sidebar_widgets import ElidedLabel
from manic.ui.theme import RADIUS, color
from manic.ui import theme
from manic.validation.peak_verdict import PeakVerdict
from manic.validation.unlabelled_identity import (
    IdentitySampleAssessment,
    QualifierOutcome,
    qualifier_outcome,
)

TILE_GAP = 8
TILE_ASPECT = 1.45

# Minimum readable tile (width, height) per grid density.
DENSITY_MIN_TILE = {"comfortable": (230, 165), "compact": (130, 95)}
# (axis and scale text px, caption px) per grid density.
DENSITY_TEXT = {"comfortable": (11, 13), "compact": (AXIS_LABEL_PX, 12)}

# (text colour, fill) per badge tone. A tinted card's badge is a surface pill,
# since a fill matching the tint would leave bare text.
_TONES = {
    "danger": ("danger", "surface"),
    "warning": ("warning", "surface"),
    "success": ("success", "success_soft"),
    # A grey pill on the grey card tint, so the badge reads as one.
    "neutral": ("text", "border_strong"),
}
# Card fill per tone, most serious first.
_TINTS = {"danger": "danger_soft", "warning": "warning_soft", "neutral": "surface_hover"}


@dataclass(frozen=True, slots=True)
class TileBadge:
    text: str
    tone: str
    tooltip: str


PEAK_BADGES = {
    PeakVerdict.FAIL: TileBadge(
        "Below threshold", "warning", "Right-click to accept it or mark it as bad."
    ),
    PeakVerdict.ACCEPTED: TileBadge(
        "Accepted", "success", "Below threshold, accepted on review."
    ),
    PeakVerdict.REJECTED: TileBadge("Marked bad", "danger", ""),
}

_QC_BADGES = {
    QualifierOutcome.PARTIAL: ("QC partial", "warning"),
    QualifierOutcome.FAIL: ("QC fail", "danger"),
    QualifierOutcome.NOT_DETECTED: ("Not detected", "neutral"),
}


def tile_badges(
    verdict: PeakVerdict, identity: IdentitySampleAssessment | None
) -> list[TileBadge]:
    """Badges for a tile: the peak review verdict, then any qualifier QC problem.

    A clean pass gets no badge, so the badges that do show stand out.
    """
    badges = [PEAK_BADGES[verdict]] if verdict in PEAK_BADGES else []
    if identity is not None and identity.qc is not None:
        outcome = qualifier_outcome(identity.qc)
        if outcome in _QC_BADGES:
            text, tone = _QC_BADGES[outcome]
            detail = "\n".join(identity.qc.reasons)
            badges.append(
                TileBadge(text, tone, f"Qualifier QC: {outcome.value}" + (f"\n{detail}" if detail else ""))
            )
    return badges


def tile_tint(badges: list[TileBadge]) -> str | None:
    """Soft card fill token for the most serious badge, so problems stand out."""
    tones = {badge.tone for badge in badges}
    return next((tint for tone, tint in _TINTS.items() if tone in tones), None)


def grid_columns(
    count: int, width: int, height: int, *, min_width: int, min_height: int
) -> tuple[int, int]:
    """(columns, fixed row height) for ``count`` tiles in a width x height viewport.

    Row height 0 means every row fits and rows stretch to fill the height.
    Otherwise the grid keeps the most columns that stay readable and scrolls.
    """
    if count <= 0 or width <= 0 or height <= 0:
        return max(1, math.ceil(math.sqrt(max(count, 1)))), 0
    max_cols = max(1, min(count, (width + TILE_GAP) // (min_width + TILE_GAP)))
    best: tuple[float, int] | None = None
    for cols in range(1, max_cols + 1):
        rows = math.ceil(count / cols)
        tile_w = (width - TILE_GAP * (cols - 1)) / cols
        tile_h = (height - TILE_GAP * (rows - 1)) / rows
        if tile_h < min_height:
            continue
        score = min(tile_w, tile_h * TILE_ASPECT)
        if best is None or score > best[0]:
            best = (score, cols)
    if best is not None:
        return best[1], 0
    tile_w = (width - TILE_GAP * (max_cols - 1)) / max_cols
    return max_cols, max(min_height, int(tile_w / TILE_ASPECT))


def _badge_label(badge: TileBadge) -> QLabel:
    fg, bg = _TONES[badge.tone]
    label = QLabel(badge.text)
    if badge.tooltip:
        label.setToolTip(badge.tooltip)
    label.setFixedHeight(16)
    theme.style(
        label,
        f"color: @{fg}; background: @{bg}; font-size: 10px;"
        " font-weight: 600; border: none; border-radius: 4px; padding: 0px 5px;"
    )
    return label


class PlotTile(QWidget):
    """Card holding one chart view. Paints its own fill, border and outlines."""

    def __init__(self, chart_view: QWidget, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.chart_view = chart_view
        self.verdict = PeakVerdict.PASS
        self._tint: str | None = None
        self._focused = False
        self._badges: list[TileBadge] = []
        self._caption_selected: bool | None = None
        self._text_size = DENSITY_TEXT["compact"]
        self.setAttribute(Qt.WA_Hover)

        self.caption = ElidedLabel(hover=True)
        self.caption.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.caption.setMinimumWidth(24)

        self.scale_label = QLabel()
        theme.style(self.scale_label, text_style("text_tertiary", self._text_size[0]))
        self.scale_label.setToolTip("Intensity axis multiplier")

        # Badges always sit on their own line under the name, on every platform
        # and tile width, so the verdict never moves and the name is never cut for it.
        self._badge_box = QWidget()
        self._badge_row = QHBoxLayout(self._badge_box)
        self._badge_row.setContentsMargins(6, 2, 4, 0)
        self._badge_row.setSpacing(4)
        self._badge_row.addStretch()
        self._badge_box.hide()

        self._header = QHBoxLayout()
        self._header.setContentsMargins(6, 0, 4, 0)
        self._header.setSpacing(6)
        self._header.addWidget(self.caption, stretch=1)
        self._header.addWidget(self.scale_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 5, 3, 3)
        layout.setSpacing(0)
        layout.addLayout(self._header)
        layout.addWidget(self._badge_box)
        layout.addWidget(chart_view, stretch=1)
        self._refresh_caption_colour()

    @property
    def is_selected(self) -> bool:
        return bool(getattr(self.chart_view, "is_selected", False))

    def set_caption(self, text: str) -> None:
        self.caption.setText(text)

    def set_scale(self, exponent: int) -> None:
        self.scale_label.setText(scale_text(exponent))
        self.scale_label.setVisible(bool(exponent))

    def text_size(self) -> tuple[int, int]:
        return self._text_size

    def set_text_size(self, scale_px: int, caption_px: int) -> None:
        self._text_size = (scale_px, caption_px)
        theme.style(self.scale_label, text_style("text_tertiary", scale_px))
        self._caption_selected = None
        self._refresh_caption_colour()

    def set_badges(self, badges: list[TileBadge]) -> None:
        if badges == self._badges:
            return
        self._badges = list(badges)
        while self._badge_row.count() > 1:
            widget = self._badge_row.takeAt(0).widget()
            widget.hide()
            widget.deleteLater()
        for index, badge in enumerate(badges):
            self._badge_row.insertWidget(index, _badge_label(badge))
        self._badge_box.setVisible(bool(badges))
        self._tint = tile_tint(badges)
        self.update()

    def badges(self) -> list[TileBadge]:
        return list(self._badges)

    def tint(self) -> str | None:
        return self._tint

    def set_focused(self, focused: bool) -> None:
        if focused != self._focused:
            self._focused = focused
            self.update()

    def refresh_selection(self) -> None:
        self._refresh_caption_colour()
        self.update()

    def _refresh_caption_colour(self) -> None:
        # Restyling is slow and tiles are reset several times per replot.
        if self._caption_selected is self.is_selected:
            return
        self._caption_selected = self.is_selected
        theme.style(
            self.caption,
            text_style("accent" if self.is_selected else "text", self._text_size[1], 600),
        )

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setBrush(color(self._tint or "surface"))
        if self.is_selected:
            painter.setPen(QPen(color("accent"), 2))
        elif self.underMouse():
            painter.setPen(QPen(color("border_strong"), 1))
        else:
            painter.setPen(QPen(color("border"), 1))
        painter.drawRoundedRect(rect, RADIUS, RADIUS)
        if self._focused:
            ring = color("accent")
            ring.setAlpha(150)
            pen = QPen(ring, 1.5, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), RADIUS - 3, RADIUS - 3)
