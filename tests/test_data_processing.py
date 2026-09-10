"""
Data processing tests for MANIC.
Combines tests for EIC extraction, processing, correction management,
and data flow through the application.
"""

import numpy as np
import pytest
from types import SimpleNamespace

import manic.io.cdf_data_extractor as cdf_data_extractor
from manic.io.cdf_data_extractor import (
    _extract_ms_at_time_from_cdf_data,
    ensure_ms_data_for_time,
)
from manic.io.cdf_reader import CdfFileData
from manic.io.eic_importer import _extract_eic_optimized
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


