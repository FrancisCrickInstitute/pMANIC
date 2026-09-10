"""Tests for natural abundance correction performance helpers."""

import numpy as np

from manic.processors.natural_abundance_correction import (
    NaturalAbundanceCorrector,
)


def _reference_direct_correct(intensity_2d: np.ndarray, correction_matrix: np.ndarray) -> np.ndarray:
    corrected_2d = np.linalg.solve(correction_matrix, intensity_2d)
    return np.maximum(corrected_2d, 0.0)


def test_vectorized_correction_matches_reference():
    """Ensure the broadcasted implementation matches the legacy loop-based math."""
    corrector = NaturalAbundanceCorrector()
    correction_matrix = corrector.build_correction_matrix(
        formula="C6H12O6", label_element="C", label_atoms=3
    )

    rng = np.random.default_rng(42)
    intensity = np.abs(rng.normal(loc=100.0, scale=25.0, size=(4, 120)))
    # Inject some zero-total time points and very small totals to exercise edge cases
    intensity[:, ::17] = 0.0
    intensity[:, 5::23] = 1e-12

    fast = corrector._correct_vectorized_direct(intensity.copy(), correction_matrix)
    reference = _reference_direct_correct(intensity.copy(), correction_matrix)

    np.testing.assert_allclose(fast, reference, rtol=1e-10, atol=1e-12)
