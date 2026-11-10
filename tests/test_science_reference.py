"""The comparison behind bench/reference.py: what counts as a changed result."""

import importlib.util
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1] / "bench"


def _reference():
    sys.path.insert(0, str(BENCH))
    try:
        spec = importlib.util.spec_from_file_location("bench_reference", BENCH / "reference.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(BENCH))


def test_compare_counts_moved_numbers_and_other_changes(tmp_path):
    reference = _reference()
    old = {"Areas": [["Sample", "A", "B"], ["S1", "100", "5"], ["S2", "nan", ""]]}
    reference.write(old, tmp_path / "old.tsv")
    assert reference.read(tmp_path / "old.tsv") == {
        "Areas": [["Sample", "A", "B"], ["S1", "100", "5"], ["S2", "nan"]]
    }

    same = reference.compare(old, reference.read(tmp_path / "old.tsv"))["Areas"]
    assert (same["numbers"], same["moved"], same["other"]) == (3, [], 0)

    # One part in ten million is noise; 10% is a change; a new name and a new cell are too.
    new = {"Areas": [["Sample", "A", "B"], ["S1", "100.00001", "5.5"], ["S2x", "nan", "7"]]}
    changed = reference.compare(old, new)["Areas"]
    assert changed["numbers"] == 4
    assert [round(change, 4) for change in changed["moved"]] == [0.0909]
    assert changed["other"] == 2

    assert reference.compare(old, {})["Areas"]["other"] == 8
