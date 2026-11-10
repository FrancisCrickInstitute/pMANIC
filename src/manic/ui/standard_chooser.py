"""The internal standard chooser: a filter over the method's compounds, in a popup."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from manic.ui import theme
from manic.utils.paths import resource_path

from .sidebar_widgets import FilterField

NO_STANDARD = "No internal standard"
# Heads the compounds the export cannot calibrate with.
NO_AMOUNT = "No amount: exports peak areas"
NO_MATCH = "No matching compounds"
VISIBLE_ROWS = 10
WIDTH = 280


def _check_icon() -> QIcon:
    """The app's checkmark, in the text colour, for the current choice."""
    colour = theme.color("text").name()
    path = Path(tempfile.gettempdir()) / f"manic-menu-check-{colour[1:]}.svg"
    if not path.exists():
        svg = Path(resource_path("resources", "checkmark.svg")).read_text()
        path.write_text(svg.replace('fill="white"', f'fill="{colour}"'))
    return QIcon(path.as_posix())


class StandardChooser(QFrame):
    """Type to filter, arrows to move, Return or a click to choose, Esc to cancel.

    Compounds with an amount come first; one heading marks the rest. ``chosen`` carries
    the compound's name, or None for no internal standard."""

    chosen = Signal(object)

    def __init__(
        self, names: list[str], current: str | None, lacking: set[str], parent: QWidget
    ):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("standardChooser")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.list = QListWidget()
        self.list.setAccessibleName("Internal standard")
        # As in the sidebar lists: long names share a prefix, so keep their ends; hover shows all.
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.filter = FilterField(self.list, "Filter compounds")
        self.filter.installEventFilter(self)
        self.filter.filtered.connect(self._on_filtered)
        layout.addWidget(self.filter)
        layout.addWidget(self.list)
        # Only once parented: a parentless widget shown is its own window, which takes
        # activation on Windows and so closes the popup.
        self.filter.setVisible(bool(names))

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
            item.setToolTip(name or "")
            item.setIcon(check if name == current else QIcon(blank))
            if name == current:
                self._current_row = self.list.row(item)
        self._no_match = QListWidgetItem(
            NO_MATCH if names else "Load a compound list first", self.list
        )
        self._no_match.setFlags(Qt.ItemFlag.NoItemFlags)
        self._no_match.setHidden(bool(names))
        if current not in names:
            self._current_row = 0
        self.list.setCurrentRow(self._current_row)
        self._opened_above = False
        self._fit_rows()
        self.list.itemClicked.connect(self._choose)
        self.list.itemActivated.connect(self._choose)

    def popup(self, pos: QPoint) -> None:
        self.adjustSize()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        x = min(max(pos.x(), area.left()), area.right() - self.width())
        self._opened_above = pos.y() + self.height() > area.bottom()
        y = pos.y() - self.height() if self._opened_above else pos.y()
        self.move(x, max(y, area.top()))
        self.show()

    def _fit_rows(self) -> None:
        """Size the list to its shown rows, up to VISIBLE_ROWS, keeping the edge
        nearest the anchor in place."""
        shown = sum(not self.list.isRowHidden(r) for r in range(self.list.count()))
        bottom = self.geometry().bottom()
        self.list.setFixedSize(
            WIDTH,
            min(shown, VISIBLE_ROWS) * self.list.sizeHintForRow(0) + 2 * self.list.frameWidth(),
        )
        self.adjustSize()
        if self._opened_above:
            self.move(self.x(), bottom - self.height() + 1)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.list.scrollToItem(self.list.currentItem(), QListWidget.ScrollHint.PositionAtCenter)
        (self.filter if self.filter.isVisibleTo(self) else self.list).setFocus()

    def _on_filtered(self) -> None:
        """A filter moves to its first matching compound, or to nothing, so Return never
        clears the standard by a stray match; clearing it returns to the current choice.
        No internal standard stays in reach above the matches."""
        self.list.setRowHidden(0, False)
        self._no_match.setHidden(True)
        if self._no_amount is not None:
            start = self.list.row(self._no_amount) + 1
            self.list.setRowHidden(
                start - 1,
                all(self.list.isRowHidden(row) for row in range(start, self.list.count())),
            )
        if not self.filter.text().strip():
            self.list.setCurrentRow(self._current_row)
            self._fit_rows()
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
        self._no_match.setHidden(first != -1)
        self.list.clearSelection()
        self.list.setCurrentRow(first)
        self._fit_rows()

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
