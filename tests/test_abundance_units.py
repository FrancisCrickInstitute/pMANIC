from unittest.mock import MagicMock

import pytest

from manic.sheet_generators.abundances import write


class TestAbundanceExportLogic:
    @pytest.fixture
    def setup_base_mocks(self):
        workbook = MagicMock()
        worksheet = MagicMock()
        workbook.add_worksheet.return_value = worksheet

        provider = MagicMock()
        provider.get_all_samples.return_value = ["Sample1"]
        provider.get_sample_corrected_data.return_value = {
            "ISTD": [1000.0],
            "Cmp_Absolute": [500.0],
            "Cmp_Relative": [500.0],
        }
        return workbook, worksheet, provider

    def test_abundance_with_internal_standard(self, setup_base_mocks):
        """Tests 'nmol' and 'Relative' headers and math."""
        workbook, worksheet, provider = setup_base_mocks
        exporter = MagicMock()
        exporter.internal_standard_compound = "ISTD"

        compounds = [
            {
                "compound_name": "ISTD",
                "amount_in_std_mix": 1.0,
                "int_std_amount": 10.0,
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
        provider.get_all_compounds.return_value = compounds
        provider.get_mrrf_values.return_value = {"Cmp_Absolute": 2.0}

        write(workbook, exporter, None, 0, 100, provider=provider)

        # Skip col 0 ('Units') and col 1 (None)
        unit_calls = [
            c.args[2]
            for c in worksheet.write.call_args_list
            if c.args[0] == 4 and c.args[1] >= 2
        ]
        assert unit_calls == ["nmol", "nmol", "Relative"]

        # Math check (Row 5)
        val_calls = [
            c.args[2]
            for c in worksheet.write.call_args_list
            if c.args[0] == 5 and c.args[1] >= 2
        ]
        assert val_calls[1] == pytest.approx(2.5)  # Absolute
        assert val_calls[2] == pytest.approx(5.0)  # Relative

    def test_abundance_no_internal_standard(self, setup_base_mocks):
        """Tests 'Peak Area' mode when no standard is selected."""
        workbook, worksheet, provider = setup_base_mocks
        exporter = MagicMock()
        exporter.internal_standard_compound = None  # Trigger no-standard mode

        # Use the names that match the signal data in setup_base_mocks
        compounds = [
            {
                "compound_name": "Cmp_Absolute",
                "amount_in_std_mix": 1.0,
                "mass0": 100,
                "retention_time": 5.0,
            },
            {
                "compound_name": "Cmp_Relative",
                "amount_in_std_mix": 0.0,
                "mass0": 110,
                "retention_time": 5.5,
            },
        ]
        provider.get_all_compounds.return_value = compounds

        write(workbook, exporter, None, 0, 100, provider=provider)

        # Assert Headers (Row 4): Should all be "Peak Area"
        unit_calls = [
            c.args[2]
            for c in worksheet.write.call_args_list
            if c.args[0] == 4 and c.args[1] >= 2
        ]
        assert all(u == "Peak Area" for u in unit_calls)

        # Assert Values (Row 5): Signals are 500.0 in the fixture
        val_calls = [
            c.args[2]
            for c in worksheet.write.call_args_list
            if c.args[0] == 5 and c.args[1] >= 2
        ]
        assert val_calls[0] == 500.0  # Sum of corrected areas for Cmp_Absolute
        assert val_calls[1] == 500.0  # Sum of corrected areas for Cmp_Relative
