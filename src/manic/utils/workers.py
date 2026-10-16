# In src/manic/utils/workers.py
import logging
import threading

from PySide6.QtCore import QObject, QThread, Signal, Slot

from manic.constants import DEFAULT_MASS_TOLERANCE
from manic.io.eic_importer import (
    import_eics,
    regenerate_all_eics_with_mass_tolerance,
    regenerate_compound_eics,
)
from manic.models.session_activity import PendingRegeneration
from manic.models.session_export import reextract_session_eics
from manic.processors.display_deconvolution import plot_display
from manic.processors.eic_correction_manager import ensure_corrections_for_export
from manic.utils.update_check import check_for_update

logger = logging.getLogger(__name__)


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
        self.compound_name = compound_name
        self._tr_window = tr_window
        self._sample_names = sample_names
        self._retention_time = retention_time
        self._pending_regeneration = pending_regeneration

    @Slot()
    def run(self):
        try:
            count = regenerate_compound_eics(
                compound_name=self.compound_name,
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


class SessionReextractionWorker(QObject):
    progress = Signal(int, int)  # current, total
    finished = Signal(object)  # SessionReextraction
    failed = Signal(str)

    def __init__(self, import_path: str, mass_tol: float = DEFAULT_MASS_TOLERANCE):
        super().__init__()
        self._import_path = import_path
        self._mass_tol = mass_tol

    @Slot()
    def run(self):
        try:
            self.finished.emit(
                reextract_session_eics(
                    self._import_path, self._mass_tol, self.progress.emit
                )
            )
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


class ExportWorker(QObject):
    progress = Signal(int)
    finished = Signal(bool)
    failed = Signal(str)

    def __init__(
        self,
        exporter,
        path: str,
        use_legacy_integration: bool = False,
        include_carbon_enrichment: bool = False,
    ):
        super().__init__()
        self._exporter = exporter
        self._path = path
        self._use_legacy_integration = use_legacy_integration
        self._include_carbon_enrichment = include_carbon_enrichment
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def _progress_cb(self, value):
        self.progress.emit(value)
        return not self._cancel_event.is_set()

    @Slot()
    def run(self):
        try:
            ensure_corrections_for_export()
            success = self._exporter.export_to_excel(
                self._path,
                self._progress_cb,
                use_legacy_integration=self._use_legacy_integration,
                include_carbon_enrichment=self._include_carbon_enrichment,
            )
            self.finished.emit(success)
        except Exception as exc:
            self.failed.emit(str(exc))


class DisplayFitWorker(QObject):
    """Fit each plot tile's peaks on a pool thread; the GUI thread draws them."""

    fitted = Signal(int, str, object)  # generation, sample name, PlotDisplay
    finished = Signal(int)  # generation

    def __init__(self, generation: int, jobs: list, use_corrected: bool):
        super().__init__()
        self._generation = generation
        self._jobs = jobs  # (sample name, time, intensity, compound)
        self._use_corrected = use_corrected
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    @Slot()
    def run(self):
        for sample_name, time, intensity, compound in self._jobs:
            if self._cancel_event.is_set():
                return
            try:
                prepared = plot_display(
                    time, intensity, compound, use_corrected=self._use_corrected
                )
            except Exception:
                logger.exception("Display fit failed for %s", sample_name)
                continue
            self.fitted.emit(self._generation, sample_name, prepared)
        self.finished.emit(self._generation)
