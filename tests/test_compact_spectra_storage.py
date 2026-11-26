"""Tests for compact blob storage and migration of TIC and MS spectra (#199)."""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest

from manic.io.ms_reader import (
    ms_data_exists,
    read_ms_at_time,
    read_ms_times_for_sample,
    store_ms_data,
    store_ms_data_batch,
)
from manic.io.tic_reader import read_tic, store_tic_data, tic_data_exists
from manic.models import database


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "compact.db"
    database._close_cached_connection()
    monkeypatch.setattr(database, "DB_FILE", db_path)
    database.init_db()
    with database.get_connection() as conn:
        conn.execute("INSERT INTO samples (sample_name, file_name) VALUES ('S1', '/tmp/S1.cdf')")
        conn.execute("INSERT INTO samples (sample_name, file_name) VALUES ('S2', '/tmp/S2.cdf')")
    yield db_path
    database._close_cached_connection()


def test_tic_stores_one_compressed_row_drops_masked_and_sorts(isolated_db):
    times = np.ma.masked_array([2.0, 1.0, 3.0, 4.0], mask=[False, False, True, False])
    intensities = np.ma.masked_array([20.0, 10.0, 30.0, 40.0], mask=[False, False, False, True])

    assert store_tic_data("S1", times, intensities)
    assert tic_data_exists("S1")

    with database.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM tic_data WHERE sample_name = 'S1'").fetchone()[0]
    assert count == 1

    loaded = read_tic("S1")
    assert loaded is not None
    np.testing.assert_array_equal(loaded.time, np.array([1.0, 2.0]))
    np.testing.assert_array_equal(loaded.intensity, np.array([10.0, 20.0]))

    # Storing an all-masked TIC clears the previous row cleanly.
    all_masked = np.ma.masked_array([1.0], mask=[True])
    assert store_tic_data("S1", all_masked, all_masked)
    assert not tic_data_exists("S1")
    assert read_tic("S1") is None


def test_ms_batch_stores_one_row_per_scan_deduplicates_and_filters(isolated_db):
    mz_unsorted = np.ma.masked_array([200.0, 100.0, 150.0, 300.0], mask=[False, False, True, False])
    int_vals = np.ma.masked_array([50.0, 10.0, 99.0, 0.0], mask=[False, False, False, False])

    points = [
        (5.0, mz_unsorted, int_vals),
        (5.0, np.array([999.0]), np.array([1.0])),  # duplicate scan time ignored
        (7.5, np.array([73.0, 147.0]), np.array([100.0, 250.0])),
    ]
    assert store_ms_data_batch("S1", points)
    assert ms_data_exists("S1")
    assert ms_data_exists("S1", 5.0)
    assert read_ms_times_for_sample("S1") == [5.0, 7.5]

    with database.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM ms_data WHERE sample_name = 'S1'").fetchone()[0]
    assert count == 2

    spec = read_ms_at_time("S1", 5.02, tolerance=0.1)
    assert spec is not None
    assert spec.time == pytest.approx(5.0)
    np.testing.assert_array_equal(spec.mz, np.array([100.0, 200.0]))
    np.testing.assert_array_equal(spec.intensity, np.array([10.0, 50.0]))

    # Single-time replacement overwrites the scan cleanly.
    assert store_ms_data("S1", 5.0, np.array([120.0, 110.0]), np.array([5.0, 8.0]))
    replaced = read_ms_at_time("S1", 5.0, tolerance=0.05)
    assert replaced is not None
    np.testing.assert_array_equal(replaced.mz, np.array([110.0, 120.0]))
    np.testing.assert_array_equal(replaced.intensity, np.array([8.0, 5.0]))


def test_init_db_migrates_legacy_scalar_tic_and_ms_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    database._close_cached_connection()
    monkeypatch.setattr(database, "DB_FILE", db_path)

    # Build a legacy scalar schema directly.
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_name TEXT NOT NULL UNIQUE,
                file_name TEXT,
                deleted INTEGER DEFAULT 0
            );
            CREATE TABLE tic_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_name TEXT NOT NULL,
                time REAL NOT NULL,
                intensity REAL NOT NULL,
                deleted INTEGER DEFAULT 0,
                FOREIGN KEY (sample_name) REFERENCES samples(sample_name),
                UNIQUE(sample_name, time)
            );
            CREATE TABLE ms_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_name TEXT NOT NULL,
                time REAL NOT NULL,
                mz REAL NOT NULL,
                intensity REAL NOT NULL,
                deleted INTEGER DEFAULT 0,
                FOREIGN KEY (sample_name) REFERENCES samples(sample_name),
                UNIQUE(sample_name, time, mz)
            );
            INSERT INTO samples (sample_name, file_name) VALUES ('S1', '/tmp/S1.cdf');
            INSERT INTO tic_data (sample_name, time, intensity, deleted) VALUES
                ('S1', 2.0, 200.0, 0),
                ('S1', 1.0, 100.0, 0),
                ('S1', 3.0, 300.0, 1);
            INSERT INTO ms_data (sample_name, time, mz, intensity, deleted) VALUES
                ('S1', 5.0, 147.0, 25.0, 0),
                ('S1', 5.0, 73.0, 80.0, 0),
                ('S1', 5.0, 200.0, 10.0, 1),
                ('S1', 8.0, 318.0, 40.0, 0);
            """
        )

    database.init_db()

    with database.get_connection() as conn:
        tic_cols = {row[1] for row in conn.execute("PRAGMA table_info(tic_data)")}
        ms_cols = {row[1] for row in conn.execute("PRAGMA table_info(ms_data)")}
        tic_rows = conn.execute("SELECT COUNT(*) FROM tic_data").fetchone()[0]
        ms_rows = conn.execute("SELECT COUNT(*) FROM ms_data").fetchone()[0]

    assert "time_blob" in tic_cols and "intensity_blob" in tic_cols
    assert "mz_blob" in ms_cols and "intensity_blob" in ms_cols
    assert tic_rows == 1
    assert ms_rows == 2

    tic = read_tic("S1")
    assert tic is not None
    np.testing.assert_array_equal(tic.time, np.array([1.0, 2.0]))
    np.testing.assert_array_equal(tic.intensity, np.array([100.0, 200.0]))

    ms5 = read_ms_at_time("S1", 5.0, tolerance=0.05)
    assert ms5 is not None
    np.testing.assert_array_equal(ms5.mz, np.array([73.0, 147.0]))
    np.testing.assert_array_equal(ms5.intensity, np.array([80.0, 25.0]))
    assert read_ms_times_for_sample("S1") == [5.0, 8.0]
    database._close_cached_connection()
