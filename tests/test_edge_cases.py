"""
Edge case and error handling tests for MANIC.
Tests boundary conditions, error scenarios, and data validation.
"""

import numpy as np
import pytest

from manic.processors.integration import calculate_peak_areas


class TestZeroHandling:
    """Test handling of zero values in calculations."""

    def test_zero_intensity_integration(self):
        """Test integration with all zero intensities."""
        time = np.linspace(0, 10, 100)
        intensity = np.zeros(100)

        areas = calculate_peak_areas(time, intensity, 0, 5.0, 1.0, 1.0)

        assert len(areas) == 1
        assert areas[0] == 0.0


class TestBoundaryConditions:
    """Test boundary conditions and extreme values."""

    def test_rt_window_smaller_than_offset(self):
        """Test when RT window < max(loffset, roffset)."""
        time = np.linspace(0, 10, 1000)
        intensity = np.ones(1000)

        # RT window of 0.2 but offsets of 1.0
        # This means some data outside RT window won't be captured
        rt = 5.0
        rt_window = 0.2  # Only captures 4.8 to 5.2
        loffset = 1.0  # Wants 4.0 to 5.0
        roffset = 1.0  # Wants 5.0 to 6.0

        # Filter by RT window first (as done in EIC extraction)
        rt_mask = (time >= rt - rt_window) & (time <= rt + rt_window)
        filtered_time = time[rt_mask]
        filtered_intensity = intensity[rt_mask]

        # Then try to integrate with larger offsets
        # This will miss data!
        if len(filtered_time) > 0:
            areas = calculate_peak_areas(
                filtered_time, filtered_intensity, 0, rt, loffset, roffset
            )
        else:
            areas = [0.0]

        # Area will be less than expected due to missing data
        assert areas[0] < 2.0  # Less than full 2-minute window

    def test_exact_boundary_points(self):
        """Test points exactly at integration boundaries."""
        time = np.array([3.0, 4.0, 5.0, 6.0, 7.0])
        intensity = np.array([100, 200, 300, 400, 500])

        # Integration: 4.0 < t < 6.0 (strict inequality)
        areas = calculate_peak_areas(time, intensity, 0, 5.0, 1.0, 1.0)

        # Should only include point at t=5.0
        # Points at 4.0 and 6.0 are excluded
        assert len(areas) == 1
        # Only one point means area is 0 (need at least 2 for trapezoid)
        assert areas[0] == 0.0


