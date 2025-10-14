"""
Tests for UI number and value formatting utilities.

Tests formatting logic used to display values in the integration window
and other UI components.
"""

import pytest
from PySide6.QtWidgets import QApplication
import sys

from manic.ui.integration_window_widget import IntegrationWindow


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for UI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def integration_window(qapp):
    """Create IntegrationWindow instance for testing."""
    window = IntegrationWindow()
    yield window
    window.deleteLater()


class TestSignificantFigures:
    """Test formatting numbers to 4 significant figures."""

    def test_normal_retention_times(self, integration_window):
        """Test typical retention time values."""
        assert integration_window._format_number(9.77123456) == "9.771"
        assert integration_window._format_number(15.4567) == "15.46"
        assert integration_window._format_number(7.171234) == "7.171"
        assert integration_window._format_number(12.3456) == "12.35"

    def test_small_offsets(self, integration_window):
        """Test small offset values (typically < 1)."""
        assert integration_window._format_number(0.123456) == "0.1235"
        assert integration_window._format_number(0.1) == "0.1"
        assert integration_window._format_number(0.456789) == "0.4568"
        assert integration_window._format_number(0.999) == "0.999"

    def test_zero_handling(self, integration_window):
        """Test zero and near-zero values."""
        assert integration_window._format_number(0) == "0"
        assert integration_window._format_number(0.0) == "0"
        assert integration_window._format_number(-0.0) == "0"

    def test_very_small_values(self, integration_window):
        """Test very small non-zero values."""
        assert integration_window._format_number(0.001) == "0.001"
        assert integration_window._format_number(0.001234) == "0.001234"
        assert integration_window._format_number(0.0004567) == "0.0004567"

    def test_boundary_values(self, integration_window):
        """Test values near rounding boundaries."""
        assert integration_window._format_number(0.99995) == "1"
        assert integration_window._format_number(1.0001) == "1"
        assert integration_window._format_number(9.9995) == "9.999"  # Keeps 4 sig figs
        assert integration_window._format_number(10.001) == "10"

    def test_large_values(self, integration_window):
        """Test larger values (e.g., mass values)."""
        assert integration_window._format_number(123.456) == "123.5"
        assert integration_window._format_number(318.123) == "318.1"
        assert integration_window._format_number(999.999) == "1000"

    def test_negative_values(self, integration_window):
        """Test negative values (shouldn't occur but test anyway)."""
        assert integration_window._format_number(-9.77123) == "-9.771"
        assert integration_window._format_number(-0.1235) == "-0.1235"
        assert integration_window._format_number(-15.4567) == "-15.46"

    def test_edge_case_precision(self, integration_window):
        """Test precise rounding behavior."""
        # Test that 4 sig figs is applied correctly
        assert integration_window._format_number(1.2345) == "1.234"
        assert integration_window._format_number(1.2346) == "1.235"  # Round up
        assert integration_window._format_number(1.2344) == "1.234"


class TestRangeFormatting:
    """Test formatting value ranges for display."""

    def test_single_value_range(self, integration_window):
        """Test range when all values are identical."""
        values = [9.77, 9.77, 9.77]
        result = integration_window._format_range(values)
        assert result == "9.77"

    def test_single_value_with_float_error(self, integration_window):
        """Test range with values that are very close (floating point precision)."""
        values = [9.77, 9.77000001, 9.76999999]
        result = integration_window._format_range(values)
        # Should treat as single value (within 1e-6 tolerance)
        assert result == "9.77"

    def test_actual_range(self, integration_window):
        """Test range with different values."""
        values = [9.5, 10.2]
        result = integration_window._format_range(values)
        assert result == "9.5 - 10.2"

    def test_range_multiple_values(self, integration_window):
        """Test range with many values (should show min-max)."""
        values = [7.1, 7.5, 7.3, 7.8, 7.2]
        result = integration_window._format_range(values)
        assert result == "7.1 - 7.8"

    def test_range_with_none_values(self, integration_window):
        """Test range handling None values."""
        values = [9.5, None, 10.2, None]
        result = integration_window._format_range(values)
        # Should filter out None and show range
        assert result == "9.5 - 10.2"

    def test_range_all_none(self, integration_window):
        """Test range with all None values."""
        values = [None, None, None]
        result = integration_window._format_range(values)
        assert result == ""

    def test_empty_range(self, integration_window):
        """Test range with empty list."""
        values = []
        result = integration_window._format_range(values)
        assert result == ""

    def test_range_consistent_sig_figs(self, integration_window):
        """Test that both endpoints use 4 sig figs."""
        values = [9.77123, 10.4567]
        result = integration_window._format_range(values)
        # Both values should be formatted to 4 sig figs
        assert result == "9.771 - 10.46"

    def test_range_with_small_values(self, integration_window):
        """Test range with small offset-like values."""
        values = [0.123456, 0.456789]
        result = integration_window._format_range(values)
        assert result == "0.1235 - 0.4568"

    def test_range_invalid_values(self, integration_window):
        """Test range with non-numeric values."""
        values = [9.5, "invalid", 10.2]
        result = integration_window._format_range(values)
        # Should filter out invalid and show range of valid values
        assert result == "9.5 - 10.2"


class TestTRWindowFormatting:
    """Test tR window field formatting."""

    def test_tr_window_default_value(self, integration_window):
        """Test default tR window value formatting."""
        # Default is typically 0.2
        assert integration_window._format_number(0.2) == "0.2"

    def test_tr_window_custom_values(self, integration_window):
        """Test various tR window values."""
        assert integration_window._format_number(0.15) == "0.15"
        assert integration_window._format_number(0.25) == "0.25"
        assert integration_window._format_number(0.5) == "0.5"
        assert integration_window._format_number(1.0) == "1"


class TestFormattingConsistency:
    """Test formatting consistency across different contexts."""

    def test_same_value_formatted_identically(self, integration_window):
        """Test that same value formats the same way every time."""
        value = 9.77123
        result1 = integration_window._format_number(value)
        result2 = integration_window._format_number(value)
        assert result1 == result2
        assert result1 == "9.771"

    def test_range_endpoints_use_same_formatting(self, integration_window):
        """Test that range endpoints use same formatting as single values."""
        value1 = 9.77123
        value2 = 10.4567

        # Format as single values
        single1 = integration_window._format_number(value1)
        single2 = integration_window._format_number(value2)

        # Format as range
        range_result = integration_window._format_range([value1, value2])

        # Range should contain both formatted single values
        assert single1 in range_result
        assert single2 in range_result
        assert range_result == f"{single1} - {single2}"
