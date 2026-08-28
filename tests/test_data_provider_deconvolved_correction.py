import sqlite3
import zlib
from pathlib import Path

import numpy as np
import pytest

from manic.io import data_provider
from manic.io.data_provider import DataProvider
from manic.models import database
from manic.processors.chromatographic_peak_deconvolution import (
    ChannelDeconvolution,
    ChannelDeconvolutionBundle,
    EICChromatographicPeakDeconvolutionResult,
    deconvolve_channel_matrix,
    deconvolve_eic,
)
from manic.processors.integration import (
    _integrate_dense_rows,
    _integrate_model_component,
    calculate_peak_areas,
)


SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "deconvolved_correction.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    yield conn
    conn.close()


def _blob(values: np.ndarray) -> bytes:
    return zlib.compress(np.asarray(values, dtype=np.float64).tobytes())


def test_corrected_export_uses_deconvolved_raw_component(temp_db, monkeypatch):
    time = np.array([0, 1, 2, 3, 4], dtype=np.float64)
    raw = np.vstack(
        [
            [0, 20, 20, 0, 0],
            [0, 8, 8, 0, 0],
        ]
    )
    stored_full_trace_correction = np.vstack(
        [
            [100, 100, 100, 100, 100],
            [50, 50, 50, 50, 50],
        ]
    )
    selected_component = np.vstack(
        [
            [0, 10, 10, 0, 0],
            [0, 4, 4, 0, 0],
        ]
    )
    selected_mask = np.tile(np.array([False, True, True, True, False]), (2, 1))

    temp_db.execute("INSERT INTO samples (sample_name) VALUES ('S1')")
    temp_db.execute(
        "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
        "mass0, label_atoms, formula, label_type, baseline_correction, "
        "deconvolution_level, deconvolution_fit_type, deconvolution_noise_gate) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("Urea", 2.0, 2.0, 2.0, 189.0, 1, "C1", "C", 0, "4", "auto", "balanced"),
    )
    temp_db.execute(
        "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis) VALUES (?, ?, ?, ?)",
        ("S1", "Urea", _blob(time), _blob(raw.ravel())),
    )
    temp_db.execute(
        "INSERT INTO eic_corrected "
        "(sample_name, compound_name, x_axis, y_axis_corrected, correction_applied, deleted) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("S1", "Urea", _blob(time), _blob(stored_full_trace_correction.ravel()), 1, 0),
    )
    temp_db.commit()

    deconvolution_calls = []

    def fake_deconvolve(*args, **kwargs):
        deconvolution_calls.append((args, kwargs))
        return ChannelDeconvolutionBundle(
            time=time,
            channels=tuple(
                ChannelDeconvolution(
                    index=index,
                    result=EICChromatographicPeakDeconvolutionResult(
                        selected=selected_component[index],
                        selected_mask=selected_mask[index],
                        excluded=[],
                        excluded_masks=[],
                        selected_center=2.0,
                        component_centers=[2.0],
                        model=None,
                    ),
                )
                for index in range(selected_component.shape[0])
            ),
        )

    monkeypatch.setattr(data_provider, "deconvolve_channel_matrix", fake_deconvolve)

    class IdentityCorrector:
        def correct_time_series(self, matrix, *args, **kwargs):
            return np.asarray(matrix, dtype=np.float64)

    monkeypatch.setattr(data_provider, "NaturalAbundanceCorrector", IdentityCorrector)

    provider = DataProvider()
    corrected = provider.load_bulk_sample_data()["S1"]["Urea"]
    raw_export = provider.get_sample_raw_data("S1")["Urea"]

    # No model: fallback integrates the raw EIC in the exclusive window
    # (times 1, 2, 3), not the stored full-trace correction.
    assert corrected == pytest.approx([30.0, 12.0])
    assert raw_export == pytest.approx([30.0, 12.0])
    assert len(deconvolution_calls) == 1


