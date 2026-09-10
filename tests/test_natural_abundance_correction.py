import numpy as np

from manic.processors.natural_abundance_correction import (
    NaturalAbundanceCorrector,
)


def test_direct_correct_recovers_known_c1_true_vector():
    corrector = NaturalAbundanceCorrector()
    matrix = corrector.build_correction_matrix("C1", "C", 1)
    np.testing.assert_allclose(matrix[:, 0], [0.9893, 0.0107], atol=5e-5)
    np.testing.assert_allclose(matrix[:, 1], [0.01, 0.99], atol=5e-5)
    measured = np.array(
        [
            [0.9893 * 2.0 + 0.01 * 1.0],
            [0.0107 * 2.0 + 0.99 * 1.0],
        ],
        dtype=np.float64,
    )
    recovered = corrector._correct_vectorized_direct(measured, matrix)
    np.testing.assert_allclose(recovered[:, 0], [2.0, 1.0], atol=1e-3)
