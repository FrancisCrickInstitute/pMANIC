import sqlite3
import zlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from manic.io.compound_reader import read_compound
from manic.io.eic_reader import read_eics_batch
from manic.io.eic_importer import _compress, regenerate_compound_eics
from manic.models import database
from manic.models.session_activity import PendingRegeneration
from manic.processors.eic_calculator import EmptyRtWindowError
from manic.ui.main_window import MainWindow
from manic.ui.integration_window_widget import (
    calculate_integration_boundaries,
    calculate_minimum_rt_window,
    check_boundaries_within_window,
    IntegrationWindow,
)

SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"


class TestIntegrationBoundaryCalculation:
    def test_symmetric_offsets(self):
        left, right = calculate_integration_boundaries(rt=10.0, loffset=0.5, roffset=0.5)
        assert left == 9.5
        assert right == 10.5

    def test_asymmetric_offsets(self):
        left, right = calculate_integration_boundaries(rt=7.17, loffset=0.1, roffset=0.3)
        assert abs(left - 7.07) < 1e-10
        assert abs(right - 7.47) < 1e-10

    def test_zero_offsets(self):
        left, right = calculate_integration_boundaries(rt=5.0, loffset=0.0, roffset=0.0)
        assert left == 5.0
        assert right == 5.0

    def test_large_offsets(self):
        left, right = calculate_integration_boundaries(rt=15.0, loffset=2.0, roffset=3.0)
        assert left == 13.0
        assert right == 18.0


class TestMinimumRTWindowCalculation:
    def test_symmetric_offsets(self):
        min_window = calculate_minimum_rt_window(loffset=0.2, roffset=0.2, buffer=0.1)
        assert abs(min_window - 0.3) < 1e-10

    def test_larger_left_offset(self):
        min_window = calculate_minimum_rt_window(loffset=0.5, roffset=0.2, buffer=0.1)
        assert min_window == 0.6

    def test_larger_right_offset(self):
        min_window = calculate_minimum_rt_window(loffset=0.1, roffset=0.8, buffer=0.1)
        assert min_window == 0.9

    def test_zero_buffer(self):
        min_window = calculate_minimum_rt_window(loffset=0.3, roffset=0.3, buffer=0.0)
        assert min_window == 0.3

    def test_custom_buffer(self):
        min_window = calculate_minimum_rt_window(loffset=0.2, roffset=0.2, buffer=0.05)
        assert min_window == 0.25


