from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench"
sys.path.insert(0, str(BENCH))
areas = importlib.import_module("areas")


def _provenance(digest: str = "abc") -> dict[str, str]:
    return {
        "labelled": f"labelled-abc.db:{digest}",
        "unlabelled": f"unlabelled-abc.db:{digest}",
    }


def test_relative_difference_checks_each_channel() -> None:
    before = np.array([1_000_000.0, 1.0])
    after = np.array([1_000_000.0, 1_000.0])

    assert areas._relative_difference(before, after) == pytest.approx(999.0)


@pytest.mark.parametrize(
    ("before", "after", "message"),
    [
        (np.array([1.0, 2.0]), np.array([1.0]), "area shapes differ"),
        (np.array([1.0, np.nan]), np.array([1.0, 2.0]), "finite"),
        (np.array([]), np.array([]), "non-empty"),
    ],
)
def test_relative_difference_rejects_invalid_areas(
    before: np.ndarray, after: np.ndarray, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        areas._relative_difference(before, after)


def test_discover_databases_requires_one_database_per_mode(tmp_path: Path) -> None:
    (tmp_path / "labelled-one.db").touch()
    (tmp_path / "labelled-two.db").touch()
    (tmp_path / "unlabelled-one.db").touch()

    with pytest.raises(SystemExit, match="labelled has 2 databases"):
        areas._discover_databases(tmp_path)


def test_save_snapshot_is_atomic_and_refuses_to_overwrite(tmp_path: Path) -> None:
    requested = tmp_path / "before"
    table = {"labelled|4|glucose|sample": np.array([1.0, 2.0])}

    saved = areas._save_snapshot(requested, table, _provenance())

    assert saved == tmp_path / "before.npz"
    assert saved.is_file()
    metadata, loaded = areas._load_snapshot(saved)
    assert metadata == _provenance()
    np.testing.assert_array_equal(loaded[next(iter(table))], next(iter(table.values())))

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        areas._save_snapshot(requested, table, _provenance())


def test_save_snapshot_removes_partial_file_on_failure(
    tmp_path: Path, monkeypatch
) -> None:
    def fail_to_save(*args, **kwargs) -> None:
        raise RuntimeError("save failed")

    monkeypatch.setattr(areas.np, "savez", fail_to_save)

    with pytest.raises(RuntimeError, match="save failed"):
        areas._save_snapshot(
            tmp_path / "before.npz",
            {"labelled|4|glucose|sample": np.array([1.0])},
            _provenance(),
        )

    assert list(tmp_path.iterdir()) == []


def test_diff_rejects_different_database_provenance(tmp_path: Path) -> None:
    table = {"labelled|4|glucose|sample": np.array([1.0, 2.0])}
    before = areas._save_snapshot(tmp_path / "before.npz", table, _provenance("before"))
    after = areas._save_snapshot(tmp_path / "after.npz", table, _provenance("after"))

    with pytest.raises(SystemExit, match="different bench databases"):
        areas.diff(before, after, show=10)


def test_diff_reports_minor_channel_changes(tmp_path: Path, capsys) -> None:
    key = "labelled|4|glucose|sample"
    before = areas._save_snapshot(
        tmp_path / "before.npz",
        {key: np.array([1_000_000.0, 1.0])},
        _provenance(),
    )
    after = areas._save_snapshot(
        tmp_path / "after.npz",
        {key: np.array([1_000_000.0, 1_000.0])},
        _provenance(),
    )

    areas.diff(before, after, show=1)

    output = capsys.readouterr().out
    assert ">0.01: 1" in output
    assert "9.990e+02" in output
