"""
Data processing tests for MANIC.
Combines tests for EIC extraction, processing, correction management,
and data flow through the application.
"""

import zlib

import numpy as np
import pytest
from types import SimpleNamespace

from netCDF4 import Dataset

import manic.io.cdf_data_extractor as cdf_data_extractor
from manic.io.cdf_data_extractor import (
    _extract_ms_at_time_from_cdf_data,
    ensure_ms_data_for_time,
)
from manic.io.cdf_reader import CdfFileData, read_cdf_file
from manic.io.eic_importer import _extract_eic_optimized, import_eics
from manic.io.ms_reader import read_ms_at_time, store_ms_data_batch
from manic.io.tic_reader import read_tic, store_tic_data
from manic.models import database
from manic.processors.eic_calculator import extract_eic
from manic.processors.integration import calculate_peak_areas
import manic.processors.eic_processing as eic_processing


# ============================================================================
# EIC EXTRACTION AND CALCULATION TESTS
# ============================================================================

def make_cdf(sample_name="S1"):
    """Helper function to create a mock CDF file data structure."""
    # Three scans, each with 3 masses (target, +1, +2)
    scan_time = np.array([60.0, 70.0, 80.0])  # seconds
    mass = np.array([
        100.0, 101.0, 102.0,  # scan 0
        100.0, 101.0, 102.0,  # scan 1
        100.0, 101.0, 102.0,  # scan 2
    ])
    # Intensities per mass per scan: simple increasing pattern
    intensity = np.array([
        10.0, 4.0, 2.0,   # scan 0
        20.0, 8.0, 4.0,   # scan 1
        30.0, 12.0, 6.0,  # scan 2
    ])
    scan_index = np.array([0, 3, 6])
    point_count = np.array([3, 3, 3])
    total_intensity = np.array([16.0, 32.0, 48.0])
    return CdfFileData(
        sample_name=sample_name,
        file_path=f"/fake/{sample_name}.cdf",
        scan_time=scan_time,
        mass=mass,
        intensity=intensity,
        scan_index=scan_index,
        point_count=point_count,
        total_intensity=total_intensity,
    )


def test_extract_ms_at_time_converts_seconds_to_minutes():
    cdf = make_cdf()
    target_time = 70.0 / 60.0  # minutes

    mz, intensities, actual_time = _extract_ms_at_time_from_cdf_data(
        cdf,
        target_time,
        tolerance=0.2,
    )

    assert actual_time == pytest.approx(target_time)
    assert mz.size == intensities.size == 3


def test_ensure_ms_data_reuses_close_cached_data(monkeypatch):
    sample = "SampleA"
    retention_time = 1.25
    cached = SimpleNamespace(time=retention_time + 0.005, mz=np.array([100.0]), intensity=np.array([10.0]))
    called = {"refresh": False}

    monkeypatch.setattr(cdf_data_extractor, "read_ms_at_time", lambda *args, **kwargs: cached)

    def fake_extract(*args, **kwargs):
        called["refresh"] = True
        return SimpleNamespace(time=retention_time, mz=np.array([99.0]), intensity=np.array([5.0]))

    monkeypatch.setattr(cdf_data_extractor, "extract_ms_on_demand", fake_extract)

    result = ensure_ms_data_for_time(
        sample,
        retention_time,
        tolerance=0.1,
        refresh_threshold=0.01,
    )

    assert result is cached
    assert called["refresh"] is False


def test_ensure_ms_data_refreshes_when_cache_is_stale(monkeypatch):
    sample = "SampleB"
    retention_time = 1.5
    stale = SimpleNamespace(time=retention_time + 0.2, mz=np.array([100.0]), intensity=np.array([1.0]))
    refreshed = SimpleNamespace(time=retention_time, mz=np.array([101.0]), intensity=np.array([5.0]))
    called = {"refresh": 0}

    monkeypatch.setattr(cdf_data_extractor, "read_ms_at_time", lambda *args, **kwargs: stale)

    def fake_extract(*args, **kwargs):
        called["refresh"] += 1
        return refreshed

    monkeypatch.setattr(cdf_data_extractor, "extract_ms_on_demand", fake_extract)

    result = ensure_ms_data_for_time(
        sample,
        retention_time,
        tolerance=0.1,
        refresh_threshold=0.05,
    )

    assert result is refreshed
    assert called["refresh"] == 1


