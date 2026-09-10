from manic.models.mm_file_check import MmFileStatus, build_mm_file_report


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
