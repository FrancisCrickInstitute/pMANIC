import sqlite3

import openpyxl

from manic.io.data_exporter import DataExporter
from manic.io.eic_importer import regenerate_all_eics_with_mass_tolerance
from manic.io.sample_reader import list_stale_samples
from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.models.database import get_connection
from conftest import SCHEMA
from test_restore_after_mass_tolerance_change import _write_cdf


def _raw_value_fills(path):
    raw = openpyxl.load_workbook(path)["Raw Values"]
    return {
        row[1].value: {cell.fill.fgColor.rgb for cell in row[2:]}
        for row in raw.iter_rows(min_row=5)
    }


def test_export_marks_a_sample_whose_cdf_failed_the_tolerance_reload(tmp_path):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, mass0, "
            "label_atoms, formula) VALUES ('Pyruvate', 5.0, 100.0, 1, 'C6H12O3NSi')"
        )
        for sample in ("s1", "s2"):
            _write_cdf(tmp_path / f"{sample}.cdf")
            conn.execute(
                "INSERT INTO samples (sample_name, file_name) VALUES (?, ?)",
                (sample, str(tmp_path / f"{sample}.cdf")),
            )
    regenerate_all_eics_with_mass_tolerance(0.2)

    (tmp_path / "s2.cdf").rename(tmp_path / "s2.moved")
    regenerate_all_eics_with_mass_tolerance(0.3)
    assert DataExporter(AnalysisMode.LABELLED).export_to_excel(str(tmp_path / "a.xlsx"))
    assert _raw_value_fills(tmp_path / "a.xlsx") == {
        "s1": {"00000000"},
        "s2": {"FFFFE699"},
    }

    (tmp_path / "s2.moved").rename(tmp_path / "s2.cdf")
    regenerate_all_eics_with_mass_tolerance(0.3)
    assert DataExporter(AnalysisMode.LABELLED).export_to_excel(str(tmp_path / "b.xlsx"))
    assert _raw_value_fills(tmp_path / "b.xlsx") == {
        "s1": {"00000000"},
        "s2": {"00000000"},
    }


def test_database_from_before_stale_tracking_loads_with_no_stale_samples(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "old.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    old_schema = SCHEMA.read_text(encoding="utf-8").replace(
        "    eics_stale   INTEGER DEFAULT 0,\n", ""
    )
    with sqlite3.connect(db_path) as conn:
        conn.executescript(old_schema)
        conn.execute("INSERT INTO samples (sample_name, file_name) VALUES ('s1', 'x')")

    database.init_db()

    assert list_stale_samples() == []