class TestBoundaryWindowChecking:
    def test_boundaries_fit_exactly(self):
        fits = check_boundaries_within_window(
            left_boundary=9.0,
            right_boundary=11.0,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is True

    def test_boundaries_fit_with_margin(self):
        fits = check_boundaries_within_window(
            left_boundary=9.5,
            right_boundary=10.5,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is True

    def test_left_boundary_exceeds(self):
        fits = check_boundaries_within_window(
            left_boundary=8.5,
            right_boundary=10.5,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is False

    def test_right_boundary_exceeds(self):
        fits = check_boundaries_within_window(
            left_boundary=9.5,
            right_boundary=11.5,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is False

    def test_both_boundaries_exceed(self):
        fits = check_boundaries_within_window(
            left_boundary=8.5,
            right_boundary=11.5,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is False

    def test_floating_point_tolerance(self):
        fits = check_boundaries_within_window(
            left_boundary=8.9999,
            right_boundary=10.5,
            window_min=9.0,
            window_max=11.0,
            tolerance=0.001,
        )
        assert fits is True

    def test_outside_tolerance(self):
        fits = check_boundaries_within_window(
            left_boundary=8.998,
            right_boundary=10.5,
            window_min=9.0,
            window_max=11.0,
            tolerance=0.001,
        )
        assert fits is False


class TestReloadScenarios:
    def test_small_rt_change_no_reload(self):
        left, right = calculate_integration_boundaries(10.05, 0.1, 0.1)
        fits = check_boundaries_within_window(left, right, 9.8, 10.2)
        assert fits is True

    def test_large_rt_change_needs_reload(self):
        left, right = calculate_integration_boundaries(11.0, 0.1, 0.1)
        fits = check_boundaries_within_window(left, right, 9.8, 10.2)
        assert fits is False

    def test_offset_increase_needs_reload(self):
        left, right = calculate_integration_boundaries(10.0, 0.3, 0.3)
        fits = check_boundaries_within_window(left, right, 9.8, 10.2)
        assert fits is False

    def test_offset_decrease_no_reload(self):
        left, right = calculate_integration_boundaries(10.0, 0.1, 0.1)
        fits = check_boundaries_within_window(left, right, 9.8, 10.2)
        assert fits is True

    def test_asymmetric_offset_change(self):
        left, right = calculate_integration_boundaries(7.17, 0.1, 0.5)
        fits = check_boundaries_within_window(left, right, 6.97, 7.37)
        assert fits is False

    def test_rt_window_expansion_needed(self):
        current_window = 0.2
        min_required = calculate_minimum_rt_window(0.5, 0.4, buffer=0.1)
        assert min_required > current_window
        assert min_required == 0.6


class TestEdgeCases:
    def test_negative_offsets_invalid(self):
        left, right = calculate_integration_boundaries(10.0, -0.1, -0.1)
        assert left == 10.1
        assert right == 9.9

    def test_very_small_window(self):
        left, right = calculate_integration_boundaries(10.0, 0.01, 0.01)
        fits = check_boundaries_within_window(left, right, 9.99, 10.01)
        assert fits is True

    def test_very_large_window(self):
        left, right = calculate_integration_boundaries(10.0, 1.0, 1.0)
        fits = check_boundaries_within_window(left, right, 5.0, 15.0)
        assert fits is True

    def test_zero_tolerance(self):
        fits = check_boundaries_within_window(
            left_boundary=9.0,
            right_boundary=11.0,
            window_min=9.0,
            window_max=11.0,
            tolerance=0.0,
        )
        assert fits is True


class TestBufferConstant:
    def test_buffer_from_constants(self):
        from manic.constants import DEFAULT_RT_WINDOW_BUFFER

        assert DEFAULT_RT_WINDOW_BUFFER > 0

        min_window = calculate_minimum_rt_window(
            0.2, 0.3, buffer=DEFAULT_RT_WINDOW_BUFFER
        )
        assert min_window == 0.3 + DEFAULT_RT_WINDOW_BUFFER


class TestPerSampleReloadChecking:
    def test_reload_check_uses_per_sample_rt(self):
        # Avoid constructing QWidget subclasses in tests (requires a QApplication).
        w = IntegrationWindow.__new__(IntegrationWindow)
        w._current_compound = "cmpd"
        w._data_window_bounds = {
            ("cmpd", "s1"): (9.0, 11.0),
            ("cmpd", "s2"): (19.0, 21.0),
        }

        sample_rts = {"s1": 10.0, "s2": 20.0}

        need_reload = w._get_samples_needing_reload_with_sample_rts(
            sample_rts, new_loffset=0.5, new_roffset=0.5, samples_to_check=["s1", "s2"]
        )
        assert need_reload == []

        need_reload = w._get_samples_needing_reload_with_sample_rts(
            sample_rts, new_loffset=2.0, new_roffset=2.0, samples_to_check=["s1", "s2"]
        )
        assert set(need_reload) == {"s1", "s2"}

    def test_offset_only_reload_emits_each_sample_retention_time(self, monkeypatch):
        sample_rts = {"s1": 7.1, "s2": 7.5}
        monkeypatch.setattr(
            "manic.ui.integration_window_widget.read_compound_with_session",
            lambda _compound, sample: SimpleNamespace(
                retention_time=sample_rts[sample]
            ),
        )
        emitted = []
        fields = {
            "tr_input": SimpleNamespace(text=lambda: "7.1 - 7.5"),
            "tr_window_input": SimpleNamespace(text=lambda: "0.2"),
        }
        window = SimpleNamespace(
            _current_compound="Glucose",
            _selected_samples=["s1", "s2"],
            _all_samples=["s1", "s2"],
            _get_validated_inputs=lambda: (7.1, 2.0, 2.0),
            _get_samples_needing_reload_with_sample_rts=(
                lambda *_args: ["s1", "s2"]
            ),
            findChild=lambda _widget_type, name: fields.get(name),
            data_regeneration_requested=SimpleNamespace(
                emit=lambda *args: emitted.append(args)
            ),
            _show_message=lambda *_args: None,
        )

        IntegrationWindow._on_apply_clicked(window)

        assert emitted == [
            ("Glucose", 2.1, ["s1", "s2"], sample_rts)
        ]

    def test_update_tr_window_emits_each_sample_retention_time(self, monkeypatch):
        sample_rts = {"s1": 7.1, "s2": 7.5}
        monkeypatch.setattr(
            "manic.ui.integration_window_widget.read_compound_with_session",
            lambda _compound, sample: SimpleNamespace(
                retention_time=sample_rts[sample]
            ),
        )
        emitted = []
        fields = {
            "tr_input": SimpleNamespace(text=lambda: "7.1 - 7.5"),
            "tr_window_input": SimpleNamespace(text=lambda: "0.2"),
        }
        window = SimpleNamespace(
            _current_compound="Glucose",
            _all_samples=["s1", "s2"],
            findChild=lambda _widget_type, name: fields.get(name),
            data_regeneration_requested=SimpleNamespace(
                emit=lambda *args: emitted.append(args)
            ),
            _get_current_retention_time=lambda: 7.1,
            _show_message=lambda *_args: None,
        )

        IntegrationWindow._on_regenerate_clicked(window)

        assert emitted == [
            ("Glucose", 0.2, ["s1", "s2"], sample_rts)
        ]


def _seed_eic_db(db_path: Path, sample_files: dict[str, Path]):
    time_axis = np.array([7.07, 7.17, 7.27], dtype=np.float64)
    intensity = np.array([1.0, 10.0, 1.0], dtype=np.float64)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, mass0, label_atoms) "
            "VALUES (?, ?, ?, ?)",
            ("Glucose", 7.17, 100.0, 0),
        )
        for sample_name, cdf_path in sample_files.items():
            conn.execute(
                "INSERT INTO samples (sample_name, file_name) VALUES (?, ?)",
                (sample_name, str(cdf_path)),
            )
            conn.execute(
                """
                INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window, deleted)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (
                    sample_name,
                    "Glucose",
                    _compress(time_axis),
                    _compress(intensity),
                    0.2,
                ),
            )


def test_batch_read_falls_back_to_raw_per_sample(tmp_path, monkeypatch):
    db_path = tmp_path / "eics.db"
    sample_files = {
        "s1": tmp_path / "s1.cdf",
        "s2": tmp_path / "s2.cdf",
    }
    monkeypatch.setattr(database, "DB_FILE", db_path)
    _seed_eic_db(db_path, sample_files)
    corrected = np.array([2.0, 20.0, 2.0], dtype=np.float64)
    time_axis = np.array([7.07, 7.17, 7.27], dtype=np.float64)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO eic_corrected (
                sample_name, compound_name, x_axis, y_axis_corrected
            ) VALUES (?, ?, ?, ?)
            """,
            (
                "s1",
                "Glucose",
                _compress(time_axis),
                _compress(corrected),
            ),
        )

    eics = read_eics_batch(
        ["s1", "s2"],
        read_compound("Glucose"),
        use_corrected=True,
    )

    assert [eic.sample_name for eic in eics] == ["s1", "s2"]
    assert eics[0].intensity == pytest.approx(corrected)
    assert eics[1].intensity == pytest.approx([1.0, 10.0, 1.0])


class TestRecoveryAfterEmptyExtract:
    def test_refresh_drops_bounds_when_eic_missing(self, monkeypatch):
        w = IntegrationWindow.__new__(IntegrationWindow)
        w._current_compound = "cmpd"
        w._data_window_bounds = {("cmpd", "s1"): (6.97, 7.37)}

        def _no_eics(*_args, **_kwargs):
            raise LookupError("No EIC data found")

        monkeypatch.setattr(
            "manic.ui.integration_window_widget.get_eics_for_compound",
            _no_eics,
        )
        w.refresh_data_window_bounds("cmpd", ["s1"])

        assert ("cmpd", "s1") not in w._data_window_bounds
        assert w._get_samples_needing_reload(7.17, 0.1, 0.1, ["s1"]) == ["s1"]

    def test_failed_extract_rejects_change_and_keeps_existing_eic(
        self, tmp_path, monkeypatch
    ):
        db_path = tmp_path / "regen.db"
        cdf_path = tmp_path / "s1.cdf"
        cdf_path.write_bytes(b"cdf")
        monkeypatch.setattr(database, "DB_FILE", db_path)
        _seed_eic_db(db_path, {"s1": cdf_path})

        monkeypatch.setattr(
            "manic.io.eic_importer.read_cdf_file",
            lambda _path: object(),
        )

        def _no_scans(*_args, **_kwargs):
            raise EmptyRtWindowError("no scans inside RT window")

        monkeypatch.setattr("manic.io.eic_importer.extract_eic", _no_scans)
        monkeypatch.setattr(
            "manic.processors.eic_correction_manager.apply_correction_to_eic",
            lambda *_args, **_kwargs: False,
        )

        with pytest.raises(
            ValueError,
            match="Cannot apply retention time 717.000 min.*sample 's1'.*No changes were applied",
        ):
            regenerate_compound_eics(
                "Glucose",
                0.2,
                ["s1"],
                retention_time=717.0,
            )

        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM eic WHERE compound_name = ? AND sample_name = ? AND deleted = 0",
                ("Glucose", "s1"),
            ).fetchone()

        assert row[0] == 1

    def test_missing_sample_rejects_before_extracting(self, tmp_path, monkeypatch):
        db_path = tmp_path / "regen.db"
        cdf_path = tmp_path / "s1.cdf"
        cdf_path.write_bytes(b"cdf")
        monkeypatch.setattr(database, "DB_FILE", db_path)
        _seed_eic_db(db_path, {"s1": cdf_path})

        with pytest.raises(
            ValueError,
            match="sample 'missing'.*No changes were applied",
        ):
            regenerate_compound_eics(
                "Glucose",
                0.2,
                ["s1", "missing"],
                retention_time=7.17,
            )

        with sqlite3.connect(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM eic WHERE compound_name = ?",
                ("Glucose",),
            ).fetchone()[0]
        assert count == 1

    def test_missing_cdf_rejects_before_writing(self, tmp_path, monkeypatch):
        db_path = tmp_path / "regen.db"
        missing_cdf = tmp_path / "missing.cdf"
        monkeypatch.setattr(database, "DB_FILE", db_path)
        _seed_eic_db(db_path, {"s1": missing_cdf})

        with pytest.raises(
            ValueError,
            match="CDF file not found for sample 's1'.*No changes were applied",
        ):
            regenerate_compound_eics(
                "Glucose",
                0.2,
                ["s1"],
                retention_time=7.17,
            )

        with sqlite3.connect(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM eic WHERE compound_name = ?",
                ("Glucose",),
            ).fetchone()[0]
        assert count == 1

    def test_unreadable_cdf_rejects_before_writing(self, tmp_path, monkeypatch):
        db_path = tmp_path / "regen.db"
        cdf_path = tmp_path / "s1.cdf"
        cdf_path.write_bytes(b"cdf")
        monkeypatch.setattr(database, "DB_FILE", db_path)
        _seed_eic_db(db_path, {"s1": cdf_path})

        def _unreadable(_path):
            raise OSError("invalid CDF")

        monkeypatch.setattr(
            "manic.io.eic_importer.read_cdf_file",
            _unreadable,
        )

        with pytest.raises(
            RuntimeError,
            match="Could not regenerate sample 's1'.*No changes were applied",
        ):
            regenerate_compound_eics(
                "Glucose",
                0.2,
                ["s1"],
                retention_time=7.17,
            )

        with sqlite3.connect(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM eic WHERE compound_name = ?",
                ("Glucose",),
            ).fetchone()[0]
        assert count == 1

    def test_one_empty_sample_rejects_entire_batch(self, tmp_path, monkeypatch):
        db_path = tmp_path / "regen.db"
        sample_files = {
            "s1": tmp_path / "s1.cdf",
            "s2": tmp_path / "s2.cdf",
        }
        for cdf_path in sample_files.values():
            cdf_path.write_bytes(b"cdf")
        monkeypatch.setattr(database, "DB_FILE", db_path)
        _seed_eic_db(db_path, sample_files)

        monkeypatch.setattr(
            "manic.io.eic_importer.read_cdf_file",
            lambda path: SimpleNamespace(sample_name=Path(path).stem),
        )
        replacement_time = np.array([717.0, 717.1], dtype=np.float64)

        def _extract(_compound, _rt, _mz, cdf, *_args):
            if cdf.sample_name == "s2":
                raise EmptyRtWindowError("no scans inside RT window")
            return SimpleNamespace(
                sample_name=cdf.sample_name,
                compound_name="Glucose",
                time=replacement_time,
                intensity=np.array([2.0, 20.0], dtype=np.float64),
            )

        monkeypatch.setattr("manic.io.eic_importer.extract_eic", _extract)

        with pytest.raises(ValueError, match="sample 's2'"):
            regenerate_compound_eics(
                "Glucose",
                0.2,
                ["s1", "s2"],
                retention_time=717.0,
            )

        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT sample_name, x_axis FROM eic ORDER BY sample_name"
            ).fetchall()

        original_time = np.array([7.07, 7.17, 7.27], dtype=np.float64)
        assert [row[0] for row in rows] == ["s1", "s2"]
        for row in rows:
            stored_time = np.frombuffer(zlib.decompress(row[1]), dtype=np.float64)
            assert stored_time == pytest.approx(original_time)

    def test_successful_extract_replaces_existing_eic(self, tmp_path, monkeypatch):
        db_path = tmp_path / "regen.db"
        cdf_path = tmp_path / "s1.cdf"
        cdf_path.write_bytes(b"cdf")
        monkeypatch.setattr(database, "DB_FILE", db_path)
        _seed_eic_db(db_path, {"s1": cdf_path})

        new_time = np.array([7.00, 7.10, 7.20], dtype=np.float64)
        new_intensity = np.array([2.0, 20.0, 2.0], dtype=np.float64)
        monkeypatch.setattr(
            "manic.io.eic_importer.read_cdf_file",
            lambda _path: object(),
        )
        monkeypatch.setattr(
            "manic.io.eic_importer.extract_eic",
            lambda *_args, **_kwargs: SimpleNamespace(
                sample_name="cdf-stem",
                compound_name="Glucose",
                time=new_time,
                intensity=new_intensity,
            ),
        )
        monkeypatch.setattr(
            "manic.processors.eic_correction_manager.apply_correction_to_eic",
            lambda *_args, **_kwargs: False,
        )

        regenerated = regenerate_compound_eics(
            "Glucose",
            0.2,
            ["s1"],
            retention_time=7.10,
        )

        with sqlite3.connect(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM eic WHERE compound_name = ? AND sample_name = ?",
                ("Glucose", "s1"),
            ).fetchone()[0]
            stored = conn.execute(
                "SELECT sample_name, x_axis FROM eic "
                "WHERE compound_name = ? AND sample_name = ?",
                ("Glucose", "s1"),
            ).fetchone()

        restored = np.frombuffer(zlib.decompress(stored[1]), dtype=np.float64)
        assert regenerated == 1
        assert count == 1
        assert stored[0] == "s1"
        assert restored == pytest.approx(new_time)

    def test_eic_and_session_values_commit_together(self, tmp_path, monkeypatch):
        db_path = tmp_path / "regen.db"
        cdf_path = tmp_path / "s1.cdf"
        cdf_path.write_bytes(b"cdf")
        monkeypatch.setattr(database, "DB_FILE", db_path)
        _seed_eic_db(db_path, {"s1": cdf_path})
        monkeypatch.setattr(
            "manic.io.eic_importer.read_cdf_file",
            lambda _path: SimpleNamespace(sample_name="s1"),
        )
        monkeypatch.setattr(
            "manic.io.eic_importer.extract_eic",
            lambda *_args, **_kwargs: SimpleNamespace(
                time=np.array([7.0, 7.1, 7.2]),
                intensity=np.array([2.0, 20.0, 2.0]),
            ),
        )
        monkeypatch.setattr(
            "manic.processors.eic_correction_manager.apply_correction_to_eic",
            lambda *_args, **_kwargs: False,
        )
        pending = PendingRegeneration(
            compound_name="Glucose",
            retention_time=7.1,
            loffset=0.2,
            roffset=0.3,
            sample_names=("s1",),
            regenerated_sample_names=("s1",),
        )

        regenerate_compound_eics(
            "Glucose",
            0.3,
            ["s1"],
            retention_time=7.1,
            pending_regeneration=pending,
        )

        with sqlite3.connect(db_path) as conn:
            session = conn.execute(
                """
                SELECT retention_time, loffset, roffset
                FROM session_activity
                WHERE compound_name = ? AND sample_name = ?
                """,
                ("Glucose", "s1"),
            ).fetchone()
        assert session == pytest.approx((7.1, 0.2, 0.3))

    def test_session_write_failure_rolls_back_eic_replace(
        self, tmp_path, monkeypatch
    ):
        db_path = tmp_path / "regen.db"
        cdf_path = tmp_path / "s1.cdf"
        cdf_path.write_bytes(b"cdf")
        monkeypatch.setattr(database, "DB_FILE", db_path)
        _seed_eic_db(db_path, {"s1": cdf_path})
        monkeypatch.setattr(
            "manic.io.eic_importer.read_cdf_file",
            lambda _path: SimpleNamespace(sample_name="s1"),
        )
        monkeypatch.setattr(
            "manic.io.eic_importer.extract_eic",
            lambda *_args, **_kwargs: SimpleNamespace(
                time=np.array([717.0, 717.1, 717.2]),
                intensity=np.array([2.0, 20.0, 2.0]),
            ),
        )

        def _session_write_fails(**_kwargs):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(
            "manic.models.session_activity.SessionActivityService."
            "update_session_data",
            _session_write_fails,
        )
        pending = PendingRegeneration(
            compound_name="Glucose",
            retention_time=717.1,
            loffset=0.2,
            roffset=0.3,
            sample_names=("s1",),
            regenerated_sample_names=("s1",),
        )

        with pytest.raises(
            RuntimeError,
            match="Could not commit regenerated data.*No changes were applied",
        ):
            regenerate_compound_eics(
                "Glucose",
                0.3,
                ["s1"],
                retention_time=717.1,
                pending_regeneration=pending,
            )

        with sqlite3.connect(db_path) as conn:
            stored = conn.execute(
                "SELECT x_axis FROM eic WHERE compound_name = ? AND sample_name = ?",
                ("Glucose", "s1"),
            ).fetchone()[0]
            session_count = conn.execute(
                "SELECT COUNT(*) FROM session_activity"
            ).fetchone()[0]
        restored = np.frombuffer(zlib.decompress(stored), dtype=np.float64)
        assert restored == pytest.approx([7.07, 7.17, 7.27])
        assert session_count == 0

    def test_lost_correction_rejects_change_and_keeps_existing_rows(
        self, tmp_path, monkeypatch
    ):
        db_path = tmp_path / "regen.db"
        cdf_path = tmp_path / "s1.cdf"
        cdf_path.write_bytes(b"cdf")
        monkeypatch.setattr(database, "DB_FILE", db_path)
        _seed_eic_db(db_path, {"s1": cdf_path})
        original_time = np.array([7.07, 7.17, 7.27], dtype=np.float64)
        original_corrected = np.array([2.0, 20.0, 2.0], dtype=np.float64)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO eic_corrected (
                    sample_name, compound_name, x_axis, y_axis_corrected
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    "s1",
                    "Glucose",
                    _compress(original_time),
                    _compress(original_corrected),
                ),
            )
        monkeypatch.setattr(
            "manic.io.eic_importer.read_cdf_file",
            lambda _path: object(),
        )
        monkeypatch.setattr(
            "manic.io.eic_importer.extract_eic",
            lambda *_args, **_kwargs: SimpleNamespace(
                time=np.array([7.0, 7.1, 7.2]),
                intensity=np.array([3.0, 30.0, 3.0]),
            ),
        )
        monkeypatch.setattr(
            "manic.io.eic_importer.compute_corrected_intensity",
            lambda *_args, **_kwargs: None,
        )

        with pytest.raises(
            RuntimeError,
            match="Could not recreate the natural abundance correction.*sample 's1'",
        ):
            regenerate_compound_eics(
                "Glucose",
                0.2,
                ["s1"],
                retention_time=7.10,
            )

        with sqlite3.connect(db_path) as conn:
            raw = conn.execute(
                "SELECT x_axis FROM eic WHERE compound_name = ? AND sample_name = ?",
                ("Glucose", "s1"),
            ).fetchone()[0]
            corrected = conn.execute(
                """
                SELECT y_axis_corrected FROM eic_corrected
                WHERE compound_name = ? AND sample_name = ?
                """,
                ("Glucose", "s1"),
            ).fetchone()[0]
        assert np.frombuffer(zlib.decompress(raw), dtype=np.float64) == pytest.approx(
            original_time
        )
        assert np.frombuffer(
            zlib.decompress(corrected), dtype=np.float64
        ) == pytest.approx(original_corrected)

    def test_extracts_each_sample_around_its_own_retention_time(
        self, tmp_path, monkeypatch
    ):
        db_path = tmp_path / "regen.db"
        sample_files = {
            "s1": tmp_path / "s1.cdf",
            "s2": tmp_path / "s2.cdf",
        }
        for cdf_path in sample_files.values():
            cdf_path.write_bytes(b"cdf")
        monkeypatch.setattr(database, "DB_FILE", db_path)
        _seed_eic_db(db_path, sample_files)
        monkeypatch.setattr(
            "manic.io.eic_importer.read_cdf_file",
            lambda path: SimpleNamespace(sample_name=Path(path).stem),
        )
        seen = []

        def _extract(compound, rt, _mz, cdf, *_args):
            seen.append((cdf.sample_name, rt))
            return SimpleNamespace(
                sample_name=cdf.sample_name,
                compound_name=compound,
                time=np.array([rt - 0.1, rt, rt + 0.1]),
                intensity=np.array([1.0, 10.0, 1.0]),
            )

        monkeypatch.setattr("manic.io.eic_importer.extract_eic", _extract)
        monkeypatch.setattr(
            "manic.processors.eic_correction_manager.apply_correction_to_eic",
            lambda *_args, **_kwargs: False,
        )

        regenerated = regenerate_compound_eics(
            "Glucose",
            0.2,
            ["s1", "s2"],
            retention_time={"s1": 7.1, "s2": 7.5},
        )

        assert regenerated == 2
        assert seen == [("s1", 7.1), ("s2", 7.5)]


