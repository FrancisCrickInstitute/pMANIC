"""The workspace shown before raw data is loaded: the empty canvas as a drop target."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from manic.models.analysis import AnalysisMode
from manic.ui.sidebar_widgets import ElidedLabel
from manic.ui.theme import set_style_property

RECENT_LIMIT = 3


class StartPanel(QWidget):
    """One next step at a time; the sidebar header owns the load status.

    Install it as an event filter on the main window so the drop zone lights up
    while a drag the window would accept is over it.
    """

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
        outer.setContentsMargins(20, 20, 20, 20)

        self.drop_zone = QFrame()
        self.drop_zone.setObjectName("dropZone")
        outer.addWidget(self.drop_zone)
        zone = QVBoxLayout(self.drop_zone)
        zone.setContentsMargins(24, 24, 24, 16)
        zone.setSpacing(0)
        zone.addStretch(2)

        column = QWidget()
        column.setFixedWidth(360)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.prompt = QLabel()
        self.prompt.setObjectName("dropPrompt")
        self.prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.prompt)
        layout.addSpacing(16)
        self.primary_button = QPushButton()
        self.primary_button.setProperty("variant", "primary")
        self.primary_button.setMinimumWidth(200)
        self.primary_button.clicked.connect(self._primary_clicked)
        layout.addWidget(self.primary_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self._recent_space = QWidget()
        self._recent_space.setFixedHeight(36)
        layout.addWidget(self._recent_space)
        self._recent_heading = QLabel("Recent")
        self._recent_heading.setProperty("role", "hint")
        layout.addWidget(self._recent_heading)
        layout.addSpacing(6)
        self._recent_box = QVBoxLayout()
        self._recent_box.setSpacing(2)
        layout.addLayout(self._recent_box)

        zone.addWidget(column, 0, Qt.AlignmentFlag.AlignHCenter)
        zone.addStretch(3)
        centred = QHBoxLayout()
        centred.addStretch(1)
        centred.addWidget(self._footer(mode), 1000)  # grows to its cap before the margins do
        centred.addStretch(1)
        zone.addLayout(centred)
        self._compounds_next = True
        self.refresh(False, 0, True, False, [], [])

    def _footer(self, mode: AnalysisMode) -> QWidget:
        footer = QWidget()
        row = QHBoxLayout(footer)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        switch = _footer_link("Change analysis mode", self.new_session_requested)
        switch.setToolTip(f"This window runs a {mode.display_name.lower()} analysis")
        session = QLabel("Saved session: load its data, then File → Import Session")
        session.setProperty("role", "hint")
        for widget in (
            switch,
            _dot(),
            _footer_link("Quick start guide", self.documentation_requested),
            _dot(),
        ):
            row.addWidget(widget)
        row.addWidget(session, 1)
        # One line when it fits; below that the hint wraps instead of widening the window.
        footer.ensurePolished()
        footer.setMaximumWidth(footer.sizeHint().width())
        session.setWordWrap(True)
        return footer

    def refresh(
        self,
        compounds_loaded: bool,
        compound_count: int,
        can_load_compounds: bool,
        can_load_raw: bool,
        recent_compound_lists: list[str],
        recent_raw_folders: list[str],
    ) -> None:
        # The sidebar already says what is loaded and how many compounds; only the next step lives here.
        self._compounds_next = not compounds_loaded
        if self._compounds_next:
            self.prompt.setText("Drop a compound list here")
            self.primary_button.setText("Load compound list…")
            enabled, paths = can_load_compounds, recent_compound_lists
            signal = self.recent_compound_list_requested
        else:
            self.prompt.setText("Drop the folder of CDF files here")
            self.primary_button.setText("Load raw data folder…")
            enabled, paths = can_load_raw, recent_raw_folders
            signal = self.recent_raw_data_requested
        self.primary_button.setEnabled(enabled)

        while self._recent_box.count():
            widget = self._recent_box.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        for path in paths[:RECENT_LIMIT]:
            self._recent_box.addWidget(_recent_row(path, enabled, signal))
        has_recent = bool(paths)
        self._recent_space.setVisible(has_recent)
        self._recent_heading.setVisible(has_recent)

    def _primary_clicked(self) -> None:
        if self._compounds_next:
            self.load_compounds_requested.emit()
        else:
            self.load_raw_data_requested.emit()

    def eventFilter(self, watched, event):  # noqa: N802 (Qt override)
        kind = event.type()
        if kind == QEvent.Type.DragEnter:
            # Let the window decide first, so the zone only lights for drops it will take.
            handled = watched.event(event)
            self._set_drag_over(event.isAccepted())
            return handled
        if kind in (QEvent.Type.DragLeave, QEvent.Type.Drop):
            self._set_drag_over(False)
        return False

    def _set_drag_over(self, active: bool) -> None:
        set_style_property(self.drop_zone, "dragOver", "true" if active else None)


def _footer_link(text: str, signal) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("startFooterLink")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.clicked.connect(signal.emit)
    return button


def _dot() -> QLabel:
    dot = QLabel("·")
    dot.setProperty("role", "hint")
    return dot


def _recent_row(path: str, enabled: bool, signal) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    button = QPushButton(Path(path).name or path)
    button.setObjectName("recentName")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip(path)
    button.setEnabled(enabled)
    button.clicked.connect(lambda: signal.emit(path))
    where = ElidedLabel(_home_relative(Path(path).parent))
    where.setProperty("role", "hint")
    where.setToolTip(path)
    layout.addWidget(button)
    layout.addWidget(where, 1)
    return row


def _home_relative(folder: Path) -> str:
    try:
        return str(Path("~") / folder.relative_to(Path.home()))
    except ValueError:
        return str(folder)
