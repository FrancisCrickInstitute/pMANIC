import pytest

from manic.io.data_exporter import validate_internal_standard_metadata


class _MockProvider:
    def __init__(self, compounds):
        self._compounds = compounds

    def get_all_compounds(self):
        return self._compounds


def test_validate_internal_standard_metadata_ok_when_none_selected():
    ok, problems = validate_internal_standard_metadata(_MockProvider([]), None)
    assert ok
    assert problems == []


def test_validate_internal_standard_metadata_fails_when_missing_fields():
    provider = _MockProvider(
        [
            {
                "compound_name": "ISTD",
                "int_std_amount": None,
                "amount_in_std_mix": 0,
            }
        ]
    )

    ok, problems = validate_internal_standard_metadata(provider, "ISTD")
    assert not ok
    assert "Missing or zero 'int_std_amount'" in problems
    assert "Missing or zero 'amount_in_std_mix'" in problems


def test_validate_internal_standard_metadata_fails_when_not_found():
    provider = _MockProvider([{ "compound_name": "Other", "int_std_amount": 1, "amount_in_std_mix": 1 }])
    ok, problems = validate_internal_standard_metadata(provider, "ISTD")
    assert not ok
    assert any("not found" in p.lower() for p in problems)
