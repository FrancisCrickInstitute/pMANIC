from PySide6.QtCore import QObject, Signal, Slot

from manic.io.eic_importer import import_eics


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