def test_model_path_raw_and_corrected_differ_only_by_correction():
    """Raw and corrected model-path areas use one shared integration route."""
    grid_left, grid_right = 1.0, 3.0

    class Fake1DModel:
        integration_left = grid_left
        integration_right = grid_right

        def __init__(self, scale: float):
            self.scale = scale

        def evaluate_selected(self, grid):
            grid = np.asarray(grid, dtype=np.float64)
            return self.scale * np.exp(-((grid - 2.0) ** 2) / 0.2)

    selected_mask = np.array([False, True, True, True, False])
    time = np.array([0, 1, 2, 3, 4], dtype=np.float64)

    def _channel(index: int, scale: float) -> ChannelDeconvolution:
        return ChannelDeconvolution(
            index=index,
            result=EICChromatographicPeakDeconvolutionResult(
                selected=np.zeros(5),
                selected_mask=selected_mask,
                excluded=[],
                excluded_masks=[],
                selected_center=2.0,
                component_centers=[2.0],
                model=Fake1DModel(scale),
            ),
        )

    deconvolved = ChannelDeconvolutionBundle(
        time=time,
        channels=(_channel(0, 10.0), _channel(1, 4.0)),
    )
    row = {
        "label_atoms": 1,
        "retention_time": 2.0,
        "loffset": 1.0,
        "roffset": 1.0,
        "formula": "C1",
        "label_type": "C",
        "tbdms": 0,
        "meox": 0,
        "me": 0,
    }

    provider = DataProvider()
    # Identity correction: raw and corrected must be bit-for-bit identical
    # because they now flow through the same integration routine.
    provider._correct_time_series = lambda matrix, r: np.asarray(
        matrix, dtype=np.float64
    )
    raw_intensity = np.zeros((2, 5), dtype=np.float64)
    raw_areas, corrected_areas = provider._areas_from_deconvolved(
        np.array([0, 1, 2, 3, 4], dtype=np.float64),
        deconvolved,
        row,
        raw_intensity,
        use_legacy=False,
        baseline_correction=False,
    )
    assert raw_areas == pytest.approx(corrected_areas)

    # A pure channel-wise scaling correction scales the integrated areas by the
    # same factor, proving correction is the only thing that differs.
    provider._correct_time_series = lambda matrix, r: np.asarray(
        matrix, dtype=np.float64
    ) * np.array([[0.5], [2.0]])
    raw_areas2, corrected_areas2 = provider._areas_from_deconvolved(
        np.array([0, 1, 2, 3, 4], dtype=np.float64),
        deconvolved,
        row,
        raw_intensity,
        use_legacy=False,
        baseline_correction=False,
    )
    assert raw_areas2 == pytest.approx(raw_areas)
    assert corrected_areas2[0] == pytest.approx(raw_areas2[0] * 0.5)
    assert corrected_areas2[1] == pytest.approx(raw_areas2[1] * 2.0)


def test_model_path_corrected_baseline_uses_corrected_scans():
    class Fake1DModel:
        integration_left = 1.0
        integration_right = 3.0

        def evaluate_selected(self, grid):
            return 10.0 * np.ones_like(np.asarray(grid, dtype=np.float64))

    time = np.linspace(0.0, 4.0, 21)
    selected_mask = (time > 1.0) & (time < 3.0)
    selected = 4.0 + 6.0 * np.exp(-((time - 2.0) ** 2) / 0.3)
    bundle = ChannelDeconvolutionBundle(
        time=time,
        channels=tuple(
            ChannelDeconvolution(
                index=index,
                result=EICChromatographicPeakDeconvolutionResult(
                    selected=selected,
                    selected_mask=selected_mask,
                    excluded=[],
                    excluded_masks=[],
                    selected_center=2.0,
                    component_centers=[2.0],
                    model=Fake1DModel(),
                ),
            )
            for index in range(2)
        ),
    )
    row = {
        "label_atoms": 1,
        "retention_time": 2.0,
        "loffset": 1.0,
        "roffset": 1.0,
        "formula": "C1",
        "label_type": "C",
        "tbdms": 0,
        "meox": 0,
        "me": 0,
    }
    provider = DataProvider()
    provider._correct_time_series = lambda matrix, r: np.asarray(
        matrix, dtype=np.float64
    ) * np.array([[0.5], [2.0]])
    raw_areas, corrected_areas = provider._areas_from_deconvolved(
        time,
        bundle,
        row,
        np.zeros((2, time.size)),
        use_legacy=False,
        baseline_correction=True,
    )
    grid = np.linspace(1.0, 3.0, max(65, 3 * 16))
    raw_dense = bundle.evaluate_selected_stack(grid)
    corrected_dense = raw_dense * np.array([[0.5], [2.0]])
    scan_times = [time[selected_mask], time[selected_mask]]
    expected_raw = _integrate_dense_rows(
        grid,
        raw_dense,
        scan_times,
        [selected[selected_mask], selected[selected_mask]],
        baseline_correction=True,
    )
    expected_corrected = _integrate_dense_rows(
        grid,
        corrected_dense,
        scan_times,
        [0.5 * selected[selected_mask], 2.0 * selected[selected_mask]],
        baseline_correction=True,
    )
    assert raw_areas == pytest.approx(expected_raw)
    assert corrected_areas == pytest.approx(expected_corrected)
    raw_baseline_on_corrected = _integrate_dense_rows(
        grid,
        corrected_dense,
        scan_times,
        [selected[selected_mask], selected[selected_mask]],
        baseline_correction=True,
    )
    assert corrected_areas[0] != pytest.approx(raw_baseline_on_corrected[0])


