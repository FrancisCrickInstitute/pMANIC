"""Guards for export and compound-switching performance optimisations (#321)."""

from __future__ import annotations

import zlib
from concurrent.futures import Future

import numpy as np
import pytest

from manic.io.compound_reader import read_compound_with_session
from manic.io.data_provider import DataProvider, _integrate_task
from manic.models import database
from manic.processors import chromatographic_peak_deconvolution as deconv
from manic.processors import fit_prefetch
from manic.processors.display_deconvolution import (
    integrate_prepared_raw_areas,
    plot_display,
)
from manic.processors.eic_processing import get_eics_for_compound


def _seed_unlabelled_db(n_samples: int = 3) -> tuple[np.ndarray, list[str]]:
    time = np.linspace(4.5, 5.5, 101, dtype=np.float64)
    samples = [f"S{i}" for i in range(1, n_samples + 1)]
    with database.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO compounds (
                compound_name, retention_time, loffset, roffset, mass0,
                label_atoms, rt_tolerance, deconvolution_level,
                deconvolution_fit_type, deconvolution_noise_gate
            ) VALUES ('Target', 5.0, 0.15, 0.15, 200.0, 0, 0.1, '4', 'auto', 'balanced')
            """
        )
        conn.execute(
            "INSERT INTO compound_ions (compound_name, role, ordinal, mz, expected_ratio, ratio_tolerance) "
            "VALUES ('Target', 'quantifier', 0, 200.0, NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO compound_ions (compound_name, role, ordinal, mz, expected_ratio, ratio_tolerance) "
            "VALUES ('Target', 'qualifier', 1, 215.0, 0.4, 0.25)"
        )
        for i, sample in enumerate(samples):
            conn.execute("INSERT INTO samples (sample_name) VALUES (?)", (sample,))
            center = 5.0 + (i - 1) * 0.01
            q_trace = 1000.0 * np.exp(-0.5 * ((time - center) / 0.03) ** 2)
            v_trace = 400.0 * np.exp(-0.5 * ((time - center) / 0.03) ** 2)
            y = np.vstack([q_trace, v_trace]).astype(np.float64)
            conn.execute(
                "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
                "VALUES (?, 'Target', ?, ?, 0.5)",
                (
                    sample,
                    zlib.compress(time.tobytes()),
                    zlib.compress(y.tobytes()),
                ),
            )
    return time, samples


def test_thread_local_connection_reuses_same_db_and_isolates_nested_calls(tmp_path, monkeypatch):
    db_a = tmp_path / "a.db"
    db_b = tmp_path / "b.db"
    monkeypatch.setattr(database, "DB_FILE", db_a)
    database.init_db()

    with database.get_connection() as conn1:
        id1 = id(conn1)
        with database.get_connection() as nested:
            assert id(nested) != id1
    with database.get_connection() as conn2:
        assert id(conn2) == id1

    monkeypatch.setattr(database, "DB_FILE", db_b)
    database.init_db()
    with database.get_connection() as conn3:
        assert id(conn3) != id1


def test_cached_connection_discards_uncommitted_work_on_keyboard_interrupt():
    with pytest.raises(KeyboardInterrupt):
        with database.get_connection() as conn:
            conn.execute("INSERT INTO samples (sample_name) VALUES ('Aborted')")
            raise KeyboardInterrupt

    # A subsequent unrelated block must not commit the interrupted write.
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT sample_name FROM samples WHERE sample_name = 'Aborted'"
        ).fetchall()
    assert rows == []


def test_cached_connection_resets_session_pragmas_after_error():
    def failing_progress(step, _total, _msg):
        if step == 1:
            raise RuntimeError("abort mid-clear")

    with pytest.raises(RuntimeError, match="abort mid-clear"):
        database.clear_database(progress_callback=failing_progress, fast_mode=True)

    with database.get_connection() as conn:
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


@pytest.mark.parametrize("use_legacy", [False, True])
@pytest.mark.parametrize("deconv_level", ["off", "4"])
def test_seed_compound_raw_areas_matches_provider_compute(use_legacy, deconv_level):
    time = np.linspace(4.5, 5.5, 101, dtype=np.float64)
    peak = 1000.0 * np.exp(-0.5 * ((time - 5.0) / 0.03) ** 2)
    cases = [
        ("UnlabelledOne", 0, None, "C", peak.reshape(1, -1), False),
        ("UnlabelledQV", 0, None, "C", np.vstack([peak, 0.4 * peak]), True),
        ("LabelledGood", 2, "C3H7NO2", "C", np.vstack([peak, 0.2 * peak, 0.05 * peak]), False),
        ("LabelledNoFormula", 2, None, "C", np.vstack([peak, 0.2 * peak, 0.05 * peak]), False),
        ("LabelledNullType", 2, "C3H7NO2", None, np.vstack([peak, 0.2 * peak, 0.05 * peak]), False),
    ]
    with database.get_connection() as conn:
        conn.execute("INSERT INTO samples (sample_name) VALUES ('S1')")
        for name, atoms, formula, label_type, y, has_ions in cases:
            conn.execute(
                """
                INSERT INTO compounds (
                    compound_name, retention_time, loffset, roffset, mass0,
                    label_atoms, formula, label_type, deconvolution_level,
                    deconvolution_fit_type, deconvolution_noise_gate
                ) VALUES (?, 5.0, 0.15, 0.15, 200.0, ?, ?, ?, ?, 'auto', 'balanced')
                """,
                (name, atoms, formula, label_type, deconv_level),
            )
            if has_ions:
                conn.execute(
                    "INSERT INTO compound_ions (compound_name, role, ordinal, mz, expected_ratio, ratio_tolerance) "
                    "VALUES (?, 'quantifier', 0, 200.0, NULL, NULL)",
                    (name,),
                )
                conn.execute(
                    "INSERT INTO compound_ions (compound_name, role, ordinal, mz, expected_ratio, ratio_tolerance) "
                    "VALUES (?, 'qualifier', 1, 215.0, 0.4, 0.25)",
                    (name,),
                )
            conn.execute(
                "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
                "VALUES ('S1', ?, ?, ?, 0.5)",
                (name, zlib.compress(time.tobytes()), zlib.compress(y.astype(np.float64).tobytes())),
            )

    direct = DataProvider(use_legacy_integration=use_legacy)
    seeded = DataProvider(use_legacy_integration=use_legacy)

    for name, _atoms, _formula, _label_type, _y, _has_ions in cases:
        eics = get_eics_for_compound(name, ["S1"], use_corrected=False)
        compound = read_compound_with_session(name, "S1")
        prepared = plot_display(eics[0].time, eics[0].intensity, compound, use_corrected=False)
        raw_areas = integrate_prepared_raw_areas(
            eics[0].time, eics[0].intensity, compound, prepared, use_legacy=use_legacy
        )
        seeded.seed_compound_raw_areas(name, {"S1": raw_areas}, {"S1": compound})
        assert seeded.get_compound_areas("S1", name) == pytest.approx(
            direct.get_compound_areas("S1", name), rel=1e-12, abs=1e-12
        )
        assert seeded.get_compound_total_area("S1", name) == pytest.approx(
            direct.get_compound_total_area("S1", name), rel=1e-12, abs=1e-12
        )


def test_integrate_task_returns_none_observed_rt_without_quantifier():
    time = np.linspace(4.5, 5.5, 81, dtype=np.float64)
    y = 1000.0 * np.exp(-0.5 * ((time - 5.0) / 0.03) ** 2)
    row = {
        "sample_name": "S1",
        "compound_name": "Plain",
        "x_axis": zlib.compress(time.tobytes()),
        "baseline_correction": 1,
        "label_atoms": 0,
        "retention_time": 5.0,
        "loffset": 0.15,
        "roffset": 0.15,
        "formula": None,
        "label_type": "C",
        "tbdms": 0,
        "meox": 0,
        "me": 0,
        "deconvolution_level": "off",
        "deconvolution_fit_type": "auto",
        "deconvolution_noise_gate": "balanced",
        "channel_count": 1,
        "has_quantifier": 0,
    }
    sample, compound, areas, corrected, obs_rt = _integrate_task(
        (False, (row, zlib.compress(y.tobytes())))
    )
    assert (sample, compound) == ("S1", "Plain")
    assert len(areas) == 1 and areas[0] > 0
    assert corrected == areas
    assert obs_rt is None


def test_bulk_export_reuses_parent_cached_fits_and_observed_rt(monkeypatch):
    _time, samples = _seed_unlabelled_db(n_samples=3)
    deconv._fit_single_component_model_cached.cache_clear()
    deconv._fit_joint_component_model_cached.cache_clear()

    # Baseline cold load and cold per-sample identity assessments.
    cold_provider = DataProvider()
    cold_provider.load_bulk_sample_data()
    cold_areas = {s: cold_provider.get_compound_areas(s, "Target") for s in samples}
    cold_identity = {
        s: DataProvider().assess_unlabelled_identity(s, "Target") for s in samples
    }

    # Partially warm: fit only S1 on screen, then run a full bulk load. The
    # cache-miss tasks (S2, S3) must not record unfitted FitMissing placeholders.
    eics = get_eics_for_compound("Target", samples, use_corrected=False)
    first_compound = read_compound_with_session("Target", eics[0].sample_name)
    plot_display(eics[0].time, eics[0].intensity, first_compound, use_corrected=False)
    partial_provider = DataProvider()
    partial_provider.load_bulk_sample_data()
    partial_areas = {s: partial_provider.get_compound_areas(s, "Target") for s in samples}
    assert partial_areas == cold_areas

    # Now populate every sample's fit in the parent cache.
    for eic in eics[1:]:
        compound = read_compound_with_session("Target", eic.sample_name)
        plot_display(eic.time, eic.intensity, compound, use_corrected=False)

    assert deconv.has_cached_fits()

    # Lower the process-pool threshold to 1 so any unexpected miss would trigger start_pool.
    monkeypatch.setattr("manic.io.data_provider._PROCESS_POOL_MIN_TASKS", 1)

    def fail_start_pool():
        raise AssertionError("start_pool should not be called when all fits are cached")

    monkeypatch.setattr("manic.processors.fit_prefetch.start_pool", fail_start_pool)
    warm_provider = DataProvider()
    warm_provider.load_bulk_sample_data()
    warm_areas = {s: warm_provider.get_compound_areas(s, "Target") for s in samples}
    assert warm_areas == cold_areas

    # Unlabelled QC by sample reuses bulk-computed observed RTs without calling quantifier_apex_time.
    monkeypatch.setattr(
        "manic.io.data_provider.quantifier_apex_time",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should reuse cached observed_rt")),
    )
    by_sample = warm_provider.assess_unlabelled_identity_by_sample("Target", samples)
    assert set(by_sample.keys()) == set(samples)
    for sample in samples:
        assert by_sample[sample].observed_rt == cold_identity[sample].observed_rt
        assert by_sample[sample].status == cold_identity[sample].status


def test_batched_assess_unlabelled_identities_matches_per_sample():
    _time, samples = _seed_unlabelled_db(n_samples=3)
    provider = DataProvider()
    batched = provider.assess_unlabelled_identities("Target", samples)
    per_sample = {
        s: provider.assess_unlabelled_identity(s, "Target") for s in samples
    }
    by_name = {item.sample_name: item.qc for item in batched.samples}
    assert set(by_name.keys()) == set(per_sample.keys())
    for sample in samples:
        b = by_name[sample]
        p = per_sample[sample]
        assert b is not None
        assert b.status == p.status
        assert b.observed_rt == p.observed_rt
        assert b.quantifier_area == p.quantifier_area


def test_background_lookahead_prefetch_does_not_deadlock_on_immediate_or_cancelled_future(
    monkeypatch,
):
    """Both immediate completion and cancellation invoke done callbacks inline."""
    deconv._fit_single_component_model_cached.cache_clear()
    _time, samples = _seed_unlabelled_db(n_samples=2)

    class ImmediatePool:
        def submit(self, fn, key):
            fut = Future()
            fut.set_result(fn(key))
            return fut

    monkeypatch.setattr(fit_prefetch, "start_pool", lambda: ImmediatePool())
    fit_prefetch.cancel_background_prefetch()

    fit_prefetch.prefetch_display_fits_async("Target", samples, use_corrected=False)
    assert deconv._fit_single_component_model_cached.cache_info().currsize > 0
    assert not fit_prefetch._bg_futures

    # Also guard cancelling pending futures whose done callbacks acquire _bg_lock.
    deconv._fit_single_component_model_cached.cache_clear()

    class PendingPool:
        def submit(self, fn, key):
            return Future()

    monkeypatch.setattr(fit_prefetch, "start_pool", lambda: PendingPool())
    fit_prefetch.prefetch_display_fits_async("Target", samples, use_corrected=False)
    assert len(fit_prefetch._bg_futures) >= 2
    fit_prefetch.cancel_background_prefetch()
    assert not fit_prefetch._bg_futures


def test_reset_pool_shuts_down_broken_pool(monkeypatch):
    calls: list[tuple[bool, bool]] = []

    class FakePool:
        def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
            calls.append((wait, cancel_futures))

    fake = FakePool()
    monkeypatch.setattr(fit_prefetch, "_pool", fake)
    fit_prefetch.reset_pool(fake)
    assert fit_prefetch._pool is None
    assert calls == [(False, True)]