class TestAbundanceCalculations:
    """Test abundance calculation edge cases and bugs."""

    def test_internal_standard_uses_amount_in_std_mix(self):
        """
        Test for Issue #55: Internal standard should use amount_in_std_mix, not int_std_amount.

        Bug: When the internal standard compound (e.g., scyllo-Ins) has:
          - int_std_amount = 1.0 (normalization factor for other metabolites)
          - amount_in_std_mix = 0.5 (ACTUAL amount in MM files)

        The code incorrectly used int_std_amount (1.0) for the internal standard's
        own abundance, causing it to be doubled. It should use amount_in_std_mix (0.5).
        """
        from io import BytesIO
        from types import SimpleNamespace

        import xlsxwriter

        # Mock exporter with internal standard set
        exporter = SimpleNamespace(
            internal_standard_compound="scyllo-Ins",
            internal_standard_reference_isotope=0,
        )

        # Mock provider that returns corrected data
        class MockProvider:
            def __init__(self):
                self._samples = ["Sample_MM1", "Sample1"]

            def get_all_compounds(self):
                return [
                    {
                        "compound_name": "scyllo-Ins",
                        "mass0": 318.0,
                        "retention_time": 15.5,
                        "amount_in_std_mix": 0.5,  # Actual amount in standard mix
                        "int_std_amount": 1.0,  # Normalization factor (wrong if used for abundance)
                        "mm_files": "*_MM*",
                    },
                    {
                        "compound_name": "Pyruvate",
                        "mass0": 174.0,
                        "retention_time": 7.17,
                        "amount_in_std_mix": 20.0,
                        "int_std_amount": None,
                        "mm_files": "*_MM*",
                    },
                ]

            def get_all_samples(self):
                return list(self._samples)

            def get_sample_corrected_data(self, sample_name):
                base_data = {
                    "scyllo-Ins": [1000.0],  # M+0 signal for internal standard
                    "Pyruvate": [500.0, 100.0, 50.0],  # M+0, M+1, M+2
                }
                return base_data

            def get_mrrf_values(self, compounds, internal_std):
                return {"Pyruvate": 2.0}

            def resolve_mm_samples(self, mm_field):
                if not mm_field:
                    return []
                return [sample for sample in self._samples if "MM" in sample]

        provider = MockProvider()

        # Create a workbook in memory
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        # Import and call the abundances sheet generator
        from manic.sheet_generators import abundances

        abundances.write(
            workbook,
            exporter,
            progress_callback=None,
            start_progress=0,
            end_progress=100,
            provider=provider,
        )

        workbook.close()

        # Read back the workbook to check values
        output.seek(0)
        from openpyxl import load_workbook

        wb = load_workbook(output)
        ws = wb["Abundances"]

        # Headers are in rows 1-5, data starts at row 6
        # Column structure: [empty, Sample, Compound1, Compound2, ...]
        # scyllo-Ins should be in column 3 (index C)
        # Sample rows: row 6 = Sample_MM1, row 7 = Sample1

        scyllo_ins_abundance_mm = ws["C6"].value  # Sample_MM1 (MM file)
        scyllo_ins_abundance_non_mm = ws["C7"].value  # Sample1 (non-MM)

        # MM samples should use amount_in_std_mix, regular samples use int_std_amount
        assert scyllo_ins_abundance_mm == 0.5, (
            "Internal standard abundance for MM samples should use amount_in_std_mix (0.5)"
        )
        assert scyllo_ins_abundance_non_mm == 1.0, (
            "Internal standard abundance for non-MM samples should use int_std_amount (1.0)"
        )

        # Non-internal-standard metabolite should also be scaled differently per sample
        pyruvate_mm = ws["D6"].value
        pyruvate_non_mm = ws["D7"].value

        # Expected values based on formula: total_signal=650, IS signal=1000, MRRF=2
        assert pyruvate_mm == pytest.approx(0.1625)
        assert pyruvate_non_mm == pytest.approx(0.325)


    def test_internal_standard_missing_amounts(self):
        """Exporter should fail fast when required IS amounts are missing."""
        from io import BytesIO
        from types import SimpleNamespace

        import xlsxwriter

        exporter = SimpleNamespace(
            internal_standard_compound="scyllo-Ins",
            internal_standard_reference_isotope=0,
        )

        class MissingAmountProvider:

            def __init__(self, *, missing_field):
                self._missing_field = missing_field

            def get_all_compounds(self):
                base = {
                    "compound_name": "scyllo-Ins",
                    "mass0": 318.0,
                    "retention_time": 15.5,
                    "amount_in_std_mix": 0.5,
                    "int_std_amount": 1.0,
                    "mm_files": "*_MM*",
                }
                base[self._missing_field] = None
                return [base]

            def get_all_samples(self):
                return ["Sample1"]

            def get_sample_corrected_data(self, sample_name):
                return {"scyllo-Ins": [1000.0]}

            def get_mrrf_values(self, compounds, internal_std):
                return {}

            def resolve_mm_samples(self, mm_field):
                return []

        from manic.sheet_generators import abundances

        for missing_field, expected_msg in (
            ("int_std_amount", "'int_std_amount'"),
            ("amount_in_std_mix", "'amount_in_std_mix'"),
        ):
            provider = MissingAmountProvider(missing_field=missing_field)
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {"in_memory": True})
            with pytest.raises(ValueError, match=expected_msg):
                abundances.write(
                    workbook,
                    exporter,
                    progress_callback=None,
                    start_progress=0,
                    end_progress=100,
                    provider=provider,
                )
            workbook.close()
