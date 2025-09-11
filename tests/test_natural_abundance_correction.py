import numpy as np

from manic.processors.natural_abundance_correction import NaturalAbundanceCorrector


def test_parse_and_derivative_formula():
    corr = NaturalAbundanceCorrector()
    elems = corr.parse_formula('C6 H12 O6')
    assert elems['C'] == 6 and elems['H'] == 12 and elems['O'] == 6

    # Apply derivatization markers
    f, e = corr.calculate_derivative_formula('C1H2', tbdms=1, meox=1, me=1)
    # Should add atoms; just basic checks that counts increased
    assert e['C'] >= 1 + 6 + 1 + 1
    assert e['H'] >= 2 + 15 - 1 + 3 + 2
    assert e['O'] >= 1
    assert e['N'] >= 1
    assert e['Si'] >= 1


def test_build_correction_matrix_dims_and_diagonal():
    corr = NaturalAbundanceCorrector()
    # Simple small case
    mat = corr.build_correction_matrix('C1H4', label_element='C', label_atoms=1)
    assert mat.shape == (2, 2)
    # Diagonal should be positive
    assert np.all(np.diag(mat) > 0)


def test_correct_time_series_shapes_and_nonnegativity():
    corr = NaturalAbundanceCorrector()
    # 2 isotopologues × 5 timepoints with simple increasing signal
    inten2d = np.vstack([np.arange(1, 6), np.arange(1, 6)]).astype(float)
    out = corr.correct_time_series(inten2d, 'C1H4', 'C', 1)
    assert out.shape == inten2d.shape
    assert np.all(out >= 0)

