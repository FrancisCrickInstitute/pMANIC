from __future__ import annotations

import sqlite3
import zlib

import numpy as np
import pytest

from manic.models import database


def _assert_imported_dataset(path, case) -> None:
    with sqlite3.connect(path) as conn:
        sample_count = conn.execute(
            "SELECT COUNT(*) FROM samples WHERE deleted = 0"
        ).fetchone()[0]
        compound_count = conn.execute(
            "SELECT COUNT(*) FROM compounds WHERE deleted = 0"
        ).fetchone()[0]
        blobs = [
            row[0]
            for row in conn.execute(
                "SELECT y_axis FROM eic WHERE deleted = 0 "
                "ORDER BY sample_name, compound_name LIMIT 20"
            )
        ]
    assert sample_count == case.n_samples
    assert compound_count == case.n_compounds
    assert blobs
    assert all(
        np.any(np.frombuffer(zlib.decompress(blob), dtype=np.float64) > 0)
        for blob in blobs
    )


def test_import(case, importer, benchmark, repeat, tmp_path):
    db_path = tmp_path / "bench.db"
    previous = database.DB_FILE
    try:
        rows = benchmark.pedantic(importer, args=(db_path,), rounds=repeat)
    finally:
        database.DB_FILE = previous
    assert rows == case.n_samples * case.n_compounds
    _assert_imported_dataset(db_path, case)
