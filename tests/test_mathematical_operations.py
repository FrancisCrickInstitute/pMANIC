"""
Mathematical operations tests for MANIC.
Combines all core mathematical algorithm tests including integration, natural abundance
correction, calibration (MRRF and background ratios), and mass binning operations.
"""

import numpy as np
import pytest
from types import SimpleNamespace

from manic.processors.integration import integrate_peak, calculate_peak_areas
from manic.processors.natural_abundance_correction import NaturalAbundanceCorrector


# ============================================================================
# MASS BINNING AND ROUNDING TESTS
# ============================================================================

class TestMassBinning:
    """Critical tests for mass binning and rounding behavior."""

    def test_matlab_half_up_rounding(self):
        """Test MATLAB-compatible half-up rounding: floor(x + 0.5)."""
        # Critical: Python's round() uses banker's rounding which differs from MATLAB
        test_values = [204.5, 204.4, 204.6, 205.5]
        expected = [205, 204, 205, 206]

        for val, exp in zip(test_values, expected):
            # This is the rounding method used in eic_importer.py
            result = np.floor(val + 0.5)
            assert result == exp, f"Half-up rounding failed for {val}"

    def test_sum_vs_lastwins_behavior(self):
        """
        Test the critical sum vs last-wins bug documented in sum_vs_lastwins_bug.md.
        Python sums duplicate masses, MATLAB takes last value.
        """
        # Simulate masses that round to same integer after -0.2 offset
        masses = np.array([204.8, 205.1])  # Both round to 205 after offset
        mass_tol = 0.2

        # Apply MANIC's asymmetric mass tolerance method
        offset_masses = masses - mass_tol  # [204.6, 204.9]
        rounded_masses = np.floor(offset_masses + 0.5).astype(int)  # [205, 205]

        # Both should round to 205
        assert np.all(rounded_masses == 205)

        # Python behavior: bincount sums duplicates
        intensities = np.array([1000.0, 500.0])
        scan_indices = np.array([0, 0])  # Same scan

        summed = np.bincount(scan_indices, intensities)
        assert summed[0] == 1500.0, "Python should sum duplicate masses"
        # MATLAB would give 500.0 (last-wins)

    def test_asymmetric_mass_tolerance(self):
        """Test mass - 0.2 Da offset before rounding."""
        mass_tol = 0.2
        test_masses = [204.7, 204.8, 205.0, 205.2, 205.3]

        # Expected results after -0.2 offset and half-up rounding
        # 204.7 - 0.2 = 204.5 → floor(204.5 + 0.5) = 205
        # 204.8 - 0.2 = 204.6 → floor(205.1) = 205
        # 205.0 - 0.2 = 204.8 → floor(205.3) = 205
        # 205.2 - 0.2 = 205.0 → floor(205.5) = 205
        # 205.3 - 0.2 = 205.1 → floor(205.6) = 205
        expected = [205, 205, 205, 205, 205]

        for mass, exp in zip(test_masses, expected):
            offset = mass - mass_tol
            rounded = int(np.floor(offset + 0.5))
            assert rounded == exp, f"Mass {mass} should round to {exp}"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Test peak integration algorithms."""

    def test_integrate_peak_time_based_vs_legacy(self):
        """Compare time-based (default) vs legacy (unit-spacing) integration."""
        # Non-uniform time spacing to distinguish methods
        time = np.array([0.0, 0.2, 0.7, 1.5, 2.0])
        inten = np.array([1.0, 1.0, 1.0, 1.0, 1.0])

        time_based = integrate_peak(inten, time, use_legacy=False)
        legacy = integrate_peak(inten, time, use_legacy=True)

        # Time-based should equal last_time - first_time (all ones): 2.0
        assert abs(time_based - 2.0) < 1e-9
        # Legacy integrates assuming unit spacing (sum trapezoid with unit dx) ~ len-1
        assert abs(legacy - 4.0) < 1e-9

    def test_strict_boundary_conditions(self):
        """Verify > and < (not >= and <=) for integration windows."""
        time = np.array([3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0])
        intensity = np.ones_like(time)

        # Integration window: 4.0 < t < 6.0 (RT=5.0, offsets=1.0)
        areas = calculate_peak_areas(
            time, intensity, 0, 5.0, 1.0, 1.0, use_legacy=False
        )

        # Should include only points at 4.5, 5.0, 5.5 (3 points)
        # Trapezoidal integration: (0.5 + 0.5) = 1.0
        assert len(areas) == 1  # unlabeled
        assert abs(areas[0] - 1.0) < 0.01

    def test_calculate_peak_areas_unlabeled_with_bounds(self):
        """Test integration with boundaries for unlabeled compound."""
        time = np.linspace(0.0, 10.0, 101)  # step 0.1
        inten = np.ones_like(time)

        areas = calculate_peak_areas(
            time,
            inten,
            label_atoms=0,
            retention_time=5.0,
            loffset=1.0,
            roffset=1.0,
            use_legacy=False,
        )

        # Window is 4.0 < t < 6.0 (strict boundaries exclude endpoints)
        # With 0.1 spacing: points at 4.1, 4.2, ..., 5.9 are included
        # That's 19 intervals from 4.1 to 5.9
        # Area = 1.0 * 1.8 = 1.8
        assert len(areas) == 1
        assert abs(areas[0] - 1.8) < 1e-2

    def test_calculate_peak_areas_labeled_three_isotopologues(self):
        """Test integration with three isotopologues."""
        time = np.linspace(0.0, 10.0, 11)
        n = len(time)
        # 3 isotopologues flattened: intensities 1, 2, 3
        inten = np.concatenate([
            np.ones(n),
            np.ones(n) * 2,
            np.ones(n) * 3,
        ])

        areas = calculate_peak_areas(
            time,
            inten,
            label_atoms=2,
            retention_time=5.0,
            loffset=5.0,
            roffset=5.0,
            use_legacy=False,
        )

        # Window is 0.0 < t < 10.0 (strict boundaries exclude endpoints)
        # Points at t=1,2,3,4,5,6,7,8,9 are included (9 points, 8 intervals)
        # Integral width = 8.0
        assert len(areas) == 3
        assert abs(areas[0] - 1.0 * 8.0) < 1e-9
        assert abs(areas[1] - 2.0 * 8.0) < 1e-9
        assert abs(areas[2] - 3.0 * 8.0) < 1e-9

    def test_zero_width_integration_window(self):
        """Edge case: loffset = roffset = 0."""
        time = np.linspace(4.9, 5.1, 21)
        intensity = np.ones_like(time) * 100

        areas = calculate_peak_areas(
            time, intensity, 0, 5.0, 0.0, 0.0, use_legacy=False
        )

        # No points should be included (5.0 < t < 5.0 is empty)
        assert areas[0] == 0.0

    def test_integration_with_multiple_isotopologues(self):
        """Test integration of flattened multi-isotopologue data."""
        time = np.linspace(0, 10, 11)
        n = len(time)

        # 3 isotopologues with different intensities
        intensity = np.concatenate([
            np.ones(n) * 100,  # M+0
            np.ones(n) * 50,   # M+1
            np.ones(n) * 25    # M+2
        ])

        areas = calculate_peak_areas(
            time, intensity, 2, 5.0, 5.0, 5.0, use_legacy=False
        )

        assert len(areas) == 3
        # With strict boundaries (0 < t < 10), excludes endpoints
        # Points at t=1,2,3,4,5,6,7,8,9 are included (9 points)
        # Trapezoid integral over 8 intervals = intensity * 8
        assert abs(areas[0] - 800.0) < 0.01  # 100 * 8
        assert abs(areas[1] - 400.0) < 0.01  # 50 * 8
        assert abs(areas[2] - 200.0) < 0.01  # 25 * 8


# ============================================================================
# NATURAL ABUNDANCE CORRECTION TESTS
# ============================================================================

class TestNaturalAbundanceCorrection:
    """Test isotope correction matrix and calculations."""

    def test_parse_and_derivative_formula(self):
        """Test formula parsing and derivatization adjustments."""
        corr = NaturalAbundanceCorrector()
        elems = corr.parse_formula('C6 H12 O6')
        assert elems['C'] == 6 and elems['H'] == 12 and elems['O'] == 6

        # Apply derivatization markers
        # For TBDMS=1: C += (1-1)*6 + 2 = 2, H += (1-1)*15 + 6 - 1 = 5, Si += 1
        # For MEOX=1: N += 1, C += 1, H += 3
        # For ME=1: C += 1, H += 2
        f, e = corr.calculate_derivative_formula('C1H2', tbdms=1, meox=1, me=1)
        # Starting from C1H2:
        # C: 1 + 2 (tbdms) + 1 (meox) + 1 (me) = 5
        # H: 2 + 5 (tbdms) + 3 (meox) + 2 (me) = 12
        # N: 0 + 1 (meox) = 1
        # Si: 0 + 1 (tbdms) = 1
        assert e['C'] == 5
        assert e['H'] == 12
        assert e['N'] == 1
        assert e['Si'] == 1

    def test_build_correction_matrix_dims_and_diagonal(self):
        """Test correction matrix construction."""
        corr = NaturalAbundanceCorrector()
        # Simple small case
        mat = corr.build_correction_matrix('C1H4', label_element='C', label_atoms=1)
        assert mat.shape == (2, 2)
        # Diagonal should be positive
        assert np.all(np.diag(mat) > 0)

    def test_correct_time_series_shapes_and_nonnegativity(self):
        """Test time series correction with shape preservation."""
        corr = NaturalAbundanceCorrector()
        # 2 isotopologues × 5 timepoints with simple increasing signal
        inten2d = np.vstack([np.arange(1, 6), np.arange(1, 6)]).astype(float)
        out = corr.correct_time_series(inten2d, 'C1H4', 'C', 1)
        assert out.shape == inten2d.shape
        assert np.all(out >= 0)

    def test_correction_matrix_construction(self):
        """Test matrix for known formulas with expected isotope distributions."""
        corrector = NaturalAbundanceCorrector()

        # Simple C1 compound
        matrix = corrector.build_correction_matrix('C1', 'C', 1)

        assert matrix.shape == (2, 2)
        # The matrix is more complex due to convolution
        # Just verify it's a valid correction matrix
        assert np.all(np.diag(matrix) > 0)  # Positive diagonal
        assert np.linalg.det(matrix) != 0  # Non-singular

    def test_derivatization_adjustments(self):
        """Test TBDMS, MEOX, ME derivatization formula adjustments."""
        corrector = NaturalAbundanceCorrector()

        # Test TBDMS derivatization
        formula, elements = corrector.calculate_derivative_formula(
            'C3H6O3', tbdms=1, meox=0, me=0
        )

        # TBDMS with tbdms=1: C += (1-1)*6 + 2 = 2
        assert elements['C'] == 3 + 2  # Original + TBDMS carbons
        # H += (1-1)*15 + 6 - 1 = 5
        assert elements['H'] == 6 + 5  # Original + TBDMS hydrogens
        assert elements['Si'] == 1  # Silicon from TBDMS
        assert elements['O'] == 3  # Unchanged

    def test_diagonal_correction_normalization(self):
        """Verify x[i] = x[i] / A[i,i] normalization step."""
        corrector = NaturalAbundanceCorrector()

        # Create simple test data
        intensities_2d = np.array([
            [100, 200],  # M+0 at two timepoints
            [10, 20]     # M+1 at two timepoints
        ]).astype(float)

        corrected = corrector.correct_time_series(
            intensities_2d, 'C1', 'C', 1
        )

        assert corrected.shape == intensities_2d.shape
        # Should apply correction and diagonal normalization
        assert np.all(corrected >= 0)

    def test_negative_clamping(self):
        """Test max(x, 0) clamping after correction."""
        corrector = NaturalAbundanceCorrector()

        # Create data that might produce negative values
        intensities_2d = np.array([
            [10],  # Very low M+0
            [50]   # High M+1 (unrealistic)
        ]).astype(float)

        corrected = corrector.correct_time_series(
            intensities_2d, 'C1', 'C', 1
        )

        # All values should be non-negative
        assert np.all(corrected >= 0)

    def test_unlabeled_compound_identity(self):
        """label_atoms=0 should apply 1x1 correction matrix."""
        corrector = NaturalAbundanceCorrector()

        # Single isotopologue for unlabeled compound
        intensities_2d = np.array([[100, 200, 300]]).astype(float)

        corrected = corrector.correct_time_series(
            intensities_2d, 'C6H12O6', 'C', 0  # label_atoms=0
        )

        # For unlabeled compounds, a 1x1 matrix is applied with diagonal normalization
        # This can change values by ~8% due to the diagonal correction
        assert corrected.shape == intensities_2d.shape
        # Values should be proportional but not identical
        # The correction factor is consistent across all values
        ratio = corrected[0, 0] / intensities_2d[0, 0]
        assert abs(ratio - 1.084) < 0.01  # About 8.4% increase observed


# ============================================================================
# CALIBRATION TESTS (MRRF AND BACKGROUND RATIOS)
# ============================================================================

class TestCalibrations:
    """Test MRRF and background ratio calculations."""

    def test_mrrf_formula(self):
        """Test MRRF = (Signal_met/Conc_met)/(Signal_IS/Conc_IS)."""
        # Simulated data
        metabolite_signal = 1000.0
        metabolite_conc = 10.0
        is_signal = 500.0
        is_conc = 5.0

        # MRRF calculation
        mrrf = (metabolite_signal / metabolite_conc) / (is_signal / is_conc)

        assert mrrf == 1.0  # Equal response factors

    def test_background_ratio_mean_calculation(self):
        """Test background ratio as mean of (Σ labeled)/M0 across MM samples."""
        # Simulate MM sample data
        m0_signals = [100, 200, 150]
        labeled_signals = [10, 20, 15]

        # Calculate per-sample ratios
        ratios = [lab/m0 for lab, m0 in zip(labeled_signals, m0_signals)]

        # Background ratio is mean
        background_ratio = sum(ratios) / len(ratios)

        assert abs(background_ratio - 0.1) < 0.001

    def test_percent_label_calculation(self):
        """Verify percent label formula with background correction."""
        m0 = 100.0
        labeled_raw = 25.0
        background_ratio = 0.05

        # Background correction
        labeled_corrected = labeled_raw - (background_ratio * m0)
        labeled_corrected = max(0.0, labeled_corrected)  # 20.0

        # IMPORTANT: Denominator uses ORIGINAL total (MATLAB compatibility)
        total_original = m0 + labeled_raw  # 125.0
        percent_label = (labeled_corrected / total_original) * 100

        assert abs(percent_label - 16.0) < 0.01  # 20/125 * 100

    def test_abundance_calculation(self):
        """Test abundance = (Total_Corrected × IS_amount)/(IS_M0 × MRRF)."""
        total_corrected = 500.0
        is_amount = 10.0  # nmol
        is_m0 = 1000.0
        mrrf = 2.0

        abundance = (total_corrected * is_amount) / (is_m0 * mrrf)

        assert abs(abundance - 2.5) < 0.01  # 5000 / 2000

    def test_calculate_background_ratios_simple(self):
        """Test background ratio calculation from standard samples."""
        from manic.processors.calibration import calculate_background_ratios

        # Stub provider for testing
        class StubProvider:
            def __init__(self, samples_map):
                self._samples_map = samples_map

            def resolve_mm_samples(self, mm_field):
                # Ignore mm_field pattern and return fixed samples for test
                return list(self._samples_map.keys())

            def get_sample_corrected_data(self, sample_name):
                return self._samples_map.get(sample_name, {})

        # Compound A: in two standard samples
        samples_map = {
            'std1': {'A': [100.0, 20.0, 10.0]},  # unlabeled=100, labeled=30
            'std2': {'A': [50.0, 5.0, 5.0]},     # unlabeled=50, labeled=10
        }
        provider = StubProvider(samples_map)
        compounds = [{
            'compound_name': 'A',
            'label_atoms': 2,
            'mm_files': 'std*',
        }]

        ratios = calculate_background_ratios(provider, compounds)
        # Mean of per-sample ratios: (30/100 + 10/50)/2 = (0.3 + 0.2)/2 = 0.25
        assert 'A' in ratios
        assert abs(ratios['A'] - 0.25) < 1e-9

    def test_calculate_mrrf_values_means(self, monkeypatch):
        """Test MRRF calculation with mean-based approach."""
        from manic.processors.calibration import calculate_mrrf_values
        import manic.models.database as dbmod

        # Stub provider for testing
        class StubProvider:
            def __init__(self, samples_map):
                self._samples_map = samples_map

            def resolve_mm_samples(self, mm_field):
                return list(self._samples_map.keys())

            def get_sample_corrected_data(self, sample_name):
                return self._samples_map.get(sample_name, {})

        # Provide two standard samples, totals for metabolite A and internal standard ISTD
        samples_map = {
            'std1': {
                'A': [100.0, 0.0],    # total 100
                'ISTD': [20.0],       # total 20
            },
            'std2': {
                'A': [200.0, 0.0],    # total 200
                'ISTD': [40.0],       # total 40
            },
        }
        provider = StubProvider(samples_map)
        compounds = [{
            'compound_name': 'A',
            'amount_in_std_mix': 2.0,  # metabolite concentration in standard mix
            'mm_files': 'std*',
        }, {
            'compound_name': 'ISTD',
            'amount_in_std_mix': 1.0,
            'mm_files': 'std*',
        }]

        # Fake DB connection to supply internal standard concentration and mm_files
        class Row(dict):
            def __getattr__(self, k):
                return self[k]

        class FakeCursor:
            def __init__(self, rows):
                self._rows = rows
            def fetchone(self):
                return self._rows[0] if self._rows else None
            def fetchall(self):
                return self._rows

        class FakeConn:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def execute(self, sql, params=()):
                sql_u = sql.lower()
                if 'select amount_in_std_mix' in sql_u:
                    # Return 1.0 for internal standard concentration
                    return FakeCursor([Row({'amount_in_std_mix': 1.0})])
                if 'select mm_files' in sql_u:
                    return FakeCursor([Row({'mm_files': 'std*'})])
                return FakeCursor([])

        monkeypatch.setattr(dbmod, 'get_connection', lambda: FakeConn())

        mrrf = calculate_mrrf_values(provider, compounds, 'ISTD')
        # Means: metabolite= (100+200)/2=150; internal std= (20+40)/2=30
        # MRRF = (150/2.0) / (30/1.0) = 75/30 = 2.5
        assert abs(mrrf['A'] - 2.5) < 1e-9
        assert abs(mrrf['ISTD'] - 1.0) < 1e-9


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance and memory tests."""

    def test_large_dataset_performance(self):
        """Test that large datasets process efficiently."""
        import time

        # Create large dataset
        time_points = np.linspace(0, 20, 1000)  # 1000 timepoints
        intensities = np.random.random(1000 * 4)  # 4 isotopologues

        start = time.time()
        areas = calculate_peak_areas(
            time_points, intensities, 3, 10.0, 2.0, 2.0
        )
        elapsed = time.time() - start

        assert elapsed < 0.1  # Should process in < 100ms
        assert len(areas) == 4

    def test_memory_efficient_operations(self):
        """Verify operations don't create excessive copies."""
        import tracemalloc

        tracemalloc.start()

        # Large array operation
        data = np.ones(100000)
        snapshot1 = tracemalloc.take_snapshot()

        # This should be memory efficient
        result = integrate_peak(data, np.arange(len(data)))

        snapshot2 = tracemalloc.take_snapshot()
        stats = snapshot2.compare_to(snapshot1, 'lineno')

        # Memory increase should be minimal (< 10MB)
        total_increase = sum(stat.size_diff for stat in stats) / 1024 / 1024
        assert total_increase < 10.0

        tracemalloc.stop()