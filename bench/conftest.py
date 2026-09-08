"""Fixtures for the performance bench. See docs/Benchmarking.md.

The first run on a machine generates testdata/bench (gitignored) and builds one
populated database per dataset under bench/cache. Later runs reuse both.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from manic.io.compound_reader import read_compound
from manic.io.compounds_import import import_compound_excel
from manic.io.eic_importer import import_eics
from manic.io.eic_reader import read_eics_batch
from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.processors.eic_correction_manager import process_all_corrections

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")

ROOT = Path(__file__).resolve().parents[1]
BENCH_DATA = ROOT / "testdata" / "bench"
CACHE_DIR = ROOT / "bench" / "cache"
GENERATOR = ROOT / "scripts" / "generate_bench_data.py"

DEFAULT_WINDOWS = 12
FULL_WINDOWS = 60
DEFAULT_NAVIGATIONS = 10

# Generator scenarios that make a deconvolution window expensive. The corpus is
# drawn round-robin from these so any prefix is a mix.
HARD_SCENARIOS = ("OVERLAP_NEIGHBOUR", "NEAR_COELUTION", "SHOULDER", "BROAD_TAILING", "NOISY")


@dataclass(frozen=True)
class Case:
    name: str
    mode: AnalysisMode

    @property
    def cdf_dir(self) -> Path:
        return BENCH_DATA / self.name

    @property
    def compounds_csv(self) -> Path:
        return self.cdf_dir / "compounds.csv"

    @property
    def labelled(self) -> bool:
        return self.mode is AnalysisMode.LABELLED

    @cached_property
    def manifest(self) -> dict:
        return json.loads((self.cdf_dir / "manifest.json").read_text(encoding="utf-8"))

    @property
    def internal_standard(self) -> str:
        return self.manifest["internal_standard"]

    @property
    def n_compounds(self) -> int:
        return int(self.manifest["n_compounds"])

    @property
    def n_samples(self) -> int:
        return int(self.manifest["n_samples"])

    def corpus_keys(self, n: int) -> list[tuple[str, str]]:
        """(sample, compound) cells the generator planted as hard, interleaved by scenario."""
        by_scenario: dict[str, list[tuple[str, str]]] = {s: [] for s in HARD_SCENARIOS}
        for truth in sorted(self.manifest["truths"], key=lambda t: (t["compound"], t["sample"])):
            for scenario in HARD_SCENARIOS:
                if scenario in truth["scenarios"] and truth["present"]:
                    by_scenario[scenario].append((truth["sample"], truth["compound"]))
                    break
        out: list[tuple[str, str]] = []
        for i in range(-(-n // len(HARD_SCENARIOS))):
            out.extend(cells[i] for cells in by_scenario.values() if i < len(cells))
        return out[:n]


CASES = {
    "labelled": Case("labelled", AnalysisMode.LABELLED),
    "unlabelled": Case("unlabelled", AnalysisMode.UNLABELLED),
}


def pytest_addoption(parser):
    parser.addoption(
        "--bench-full",
        action="store_true",
        help="60 deconvolution windows at both stringency levels and every compound navigated.",
    )
    parser.addoption("--bench-repeat", type=int, default=1, help="Rounds per stage (default 1).")


@pytest.fixture(scope="session")
def full(request) -> bool:
    return bool(request.config.getoption("--bench-full"))


@pytest.fixture(scope="session")
def repeat(request) -> int:
    return int(request.config.getoption("--bench-repeat"))


@pytest.fixture(scope="session")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture(scope="module", params=list(CASES), ids=list(CASES))
def case(request) -> Case:
    case = CASES[request.param]
    if not (case.cdf_dir / "manifest.json").exists():
        print(f"\ngenerating {case.name} dataset (first run only)", flush=True)
        subprocess.check_call([sys.executable, str(GENERATOR), "--mode", case.name], cwd=ROOT)
    return case


@pytest.fixture
def db(case):
    """Populated, corrected database for ``case``. Cached across runs, read-only to tests."""
    previous = database.DB_FILE
    yield cached_db(case)
    database.DB_FILE = previous


@pytest.fixture
def db_copy(case, db, tmp_path):
    """A throwaway copy for stages that write."""
    path = tmp_path / "copy.db"
    shutil.copyfile(db, path)
    database.DB_FILE = path
    yield path
    database.DB_FILE = db


@pytest.fixture
def corpus(case, db, full):
    """Hard deconvolution windows as (compound, eic) pairs."""
    keys = case.corpus_keys(FULL_WINDOWS if full else DEFAULT_WINDOWS)
    by_compound: dict[str, list[str]] = {}
    for sample, compound in keys:
        by_compound.setdefault(compound, []).append(sample)
    windows = []
    for name, samples in by_compound.items():
        compound = read_compound(name)
        windows.extend((compound, eic) for eic in read_eics_batch(samples, compound, use_corrected=False))
    assert len(windows) == len(keys)
    return windows


@pytest.fixture
def importer(case):
    return lambda db_path: import_dataset(case, db_path)


@pytest.fixture
def navigation(case, full) -> list[int]:
    return navigation_indices(case.n_compounds, full)


def import_dataset(case: Case, db_path: Path) -> int:
    """Import the whole dataset into a fresh database at ``db_path`` and leave it selected."""
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database.DB_FILE = db_path
    database.init_db()
    import_compound_excel(case.compounds_csv, case.mode)
    return import_eics(case.cdf_dir, mass_tol=0.2, rt_window=0.2)


def cached_db(case: Case) -> Path:
    """Rebuilt only when the dataset or schema changes."""
    digest = hashlib.sha256()
    digest.update((case.cdf_dir / "manifest.json").read_bytes())
    digest.update((ROOT / "src" / "manic" / "models" / "schema.sql").read_bytes())
    path = CACHE_DIR / f"{case.name}-{digest.hexdigest()[:12]}.db"
    if not path.exists():
        for stale in CACHE_DIR.glob(f"{case.name}-*.db"):
            stale.unlink()
        print(f"\nbuilding {path.name} (first run only)", flush=True)
        import_dataset(case, path)
        if case.labelled:
            process_all_corrections()
    database.DB_FILE = path
    return path


def navigation_indices(n_compounds: int, full: bool) -> list[int]:
    if full:
        return list(range(1, n_compounds))
    step = (n_compounds - 1) / (DEFAULT_NAVIGATIONS - 1)
    return [round(i * step) for i in range(1, DEFAULT_NAVIGATIONS)]