def _gaussian(time, center, width, height):
    return height * np.exp(-0.5 * ((time - center) / width) ** 2)


def test_export_raw_areas_match_direct_integration():
    time = np.linspace(4.0, 6.0, 201)
    intensity = np.vstack(
        [
            _gaussian(time, 5.0, 0.07, 12.0),
            _gaussian(time, 5.0, 0.07, 4.0) + _gaussian(time, 5.26, 0.06, 10.0),
        ]
    )
    row = {
        "label_atoms": 1,
        "retention_time": 5.0,
        "loffset": 0.5,
        "roffset": 0.5,
        "formula": "C1",
        "label_type": "C",
        "tbdms": 0,
        "meox": 0,
        "me": 0,
    }
    bundle = deconvolve_channel_matrix(
        time,
        intensity,
        retention_time=5.0,
        loffset=0.5,
        roffset=0.5,
        stringency="7",
    )
    assert all(channel.result.model is not None for channel in bundle.channels)
    model = bundle.channels[0].result.model
    assert model.integration_left > 5.0 - 0.5
    assert model.integration_right < 5.0 + 0.5

    provider = DataProvider()
    provider._correct_time_series = lambda matrix, r: np.asarray(matrix, dtype=np.float64)
    raw_areas, _ = provider._areas_from_deconvolved(
        time,
        bundle,
        row,
        intensity,
        use_legacy=False,
        baseline_correction=True,
    )
    direct = calculate_peak_areas(
        time,
        intensity.ravel(),
        1,
        5.0,
        0.5,
        0.5,
        use_legacy=False,
        baseline_correction=True,
        chromatographic_peak_deconvolution_stringency="7",
    )
    assert raw_areas == pytest.approx(direct)


def _mixed_row():
    return {
        "label_atoms": 1,
        "retention_time": 5.0,
        "loffset": 0.4,
        "roffset": 0.4,
        "formula": "C1",
        "label_type": "C",
        "tbdms": 0,
        "meox": 0,
        "me": 0,
    }


def _mixed_bundle(time, fitted, failed_trace):
    return ChannelDeconvolutionBundle(
        time=time,
        channels=(
            ChannelDeconvolution(index=0, result=fitted),
            ChannelDeconvolution(
                index=1,
                result=EICChromatographicPeakDeconvolutionResult(
                    selected=failed_trace,
                    selected_mask=np.asarray(fitted.selected_mask, dtype=bool),
                    excluded=[],
                    excluded_masks=[],
                    selected_center=5.0,
                    component_centers=[5.0],
                    model=None,
                ),
            ),
        ),
    )


def test_mixed_bundle_uses_raw_scans_for_every_channel():
    time = np.linspace(4.0, 6.0, 81)
    clean = _gaussian(time, 5.0, 0.08, 12.0)
    fitted = deconvolve_eic(
        time,
        clean,
        retention_time=5.0,
        loffset=0.4,
        roffset=0.4,
        stringency="4",
    )
    assert fitted.model is not None
    failed = np.full(time.size, 3.0)
    intensity = np.vstack([clean, failed])
    row = _mixed_row()
    provider = DataProvider()
    provider._correct_time_series = lambda matrix, r: np.asarray(matrix, dtype=np.float64)
    raw_areas, corrected_areas = provider._areas_from_deconvolved(
        time,
        _mixed_bundle(time, fitted, failed),
        row,
        intensity,
        use_legacy=False,
        baseline_correction=False,
    )

    expected = calculate_peak_areas(
        time,
        intensity.ravel(),
        1,
        5.0,
        0.4,
        0.4,
        use_legacy=False,
        baseline_correction=False,
        chromatographic_peak_deconvolution_stringency="off",
    )
    assert raw_areas == pytest.approx(expected)
    assert corrected_areas == pytest.approx(raw_areas)


