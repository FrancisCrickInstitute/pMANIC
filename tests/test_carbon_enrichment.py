import pytest
from types import SimpleNamespace
from io import BytesIO
import xlsxwriter
from openpyxl import load_workbook

# Import the new generator
from manic.sheet_generators import carbon_enrichment

class TestCarbonEnrichment:
    """
    Tests for the % Carbons Labelled (Average Enrichment) calculation.
    Formula: Sum(i * Area_i) / (N * Total_Area)
    """

    @pytest.fixture
    def mock_provider(self):
        """Create a provider with controlled isotopologue patterns."""
        class MockProvider:
            def get_all_compounds(self):
                return [
                    {
                        'compound_name': 'Glucose', # 6 Carbons
                        'label_atoms': 6,
                        'mass0': 100.0,
                        'retention_time': 5.0
                    },
                    {
                        'compound_name': 'Alanine', # 3 Carbons
                        'label_atoms': 3,
                        'mass0': 50.0,
                        'retention_time': 2.5
                    },
                    {
                        'compound_name': 'Unlabelable', # 0 Label atoms
                        'label_atoms': 0,
                        'mass0': 200.0,
                        'retention_time': 10.0
                    }
                ]

            def get_all_samples(self):
                return ['Sample_M0', 'Sample_M1', 'Sample_Full', 'Sample_Mixed', 'Sample_Empty']

            def get_sample_corrected_data(self, sample_name):
                # Data format: List of intensities [M+0, M+1, M+2, ...]
                
                if sample_name == 'Sample_M0':
                    # 100% Unlabelled (Natural abundance corrected M+0 only)
                    # Enrichment should be 0%
                    return {
                        'Glucose': [1000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                        'Alanine': [500.0, 0.0, 0.0, 0.0]
                    }
                
                elif sample_name == 'Sample_M1':
                    # 100% of molecules are M+1 (contain exactly one 13C)
                    # Glucose (6C): 1/6 labelled = 16.67%
                    # Alanine (3C): 1/3 labelled = 33.33%
                    return {
                        'Glucose': [0.0, 1000.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                        'Alanine': [0.0, 500.0, 0.0, 0.0]
                    }

                elif sample_name == 'Sample_Full':
                    # 100% Fully Labelled (M+N)
                    # Enrichment should be 100% for both
                    return {
                        'Glucose': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1000.0], # M+6
                        'Alanine': [0.0, 0.0, 0.0, 1000.0] # M+3
                    }

                elif sample_name == 'Sample_Mixed':
                    # 50% M+0, 50% M+Max
                    # Glucose: 50% unlabelled, 50% fully labelled
                    # Enrichment should be 50%
                    return {
                        'Glucose': [500.0, 0.0, 0.0, 0.0, 0.0, 0.0, 500.0],
                        'Alanine': [250.0, 0.0, 0.0, 250.0]
                    }
                
                elif sample_name == 'Sample_Empty':
                    return {}

                return {}

        return MockProvider()

    def test_enrichment_calculations(self, mock_provider):
        """Verify the arithmetic for various labeling scenarios."""
        
        # 1. Setup
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        exporter = SimpleNamespace() # Dummy exporter

        # 2. Execute
        carbon_enrichment.write(
            workbook, 
            exporter, 
            progress_callback=None, 
            start_progress=0, 
            end_progress=100, 
            provider=mock_provider
        )
        workbook.close()

        # 3. Read & Verify
        output.seek(0)
        wb = load_workbook(output)
        ws = wb['% Carbons Labelled']

        # Helper to map columns: Sample is Col B (1), Glucose Col C (2), Alanine Col D (3), Unlabelable Col E (4)
        # Row 5 is headers, Row 6 is first sample in code (0-indexed row 4 + 1 in xlsxwriter = row 5 in Excel? No, xlsxwriter 0 is row 1)
        # xlsxwriter row 0 -> Excel Row 1
        # Code writes data starting at row 4 -> Excel Row 5
        # So first sample is at Row 5
        
        # Sample_M0: Expect 0%
        # Coordinate C5 (Glucose)
        assert ws['C5'].value == 0.0 
        # Coordinate D5 (Alanine)
        assert ws['D5'].value == 0.0

        # Sample_M1: Single label
        # Glucose: 1/6 * 100 = 16.666...
        assert ws['C6'].value == pytest.approx(16.666666, rel=1e-4)
        # Alanine: 1/3 * 100 = 33.333...
        assert ws['D6'].value == pytest.approx(33.333333, rel=1e-4)

        # Sample_Full: Fully labelled
        # Expect 100%
        assert ws['C7'].value == 100.0
        assert ws['D7'].value == 100.0

        # Sample_Mixed: 50/50 split
        # Expect 50%
        assert ws['C8'].value == 50.0
        assert ws['D8'].value == 50.0

    def test_edge_cases(self, mock_provider):
        """Verify handling of zeros, missing data, and unlabelable compounds."""
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        exporter = SimpleNamespace()

        carbon_enrichment.write(
            workbook, exporter, None, 0, 100, provider=mock_provider
        )
        workbook.close()
        output.seek(0)
        wb = load_workbook(output)
        ws = wb['% Carbons Labelled']

        # Check 'Unlabelable' compound (Col E, label_atoms=0)
        # Should be 0.0, avoiding DivisionByZero error
        for row in range(5, 10):
            cell_val = ws.cell(row=row, column=5).value
            assert cell_val == 0.0

        # Check 'Sample_Empty' (No data)
        # Should be 0.0
        assert ws['C9'].value == 0.0
