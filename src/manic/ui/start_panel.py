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
    process_external_requested = Signal()

    def __init__(self, parent=None):
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
        zone.addWidget(self._footer(), 0, Qt.AlignmentFlag.AlignHCenter)
        self._compounds_next = True
        self.refresh(False, True, False, [], [])

    def _footer(self) -> QWidget:
        footer = QWidget()
        lines = QVBoxLayout(footer)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(4)
        self._footer_row = QHBoxLayout()
        self._footer_row.setSpacing(6)
        for widget in (
            _footer_link("Change analysis mode", self.new_session_requested),
            _dot(),
            _footer_link("Quick start guide", self.documentation_requested),
        ):
            self._footer_row.addWidget(widget)
        lines.addLayout(self._footer_row)
        self._rebuild_dot = _dot()
        self._rebuild_link = _footer_link(
            "Rebuild an export without CDF files…", self.process_external_requested
        )
        self._footer_row.addWidget(self._rebuild_dot)
        self._footer_row.addWidget(self._rebuild_link)
        # Narrower than the column above, the rebuild link takes a line of its own.
        footer.setMinimumWidth(
            self._footer_row.sizeHint().width()
            - self._rebuild_dot.sizeHint().width()
            - self._rebuild_link.sizeHint().width()
            - 2 * self._footer_row.spacing()
        )
        self._footer = footer
        return footer

    def resizeEvent(self, event):  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        lines = self._footer.layout()
        room = self.drop_zone.contentsRect().width() - self.drop_zone.layout().contentsMargins().left() * 2
        one_row = self._footer_row.sizeHint().width() + (
            0 if self._footer_row.indexOf(self._rebuild_link) >= 0
            else self._rebuild_dot.sizeHint().width() + self._rebuild_link.sizeHint().width()
            + 2 * self._footer_row.spacing()
        )
        wide = one_row <= room
        if wide == (self._footer_row.indexOf(self._rebuild_link) >= 0):
            return
        if wide:
            self._footer_row.addWidget(self._rebuild_dot)
            self._footer_row.addWidget(self._rebuild_link)
        else:
            lines.addWidget(self._rebuild_link, 0, Qt.AlignmentFlag.AlignHCenter)
        self._rebuild_dot.setVisible(wide)

    def refresh(
        self,
        compounds_loaded: bool,
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
                widget.hide()
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
    button.setEnabled(enabled)
    button.clicked.connect(lambda: signal.emit(path))
    # Middle elision keeps the home and the nearest folders.
    where = ElidedLabel(
        _home_relative(Path(path).parent), mode=Qt.TextElideMode.ElideMiddle, hover=path
    )
    where.setProperty("role", "hint")
    layout.addWidget(button)
    layout.addWidget(where, 1)
    return row


def _home_relative(folder: Path) -> str:
    try:
        return str(Path("~") / folder.relative_to(Path.home()))
    except ValueError:
        return str(folder)
