from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

from manic.processors.natural_abundance_correction import NaturalAbundanceCorrector

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
generate_bench_data = importlib.import_module("generate_bench_data")
synthetic_gcms = importlib.import_module("synthetic_gcms")

labelled_channel_fractions = generate_bench_data.labelled_channel_fractions
_emg_trace = synthetic_gcms._emg_trace


def test_emg_trace_is_independent_of_supplied_time_window():
    full_time = np.linspace(4.5, 5.5, 2001)
    cropped_time = full_time[full_time <= 4.8]

    full_trace = _emg_trace(full_time, 5.0, 1000.0, 0.03, 0.05)
    cropped_trace = _emg_trace(cropped_time, 5.0, 1000.0, 0.03, 0.05)

    assert np.allclose(cropped_trace, full_trace[: cropped_time.size])
    assert np.isclose(full_trace.max(), 1000.0, rtol=1e-4)


def test_zero_enrichment_retains_natural_carbon_abundance():
    fractions = labelled_channel_fractions("C1", 1, 0.0)

    assert np.allclose(fractions, (0.9893, 0.0107), rtol=1e-6)


def test_enrichment_round_trips_through_correction_purity():
    measured = np.asarray(labelled_channel_fractions("C1", 1, 0.98))
    corrected = NaturalAbundanceCorrector().correct_time_series(
        measured[:, None],
        "C1",
        "C",
        1,
        0,
        0,
        0,
    )[:, 0]
    corrected = corrected / corrected.sum()

    assert np.allclose(corrected, (0.02, 0.98), atol=5e-4)


def test_generation_failure_preserves_existing_corpus(tmp_path, monkeypatch):
    destination = tmp_path / "labelled"
    destination.mkdir()
    sentinel = destination / "manifest.json"
    sentinel.write_text("old corpus", encoding="utf-8")

    def fail_generation(*_args, out_dir, **_kwargs):
        out_dir.mkdir(parents=True)
        (out_dir / "partial.cdf").touch()
        raise RuntimeError("generation failed")

    monkeypatch.setattr(
        generate_bench_data,
        "_generate_dataset_contents",
        fail_generation,
    )

    with pytest.raises(RuntimeError, match="generation failed"):
        generate_bench_data.generate_dataset(
            "labelled",
            n_samples=1,
            seed=1,
            scan_dt_s=0.5,
            out_dir=destination,
        )

    assert sentinel.read_text(encoding="utf-8") == "old corpus"
    assert not list(tmp_path.glob(".labelled-generation-*"))


def test_generation_interrupt_restores_previous_corpus(tmp_path, monkeypatch):
    destination = tmp_path / "labelled"
    destination.mkdir()
    sentinel = destination / "manifest.json"
    sentinel.write_text("old corpus", encoding="utf-8")

    def complete_generation(*_args, out_dir, **_kwargs):
        out_dir.mkdir(parents=True)
        (out_dir / "manifest.json").write_text("new corpus", encoding="utf-8")
        return 1, 1, 0.0, 0.0

    real_replace = generate_bench_data.os.replace

    def interrupt_before_commit(source, target):
        if Path(source).name == "new":
            raise KeyboardInterrupt
        return real_replace(source, target)

    monkeypatch.setattr(
        generate_bench_data,
        "_generate_dataset_contents",
        complete_generation,
    )
    monkeypatch.setattr(generate_bench_data.os, "replace", interrupt_before_commit)

    with pytest.raises(KeyboardInterrupt):
        generate_bench_data.generate_dataset(
            "labelled",
            n_samples=1,
            seed=1,
            scan_dt_s=0.5,
            out_dir=destination,
        )

    assert sentinel.read_text(encoding="utf-8") == "old corpus"
    assert not list(tmp_path.glob(".labelled-generation-*"))