def test_import_stores_one_row_per_spectrum_and_per_tic():
    database.init_db()
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO samples (sample_name, file_name, deleted) "
            "VALUES ('S1', '/missing/S1.cdf', 0)"
        )
        before = conn.total_changes
        assert store_tic_data("S1", np.array([60.0, 70.0, 80.0]), np.array([16.0, 32.0, 48.0]), conn)
        assert store_ms_data_batch(
            "S1",
            [
                (1.0, np.array([100.0, 101.0, 102.0]), np.array([10.0, 4.0, 2.0])),
                (1.5, np.array([100.0, 101.0, 102.0]), np.array([30.0, 0.0, 6.0])),
            ],
            conn,
        )
        rows_written = conn.total_changes - before

    assert rows_written == 3

    tic = read_tic("S1")
    assert tic.time.tolist() == [60.0, 70.0, 80.0]
    assert tic.intensity.tolist() == [16.0, 32.0, 48.0]

    # The CDF path does not exist, so the detailed view falls back to the stored spectrum.
    ms = ensure_ms_data_for_time("S1", 1.5)
    assert ms.time == 1.5
    assert ms.mz.tolist() == [100.0, 102.0]
    assert ms.intensity.tolist() == [30.0, 6.0]


def test_import_drops_missing_cdf_intensities_from_spectrum_and_tic(tmp_path):
    from netCDF4 import Dataset

    with Dataset(tmp_path / "S1.cdf", "w", format="NETCDF3_CLASSIC") as cdf:
        cdf.createDimension("scan", 2)
        cdf.createDimension("point", 3)
        for name, dtype, dim, values in [
            ("scan_acquisition_time", "f8", "scan", [60.0, 66.0]),
            ("scan_index", "i4", "scan", [0, 3]),
            ("point_count", "i4", "scan", [3, 0]),
            ("mass_values", "f8", "point", [100.0, 101.0, 102.0]),
        ]:
            cdf.createVariable(name, dtype, (dim,))[:] = values
        cdf.createVariable("intensity_values", "f8", ("point",), fill_value=1e20)[:] = (
            np.ma.array([10.0, 0.0, 20.0], mask=[False, True, False])
        )
        cdf.createVariable("total_intensity", "f8", ("scan",), fill_value=1e20)[:] = (
            np.ma.array([30.0, 0.0], mask=[False, True])
        )
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, mass0, label_atoms) "
            "VALUES ('C1', 1.0, 100.0, 0)"
        )

    import_eics(tmp_path)

    ms = read_ms_at_time("S1", 1.0)
    assert ms.mz.tolist() == [100.0, 102.0]
    assert ms.intensity.tolist() == [10.0, 20.0]
    tic = read_tic("S1")
    assert tic.time.tolist() == [1.0]
    assert tic.intensity.tolist() == [30.0]


