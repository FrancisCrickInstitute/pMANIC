"""The workspace shown before raw data is loaded: two steps, recent files, drop hint."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from manic.models.analysis import AnalysisMode
from manic.ui.sidebar_widgets import ElidedLabel, divider, section_heading, shortcut_text
from manic.ui.theme import set_style_property
from manic.ui.logo import LogoLabel

RECENT_LIMIT = 3


class _Step(QWidget):
    clicked = Signal()

    def __init__(self, number: int, title: str, detail: str, button_text: str):
        super().__init__()
        layout = QGridLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(2)
        self._number = number
        self.badge = QLabel(str(number))
        self.badge.setProperty("role", "stepNumber")
        self.badge.setFixedSize(24, 24)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 600;")
        detail_label = QLabel(detail)
        detail_label.setProperty("role", "secondary")
        detail_label.setWordWrap(True)
        self.button = QPushButton(button_text)
        self.button.setMinimumWidth(150)
        self.button.clicked.connect(self.clicked.emit)
        self.done_label = QLabel()
        self.done_label.setProperty("role", "stepDone")
        layout.addWidget(self.badge, 0, 0, 2, 1, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title_label, 0, 1)
        layout.addWidget(detail_label, 1, 1)
        layout.addWidget(self.button, 0, 2, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.done_label, 0, 2, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.setColumnStretch(1, 1)

    def set_state(self, state: str, done_text: str = "") -> None:
        """state is 'done', 'next' or 'later'."""
        self.badge.setText("✓" if state == "done" else str(self._number))
        set_style_property(self.badge, "state", state)
        self.button.setVisible(state != "done")
        self.button.setEnabled(state == "next")
        set_style_property(self.button, "variant", "primary" if state == "next" else None)
        self.done_label.setVisible(state == "done")
        self.done_label.setText(done_text)


class StartPanel(QWidget):
    """Same actions as the File menu, laid out as the first thing a new user sees."""

    load_compounds_requested = Signal()
    load_raw_data_requested = Signal()
    recent_compound_list_requested = Signal(str)
    recent_raw_data_requested = Signal(str)
    new_session_requested = Signal()
    documentation_requested = Signal()

    def __init__(self, mode: AnalysisMode, parent=None):
        super().__init__(parent)
        self.setObjectName("startPanel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(2)

        column = QWidget()
        column.setMaximumWidth(560)
        column.setMinimumWidth(420)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo = LogoLabel(44)
        logo.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(logo)
        layout.addSpacing(12)

        title = QLabel(f"Start a {mode.display_name.lower()} analysis")
        title.setProperty("role", "title")
        title.setStyleSheet("font-size: 20px;")
        layout.addWidget(title)
        layout.addSpacing(4)
        subtitle = QLabel("Load your compound list, then the folder of raw data.")
        subtitle.setProperty("role", "secondary")
        subtitle.setStyleSheet("font-size: 13px;")
        layout.addWidget(subtitle)
        layout.addSpacing(20)

        card = QWidget()
        card.setObjectName("startCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        self.compounds_step = _Step(
            1,
            "Compound list",
            "A CSV or Excel file (.csv, .xls, .xlsx) with one row per compound.",
            f"Load list…   {shortcut_text('Ctrl+O')}",
        )
        self.raw_step = _Step(
            2,
            "Raw data folder",
            "A folder of .CDF files exported from the instrument.",
            f"Load folder…   {shortcut_text('Ctrl+Shift+O')}",
        )
        self.compounds_step.clicked.connect(self.load_compounds_requested.emit)
        self.raw_step.clicked.connect(self.load_raw_data_requested.emit)
        card_layout.addWidget(self.compounds_step)
        card_layout.addWidget(divider())
        card_layout.addWidget(self.raw_step)
        layout.addWidget(card)
        layout.addSpacing(8)
        after = QLabel(
            "Then confirm the data setup and review each compound's plots. "
            "The Review menu lists every review command and its key."
        )
        after.setObjectName("startNextSteps")
        after.setProperty("role", "hint")
        after.setWordWrap(True)
        layout.addWidget(after)

        layout.addSpacing(24)
        self._recent_heading = section_heading("Recent")
        layout.addWidget(self._recent_heading)
        layout.addSpacing(4)
        self._recent_box = QVBoxLayout()
        self._recent_box.setSpacing(0)
        layout.addLayout(self._recent_box)
        self._recent_spacer = QWidget()
        self._recent_spacer.setFixedHeight(20)
        layout.addWidget(self._recent_spacer)

        drop = QLabel(
            "You can also drop a compound list or a raw data folder onto this window."
        )
        drop.setProperty("role", "hint")
        drop.setWordWrap(True)
        layout.addWidget(drop)
        layout.addSpacing(4)
        session = QLabel(
            "Have a saved session? Load the same data, then choose "
            f"File → Import Session ({shortcut_text('Ctrl+I')})."
        )
        session.setProperty("role", "hint")
        session.setWordWrap(True)
        layout.addWidget(session)
        layout.addSpacing(12)

        links = QHBoxLayout()
        links.setSpacing(16)
        guide = QPushButton("Quick start guide")
        guide.setProperty("variant", "link")
        guide.setCursor(Qt.CursorShape.PointingHandCursor)
        guide.clicked.connect(self.documentation_requested.emit)
        switch = QPushButton("Change analysis mode…")
        switch.setProperty("variant", "link")
        switch.setCursor(Qt.CursorShape.PointingHandCursor)
        switch.clicked.connect(self.new_session_requested.emit)
        links.addWidget(guide)
        links.addWidget(switch)
        links.addStretch(1)
        layout.addLayout(links)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(column, 3)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(3)
        self.refresh(False, 0, True, False, [], [])

    def refresh(
        self,
        compounds_loaded: bool,
        compound_count: int,
        can_load_compounds: bool,
        can_load_raw: bool,
        recent_compound_lists: list[str],
        recent_raw_folders: list[str],
    ) -> None:
        if compounds_loaded:
            noun = "compound" if compound_count == 1 else "compounds"
            self.compounds_step.set_state("done", f"{compound_count} {noun} loaded")
            self.raw_step.set_state("next" if can_load_raw else "later")
        else:
            self.compounds_step.set_state("next" if can_load_compounds else "later")
            self.raw_step.set_state("later")

        while self._recent_box.count():
            widget = self._recent_box.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        recent = [
            (path, "List", can_load_compounds, self.recent_compound_list_requested)
            for path in recent_compound_lists[:RECENT_LIMIT]
        ] + [
            (path, "Folder", can_load_raw, self.recent_raw_data_requested)
            for path in recent_raw_folders[:RECENT_LIMIT]
        ]
        for path, kind, enabled, signal in recent:
            self._recent_box.addWidget(_recent_row(path, kind, enabled, signal))
        has_recent = bool(recent)
        self._recent_heading.setVisible(has_recent)
        self._recent_spacer.setVisible(has_recent)


def _recent_row(path: str, kind: str, enabled: bool, signal) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    kind_label = QLabel(kind)
    kind_label.setProperty("role", "hint")
    kind_label.setFixedWidth(44)
    button = QPushButton(Path(path).name or path)
    button.setProperty("variant", "link")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip(path)
    button.setEnabled(enabled)
    button.clicked.connect(lambda: signal.emit(path))
    where = ElidedLabel(str(Path(path).parent))
    where.setProperty("role", "hint")
    layout.addWidget(kind_label)
    layout.addWidget(button)
    layout.addWidget(where, 1)
    return row
