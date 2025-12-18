from unittest.mock import MagicMock

import pytest

from manic.sheet_generators.abundances import write


def test_abundance_units_and_calculation_logic():
    # 1. Setup Mock Workbook and Exporter
    workbook = MagicMock()
    worksheet = MagicMock()
    workbook.add_worksheet.return_value = worksheet

    exporter = MagicMock()
    exporter.internal_standard_compound = "ISTD"

    # 2. Setup Mock Compounds
    # Compound A: Has a standard mix amount (should be nmol)
    # Compound B: amount_in_std_mix is 0 (should be Relative)
    compounds = [
        {
            "compound_name": "ISTD",
            "amount_in_std_mix": 1.0,
            "int_std_amount": 10.0,
            "mm_files": "",
            "mass0": 100,
            "retention_time": 5.0,
        },
        {
            "compound_name": "Cmp_Absolute",
            "amount_in_std_mix": 5.0,
            "mass0": 110,
            "retention_time": 5.5,
        },
        {
            "compound_name": "Cmp_Relative",
            "amount_in_std_mix": 0.0,
            "mass0": 120,
            "retention_time": 6.0,
        },
    ]

    # 3. Setup Mock Data Provider
    provider = MagicMock()
    provider.get_all_compounds.return_value = compounds
    provider.get_all_samples.return_value = ["Sample1"]

    # Signals: ISTD=1000, Abs=500, Rel=500
    # MRRF for Absolute compound = 2.0
    provider.get_sample_corrected_data.return_value = {
        "ISTD": [1000.0],
        "Cmp_Absolute": [500.0],
        "Cmp_Relative": [500.0],
    }
    provider.get_mrrf_values.return_value = {"Cmp_Absolute": 2.0, "Cmp_Relative": 1.0}

    # 4. Run the write function
    write(workbook, exporter, None, 0, 100, provider=provider)

    # 5. Assertions for Row 4 (Units)
    # col 2 = ISTD, col 3 = Cmp_Absolute, col 4 = Cmp_Relative
    unit_calls = [call for call in worksheet.write.call_args_list if call.args[0] == 4]
    assert unit_calls[2].args[2] == "nmol"  # ISTD
    assert unit_calls[3].args[2] == "nmol"  # Cmp_Absolute
    assert unit_calls[4].args[2] == "Relative"  # Cmp_Relative

    # 6. Assertions for Values (Row 5)
    value_calls = [call for call in worksheet.write.call_args_list if call.args[0] == 5]

    # Calculation Check:
    # IntStdAmount = 10.0, IntStdSignal = 1000.0

    # Absolute (Cmp_Absolute): (500 * (10/1000) * (1/2.0)) = 2.5
    assert value_calls[3].args[2] == pytest.approx(2.5)

    # Relative (Cmp_Relative): (500 / 1000) * 10.0 = 5.0
    # (Note: If it had used the MRRF fallback of 1.0, it would still be 5.0,
    # but the test ensures the code path for 'Relative' is hit.)
    assert value_calls[4].args[2] == pytest.approx(5.0)
