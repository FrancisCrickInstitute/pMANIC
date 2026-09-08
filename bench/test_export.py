from __future__ import annotations

from openpyxl import load_workbook

from manic.io.data_exporter import DataExporter
from manic.io.sample_reader import list_active_samples


def test_export(case, db, benchmark, repeat, tmp_path):
    def export():
        exporter = DataExporter(case.mode)
        exporter.set_internal_standard(case.internal_standard)
        exporter.set_use_legacy_integration(False)
        path = tmp_path / "out.xlsx"
        exporter.export_to_excel(path, include_carbon_enrichment=case.labelled)
        return path

    path = benchmark.pedantic(export, rounds=repeat)
    wb = load_workbook(path, read_only=True)
    try:
        assert {"Raw Values", "Abundances"} <= set(wb.sheetnames)
        expected_samples = set(list_active_samples())
        exported = {}
        for row in wb["Abundances"].iter_rows(values_only=True):
            if len(row) > 1 and row[1] in expected_samples:
                exported[row[1]] = row[2:]
        assert set(exported) == expected_samples
        for sample, values in exported.items():
            numeric = [
                float(value) for value in values if isinstance(value, (int, float))
            ]
            assert numeric and any(value > 0 for value in numeric), sample
    finally:
        wb.close()
