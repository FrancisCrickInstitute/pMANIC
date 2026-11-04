from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
)

from manic.ui.dialog_kit import (
    MARGIN,
    button_box,
    description_label,
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
        self.resize(420, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        layout.setSpacing(8)
        layout.addWidget(title_label(f"Recover deleted {noun}s"))
        layout.addWidget(
            description_label(
                f"Click the {noun}s to restore, then choose Restore selected. "
                f"Restored {noun}s return to the {noun} list."
            )
        )
        layout.addSpacing(8)

        self.item_list = QListWidget()
        self.item_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.item_list.itemSelectionChanged.connect(self._update_button_state)
        empty = QLabel(
            f"No deleted {noun}s.\nDeleting a {noun} from its list moves it here."
        )
        empty.setProperty("role", "description")
        empty.setAlignment(Qt.AlignCenter)
        self._body = QStackedWidget()
        self._body.addWidget(self.item_list)
        self._body.addWidget(empty)
        layout.addWidget(self._body, stretch=1)

        self.status_label = hint_label("")
        layout.addWidget(self.status_label)

        layout.addSpacing(8)
        buttons, self.restore_btn = button_box("Restore selected")
        self.restore_btn.setEnabled(False)
        buttons.accepted.connect(self._on_restore_clicked)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_items()

    def _emit_restored(self, names: list[str]) -> None:
        raise NotImplementedError

    def _load_items(self) -> None:
        self.item_list.clear()
        deleted = self._load_deleted()
        self.item_list.addItems(deleted)
        self._body.setCurrentIndex(0 if deleted else 1)
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
