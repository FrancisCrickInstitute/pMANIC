"""
Tests for RT window centering and automatic data reload logic.

Tests the boundary checking and window calculation logic used to determine
when EIC data needs to be reloaded with a new RT window center.

These tests follow TDD (Test-Driven Development) principles:
1. Tests are written first (before implementation)
2. Tests define expected behavior clearly
3. Implementation will be written to make these tests pass
"""

import pytest
from manic.ui.integration_window_widget import (
    calculate_integration_boundaries,
    calculate_minimum_rt_window,
    check_boundaries_within_window,
)


class TestIntegrationBoundaryCalculation:
    """Test calculation of integration boundaries from RT and offsets."""

    def test_symmetric_offsets(self):
        """Test with equal left and right offsets."""
        left, right = calculate_integration_boundaries(rt=10.0, loffset=0.5, roffset=0.5)
        assert left == 9.5
        assert right == 10.5

    def test_asymmetric_offsets(self):
        """Test with different left and right offsets."""
        left, right = calculate_integration_boundaries(rt=7.17, loffset=0.1, roffset=0.3)
        assert abs(left - 7.07) < 1e-10
        assert abs(right - 7.47) < 1e-10

    def test_zero_offsets(self):
        """Test with zero offsets (edge case)."""
        left, right = calculate_integration_boundaries(rt=5.0, loffset=0.0, roffset=0.0)
        assert left == 5.0
        assert right == 5.0

    def test_large_offsets(self):
        """Test with large offsets exceeding typical RT window."""
        left, right = calculate_integration_boundaries(rt=15.0, loffset=2.0, roffset=3.0)
        assert left == 13.0
        assert right == 18.0


class TestMinimumRTWindowCalculation:
    """Test calculation of minimum RT window needed for offsets."""

    def test_symmetric_offsets(self):
        """Test with equal offsets."""
        min_window = calculate_minimum_rt_window(loffset=0.2, roffset=0.2, buffer=0.1)
        assert abs(min_window - 0.3) < 1e-10  # max(0.2, 0.2) + 0.1 (floating point tolerance)

    def test_larger_left_offset(self):
        """Test with larger left offset."""
        min_window = calculate_minimum_rt_window(loffset=0.5, roffset=0.2, buffer=0.1)
        assert min_window == 0.6  # max(0.5, 0.2) + 0.1

    def test_larger_right_offset(self):
        """Test with larger right offset."""
        min_window = calculate_minimum_rt_window(loffset=0.1, roffset=0.8, buffer=0.1)
        assert min_window == 0.9  # max(0.1, 0.8) + 0.1

    def test_zero_buffer(self):
        """Test with no safety buffer."""
        min_window = calculate_minimum_rt_window(loffset=0.3, roffset=0.3, buffer=0.0)
        assert min_window == 0.3

    def test_custom_buffer(self):
        """Test with custom buffer size."""
        min_window = calculate_minimum_rt_window(loffset=0.2, roffset=0.2, buffer=0.05)
        assert min_window == 0.25


