import pytest

from manic.io.data_provider import DataProvider
from manic.io.in_memory_provider import InMemoryDataProvider
from manic.models import database
from manic.models.mm_file_check import MmFileStatus, build_mm_file_report

MM_SAMPLES = ["MM1", "MM10", "xMM1", "MM_1", "MMa1", "mm2", "MM%4", "MMx4", "Bio"]

MM_PATTERN_CASES = [
    ("MM*1", ["MM1", "MM_1", "MMa1"]),
    ("mm*", ["MM%4", "MM1", "MM10", "MM_1", "MMa1", "MMx4", "mm2"]),
    ("*MM1", ["MM1", "xMM1"]),
    ("MM%", ["MM%4"]),
    ("MM1;mm2", ["MM1", "MM10", "mm2", "xMM1"]),
    ("bio\tMM_1", ["Bio", "MM_1"]),
    ("MM10\nxMM1, MMx4", ["MM10", "MMx4", "xMM1"]),
]


def _database_provider():
    with database.get_connection() as conn:
        conn.executemany(
            "INSERT INTO samples(sample_name, file_name) VALUES(?, ?)",
            [(name, f"{name}.cdf") for name in MM_SAMPLES],
        )
    return DataProvider()


def _in_memory_provider():
    return InMemoryDataProvider([], MM_SAMPLES, {name: {} for name in MM_SAMPLES})


@pytest.mark.parametrize("make_provider", [_database_provider, _in_memory_provider])
@pytest.mark.parametrize("pattern, expected", MM_PATTERN_CASES)
def test_providers_resolve_mm_patterns_alike(make_provider, pattern, expected):
    assert make_provider().resolve_mm_samples(pattern) == expected


def test_build_mm_file_report_states_and_order():
    def resolve(pattern: str) -> list[str]:
        mapping = {
            "*MM*": ["B_MM", "A_MM"],
            "missing": [],
        }
        return mapping.get(pattern, [])

    rows = [
        ("Matched", "*MM*"),
        ("Unset", None),
        ("Blank", "   "),
        ("NoMatch", "missing"),
    ]
    report = build_mm_file_report(rows, resolve)

    assert [row.compound_name for row in report] == [
        "Matched",
        "Unset",
        "Blank",
        "NoMatch",
    ]
    assert report[0] == MmFileStatus(
        compound_name="Matched",
        pattern="*MM*",
        matched=("A_MM", "B_MM"),
    )
    assert report[0].state == "matched"
    assert report[1] == MmFileStatus(
        compound_name="Unset",
        pattern=None,
        matched=(),
    )
    assert report[1].state == "unset"
    assert report[2] == MmFileStatus(
        compound_name="Blank",
        pattern=None,
        matched=(),
    )
    assert report[2].state == "unset"
    assert report[3] == MmFileStatus(
        compound_name="NoMatch",
        pattern="missing",
        matched=(),
    )
    assert report[3].state == "no_match"


def test_build_mm_file_report_skips_resolve_when_pattern_unset():
    calls: list[str] = []

    def resolve(pattern: str) -> list[str]:
        calls.append(pattern)
        return ["X"]

    report = build_mm_file_report([("A", None), ("B", "")], resolve)
    assert calls == []
    assert [row.state for row in report] == ["unset", "unset"]