class TestRegenerationCompletion:
    def test_start_failure_uses_regeneration_failure_cleanup(self):
        errors = []

        def _cannot_build(*_args):
            raise RuntimeError("thread unavailable")

        window = SimpleNamespace(
            _build_progress_dialog=_cannot_build,
            _regeneration_failed=lambda error: errors.append(error),
        )

        MainWindow.on_data_regeneration_requested(
            window,
            "Glucose",
            0.2,
            ["s1"],
            7.17,
        )

        assert errors == [
            "Could not start data regeneration. "
            "No changes were applied. thread unavailable"
        ]

    def test_success_invalidates_validation_and_refreshes_mode_charts(self):
        calls = []

        class ValidationProvider:
            def invalidate_cache(self):
                calls.append("invalidate")

        integration = SimpleNamespace(
            _pending_session_update=None,
            populate_fields_from_plots=lambda *_args: calls.append("fields"),
            populate_tr_window_field=lambda *_args: calls.append("window"),
        )
        graph_view = SimpleNamespace(
            get_current_compound=lambda: "Glucose",
            get_selected_samples=lambda: ["s1"],
            get_current_samples=lambda: ["s1"],
            refresh_plots_with_session_data=lambda *_args, **_kwargs: calls.append("plots"),
        )
        message = SimpleNamespace(exec=lambda: None)
        window = SimpleNamespace(
            toolbar=SimpleNamespace(integration=integration),
            graph_view=graph_view,
            _validation_provider=ValidationProvider(),
            min_peak_height_ratio=0,
            _identity_snapshot=lambda *_args: (None, None),
            _refresh_mode_charts=lambda *_args, **_kwargs: calls.append("charts"),
            _create_message_box=lambda *_args: message,
        )

        MainWindow._regeneration_completed(window, 1)

        assert calls == ["invalidate", "fields", "window", "plots", "charts"]

    def test_offset_only_success_refreshes_without_formatting_none(self):
        calls = []
        integration = SimpleNamespace(
            _pending_session_update=PendingRegeneration(
                compound_name="Glucose",
                retention_time=None,
                loffset=0.1,
                roffset=0.1,
                sample_names=("s1",),
                regenerated_sample_names=("s1",),
            ),
            refresh_data_window_bounds=lambda *_args: calls.append("bounds"),
            populate_fields_from_plots=lambda *_args: calls.append("fields"),
            populate_tr_window_field=lambda *_args: calls.append("window"),
        )
        graph_view = SimpleNamespace(
            get_current_compound=lambda: "Glucose",
            get_selected_samples=lambda: ["s1"],
            get_current_samples=lambda: ["s1"],
            refresh_plots_with_session_data=lambda *_args, **_kwargs: calls.append("plots"),
        )
        messages = []
        window = SimpleNamespace(
            toolbar=SimpleNamespace(integration=integration),
            graph_view=graph_view,
            _validation_provider=None,
            min_peak_height_ratio=0,
            _identity_snapshot=lambda *_args: (None, None),
            _refresh_mode_charts=lambda *_args, **_kwargs: calls.append("charts"),
            _create_message_box=lambda *args: messages.append(args)
            or SimpleNamespace(exec=lambda: None),
        )

        MainWindow._regeneration_completed(window, 1)

        assert calls == [
            "bounds",
            "fields",
            "window",
            "plots",
            "charts",
        ]
        assert messages[0][0:2] == ("information", "Regeneration Complete")

    def test_refresh_failure_does_not_claim_complete(self):
        def _refresh_fails(*_args):
            raise RuntimeError("plot widget gone")

        integration = SimpleNamespace(
            _pending_session_update=None,
            populate_fields_from_plots=_refresh_fails,
            populate_tr_window_field=lambda *_args: None,
        )
        messages = []
        window = SimpleNamespace(
            toolbar=SimpleNamespace(integration=integration),
            graph_view=SimpleNamespace(
                get_current_compound=lambda: "Glucose",
                get_selected_samples=lambda: ["s1"],
                get_current_samples=lambda: ["s1"],
            ),
            _validation_provider=None,
            min_peak_height_ratio=0,
            _create_message_box=lambda *args: messages.append(args)
            or SimpleNamespace(exec=lambda: None),
        )

        MainWindow._regeneration_completed(window, 1)

        assert messages == [
            (
                "warning",
                "Plots Did Not Refresh",
                "The new EIC data was saved, but the display failed: "
                "plot widget gone\n\nRefresh the plots manually.",
            )
        ]

    def test_failure_discards_pending_session_update(self):
        refreshed = []
        integration = SimpleNamespace(
            _pending_session_update=PendingRegeneration(
                compound_name="Glucose",
                retention_time=717.0,
                loffset=0.1,
                roffset=0.1,
                sample_names=("s1",),
                regenerated_sample_names=("s1",),
            ),
            populate_fields_from_plots=lambda *_args: refreshed.append("fields"),
            populate_tr_window_field=lambda *_args: refreshed.append("window"),
        )
        shown = []
        messages = []
        message = SimpleNamespace(exec=lambda: shown.append("shown"))
        window = SimpleNamespace(
            toolbar=SimpleNamespace(integration=integration),
            graph_view=SimpleNamespace(
                get_current_compound=lambda: "Glucose",
                get_selected_samples=lambda: ["s1"],
                get_current_samples=lambda: ["s1"],
            ),
            _create_message_box=lambda *args: messages.append(args) or message,
        )

        MainWindow._regeneration_failed(
            window,
            "Cannot apply retention time 717.000 min. No changes were applied.",
        )

        assert integration._pending_session_update is None
        assert refreshed == ["fields", "window"]
        assert shown == ["shown"]
        assert messages == [
            (
                "critical",
                "Regeneration Blocked",
                "Cannot apply retention time 717.000 min. No changes were applied.",
            )
        ]
