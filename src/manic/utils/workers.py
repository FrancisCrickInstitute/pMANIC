# In src/manic/utils/workers.py
from PySide6.QtCore import QObject, QThread, Signal, Slot

from manic.constants import DEFAULT_MASS_TOLERANCE
from manic.io.eic_importer import (
    import_eics,
    regenerate_all_eics_with_mass_tolerance,
    regenerate_compound_eics,
)
from manic.models.session_activity import PendingRegeneration
from manic.utils.update_check import check_for_update


class UpdateCheckWorker(QThread):
    # Signal emits: (success, has_update, latest_version_str, download_url)
    result = Signal(bool, bool, str, str)

    def run(self):
        outcome = check_for_update()
        self.result.emit(
            outcome.success, outcome.has_update, outcome.latest_version, outcome.url
        )


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

    def __init__(
        self,
        compound_name: str,
        tr_window: float,
        sample_names: list,
        retention_time: float | dict[str, float],
        pending_regeneration: PendingRegeneration | None = None,
        mass_tol: float = DEFAULT_MASS_TOLERANCE,
    ):
        super().__init__()
        self._mass_tol = mass_tol
        self._compound_name = compound_name
        self._tr_window = tr_window
        self._sample_names = sample_names
        self._retention_time = retention_time
        self._pending_regeneration = pending_regeneration

    @Slot()
    def run(self):
        try:
            count = regenerate_compound_eics(
                compound_name=self._compound_name,
                tr_window=self._tr_window,
                sample_names=self._sample_names,
                mass_tol=self._mass_tol,
                progress_cb=self.progress.emit,
                retention_time=self._retention_time,
                pending_regeneration=self._pending_regeneration,
            )
            self.finished.emit(count)
        except Exception as exc:
            self.failed.emit(str(exc))


class MassToleranceReloadWorker(QObject):
    progress = Signal(int, int)  # current, total
    finished = Signal(int)  # eics regenerated
    failed = Signal(str)

    def __init__(self, mass_tol: float, rt_window: float = 0.2):
        super().__init__()
        self._mass_tol = mass_tol
        self._rt_window = rt_window

    @Slot()
    def run(self):
        try:
            count = regenerate_all_eics_with_mass_tolerance(
                mass_tol=self._mass_tol,
                rt_window=self._rt_window,
                progress_cb=self.progress.emit,
            )
            self.finished.emit(count)
        except Exception as exc:
            self.failed.emit(str(exc))
