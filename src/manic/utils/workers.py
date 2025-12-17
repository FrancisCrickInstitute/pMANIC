# In src/manic/utils/workers.py
import json
import urllib.request
from typing import Tuple

from PySide6.QtCore import QObject, QThread, Signal, Slot

from manic.__version__ import __version_info__
from manic.io.eic_importer import (
    import_eics,
    regenerate_all_eics_with_mass_tolerance,
    regenerate_compound_eics,
)


class UpdateCheckWorker(QThread):
    # Signal emits: (has_update, latest_version_str, download_url)
    result = Signal(bool, str, str)

    # Configure your repository here
    REPO_OWNER = "FrancisCrickInstitute"
    REPO_NAME = "pMANIC"

    def run(self):
        try:
            url = f"https://api.github.com/repos/{self.REPO_OWNER}/{self.REPO_NAME}/releases/latest"

            # Create request with User-Agent (required by GitHub API)
            req = urllib.request.Request(
                url, headers={"User-Agent": "MANIC-Update-Checker"}
            )

            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())

                tag_name = data.get("tag_name", "").lstrip("v")
                html_url = data.get("html_url", "")

                if not tag_name:
                    self.result.emit(False, "", "")
                    return

                # Parse versions into tuples for comparison (e.g., "4.0.1" -> (4, 0, 1))
                latest_version = self._parse_version(tag_name)
                current_version = __version_info__

                if latest_version > current_version:
                    self.result.emit(True, tag_name, html_url)
                else:
                    self.result.emit(False, tag_name, html_url)

        except Exception as e:
            # Silently fail on network errors or api limits
            print(f"Update check failed: {e}")
            self.result.emit(False, "", "")

    def _parse_version(self, version_str: str) -> Tuple[int, ...]:
        """Convert '1.2.3' string to (1, 2, 3) tuple."""
        try:
            # Remove any non-numeric suffixes if necessary
            clean_ver = version_str.split("-")[0]
            return tuple(map(int, clean_ver.split(".")))
        except ValueError:
            return (0, 0, 0)


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
        retention_time: float,
    ):
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
