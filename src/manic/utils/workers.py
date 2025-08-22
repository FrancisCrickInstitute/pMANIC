from PySide6.QtCore import QObject, Signal, Slot

from manic.io.eic_importer import import_eics
from manic.io.eic_importer import regenerate_compound_eics


class CdfImportWorker(QObject):
    progress = Signal(int, int)  # current, total
    finished = Signal(int)  # rows inserted
    failed = Signal(str)

    def __init__(self, directory: str):
        super().__init__()
        self._directory = directory

    @Slot()
    def run(self):
        try:
            count = import_eics(
                self._directory,
                progress_cb=self.progress.emit,  # <- hand in the signal
            )
            self.finished.emit(count)
        except Exception as exc:
            self.failed.emit(str(exc))


class EicRegenerationWorker(QObject):
    progress = Signal(int, int)  # current, total
    finished = Signal(int)  # eics regenerated
    failed = Signal(str)

    def __init__(self, compound_name: str, tr_window: float, sample_names: list):
        super().__init__()
        self._compound_name = compound_name
        self._tr_window = tr_window
        self._sample_names = sample_names

    @Slot()
    def run(self):
        try:
            count = regenerate_compound_eics(
                compound_name=self._compound_name,
                tr_window=self._tr_window,
                sample_names=self._sample_names,
                progress_cb=self.progress.emit,
            )
            self.finished.emit(count)
        except Exception as exc:
            self.failed.emit(str(exc))
