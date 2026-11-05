"""The internal standard chooser: a filter over the method's compounds, in a popup."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QMenu,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from manic.ui import theme
from manic.utils.paths import resource_path

from .sidebar_widgets import FilterField

NO_STANDARD = "No internal standard"
# Heads the compounds the export cannot calibrate with, as the sidebar's note words it.
NO_AMOUNT = "No amount: exports peak areas"
VISIBLE_ROWS = 10
WIDTH = 280


def _check_icon() -> QIcon:
    """The app's checkmark in the text colour; macOS draws its own jagged."""
    colour = theme.color("text").name()
    path = Path(tempfile.gettempdir()) / f"manic-menu-check-{colour[1:]}.svg"
    if not path.exists():
        svg = Path(resource_path("resources", "checkmark.svg")).read_text()
        path.write_text(svg.replace('fill="white"', f'fill="{colour}"'))
    return QIcon(path.as_posix())


class StandardChooser(QMenu):
    """Type to filter, arrows to move, Return or a click to choose, Esc to cancel.

    Compounds with an amount come first; one heading marks the rest. ``chosen`` carries
    the compound's name, or None for no internal standard."""

    chosen = Signal(object)

    def __init__(
        self, names: list[str], current: str | None, lacking: set[str], parent: QWidget
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.list = QListWidget()
        self.list.setAccessibleName("Internal standard")
        self.list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.filter = FilterField(self.list, "Filter compounds")
        self.filter.setVisible(bool(names))
        self.filter.installEventFilter(self)
        self.filter.filtered.connect(self._on_filtered)
        layout.addWidget(self.filter)
        layout.addWidget(self.list)

        check = _check_icon()
        self.list.setIconSize(QSize(14, 14))
        blank = QPixmap(self.list.iconSize() * self.devicePixelRatio())
        blank.setDevicePixelRatio(self.devicePixelRatio())
        blank.fill(QColor(0, 0, 0, 0))
        self._no_amount: QListWidgetItem | None = None
        order = [None, *(n for n in names if n not in lacking)]
        if lacking:
            order += [NO_AMOUNT, *(n for n in names if n in lacking)]
        for name in order:
            item = QListWidgetItem(name or NO_STANDARD, self.list)
            if name == NO_AMOUNT:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                self._no_amount = item
                continue
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setIcon(check if name == current else QIcon(blank))
            if name == current:
                self._current_row = self.list.row(item)
        if not names:
            hint = QListWidgetItem("Load a compound list first", self.list)
            hint.setFlags(Qt.ItemFlag.NoItemFlags)
        if current not in names:
            self._current_row = 0
        self.list.setCurrentRow(self._current_row)
        rows = min(self.list.count(), VISIBLE_ROWS)
        self.list.setFixedSize(
            WIDTH, rows * self.list.sizeHintForRow(0) + 2 * self.list.frameWidth()
        )
        self.list.itemClicked.connect(self._choose)
        self.list.itemActivated.connect(self._choose)

        action = QWidgetAction(self)
        action.setDefaultWidget(body)
        self.addAction(action)

    def showEvent(self, event):
        super().showEvent(event)
        self.list.scrollToItem(self.list.currentItem(), QListWidget.ScrollHint.PositionAtCenter)
        (self.filter if self.filter.isVisibleTo(self) else self.list).setFocus()

    def _on_filtered(self) -> None:
        """A filter moves to its first matching compound, or to nothing, so Return never
        clears the standard by a stray match; clearing it returns to the current choice.
        No internal standard stays in reach above the matches."""
        self.list.setRowHidden(0, False)
        if self._no_amount is not None:
            start = self.list.row(self._no_amount) + 1
            self.list.setRowHidden(
                start - 1,
                all(self.list.isRowHidden(row) for row in range(start, self.list.count())),
            )
        if not self.filter.text().strip():
            self.list.setCurrentRow(self._current_row)
            return
        first = next(
            (
                row
                for row in range(1, self.list.count())
                if not self.list.isRowHidden(row)
                and self.list.item(row).flags() & Qt.ItemFlag.ItemIsEnabled
            ),
            -1,
        )
        self.list.clearSelection()
        self.list.setCurrentRow(first)

    def eventFilter(self, watched, event):
        if (
            watched is self.filter
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        ):
            self._choose(self.list.currentItem())
            return True
        return super().eventFilter(watched, event)

    def _choose(self, item: QListWidgetItem | None) -> None:
        # A click also activates on some platforms; the first one closes the chooser.
        if not self.isVisible() or item is None or item.isHidden():
            return
        if not item.flags() & Qt.ItemFlag.ItemIsEnabled:
            return
        self.close()
        self.chosen.emit(item.data(Qt.ItemDataRole.UserRole))
