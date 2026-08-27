"""
Tests for RT window centering and automatic data reload logic.

Tests the boundary checking and window calculation logic used to determine
when EIC data needs to be reloaded with a new RT window center.

These tests follow TDD (Test-Driven Development) principles:
1. Tests are written first (before implementation)
2. Tests define expected behavior clearly
3. Implementation will be written to make these tests pass
"""

import sqlite3
import zlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from manic.io.eic_importer import _compress, regenerate_compound_eics
from manic.models import database
from manic.ui.integration_window_widget import (
    calculate_integration_boundaries,
    calculate_minimum_rt_window,
    check_boundaries_within_window,
    IntegrationWindow,
)

SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"


class TestIntegrationBoundaryCalculation:
    """Test calculation of integration boundaries from RT and offsets."""

    def test_symmetric_offsets(self):
        """Test with equal left and right offsets."""
        left, right = calculate_integration_boundaries(rt=10.0, loffset=0.5, roffset=0.5)
        assert left == 9.5
        assert right == 10.5

    def test_asymmetric_offsets(self):
        """Test with different left and right offsets."""
        left, right = calculate_integration_boundaries(rt=7.17, loffset=0.1, roffset=0.3)
        assert abs(left - 7.07) < 1e-10
        assert abs(right - 7.47) < 1e-10

    def test_zero_offsets(self):
        """Test with zero offsets (edge case)."""
        left, right = calculate_integration_boundaries(rt=5.0, loffset=0.0, roffset=0.0)
        assert left == 5.0
        assert right == 5.0

    def test_large_offsets(self):
        """Test with large offsets exceeding typical RT window."""
        left, right = calculate_integration_boundaries(rt=15.0, loffset=2.0, roffset=3.0)
        assert left == 13.0
        assert right == 18.0


class TestMinimumRTWindowCalculation:
    """Test calculation of minimum RT window needed for offsets."""

    def test_symmetric_offsets(self):
        """Test with equal offsets."""
        min_window = calculate_minimum_rt_window(loffset=0.2, roffset=0.2, buffer=0.1)
        assert abs(min_window - 0.3) < 1e-10  # max(0.2, 0.2) + 0.1 (floating point tolerance)

    def test_larger_left_offset(self):
        """Test with larger left offset."""
        min_window = calculate_minimum_rt_window(loffset=0.5, roffset=0.2, buffer=0.1)
        assert min_window == 0.6  # max(0.5, 0.2) + 0.1

    def test_larger_right_offset(self):
        """Test with larger right offset."""
        min_window = calculate_minimum_rt_window(loffset=0.1, roffset=0.8, buffer=0.1)
        assert min_window == 0.9  # max(0.1, 0.8) + 0.1

    def test_zero_buffer(self):
        """Test with no safety buffer."""
        min_window = calculate_minimum_rt_window(loffset=0.3, roffset=0.3, buffer=0.0)
        assert min_window == 0.3

    def test_custom_buffer(self):
        """Test with custom buffer size."""
        min_window = calculate_minimum_rt_window(loffset=0.2, roffset=0.2, buffer=0.05)
        assert min_window == 0.25


