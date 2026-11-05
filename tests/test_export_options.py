import pytest
from PySide6.QtWidgets import QDialog

import manic.ui.main_window as main_window_module
from manic.models.analysis import AnalysisMode
from manic.ui.export_options_dialog import ExportOptionsDialog

from conftest import _make_window


def test_export_asks_for_options_before_the_location(qapp, monkeypatch):
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    calls = []

    def options_exec(dialog):
        calls.append("options")
        dialog.legacy_radio.setChecked(True)
        return QDialog.Accepted

    def save_name(*_args, **_kwargs):
        calls.append("location")
        return "/tmp/out.xlsx", ""

    monkeypatch.setattr(ExportOptionsDialog, "exec", options_exec)
    monkeypatch.setattr(main_window_module.QFileDialog, "getSaveFileName", save_name)
    monkeypatch.setattr(window, "_confirm", lambda *a: False)
    try:
        assert window.use_legacy_integration is False
        window.export_data()
        assert calls == ["options", "location"]
        assert window.use_legacy_integration is True

        calls.clear()
        monkeypatch.setattr(ExportOptionsDialog, "exec", lambda d: calls.append("options") or 0)
        window.export_data()
        assert calls == ["options"]
    finally:
        window.close()


@pytest.mark.parametrize("labelled", [True, False], ids=["labelled", "unlabelled"])
def test_only_labelled_export_offers_the_carbon_sheet(qapp, labelled):
    dialog = ExportOptionsDialog(False, offer_carbon_enrichment=labelled)
    assert dialog.time_radio.isChecked()
    assert (dialog.carbon_enrichment_check is not None) is labelled
    if labelled:
        assert dialog.carbon_enrichment_check.text() == "Include % Carbons Labelled sheet"
        dialog.carbon_enrichment_check.setChecked(True)
    assert dialog.include_carbon_enrichment() is labelled
    dialog.close()
