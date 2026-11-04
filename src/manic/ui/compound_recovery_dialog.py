from PySide6.QtCore import Signal

from manic.models.database import get_deleted_compounds, restore_compounds
from manic.ui.recovery_dialog import RecoveryDialog


class CompoundRecoveryDialog(RecoveryDialog):
    compounds_restored = Signal(list)

    def __init__(self, parent=None):
        super().__init__("compound", get_deleted_compounds, restore_compounds, parent)

    def _emit_restored(self, names: list[str]) -> None:
        self.compounds_restored.emit(names)
