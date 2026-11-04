from PySide6.QtCore import Signal

from manic.models.database import get_deleted_samples, restore_samples
from manic.ui.recovery_dialog import RecoveryDialog


class SampleRecoveryDialog(RecoveryDialog):
    samples_restored = Signal(list)

    def __init__(self, parent=None):
        super().__init__("sample", get_deleted_samples, restore_samples, parent)

    def _emit_restored(self, names: list[str]) -> None:
        self.samples_restored.emit(names)