def test_mixed_overlap_export_matches_raw_window_not_isolated_component():
    time = np.linspace(4.0, 6.0, 201)
    overlapped = _gaussian(time, 5.0, 0.07, 12.0) + _gaussian(time, 5.26, 0.06, 10.0)
    failed = np.full(time.size, 3.0)
    intensity = np.vstack([overlapped, failed])
    fitted = deconvolve_eic(
        time,
        overlapped,
        retention_time=5.0,
        loffset=0.4,
        roffset=0.4,
        stringency="7",
    )
    assert fitted.model is not None
    provider = DataProvider()
    provider._correct_time_series = lambda matrix, r: np.asarray(matrix, dtype=np.float64)
    raw_areas, _ = provider._areas_from_deconvolved(
        time,
        _mixed_bundle(time, fitted, failed),
        _mixed_row(),
        intensity,
        use_legacy=False,
        baseline_correction=False,
    )
    expected = calculate_peak_areas(
        time,
        intensity.ravel(),
        1,
        5.0,
        0.4,
        0.4,
        use_legacy=False,
        baseline_correction=False,
        chromatographic_peak_deconvolution_stringency="off",
    )
    mask = np.asarray(fitted.selected_mask, dtype=bool)
    isolated = _integrate_model_component(
        fitted.model,
        time[mask],
        np.asarray(fitted.selected, dtype=np.float64)[mask],
        channel=0,
        baseline_correction=False,
    )
    assert raw_areas == pytest.approx(expected)
    assert raw_areas[0] != pytest.approx(isolated)


def test_mixed_bundle_correction_and_baseline_use_raw_window():
    time = np.linspace(4.0, 6.0, 81)
    clean = _gaussian(time, 5.0, 0.08, 12.0) + 2.0
    failed = np.full(time.size, 3.0)
    intensity = np.vstack([clean, failed])
    fitted = deconvolve_eic(
        time,
        clean,
        retention_time=5.0,
        loffset=0.4,
        roffset=0.4,
        stringency="4",
    )
    assert fitted.model is not None
    provider = DataProvider()
    provider._correct_time_series = lambda matrix, r: np.asarray(
        matrix, dtype=np.float64
    ) * np.array([[0.5], [2.0]])
    raw_areas, corrected_areas = provider._areas_from_deconvolved(
        time,
        _mixed_bundle(time, fitted, failed),
        _mixed_row(),
        intensity,
        use_legacy=False,
        baseline_correction=True,
    )
    expected_raw = calculate_peak_areas(
        time,
        intensity.ravel(),
        1,
        5.0,
        0.4,
        0.4,
        use_legacy=False,
        baseline_correction=True,
        chromatographic_peak_deconvolution_stringency="off",
    )
    expected_corrected = calculate_peak_areas(
        time,
        (intensity * np.array([[0.5], [2.0]])).ravel(),
        1,
        5.0,
        0.4,
        0.4,
        use_legacy=False,
        baseline_correction=True,
        chromatographic_peak_deconvolution_stringency="off",
    )
    assert raw_areas == pytest.approx(expected_raw)
    assert corrected_areas == pytest.approx(expected_corrected)


def test_empty_ions_keep_export_on_the_model_path():
    time = np.linspace(0.0, 10.0, 201)
    fitted = _gaussian(time, 7.0, 0.25, 10.0)
    intensity = np.vstack(
        [np.zeros_like(time), fitted, np.full(time.size, 1e-12)]
    )
    bundle = deconvolve_channel_matrix(
        time,
        intensity,
        retention_time=7.0,
        loffset=4.0,
        roffset=4.0,
        stringency="4",
        fit_type="auto",
        noise_gate="balanced",
    )
    assert bundle.channels[0].result.empty
    assert bundle.channels[0].result.model is None
    assert bundle.channels[1].result.model is not None
    assert bundle.channels[2].result.empty
    assert bundle.uses_model_areas()

    provider = DataProvider()
    provider._correct_time_series = lambda matrix, r: np.asarray(matrix, dtype=np.float64)
    raw_areas, corrected_areas = provider._areas_from_deconvolved(
        time,
        bundle,
        {
            "label_atoms": 2,
            "retention_time": 7.0,
            "loffset": 4.0,
            "roffset": 4.0,
            "formula": "C1",
            "label_type": "C",
            "tbdms": 0,
            "meox": 0,
            "me": 0,
        },
        intensity,
        use_legacy=False,
        baseline_correction=False,
    )
    direct = calculate_peak_areas(
        time,
        intensity.ravel(),
        2,
        7.0,
        4.0,
        4.0,
        use_legacy=False,
        baseline_correction=False,
        chromatographic_peak_deconvolution_stringency="4",
        chromatographic_peak_deconvolution_fit_type="auto",
        chromatographic_peak_deconvolution_noise_gate="balanced",
    )
    assert raw_areas == pytest.approx(direct)
    assert raw_areas[0] == pytest.approx(0.0)
    assert raw_areas[1] > 0
    assert raw_areas[2] == pytest.approx(0.0)
    assert corrected_areas == pytest.approx(raw_areas)
