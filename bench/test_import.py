from __future__ import annotations

import sqlite3
import zlib

import numpy as np
import pytest

from manic.models import database
from manic.processors.eic_correction_manager import process_all_corrections


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


def test_corrections(case, db_copy, benchmark, repeat):
    if not case.labelled:
        pytest.skip("natural abundance correction is a labelled-mode stage")

    def reset():
        # Corrections skip cells that already have a corrected row.
        with database.get_connection() as conn:
            conn.execute("DELETE FROM eic_corrected")
        return (), {}

    count = benchmark.pedantic(process_all_corrections, setup=reset, rounds=repeat)
    assert count == case.n_samples * case.n_compounds
