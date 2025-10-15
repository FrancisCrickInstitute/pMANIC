from PySide6.QtCore import QObject, Signal, Slot

from manic.io.eic_importer import import_eics
from manic.io.eic_importer import regenerate_compound_eics


class CdfImportWorker(QObject):
    progress = Signal(int, int)  # current, total
    finished = Signal(int)  # rows inserted
    failed = Signal(str)

    def __init__(self, directory: str, mass_tolerance: float = 0.2):
        super().__init__()
        self._directory = directory
        self._mass_tolerance = mass_tolerance

    @Slot()
    def run(self):
        try:
            count = import_eics(
                self._directory,
                mass_tol=self._mass_tolerance,
                progress_cb=self.progress.emit,  # <- hand in the signal
            )
            self.finished.emit(count)
        except Exception as exc:
            self.failed.emit(str(exc))


class EicRegenerationWorker(QObject):
    progress = Signal(int, int)  # current, total
    finished = Signal(int)  # eics regenerated
    failed = Signal(str)

    def __init__(self, compound_name: str, tr_window: float, sample_names: list, retention_time: float):
        super().__init__()
        self._compound_name = compound_name
        self._tr_window = tr_window
        self._sample_names = sample_names
        self._retention_time = retention_time

    @Slot()
    def run(self):
        try:
            count = regenerate_compound_eics(
                compound_name=self._compound_name,
                tr_window=self._tr_window,
                sample_names=self._sample_names,
                progress_cb=self.progress.emit,
                retention_time=self._retention_time,
            )
            self.finished.emit(count)
        except Exception as exc:
            self.failed.emit(str(exc))