class TestBoundaryWindowChecking:
    """Test checking if boundaries fit within data window."""

    def test_boundaries_fit_exactly(self):
        """Test boundaries that exactly match window edges."""
        fits = check_boundaries_within_window(
            left_boundary=9.0,
            right_boundary=11.0,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is True

    def test_boundaries_fit_with_margin(self):
        """Test boundaries comfortably within window."""
        fits = check_boundaries_within_window(
            left_boundary=9.5,
            right_boundary=10.5,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is True

    def test_left_boundary_exceeds(self):
        """Test when left boundary falls outside window."""
        fits = check_boundaries_within_window(
            left_boundary=8.5,
            right_boundary=10.5,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is False

    def test_right_boundary_exceeds(self):
        """Test when right boundary falls outside window."""
        fits = check_boundaries_within_window(
            left_boundary=9.5,
            right_boundary=11.5,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is False

    def test_both_boundaries_exceed(self):
        """Test when both boundaries fall outside window."""
        fits = check_boundaries_within_window(
            left_boundary=8.5,
            right_boundary=11.5,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is False

    def test_floating_point_tolerance(self):
        """Test that small floating point errors are handled."""
        # Boundary is 0.0001 outside window, but within tolerance
        fits = check_boundaries_within_window(
            left_boundary=8.9999,
            right_boundary=10.5,
            window_min=9.0,
            window_max=11.0,
            tolerance=0.001,
        )
        assert fits is True

    def test_outside_tolerance(self):
        """Test that values outside tolerance are detected."""
        # Boundary is 0.002 outside window, exceeds tolerance
        fits = check_boundaries_within_window(
            left_boundary=8.998,
            right_boundary=10.5,
            window_min=9.0,
            window_max=11.0,
            tolerance=0.001,
        )
        assert fits is False


class TestReloadScenarios:
    """Test realistic scenarios that trigger or avoid reloads."""

    def test_small_rt_change_no_reload(self):
        """Test that small RT changes within window don't trigger reload."""
        # Initial: RT=10.0, offsets=0.1, window=[9.8, 10.2]
        # New: RT=10.05 (small shift)
        left, right = calculate_integration_boundaries(10.05, 0.1, 0.1)
        fits = check_boundaries_within_window(left, right, 9.8, 10.2)
        assert fits is True  # No reload needed

    def test_large_rt_change_needs_reload(self):
        """Test that large RT changes outside window trigger reload."""
        # Initial: RT=10.0, offsets=0.1, window=[9.8, 10.2]
        # New: RT=11.0 (moved outside window)
        left, right = calculate_integration_boundaries(11.0, 0.1, 0.1)
        fits = check_boundaries_within_window(left, right, 9.8, 10.2)
        assert fits is False  # Reload needed

    def test_offset_increase_needs_reload(self):
        """Test that increased offsets trigger reload."""
        # Initial: RT=10.0, offsets=0.1, window=[9.8, 10.2]
        # New: offsets=0.3 (now boundaries are [9.7, 10.3])
        left, right = calculate_integration_boundaries(10.0, 0.3, 0.3)
        fits = check_boundaries_within_window(left, right, 9.8, 10.2)
        assert fits is False  # Reload needed

    def test_offset_decrease_no_reload(self):
        """Test that decreased offsets don't trigger reload."""
        # Initial: RT=10.0, offsets=0.2, window=[9.8, 10.2]
        # New: offsets=0.1 (now boundaries are [9.9, 10.1])
        left, right = calculate_integration_boundaries(10.0, 0.1, 0.1)
        fits = check_boundaries_within_window(left, right, 9.8, 10.2)
        assert fits is True  # No reload needed

    def test_asymmetric_offset_change(self):
        """Test asymmetric offset changes."""
        # Initial: RT=7.17, window=[6.97, 7.37]
        # New: loffset=0.1, roffset=0.5 (boundaries=[7.07, 7.67])
        left, right = calculate_integration_boundaries(7.17, 0.1, 0.5)
        fits = check_boundaries_within_window(left, right, 6.97, 7.37)
        assert fits is False  # Reload needed (right boundary exceeds)

    def test_rt_window_expansion_needed(self):
        """Test scenario where RT window must be expanded for offsets."""
        # Current RT window: 0.2, but offsets require 0.5
        current_window = 0.2
        min_required = calculate_minimum_rt_window(0.5, 0.4, buffer=0.1)
        assert min_required > current_window  # Window expansion needed
        assert min_required == 0.6


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_negative_offsets_invalid(self):
        """Test behavior with negative offsets (shouldn't happen but test anyway)."""
        # Negative offsets would reverse boundaries
        left, right = calculate_integration_boundaries(10.0, -0.1, -0.1)
        assert left == 10.1  # "Left" is actually right
        assert right == 9.9  # "Right" is actually left
        # This would be caught by validation before reaching this code

    def test_very_small_window(self):
        """Test with very small data window."""
        left, right = calculate_integration_boundaries(10.0, 0.01, 0.01)
        fits = check_boundaries_within_window(left, right, 9.99, 10.01)
        assert fits is True

    def test_very_large_window(self):
        """Test with very large data window."""
        left, right = calculate_integration_boundaries(10.0, 1.0, 1.0)
        fits = check_boundaries_within_window(left, right, 5.0, 15.0)
        assert fits is True

    def test_zero_tolerance(self):
        """Test with zero tolerance (exact matching)."""
        fits = check_boundaries_within_window(
            left_boundary=9.0,
            right_boundary=11.0,
            window_min=9.0,
            window_max=11.0,
            tolerance=0.0,
        )
        assert fits is True


class TestBufferConstant:
    """Test that buffer constant is accessible and works correctly."""

    def test_buffer_from_constants(self):
        """Test that default buffer can be imported from constants."""
        from manic.constants import DEFAULT_RT_WINDOW_BUFFER

        # Buffer should be a positive number
        assert DEFAULT_RT_WINDOW_BUFFER > 0

        # Test it works with the calculation function
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

        # same offsets, different RTs per sample
        sample_rts = {"s1": 10.0, "s2": 20.0}

        # boundaries stay within each window
        need_reload = w._get_samples_needing_reload_with_sample_rts(
            sample_rts, new_loffset=0.5, new_roffset=0.5, samples_to_check=["s1", "s2"]
        )
        assert need_reload == []

        # now make offsets big enough to exceed both windows
        need_reload = w._get_samples_needing_reload_with_sample_rts(
            sample_rts, new_loffset=2.0, new_roffset=2.0, samples_to_check=["s1", "s2"]
        )
        assert set(need_reload) == {"s1", "s2"}


def _seed_eic_db(db_path: Path, cdf_path: Path):
    time_axis = np.array([7.07, 7.17, 7.27], dtype=np.float64)
    intensity = np.array([1.0, 10.0, 1.0], dtype=np.float64)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, mass0, label_atoms) "
            "VALUES (?, ?, ?, ?)",
            ("Glucose", 7.17, 100.0, 0),
        )
        conn.execute(
            "INSERT INTO samples (sample_name, file_name) VALUES (?, ?)",
            ("s1", str(cdf_path)),
        )
        conn.execute(
            """
            INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window, deleted)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            ("s1", "Glucose", _compress(time_axis), _compress(intensity), 0.2),
        )


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

    def test_corrected_rt_reloads_when_new_rt_leaves_stale_window(self):
        w = IntegrationWindow.__new__(IntegrationWindow)
        w._current_compound = "cmpd"
        w._data_window_bounds = {("cmpd", "s1"): (716.8, 717.2)}

        assert w._get_samples_needing_reload(7.17, 0.1, 0.1, ["s1"]) == ["s1"]

    def test_failed_extract_keeps_existing_eic(self, tmp_path, monkeypatch):
        db_path = tmp_path / "regen.db"
        cdf_path = tmp_path / "s1.cdf"
        cdf_path.write_bytes(b"cdf")
        monkeypatch.setattr(database, "DB_FILE", db_path)
        _seed_eic_db(db_path, cdf_path)

        monkeypatch.setattr(
            "manic.io.eic_importer.read_cdf_file",
            lambda _path: object(),
        )

        def _no_scans(*_args, **_kwargs):
            raise ValueError("No scans found within specified RT window")

        monkeypatch.setattr("manic.io.eic_importer.extract_eic", _no_scans)
        monkeypatch.setattr(
            "manic.processors.eic_correction_manager.apply_correction_to_eic",
            lambda *_args, **_kwargs: False,
        )

        regenerated = regenerate_compound_eics(
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

        assert regenerated == 0
        assert row[0] == 1

    def test_successful_extract_replaces_existing_eic(self, tmp_path, monkeypatch):
        db_path = tmp_path / "regen.db"
        cdf_path = tmp_path / "s1.cdf"
        cdf_path.write_bytes(b"cdf")
        monkeypatch.setattr(database, "DB_FILE", db_path)
        _seed_eic_db(db_path, cdf_path)

        new_time = np.array([7.00, 7.10, 7.20], dtype=np.float64)
        new_intensity = np.array([2.0, 20.0, 2.0], dtype=np.float64)
        monkeypatch.setattr(
            "manic.io.eic_importer.read_cdf_file",
            lambda _path: object(),
        )
        monkeypatch.setattr(
            "manic.io.eic_importer.extract_eic",
            lambda *_args, **_kwargs: SimpleNamespace(
                sample_name="s1",
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
                "SELECT x_axis FROM eic WHERE compound_name = ? AND sample_name = ?",
                ("Glucose", "s1"),
            ).fetchone()[0]

        restored = np.frombuffer(zlib.decompress(stored), dtype=np.float64)
        assert regenerated == 1
        assert count == 1
        assert restored == pytest.approx(new_time)