def test_init_db_migrates_row_per_point_tic_and_spectra():
    with database.get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE tic_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_name TEXT NOT NULL,
                time REAL NOT NULL,
                intensity REAL NOT NULL,
                deleted INTEGER DEFAULT 0,
                UNIQUE(sample_name, time)
            );
            CREATE TABLE ms_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_name TEXT NOT NULL,
                time REAL NOT NULL,
                mz REAL NOT NULL,
                intensity REAL NOT NULL,
                deleted INTEGER DEFAULT 0,
                UNIQUE(sample_name, time, mz)
            );
            INSERT INTO samples (sample_name, file_name, deleted) VALUES ('S1', '/missing/S1.cdf', 0);
            INSERT INTO tic_data (sample_name, time, intensity, deleted) VALUES
                ('S1', 70.0, 32.0, 0), ('S1', 60.0, 16.0, 0), ('S1', 50.0, 99.0, 1);
            INSERT INTO ms_data (sample_name, time, mz, intensity, deleted) VALUES
                ('S1', 1.5, 102.0, 6.0, 0), ('S1', 1.5, 100.0, 30.0, 0),
                ('S1', 1.5, 101.0, 9.0, 1), ('S1', 1.0, 100.0, 10.0, 0);
            """
        )

    database.init_db()

    tic = read_tic("S1")
    assert tic.time.tolist() == [60.0, 70.0]
    assert tic.intensity.tolist() == [16.0, 32.0]
    ms = ensure_ms_data_for_time("S1", 1.5)
    assert ms.mz.tolist() == [100.0, 102.0]
    assert ms.intensity.tolist() == [30.0, 6.0]
    with database.get_connection() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    assert not {"tic_data", "ms_data"} & tables


def test_extract_eic_labeled_three_isotopologues():
    """Test EIC extraction for labeled compound with three isotopologues."""
    cdf = make_cdf()
    eic = extract_eic(
        compound_name="TestCmp",
        t_r=1.2,              # minutes (72 sec)
        target_mz=100.0,
        cdf=cdf,
        mass_tol=0.5,
        rt_window=0.5,        # includes all three scans
        label_atoms=2,        # M+0, M+1, M+2
    )

    # time returns minutes
    assert np.allclose(eic.time, cdf.scan_time / 60.0)
    # intensity is flattened 2D array: shape (3 isotopologues, 3 scans) raveled
    inten_2d = eic.intensity.reshape(3, -1)
    # sums per scan for each isotopologue should match our inputs at each scan
    # For our construction, summing within mass tol per scan is just the single point
    assert np.allclose(inten_2d[0], [10.0, 20.0, 30.0])  # M+0 @ 100.0
    assert np.allclose(inten_2d[1], [4.0, 8.0, 12.0])   # M+1 @ 101.0
    assert np.allclose(inten_2d[2], [2.0, 4.0, 6.0])    # M+2 @ 102.0


@pytest.mark.parametrize(
    "label_atoms,target_mzs",
    [
        (0, None),
        (2, None),
        (0, (102.0, 100.0)),
    ],
)
def test_optimized_extraction_matches_canonical_path(label_atoms, target_mzs):
    cdf = make_cdf()
    kwargs = {
        "compound_name": "TestCmp",
        "t_r": 1.2,
        "target_mz": 100.0,
        "cdf": cdf,
        "mass_tol": 0.2,
        "rt_window": 0.5,
        "label_atoms": label_atoms,
        "target_mzs": target_mzs,
    }

    canonical = extract_eic(**kwargs)
    optimized = _extract_eic_optimized(
        "TestCmp",
        1.2,
        100.0,
        cdf,
        cdf.scan_time / 60.0,
        0.2,
        0.5,
        label_atoms,
        target_mzs,
    )

    assert np.array_equal(optimized.time, canonical.time)
    assert np.array_equal(optimized.intensity, canonical.intensity)
    assert optimized.target_mzs == canonical.target_mzs


def test_extract_eic_sums_duplicate_points_in_the_same_mass_bin():
    cdf = CdfFileData(
        sample_name="S1",
        file_path="/fake/S1.cdf",
        scan_time=np.array([60.0]),
        mass=np.array([99.9, 100.1]),
        intensity=np.array([7.0, 11.0]),
        scan_index=np.array([0]),
        point_count=np.array([2]),
        total_intensity=np.array([18.0]),
    )

    eic = extract_eic(
        "Target",
        1.0,
        100.0,
        cdf,
        mass_tol=0.2,
        rt_window=0.1,
    )

    assert eic.intensity.tolist() == [18.0]


def test_labelled_extraction_and_integration_regression():
    """Lock the labelled channel order and time-based area before refactoring."""
    cdf = make_cdf()
    eic = extract_eic(
        compound_name="TestCmp",
        t_r=1.2,
        target_mz=100.0,
        cdf=cdf,
        mass_tol=0.2,
        rt_window=0.5,
        label_atoms=2,
    )

    areas = calculate_peak_areas(
        eic.time,
        eic.intensity,
        label_atoms=2,
        retention_time=None,
        loffset=None,
        roffset=None,
    )

    expected_width = (80.0 - 60.0) / 60.0
    assert areas == pytest.approx(
        [
            20.0 * expected_width,
            8.0 * expected_width,
            4.0 * expected_width,
        ]
    )


def test_unlabelled_extraction_supports_arbitrary_diagnostic_masses():
    scan_time = np.array([60.0, 70.0, 80.0])
    mass = np.array(
        [
            73.0, 147.0, 217.0,
            73.0, 147.0, 217.0,
            73.0, 147.0, 217.0,
        ]
    )
    intensity = np.array(
        [
            2.0, 4.0, 10.0,
            4.0, 8.0, 20.0,
            6.0, 12.0, 30.0,
        ]
    )
    cdf = CdfFileData(
        sample_name="S1",
        file_path="/fake/S1.cdf",
        scan_time=scan_time,
        mass=mass,
        intensity=intensity,
        scan_index=np.array([0, 3, 6]),
        point_count=np.array([3, 3, 3]),
        total_intensity=np.array([16.0, 32.0, 48.0]),
    )

    eic = extract_eic(
        compound_name="Target",
        t_r=1.2,
        target_mz=217.0,
        cdf=cdf,
        mass_tol=0.2,
        rt_window=0.5,
        label_atoms=0,
        target_mzs=[217.0, 147.0, 73.0],
    )

    matrix = eic.intensity.reshape(3, -1)
    assert np.allclose(matrix[0], [10.0, 20.0, 30.0])
    assert np.allclose(matrix[1], [4.0, 8.0, 12.0])
    assert np.allclose(matrix[2], [2.0, 4.0, 6.0])

    areas = calculate_peak_areas(
        eic.time,
        eic.intensity,
        label_atoms=0,
        channel_count=3,
    )
    assert areas == pytest.approx([6.6666667, 2.6666667, 1.3333333])


def test_extract_eic_from_float32_cdf_bins_masses_in_float64(tmp_path):
    path = tmp_path / "S1.cdf"
    # float32 99.7 is a bin edge: float64 arithmetic bins it to 99, float32 to 100.
    with Dataset(path, "w", format="NETCDF3_CLASSIC") as cdf:
        cdf.createDimension("scan_number", 2)
        cdf.createDimension("point_number", 3)
        variables = {
            "scan_acquisition_time": ("scan_number", "f4", [60.0, 70.0]),
            "total_intensity": ("scan_number", "f4", [12.0, 3.0]),
            "scan_index": ("scan_number", "i4", [0, 2]),
            "point_count": ("scan_number", "i4", [2, 1]),
            "mass_values": ("point_number", "f4", [99.7, 100.0, 100.0]),
            "intensity_values": ("point_number", "f4", [5.0, 7.0, 3.0]),
        }
        for name, (dimension, dtype, values) in variables.items():
            cdf.createVariable(name, dtype, (dimension,))[:] = values

    cdf = read_cdf_file(path)

    for values in (cdf.scan_time, cdf.mass, cdf.intensity, cdf.total_intensity):
        assert type(values) is np.ndarray
        assert values.dtype == np.float64
    assert type(cdf.scan_index) is np.ndarray
    eic = extract_eic("Target", 1.1, 100.0, cdf, rt_window=0.2)

    assert eic.intensity.tolist() == [7.0, 3.0]


def test_extract_eic_slices_the_rt_window_once():
    class CountingArray(np.ndarray):
        slices = 0

        def __getitem__(self, key):
            CountingArray.slices += 1
            return super().__getitem__(key)

    cdf = make_cdf()
    cdf.mass = cdf.mass.view(CountingArray)

    eic = extract_eic("Target", 70.0 / 60.0, 100.0, cdf, rt_window=0.5)

    assert eic.intensity.tolist() == [10.0, 20.0, 30.0]
    assert CountingArray.slices == 1


def test_extract_eic_skips_out_of_window_scan_when_window_holds_final_scan():
    # main ended scan 0 at scan 2's start, so scan 1's 10.0 leaked into it.
    cdf = CdfFileData(
        sample_name="S1",
        file_path="/fake/S1.cdf",
        scan_time=np.array([60.0, 120.0, 70.0]),
        mass=np.array([100.0, 100.0, 100.0]),
        intensity=np.array([1.0, 10.0, 100.0]),
        scan_index=np.array([0, 1, 2]),
        point_count=np.array([1, 1, 1]),
        total_intensity=np.array([1.0, 10.0, 100.0]),
    )

    eic = extract_eic("Target", 65.0 / 60.0, 100.0, cdf, rt_window=0.1)

    assert eic.intensity.tolist() == [1.0, 100.0]


def test_import_skips_masked_cdf_intensities_in_spectra_like_main(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "manic.db")
    database.init_db()
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, mass0, "
            "label_atoms) VALUES ('Target', ?, 100, 0)",
            (70.0 / 60.0,),
        )
    with Dataset(tmp_path / "S1.cdf", "w", format="NETCDF3_CLASSIC") as cdf:
        cdf.createDimension("scan_number", 3)
        cdf.createDimension("point_number", 7)
        variables = {
            "scan_acquisition_time": ("scan_number", "f4", [60.0, 70.0, 80.0]),
            "total_intensity": ("scan_number", "f4", [12.0, 10.0, 13.0]),
            "scan_index": ("scan_number", "i4", [0, 2, 5]),
            "point_count": ("scan_number", "i4", [2, 3, 2]),
            "mass_values": (
                "point_number",
                "f4",
                [99.0, 100.0, 100.0, 101.0, 102.0, 100.0, 102.0],
            ),
        }
        for name, (dimension, dtype, values) in variables.items():
            cdf.createVariable(name, dtype, (dimension,))[:] = values
        intensity = cdf.createVariable("intensity_values", "f4", ("point_number",))
        intensity.missing_value = np.float32(7.0)
        intensity.set_auto_mask(False)
        # Point 4 (scan 1, m/z 102) is never written, so it holds netCDF's fill.
        intensity[:4] = [5.0, 2.0, 7.0, 3.0]
        intensity[5:] = [4.0, 9.0]

    import_eics(tmp_path)

    def unpack(blob):
        return np.frombuffer(zlib.decompress(blob)).tolist()

    with database.get_connection() as conn:
        spectra = sorted(
            (row["time"], mz, intensity)
            for row in conn.execute("SELECT time, mz, intensity FROM ms_spectrum")
            for mz, intensity in zip(unpack(row["mz"]), unpack(row["intensity"]))
        )
        tic_row = conn.execute("SELECT time, intensity FROM tic_trace").fetchone()
        eic = conn.execute("SELECT x_axis, y_axis FROM eic").fetchone()
    tic = list(zip(unpack(tic_row["time"]), unpack(tic_row["intensity"])))
    assert spectra == [(70.0 / 60.0, 101.0, 3.0)]
    assert tic == [
        (1.0, 12.0),
        (70.0 / 60.0, 10.0),
        (80.0 / 60.0, 13.0),
    ]
    assert np.frombuffer(zlib.decompress(eic["y_axis"])).tolist() == [2.0, 7.0, 4.0]


# ============================================================================
# EIC PROCESSING TESTS
# ============================================================================

def test_get_eics_for_compound_normalise(monkeypatch):
    """Test EIC normalization during batch processing."""
    # Stub read_compound to return an object with needed fields
    monkeypatch.setattr(
        eic_processing, 'read_compound', lambda name: SimpleNamespace(compound_name=name, label_atoms=0)
    )

    # Build two EICs with different max intensity
    def fake_read_eics_batch(samples, compound_obj, use_corrected):
        from manic.io.eic_reader import EIC
        return [
            EIC(samples[0], compound_obj.compound_name, np.array([0, 1]), np.array([1.0, 2.0])),
            EIC(samples[1], compound_obj.compound_name, np.array([0, 1]), np.array([5.0, 10.0])),
        ]

    monkeypatch.setattr(eic_processing, 'read_eics_batch', fake_read_eics_batch)

    eics = eic_processing.get_eics_for_compound('Test', ['A', 'B'], normalise=True, use_corrected=False)
    assert len(eics) == 2
    # Both should be scaled so max is 1.0
    assert eics[0].intensity.max() == 1.0
    assert eics[1].intensity.max() == 1.0