class TestBoundaryWindowChecking:
    """Test checking if boundaries fit within data window."""

    def test_boundaries_fit_exactly(self):
        """Test boundaries that exactly match window edges."""
        fits = check_boundaries_within_window(
            left_boundary=9.0,
            right_boundary=11.0,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is True

    def test_boundaries_fit_with_margin(self):
        """Test boundaries comfortably within window."""
        fits = check_boundaries_within_window(
            left_boundary=9.5,
            right_boundary=10.5,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is True

    def test_left_boundary_exceeds(self):
        """Test when left boundary falls outside window."""
        fits = check_boundaries_within_window(
            left_boundary=8.5,
            right_boundary=10.5,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is False

    def test_right_boundary_exceeds(self):
        """Test when right boundary falls outside window."""
        fits = check_boundaries_within_window(
            left_boundary=9.5,
            right_boundary=11.5,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is False

    def test_both_boundaries_exceed(self):
        """Test when both boundaries fall outside window."""
        fits = check_boundaries_within_window(
            left_boundary=8.5,
            right_boundary=11.5,
            window_min=9.0,
            window_max=11.0,
        )
        assert fits is False

    def test_floating_point_tolerance(self):
        """Test that small floating point errors are handled."""
        # Boundary is 0.0001 outside window, but within tolerance
        fits = check_boundaries_within_window(
            left_boundary=8.9999,
            right_boundary=10.5,
            window_min=9.0,
            window_max=11.0,
            tolerance=0.001,
        )
        assert fits is True

    def test_outside_tolerance(self):
        """Test that values outside tolerance are detected."""
        # Boundary is 0.002 outside window, exceeds tolerance
        fits = check_boundaries_within_window(
            left_boundary=8.998,
            right_boundary=10.5,
            window_min=9.0,
            window_max=11.0,
            tolerance=0.001,
        )
        assert fits is False


class TestReloadScenarios:
    """Test realistic scenarios that trigger or avoid reloads."""

    def test_small_rt_change_no_reload(self):
        """Test that small RT changes within window don't trigger reload."""
        # Initial: RT=10.0, offsets=0.1, window=[9.8, 10.2]
        # New: RT=10.05 (small shift)
        left, right = calculate_integration_boundaries(10.05, 0.1, 0.1)
        fits = check_boundaries_within_window(left, right, 9.8, 10.2)
        assert fits is True  # No reload needed

    def test_large_rt_change_needs_reload(self):
        """Test that large RT changes outside window trigger reload."""
        # Initial: RT=10.0, offsets=0.1, window=[9.8, 10.2]
        # New: RT=11.0 (moved outside window)
        left, right = calculate_integration_boundaries(11.0, 0.1, 0.1)
        fits = check_boundaries_within_window(left, right, 9.8, 10.2)
        assert fits is False  # Reload needed

    def test_offset_increase_needs_reload(self):
        """Test that increased offsets trigger reload."""
        # Initial: RT=10.0, offsets=0.1, window=[9.8, 10.2]
        # New: offsets=0.3 (now boundaries are [9.7, 10.3])
        left, right = calculate_integration_boundaries(10.0, 0.3, 0.3)
        fits = check_boundaries_within_window(left, right, 9.8, 10.2)
        assert fits is False  # Reload needed

    def test_offset_decrease_no_reload(self):
        """Test that decreased offsets don't trigger reload."""
        # Initial: RT=10.0, offsets=0.2, window=[9.8, 10.2]
        # New: offsets=0.1 (now boundaries are [9.9, 10.1])
        left, right = calculate_integration_boundaries(10.0, 0.1, 0.1)
        fits = check_boundaries_within_window(left, right, 9.8, 10.2)
        assert fits is True  # No reload needed

    def test_asymmetric_offset_change(self):
        """Test asymmetric offset changes."""
        # Initial: RT=7.17, window=[6.97, 7.37]
        # New: loffset=0.1, roffset=0.5 (boundaries=[7.07, 7.67])
        left, right = calculate_integration_boundaries(7.17, 0.1, 0.5)
        fits = check_boundaries_within_window(left, right, 6.97, 7.37)
        assert fits is False  # Reload needed (right boundary exceeds)

    def test_rt_window_expansion_needed(self):
        """Test scenario where RT window must be expanded for offsets."""
        # Current RT window: 0.2, but offsets require 0.5
        current_window = 0.2
        min_required = calculate_minimum_rt_window(0.5, 0.4, buffer=0.1)
        assert min_required > current_window  # Window expansion needed
        assert min_required == 0.6


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_negative_offsets_invalid(self):
        """Test behavior with negative offsets (shouldn't happen but test anyway)."""
        # Negative offsets would reverse boundaries
        left, right = calculate_integration_boundaries(10.0, -0.1, -0.1)
        assert left == 10.1  # "Left" is actually right
        assert right == 9.9  # "Right" is actually left
        # This would be caught by validation before reaching this code

    def test_very_small_window(self):
        """Test with very small data window."""
        left, right = calculate_integration_boundaries(10.0, 0.01, 0.01)
        fits = check_boundaries_within_window(left, right, 9.99, 10.01)
        assert fits is True

    def test_very_large_window(self):
        """Test with very large data window."""
        left, right = calculate_integration_boundaries(10.0, 1.0, 1.0)
        fits = check_boundaries_within_window(left, right, 5.0, 15.0)
        assert fits is True

    def test_zero_tolerance(self):
        """Test with zero tolerance (exact matching)."""
        fits = check_boundaries_within_window(
            left_boundary=9.0,
            right_boundary=11.0,
            window_min=9.0,
            window_max=11.0,
            tolerance=0.0,
        )
        assert fits is True


class TestBufferConstant:
    """Test that buffer constant is accessible and works correctly."""
    
    def test_buffer_from_constants(self):
        """Test that default buffer can be imported from constants."""
        from manic.constants import DEFAULT_RT_WINDOW_BUFFER
        
        # Buffer should be a positive number
        assert DEFAULT_RT_WINDOW_BUFFER > 0
        
        # Test it works with the calculation function
        min_window = calculate_minimum_rt_window(0.2, 0.3, buffer=DEFAULT_RT_WINDOW_BUFFER)
        assert min_window == 0.3 + DEFAULT_RT_WINDOW_BUFFER
