import zlib

import numpy as np
import openpyxl
import pytest

from manic.io.data_exporter import DataExporter
from manic.models import database
from manic.models.analysis import AnalysisMode
from manic.models.peak_review import set_peak_review
from manic.validation.peak_verdict import PeakReview

def _insert_compound(name: str, rt: float, mass0: float) -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, label_atoms, "
            "int_std_amount, amount_in_std_mix, mm_files) VALUES (?, ?, 0.6, 0.6, ?, 1, 10.0, 1.0, 'S1')",
            (name, rt, mass0),
        )


def _insert_eic(sample: str, compound: str, time, matrix) -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO samples (sample_name, file_name) VALUES (?, ?)",
            (sample, f"/fake/{sample}.cdf"),
        )
        conn.execute(
            "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
            "VALUES (?, ?, ?, ?, 0.6)",
            (
                sample,
                compound,
                zlib.compress(np.asarray(time, dtype=np.float64).tobytes()),
                zlib.compress(np.asarray(matrix, dtype=np.float64).ravel().tobytes()),
            ),
        )


def _cells_for(sheet, sample: str, compound: str):
    header = [cell.value for cell in sheet[1]]
    columns = [i for i, name in enumerate(header, start=1) if name == compound]
    assert columns, header
    for row in sheet.iter_rows(min_row=2):
        if any(cell.value == sample for cell in row[:2]):
            return [row[col - 1] for col in columns]
    raise AssertionError(f"{sample} not found")


def test_labelled_raw_values_fill_a_rejected_peak(empty_db, tmp_path):
    _insert_compound("Target", 1.0, 100.0)
    _insert_compound("Std", 2.0, 200.0)
    time = [0.0, 1.0, 2.0, 3.0]
    _insert_eic("S1", "Target", time, [[0.0, 10.0, 0.0, 0.0], [0.0, 4.0, 0.0, 0.0]])
    _insert_eic("S1", "Std", time, [[0.0, 0.0, 20.0, 0.0], [0.0, 0.0, 6.0, 0.0]])
    set_peak_review("Target", "S1", PeakReview.REJECTED)

    exporter = DataExporter(AnalysisMode.LABELLED)
    exporter.set_internal_standard("Std")
    exporter.set_min_peak_area_ratio(0.01)
    export_path = tmp_path / "labelled.xlsx"
    assert exporter.export_to_excel(str(export_path))

    raw = openpyxl.load_workbook(export_path, data_only=True)["Raw Values"]
    rejected = _cells_for(raw, "S1", "Target")
    assert len(rejected) == 2
    assert {cell.fill.fgColor.rgb for cell in rejected} == {"FFE0C9A6"}
    passing = _cells_for(raw, "S1", "Std")
    assert all(cell.fill.patternType != "solid" for cell in passing)
