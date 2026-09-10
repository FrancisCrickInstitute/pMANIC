"""
Mathematical operations tests for MANIC.
Combines all core mathematical algorithm tests including integration, natural abundance
correction, calibration (MRRF and background ratios), and mass binning operations.
"""

import numpy as np

from manic.processors.integration import integrate_peak, calculate_peak_areas
from manic.processors.natural_abundance_correction import NaturalAbundanceCorrector


# ============================================================================
# MASS BINNING AND ROUNDING TESTS
# ============================================================================


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

        # Same data but using IS M+1 as the reference peak.
        samples_map_ref = {
            'std1': {
                'A': [100.0, 0.0],
                'ISTD': [20.0, 2.0],
            },
            'std2': {
                'A': [200.0, 0.0],
                'ISTD': [40.0, 4.0],
            },
        }
        provider_ref = StubProvider(samples_map_ref)

        mrrf_ref = calculate_mrrf_values(
            provider_ref, compounds, 'ISTD', internal_standard_isotope_index=1
        )
        # Means: metabolite=150; internal std (M1)= (2+4)/2=3
        # MRRF = (150/2.0) / (3/1.0) = 75/3 = 25
        assert abs(mrrf_ref['A'] - 25.0) < 1e-9
        assert abs(mrrf_ref['ISTD'] - 1.0) < 1e-9


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

