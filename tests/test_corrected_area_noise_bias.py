import zlib
from types import SimpleNamespace

import numpy as np
import pytest

from manic.io.data_provider import DataProvider
from manic.models import database
from manic.processors.chromatographic_peak_deconvolution import (
    deconvolve_channel_matrix,
)
from manic.processors.display_deconvolution import integrated_display_areas
from manic.processors.natural_abundance_correction import NaturalAbundanceCorrector

TIME = np.arange(21, dtype=np.float64)


def _noisy_box(fractions):
    # Unlabelled M+0 peak with trapezoid area 3000, zero-mean noise on M+1 to M+3.
    true_m0 = np.zeros(21)
    true_m0[9:12] = 1000.0
    noise = np.zeros((4, 21))
    noise[1:, 2:18] = 50.0 * np.array([1.0, -1.0] * 8)
    return np.outer(fractions, true_m0) + noise, 3000.0, 1e-6


def _offset_peaks(fractions):
    # Clean unlabelled peaks that every ion fits, each 0.4 scans from M+0.
    peaks = [
        f * 1000.0 * np.exp(-0.5 * ((TIME - 10.0 - shift) / 1.5) ** 2)
        for f, shift in zip(fractions, (0.0, 0.4, -0.4, 0.4))
    ]
    return np.vstack(peaks), 1000.0 * 1.5 * np.sqrt(2 * np.pi), 0.5


@pytest.mark.parametrize(
    "deconvolution_level, signal, fitted",
    [("off", _noisy_box, False), ("4", _noisy_box, False), ("4", _offset_peaks, True)],
)
def test_unlabelled_peak_shows_no_label_in_corrected_areas(
    empty_db, deconvolution_level, signal, fitted
):
    corrector = NaturalAbundanceCorrector()
    matrix = corrector.build_correction_matrix(
        corrector.calculate_derivative_formula("C3H6O3", tbdms=2)[0], "C", 3
    )
    measured, area, tolerance = signal(matrix[:, 0])
    if deconvolution_level != "off":
        bundle = deconvolve_channel_matrix(
            TIME, measured, retention_time=10.0, loffset=10.0, roffset=10.0,
            stringency=deconvolution_level, fit_type="auto", noise_gate="balanced",
        )
        assert bundle.uses_model_areas() is fitted
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
            (zlib.compress(TIME.tobytes()), zlib.compress(measured.ravel().tobytes())),
        )

    expected = pytest.approx([area, 0.0, 0.0, 0.0], abs=tolerance)
    # No stored corrected trace exists: the tiles and the export need none.
    assert DataProvider().get_compound_areas("S1", "Lactate") == expected
    assert DataProvider().get_sample_corrected_data("S1")["Lactate"] == expected
    compound = SimpleNamespace(
        retention_time=10.0, loffset=10.0, roffset=10.0, baseline_correction=0,
        formula="C3H6O3", label_atoms=3, label_type="C", tbdms=2, meox=0, me=0,
        compound_name="Lactate", deconvolution_level=deconvolution_level,
    )
    assert integrated_display_areas(TIME, measured, compound, use_corrected=True) == expected
