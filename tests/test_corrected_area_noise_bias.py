import zlib
from types import SimpleNamespace

import numpy as np
import pytest

from manic.io.data_provider import DataProvider
from manic.models import database
from manic.processors.display_deconvolution import integrated_display_areas
from manic.processors.eic_correction_manager import ensure_corrections_for_export
from manic.processors.natural_abundance_correction import NaturalAbundanceCorrector


@pytest.mark.parametrize("deconvolution_level", ["off", "4"])
def test_zero_mean_noise_does_not_add_label_to_corrected_areas(
    empty_db, deconvolution_level
):
    corrector = NaturalAbundanceCorrector()
    matrix = corrector.build_correction_matrix(
        corrector.calculate_derivative_formula("C3H6O3", tbdms=2)[0], "C", 3
    )
    time = np.arange(21, dtype=np.float64)
    # Unlabelled M+0 peak with trapezoid area 3000.
    true_m0 = np.zeros(21)
    true_m0[9:12] = 1000.0
    noise = np.zeros((4, 21))
    noise[1:, 2:18] = 50.0 * np.array([1.0, -1.0] * 8)
    measured = np.outer(matrix[:, 0], true_m0) + noise
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms, formula, label_type, tbdms, baseline_correction, "
            "deconvolution_level) "
            "VALUES ('Lactate', 10.0, 10.0, 10.0, 261.0, 3, 'C3H6O3', 'C', 2, 0, ?)",
            (deconvolution_level,),
        )
        conn.execute(
            "INSERT INTO samples (sample_name, file_name) VALUES ('S1', '/fake/S1.cdf')"
        )
        conn.execute(
            "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
            "VALUES ('S1', 'Lactate', ?, ?, 10.0)",
            (zlib.compress(time.tobytes()), zlib.compress(measured.ravel().tobytes())),
        )

    expected = pytest.approx([3000.0, 0.0, 0.0, 0.0], abs=1e-6)
    # The tile verdict reads these areas before any export has run.
    assert DataProvider().get_compound_areas("S1", "Lactate") == expected
    ensure_corrections_for_export()
    assert DataProvider().get_sample_corrected_data("S1")["Lactate"] == expected
    compound = SimpleNamespace(
        retention_time=10.0, loffset=10.0, roffset=10.0, baseline_correction=0,
        formula="C3H6O3", label_atoms=3, label_type="C", tbdms=2, meox=0, me=0,
        compound_name="Lactate", deconvolution_level=deconvolution_level,
    )
    assert integrated_display_areas(time, measured, compound, use_corrected=True) == expected
