from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

_SPEC = importlib.util.spec_from_file_location(
    "bench_areas", Path(__file__).resolve().parents[1] / "bench" / "areas.py"
)
areas = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(areas)


def test_relative_difference_checks_each_channel() -> None:
    before = np.array([1_000_000.0, 1.0])
    after = np.array([1_000_000.0, 1_000.0])

    assert areas._relative_difference(before, after) == pytest.approx(999.0)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (np.array([1.0, 2.0]), np.array([1.0])),
        (np.array([]), np.array([])),
        (np.array([1.0, np.nan]), np.array([1.0, 2.0])),
    ],
)
def test_relative_difference_is_nan_for_incomparable_areas(
    before: np.ndarray, after: np.ndarray
) -> None:
    assert np.isnan(areas._relative_difference(before, after))


def test_discover_databases_requires_one_database_per_mode(tmp_path: Path) -> None:
    (tmp_path / "labelled-one.db").touch()
    (tmp_path / "labelled-two.db").touch()
    (tmp_path / "unlabelled-one.db").touch()

    with pytest.raises(SystemExit, match="expected one labelled database"):
        areas._discover_databases(tmp_path)


def test_dataset_provenance_follows_the_manifests(tmp_path: Path) -> None:
    for mode in ("labelled", "unlabelled"):
        (tmp_path / mode).mkdir()
        (tmp_path / mode / "manifest.json").write_text(f'{{"mode": "{mode}"}}')

    first = areas._dataset_provenance(tmp_path)
    (tmp_path / "labelled" / "manifest.json").write_text('{"mode": "changed"}')

    assert areas._dataset_provenance(tmp_path) != first


def test_snapshot_round_trips_and_overwrites_in_place(tmp_path: Path) -> None:
    out = tmp_path / "before.npz"
    key = "labelled|4|glucose|sample"

    areas._save_snapshot(out, {key: np.array([1.0, 2.0])}, "prov")
    provenance, table = areas._load_snapshot(out)
    assert provenance == "prov"
    np.testing.assert_array_equal(table[key], [1.0, 2.0])

    areas._save_snapshot(out, {key: np.array([3.0, 4.0])}, "prov")
    _, table = areas._load_snapshot(out)
    np.testing.assert_array_equal(table[key], [3.0, 4.0])


def test_diff_rejects_different_dataset_provenance(tmp_path: Path) -> None:
    table = {"labelled|4|glucose|sample": np.array([1.0, 2.0])}
    areas._save_snapshot(tmp_path / "before.npz", table, "before")
    areas._save_snapshot(tmp_path / "after.npz", table, "after")

    with pytest.raises(SystemExit, match="different generated datasets"):
        areas.diff(tmp_path / "before.npz", tmp_path / "after.npz", show=10)


def test_diff_reports_minor_channel_changes_and_incomparable_cells(
    tmp_path: Path, capsys
) -> None:
    moved = "labelled|4|glucose|sample"
    broken = "labelled|4|ribose|sample"
    areas._save_snapshot(
        tmp_path / "before.npz",
        {moved: np.array([1_000_000.0, 1.0]), broken: np.array([1.0, np.nan])},
        "prov",
    )
    areas._save_snapshot(
        tmp_path / "after.npz",
        {moved: np.array([1_000_000.0, 1_000.0]), broken: np.array([1.0, 2.0])},
        "prov",
    )

    areas.diff(tmp_path / "before.npz", tmp_path / "after.npz", show=1)

    output = capsys.readouterr().out
    assert f"not comparable  {broken}" in output
    assert "level 4: 1 cells" in output
    assert ">0.01: 1" in output
    assert "9.990e+02" in output
