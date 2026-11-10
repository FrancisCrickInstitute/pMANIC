import zlib

import numpy as np
import pytest

from manic.io.data_provider import DataProvider
from manic.models import database
from manic.processors.eic_correction_manager import ensure_corrections_for_export

from conftest import _gaussian, _make_window

TIME = np.linspace(4.0, 6.0, 401)


def _seed() -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, "
            "label_atoms, int_std_amount, deconvolution_level) "
            "VALUES ('IS', 5.0, 0.1, 0.1, 100.0, 0, 1.0, 'off')"
        )
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, "
            "label_atoms, formula, label_type, deconvolution_level) "
            "VALUES ('Lac', 5.0, 0.1, 0.1, 100.0, 2, 'C3H6O3', 'C', 'off')"
        )
        conn.execute("INSERT INTO samples (sample_name, file_name) VALUES ('S1', '/fake/S1.cdf')")
        lac = np.concatenate([_gaussian(TIME, 5.0, 0.03, h) for h in (1e4, 2e3, 5e2)])
        for name, intensity in (("IS", _gaussian(TIME, 5.0, 0.03, 1e5)), ("Lac", lac)):
            conn.execute(
                "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
                "VALUES ('S1', ?, ?, ?, 0.5)",
                (name, zlib.compress(TIME.tobytes()), zlib.compress(intensity.tobytes())),
            )


def test_tile_verdict_areas_equal_exported_corrected_areas_before_any_export(
    qapp, monkeypatch
):
    _seed()
    window = _make_window(monkeypatch)
    window.compound_data_loaded = window.cdf_data_loaded = True
    window.toolbar.update_sample_list(["S1"])
    window.toolbar.update_compound_list(["IS", "Lac"], "Lac")
    window.toolbar.on_internal_standard_selected("IS")

    tile_areas = window._validation_provider.get_compound_areas("S1", "Lac")

    ensure_corrections_for_export()
    export_areas = DataProvider().get_sample_corrected_data("S1")["Lac"]

    expected = [756.92373692353, 124.80796926748665, 29.91085904280505]
    assert tile_areas == pytest.approx(expected, rel=1e-9)
    assert export_areas == pytest.approx(expected, rel=1e-9)
