from __future__ import annotations

import pytest

from manic.models import database
from manic.processors.eic_correction_manager import process_all_corrections


def test_import(case, importer, benchmark, repeat, tmp_path):
    previous = database.DB_FILE
    try:
        rows = benchmark.pedantic(importer, args=(tmp_path / "bench.db",), rounds=repeat)
    finally:
        database.DB_FILE = previous
    assert rows == case.n_samples * case.n_compounds


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
