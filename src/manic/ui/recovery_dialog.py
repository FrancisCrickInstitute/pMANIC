from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QMessageBox,
    QVBoxLayout,
)

from manic.ui.dialog_kit import (
    MARGIN,
    button_box,
    hint_label,
    style_dialog,
    title_label,
    window_title,
)


class RecoveryDialog(QDialog):
    """Lists soft-deleted items (compounds or samples) and restores the chosen ones."""

    def __init__(
        self,
        noun: str,
        load_deleted: Callable[[], list[str]],
        restore: Callable[[list[str]], int],
        parent=None,
    ):
        super().__init__(parent)
        self._noun = noun
        self._load_deleted = load_deleted
        self._restore = restore
        self.setWindowTitle(window_title(f"Recover Deleted {noun.title()}s"))
        style_dialog(self)
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        layout.setSpacing(8)
        self.title = title_label(f"Recover deleted {noun}s")
        layout.addWidget(self.title)

        self.item_list = QListWidget()
        self.item_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        # As in the sidebar lists: names that differ near their ends keep them; hover shows all.
        self.item_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.item_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.item_list.itemSelectionChanged.connect(self._update_button_state)
        layout.addWidget(self.item_list, stretch=1)

        self.status_label = hint_label("")
        layout.addWidget(self.status_label)

        layout.addSpacing(8)
        self.buttons, self.restore_btn = button_box("Restore selected")
        self.restore_btn.setEnabled(False)
        self.buttons.accepted.connect(self._on_restore_clicked)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._load_items()

    def _emit_restored(self, names: list[str]) -> None:
        raise NotImplementedError

    def _load_items(self) -> None:
        self.item_list.clear()
        deleted = self._load_deleted()
        self.item_list.addItems(deleted)
        for row, name in enumerate(deleted):
            self.item_list.item(row).setToolTip(name)
        if deleted:
            # As tall as the names, up to twelve rows; a longer list scrolls.
            rows = min(len(deleted), 12)
            list_ = self.item_list
            chrome = self.sizeHint().height() - list_.sizeHint().height()
            self.resize(420, chrome + rows * list_.sizeHintForRow(0) + 2 * list_.frameWidth())
        else:
            # Nothing to restore: say so and offer only Close.
            self.title.setText(f"No deleted {self._noun}s")
            for widget in (self.item_list, self.status_label):
                widget.hide()
            self.restore_btn.hide()
            for button in self.buttons.buttons():
                if self.buttons.buttonRole(button) == QDialogButtonBox.RejectRole:
                    button.setText("Close")
        self._update_button_state()

    def _update_button_state(self) -> None:
        total = self.item_list.count()
        selected = len(self.item_list.selectedItems())
        self.restore_btn.setEnabled(selected > 0)
        if total:
            self.status_label.setText(f"{selected} of {total} selected")
        self.status_label.setVisible(bool(total))

    def _on_restore_clicked(self) -> None:
        names = [item.text() for item in self.item_list.selectedItems()]
        if not names:
            return
        if self._restore(names) > 0:
            # The UI refreshes from the database, so emitting the requested names
            # is fine even if some were already restored elsewhere.
            self._emit_restored(names)
            self.accept()
        else:
            QMessageBox.warning(self, "Restore Failed", f"No {self._noun}s were restored.")
