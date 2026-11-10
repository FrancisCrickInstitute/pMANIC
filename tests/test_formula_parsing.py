"""Formulas that cannot be read completely are rejected, not silently misread.

The formula parser used to skip anything it did not recognise — brackets, the
number after them, stray digits — and never check that it had used the whole
string, so ``C(CH3)4`` (C5H12) imported cleanly but was read as C2H3 and the
natural abundance correction used the wrong atom counts (#192).
"""

import pytest

from manic.io.compounds_import import CompoundRow
from manic.processors.natural_abundance_correction import (
    NaturalAbundanceCorrectionError,
    NaturalAbundanceCorrector,
)


class TestParseFormulaStrict:
    def test_readable_formulas_unchanged(self):
        assert NaturalAbundanceCorrector().parse_formula("C6H12O6") == {"C": 6, "H": 12, "O": 6}

    def test_two_letter_elements(self):
        assert NaturalAbundanceCorrector().parse_formula("C2H3Cl") == {"C": 2, "H": 3, "Cl": 1}

    def test_repeated_elements_merge(self):
        assert NaturalAbundanceCorrector().parse_formula("CH3CH3") == {"C": 2, "H": 6}

    def test_space_separated_format(self):
        assert NaturalAbundanceCorrector().parse_formula("C6 O3 N1 H12 Si1 S0 P0") == {
            "C": 6, "O": 3, "N": 1, "H": 12, "Si": 1, "S": 0, "P": 0,
        }

    def test_empty_formula(self):
        assert NaturalAbundanceCorrector().parse_formula("") == {}

    def test_bracketed_formula_rejected(self):
        with pytest.raises(NaturalAbundanceCorrectionError):
            NaturalAbundanceCorrector().parse_formula("C(CH3)4")

    @pytest.mark.parametrize("bad", ["1C", "C-2", "C6H12O6x", "(C)2", "C6;H12"])
    def test_unreadable_formulas_rejected(self, bad):
        with pytest.raises(NaturalAbundanceCorrectionError):
            NaturalAbundanceCorrector().parse_formula(bad)


def _row(formula, name="Neopentane"):
    return CompoundRow(
        compound_name=name,
        retention_time=1.0,
        mass0=100.0,
        loffset=0.0,
        roffset=0.0,
        label_atoms=0,
        formula=formula,
    )


class TestCompoundRowFormulaValidation:
    def test_bracketed_formula_rejected_with_message(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as excinfo:
            _row("C(CH3)4")
        assert "cannot be read completely" in str(excinfo.value)

    @pytest.mark.parametrize("bad", ["1C", "C-2", "C6H12O6x", "(C)2"])
    def test_unreadable_standard_formulas_rejected(self, bad):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            _row(bad)

    def test_unreadable_part_in_space_separated_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            _row("C6 O3 N1 X-")

    def test_standard_format_still_imports(self):
        assert _row("C6H12O6").formula == "C6H12O6"

    def test_space_separated_format_still_normalizes(self):
        assert _row("C6 O3 N1 H12 Si1 S0 P0").formula == "C6H12NO3Si"
