from __future__ import annotations

import json
import zlib

import numpy as np
import pytest

from manic.io.changelog_writer import generate_changelog
from manic.io.compound_reader import read_compound_with_session
from manic.io.data_provider import DataProvider
from manic.models import database
from manic.models import session_export
from manic.models.analysis import AnalysisMode
from manic.models.sample_fit_type import (
    get_sample_fit_types,
    set_sample_fit_type,
)

def _insert_compound(name: str, *, fit_type: str = "auto") -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms, deconvolution_fit_type) "
            "VALUES (?, 1.0, 0.4, 0.4, 100.0, 0, ?)",
            (name, fit_type),
        )


def _insert_eic(sample: str, compound: str) -> None:
    time = np.asarray([0.0, 1.0, 2.0], dtype=np.float64)
    intensity = np.asarray([0.0, 10.0, 0.0], dtype=np.float64)
    with database.get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO samples (sample_name, file_name) VALUES (?, ?)",
            (sample, f"/fake/{sample}.cdf"),
        )
        conn.execute(
            "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
            "VALUES (?, ?, ?, ?, 0.4)",
            (
                sample,
                compound,
                zlib.compress(time.tobytes()),
                zlib.compress(intensity.tobytes()),
            ),
        )


def test_set_and_get_sample_fit_types_round_trip(empty_db):
    _insert_compound("Target")
    _insert_eic("S1", "Target")
    _insert_eic("S2", "Target")
    set_sample_fit_type("Target", ["S1"], "gaussian")
    assert get_sample_fit_types("Target") == {("Target", "S1"): "gaussian"}
    set_sample_fit_type("Target", ["S1"], None)
    assert get_sample_fit_types("Target") == {}


def test_read_compound_with_session_uses_override_for_that_sample_only(empty_db):
    _insert_compound("Target", fit_type="auto")
    _insert_eic("S1", "Target")
    _insert_eic("S2", "Target")
    set_sample_fit_type("Target", ["S1"], "emg")

    overridden = read_compound_with_session("Target", "S1")
    inherited = read_compound_with_session("Target", "S2")
    base = read_compound_with_session("Target")

    assert overridden.deconvolution_fit_type == "emg"
    assert inherited.deconvolution_fit_type == "auto"
    assert base.deconvolution_fit_type == "auto"


def test_data_provider_bulk_sql_picks_the_override(empty_db, monkeypatch):
    _insert_compound("Target", fit_type="auto")
    _insert_eic("S1", "Target")
    _insert_eic("S2", "Target")
    set_sample_fit_type("Target", ["S1"], "gaussian")

    fits: dict[str, str] = {}

    def capture_run(_provider, _use_legacy, task):
        kind, row, _y_blob = task
        fits[row["sample_name"]] = row["deconvolution_fit_type"]
        return kind, row["sample_name"], row["compound_name"], [1.0], None

    import manic.io.data_provider as provider_module

    monkeypatch.setattr(provider_module, "_run_integration", capture_run)
    DataProvider().load_bulk_sample_data()
    assert fits == {"S1": "gaussian", "S2": "auto"}


def test_data_provider_fallback_sql_picks_the_override(empty_db, monkeypatch):
    _insert_compound("Target", fit_type="bi_gaussian")
    _insert_eic("S1", "Target")
    set_sample_fit_type("Target", ["S1"], "emg")

    fits: list[str] = []

    def capture_areas(*args, **kwargs):
        fits.append(kwargs["chromatographic_peak_deconvolution_fit_type"])
        return [1.0]

    import manic.io.data_provider as provider_module

    monkeypatch.setattr(provider_module, "calculate_peak_areas", capture_areas)
    provider = DataProvider()
    provider._bulk_sample_data_cache = {}
    provider._bulk_raw_sample_data_cache = {}
    # Skip bulk so get_sample_raw_data uses its own SELECT.
    monkeypatch.setattr(provider, "load_bulk_sample_data", lambda: {})
    areas = provider.get_sample_raw_data("S1")
    assert areas["Target"] == [1.0]
    assert fits == ["emg"]


def test_session_export_import_round_trips_sample_fit_types(empty_db, tmp_path):
    _insert_compound("Target")
    _insert_compound("Other")
    _insert_eic("S1", "Target")
    _insert_eic("S2", "Target")
    set_sample_fit_type("Target", ["S1"], "gaussian")

    assert session_export.export_session_method(str(tmp_path / "method"))
    method_path = tmp_path / "manic_session_export" / "method.json"
    exported = json.loads(method_path.read_text(encoding="utf-8"))
    assert exported["sample_fit_types"] == [
        {
            "compound_name": "Target",
            "sample_name": "S1",
            "fit_type": "gaussian",
        }
    ]
    changelog = next(
        (tmp_path / "manic_session_export").glob("changelog_*.md")
    ).read_text(encoding="utf-8")
    assert "## Per-sample Curve Fits" in changelog
    assert "| S1 | Gaussian |" in changelog

    set_sample_fit_type("Target", ["S2"], "emg")
    set_sample_fit_type("Other", ["S1"], "auto")
    ok, _ = session_export.import_session_overrides(str(method_path))
    assert ok
    assert get_sample_fit_types() == {("Target", "S1"): "gaussian"}


def test_data_export_changelog_includes_sample_fit_types(empty_db, tmp_path):
    _insert_compound("Target")
    _insert_eic("S1", "Target")
    set_sample_fit_type("Target", ["S1"], "gaussian")
    generate_changelog(
        str(tmp_path / "export.xlsx"),
        internal_standard=None,
        use_legacy_integration=False,
        analysis_mode=AnalysisMode.LABELLED,
    )
    changelog = next(tmp_path.glob("changelog_*.md")).read_text(encoding="utf-8")
    assert "## Per-sample Curve Fits" in changelog
    assert "| S1 | Gaussian |" in changelog


def test_set_sample_fit_type_none_removes_every_named_sample(empty_db):
    _insert_compound("Target")
    _insert_eic("S1", "Target")
    _insert_eic("S2", "Target")
    set_sample_fit_type("Target", ["S1", "S2"], "auto")
    set_sample_fit_type("Target", ["S1", "S2"], None)
    assert get_sample_fit_types("Target") == {}
