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
from functools import cached_property, lru_cache
from pathlib import Path

import pytest
import xlrd
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
GENERATOR_HELPER = ROOT / "scripts" / "synthetic_gcms.py"
LABELLED_XLS = ROOT / "example_compounds_list.xls"

DEFAULT_WINDOWS = 12
FULL_WINDOWS = 60
DEFAULT_NAVIGATIONS = 10
DEFAULT_SEED = 1
DEFAULT_SAMPLES = 30
DEFAULT_SCAN_DT_S = 0.5
DEFAULT_UNLABELLED_COMPOUNDS = 100

# Generator scenarios that make a deconvolution window expensive. The corpus is
# drawn round-robin from these so any prefix is a mix.
HARD_SCENARIOS = (
    "OVERLAP_NEIGHBOUR",
    "NEAR_COELUTION",
    "SHOULDER",
    "BROAD_TAILING",
    "NOISY",
)


@dataclass(frozen=True)
class BenchConfig:
    full: bool
    seed: int
    n_samples: int
    scan_dt_s: float

    @property
    def id(self) -> str:
        size = "full" if self.full else "default"
        generator = _source_fingerprint()[:12]
        return (
            f"{size}-seed{self.seed}-n{self.n_samples}-"
            f"dt{self.scan_dt_s:g}-g{generator}"
        )

    @property
    def n_windows(self) -> int:
        return FULL_WINDOWS if self.full else DEFAULT_WINDOWS


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
    parser.addoption(
        "--bench-repeat",
        type=int,
        default=1,
        help="Rounds per stage (default 1).",
    )
    parser.addoption(
        "--bench-scan-dt-s",
        type=float,
        default=DEFAULT_SCAN_DT_S,
        help="Synthetic scan interval in seconds (default 0.5; use 0.1 for dense data).",
    )


def _bench_config(pytest_config) -> BenchConfig:
    return BenchConfig(
        full=bool(pytest_config.getoption("--bench-full")),
        seed=DEFAULT_SEED,
        n_samples=DEFAULT_SAMPLES,
        scan_dt_s=float(pytest_config.getoption("--bench-scan-dt-s")),
    )


def pytest_generate_tests(metafunc):
    if "bench_config" not in metafunc.fixturenames:
        return
    config = _bench_config(metafunc.config)
    metafunc.parametrize(
        "bench_config",
        [config.id],
        ids=[config.id],
        indirect=True,
        scope="session",
    )
    if "navigation_slot" in metafunc.fixturenames:
        count = (
            _max_generated_compounds() - 1
            if config.full
            else DEFAULT_NAVIGATIONS - 1
        )
        metafunc.parametrize(
            "navigation_slot",
            range(1, count + 1),
            ids=[f"nav-{index:03d}" for index in range(1, count + 1)],
        )


@pytest.fixture(scope="session")
def bench_config(request) -> BenchConfig:
    config = _bench_config(request.config)
    assert request.param == config.id
    if config.scan_dt_s <= 0:
        pytest.fail("--bench-scan-dt-s must be greater than zero")
    return config


@pytest.fixture(scope="session")
def full(bench_config) -> bool:
    return bench_config.full


@pytest.fixture(scope="session")
def repeat(request) -> int:
    return int(request.config.getoption("--bench-repeat"))


@pytest.fixture(scope="session")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture(scope="module", params=list(CASES), ids=list(CASES))
def case(request, bench_config) -> Case:
    case = CASES[request.param]
    if not corpus_matches(case, bench_config):
        print(f"\ngenerating {case.name} dataset ({bench_config.id})", flush=True)
        subprocess.check_call(
            [
                sys.executable,
                str(GENERATOR),
                "--mode",
                case.name,
                "--seed",
                str(bench_config.seed),
                "--n-samples",
                str(bench_config.n_samples),
                "--scan-dt-s",
                str(bench_config.scan_dt_s),
            ],
            cwd=ROOT,
        )
        corpus_matches.cache_clear()
        assert corpus_matches(case, bench_config)
    return case


@pytest.fixture(scope="module")
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
def corpus(case, db, bench_config):
    """Hard deconvolution windows as (compound, eic) pairs."""
    keys = case.corpus_keys(bench_config.n_windows)
    by_compound: dict[str, list[str]] = {}
    for sample, compound in keys:
        by_compound.setdefault(compound, []).append(sample)
    windows = []
    for name, samples in by_compound.items():
        compound = read_compound(name)
        windows.extend(
            (compound, eic)
            for eic in read_eics_batch(
                samples,
                compound,
                use_corrected=False,
            )
        )
    assert len(windows) == len(keys)
    return windows


