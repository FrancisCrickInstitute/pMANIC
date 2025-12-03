"""Tests for natural abundance correction performance helpers."""

import numpy as np

from manic.processors.natural_abundance_correction import (
    NaturalAbundanceCorrector,
)


def _reference_direct_correct(intensity_2d: np.ndarray, correction_matrix: np.ndarray) -> np.ndarray:
    """Reproduce the pre-vectorized correction logic for regression comparisons."""
    n_isotopologues, n_timepoints = intensity_2d.shape
    corrected_2d = np.zeros_like(intensity_2d)

    totals = np.sum(intensity_2d, axis=0)

    if n_isotopologues == 1 and correction_matrix.shape == (1, 1):
        corrected_2d[0, :] = totals
    else:
        intensity_normalized = np.zeros_like(intensity_2d)
        for t in range(n_timepoints):
            if totals[t] > 1e-10:
                intensity_normalized[:, t] = intensity_2d[:, t] / totals[t]
            else:
                intensity_normalized[:, t] = 0

        cordist_2d = np.linalg.solve(correction_matrix, intensity_normalized)

        for t in range(n_timepoints):
            corrected_2d[:, t] = cordist_2d[:, t] * totals[t]

    diagonal_elements = np.diag(correction_matrix)
    for i in range(len(diagonal_elements)):
        if diagonal_elements[i] > 0:
            corrected_2d[i, :] = corrected_2d[i, :] / diagonal_elements[i]

    corrected_2d = np.maximum(corrected_2d, 0.0)
    return corrected_2d


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