@pytest.fixture
def importer(case):
    return lambda db_path: import_dataset(case, db_path)


@pytest.fixture
def navigation_index(case, bench_config, navigation_slot) -> int:
    if bench_config.full:
        if navigation_slot >= case.n_compounds:
            pytest.skip("navigation slot is outside this dataset")
        return navigation_slot
    return navigation_indices(case.n_compounds)[navigation_slot - 1]


def import_dataset(case: Case, db_path: Path) -> int:
    """Import the whole dataset into a fresh database at ``db_path`` and leave it selected."""
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database.DB_FILE = db_path
    database.init_db()
    import_compound_excel(case.compounds_csv, case.mode)
    return import_eics(case.cdf_dir, mass_tol=0.2, rt_window=0.2)


@lru_cache(maxsize=1)
def _source_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in (GENERATOR, GENERATOR_HELPER, LABELLED_XLS):
        digest.update(path.name.encode("utf-8"))
        digest.update(bytes.fromhex(_file_sha256(path)))
    return digest.hexdigest()


@lru_cache(maxsize=1)
def _max_generated_compounds() -> int:
    workbook = xlrd.open_workbook(LABELLED_XLS, on_demand=True)
    try:
        labelled = workbook.sheet_by_index(0).nrows - 1
    finally:
        workbook.release_resources()
    return max(labelled, DEFAULT_UNLABELLED_COMPOUNDS)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_fingerprint(manifest: dict) -> str:
    unsigned = dict(manifest)
    recorded = unsigned.pop("manifest_fingerprint", None)
    if not recorded:
        return ""
    canonical = json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    actual = hashlib.sha256(canonical).hexdigest()
    return actual if actual == recorded else ""


@lru_cache(maxsize=None)
def corpus_matches(case: Case, config: BenchConfig) -> bool:
    manifest_path = case.cdf_dir / "manifest.json"
    compounds_path = case.cdf_dir / "compounds.csv"
    if not manifest_path.exists() or not compounds_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    expected = {
        "mode": case.name,
        "seed": config.seed,
        "n_samples": config.n_samples,
        "scan_dt_s": config.scan_dt_s,
        "generator_fingerprint": _source_fingerprint(),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        return False
    if not _manifest_fingerprint(manifest):
        return False
    sample_names = {sample["name"] for sample in manifest.get("samples", ())}
    cdf_names = {path.stem for path in case.cdf_dir.glob("*.cdf")}
    if len(sample_names) != config.n_samples or sample_names != cdf_names:
        return False
    expected_artifacts = {"compounds.csv", *(f"{name}.cdf" for name in sample_names)}
    artifact_hashes = manifest.get("artifact_hashes", {})
    if set(artifact_hashes) != expected_artifacts:
        return False
    return all(
        (case.cdf_dir / name).is_file()
        and _file_sha256(case.cdf_dir / name) == expected_hash
        for name, expected_hash in artifact_hashes.items()
    )


def _update_digest(digest, path: Path) -> None:
    digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)


@lru_cache(maxsize=None)
def _database_cache_digest(case: Case) -> str:
    digest = hashlib.sha256()
    for path in (
        case.cdf_dir / "manifest.json",
        case.compounds_csv,
        *sorted(case.cdf_dir.glob("*.cdf")),
        *sorted((ROOT / "src" / "manic").rglob("*.py")),
        ROOT / "src" / "manic" / "models" / "schema.sql",
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
        Path(__file__),
    ):
        _update_digest(digest, path)
    return digest.hexdigest()


def cached_db(case: Case) -> Path:
    """Rebuilt whenever the generated data or application code changes."""
    digest = _database_cache_digest(case)
    path = CACHE_DIR / f"{case.name}-{digest[:16]}.db"
    if not path.exists():
        for stale in CACHE_DIR.glob(f"{case.name}-*.db"):
            stale.unlink()
        print(f"\nbuilding {path.name} (first run only)", flush=True)
        import_dataset(case, path)
        if case.labelled:
            process_all_corrections()
    database.DB_FILE = path
    return path


def navigation_indices(n_compounds: int) -> list[int]:
    step = (n_compounds - 1) / (DEFAULT_NAVIGATIONS - 1)
    return [round(i * step) for i in range(1, DEFAULT_NAVIGATIONS)]
