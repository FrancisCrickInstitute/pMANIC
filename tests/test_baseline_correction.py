"""
Tests for baseline correction functionality.

Tests cover:
1. Linear baseline fitting through boundary points
2. Baseline area calculation
3. Peak area calculation with baseline correction
4. Edge cases (insufficient points, flat baselines)
"""

import numpy as np
import pytest

from manic.processors.integration import (
    BASELINE_NUM_POINTS,
    calculate_peak_areas,
    compute_baseline_area,
    compute_linear_baseline,
    integrate_peak,
)


class TestComputeLinearBaseline:
    """Tests for compute_linear_baseline function."""

    def test_basic_sloped_baseline(self):
        """Test fitting a baseline through a known sloped signal."""
        # Create time array
        time_data = np.linspace(0, 10, 100)
        # Create a linear baseline: y = 2*x + 5
        intensity_data = 2 * time_data + 5

        result = compute_linear_baseline(time_data, intensity_data)

        assert result is not None
        td, baseline_y = result
        assert len(td) == len(time_data)
        # Baseline should match the original linear signal
        np.testing.assert_allclose(baseline_y, intensity_data, rtol=1e-5)

    def test_peak_on_sloped_baseline(self):
        """Test baseline fitting with a peak on top of sloped baseline."""
        time_data = np.linspace(0, 10, 100)
        # Sloped baseline: y = 1*x + 10
        baseline = 1 * time_data + 10
        # Add a Gaussian peak in the middle
        peak = 50 * np.exp(-((time_data - 5) ** 2) / 0.5)
        intensity_data = baseline + peak

        result = compute_linear_baseline(time_data, intensity_data)

        assert result is not None
        td, baseline_y = result
        # Baseline should be close to the original linear component
        # (not exact due to peak affecting boundary points slightly)
        # Check slope is approximately correct
        slope = (baseline_y[-1] - baseline_y[0]) / (td[-1] - td[0])
        assert 0.8 < slope < 1.2  # Should be close to 1

    def test_insufficient_points(self):
        """Test that baseline returns None with too few points."""
        time_data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])  # Only 5 points
        intensity_data = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

        # Default n_points=3, so need at least 6 points
        result = compute_linear_baseline(time_data, intensity_data)

        assert result is None

    def test_exactly_six_points(self):
        """Test baseline with exactly 6 points (minimum required)."""
        time_data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        intensity_data = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])

        result = compute_linear_baseline(time_data, intensity_data)

        assert result is not None
        td, baseline_y = result
        assert len(td) == 6

    def test_none_input(self):
        """Test handling of None inputs."""
        result = compute_linear_baseline(None, np.array([1, 2, 3]))
        assert result is None

        result = compute_linear_baseline(np.array([1, 2, 3]), None)
        assert result is None

    def test_flat_baseline(self):
        """Test flat baseline (zero slope)."""
        time_data = np.linspace(0, 10, 50)
        intensity_data = np.ones(50) * 100  # Constant value

        result = compute_linear_baseline(time_data, intensity_data)

        assert result is not None
        td, baseline_y = result
        # All baseline values should be approximately 100
        np.testing.assert_allclose(baseline_y, 100, rtol=1e-5)


class TestComputeBaselineArea:
    """Tests for compute_baseline_area function."""

    def test_linear_baseline_area(self):
        """Test area calculation for a linear baseline."""
        # Create a simple linear baseline: y = 10 over x = [0, 10]
        # Area should be 10 * 10 = 100
        time_data = np.linspace(0, 10, 100)
        intensity_data = np.ones(100) * 10

        area = compute_baseline_area(time_data, intensity_data)

        assert area is not None
        assert pytest.approx(area, rel=0.01) == 100.0

    def test_sloped_baseline_area(self):
        """Test area calculation for a sloped baseline (trapezoid)."""
        # Create baseline from y=0 to y=20 over x=[0, 10]
        # Area of trapezoid = (0 + 20) / 2 * 10 = 100
        time_data = np.linspace(0, 10, 100)
        intensity_data = 2 * time_data  # y = 2x, from 0 to 20

        area = compute_baseline_area(time_data, intensity_data)

        assert area is not None
        assert pytest.approx(area, rel=0.01) == 100.0

    def test_legacy_baseline_area_matches_trapezoid(self):
        """Legacy integration should match np.trapezoid for unit spacing."""
        time_data = np.linspace(0, 5, 20)
        intensity_data = 3 * time_data + 5

        area = compute_baseline_area(time_data, intensity_data, use_legacy=True)
        expected = np.trapezoid(intensity_data)

        assert area is not None
        assert pytest.approx(area, rel=0.001) == expected

    def test_insufficient_points_returns_none(self):
        """Test that insufficient points returns None."""
        time_data = np.array([1.0, 2.0, 3.0])
        intensity_data = np.array([10.0, 20.0, 30.0])

        area = compute_baseline_area(time_data, intensity_data)

        assert area is None


class TestCalculatePeakAreasWithBaselineCorrection:
    """Tests for calculate_peak_areas with baseline_correction parameter."""

    def test_unlabeled_no_baseline(self):
        """Test unlabeled compound without baseline correction."""
        time_data = np.linspace(9.5, 10.5, 50)
        # Simple peak
        intensity_data = 100 * np.exp(-((time_data - 10) ** 2) / 0.01)

        areas = calculate_peak_areas(
            time_data,
            intensity_data,
            label_atoms=0,
            retention_time=10.0,
            loffset=0.4,
            roffset=0.4,
            baseline_correction=False,
        )

        assert len(areas) == 1
        assert areas[0] > 0

    def test_unlabeled_with_baseline(self):
        """Test unlabeled compound with baseline correction."""
        time_data = np.linspace(9.5, 10.5, 50)
        # Peak on top of sloped baseline
        baseline = 0.5 * time_data + 5
        peak = 100 * np.exp(-((time_data - 10) ** 2) / 0.01)
        intensity_data = baseline + peak

        areas_no_baseline = calculate_peak_areas(
            time_data,
            intensity_data,
            label_atoms=0,
            retention_time=10.0,
            loffset=0.4,
            roffset=0.4,
            baseline_correction=False,
        )

        areas_with_baseline = calculate_peak_areas(
            time_data,
            intensity_data,
            label_atoms=0,
            retention_time=10.0,
            loffset=0.4,
            roffset=0.4,
            baseline_correction=True,
        )

        assert len(areas_no_baseline) == 1
        assert len(areas_with_baseline) == 1
        # With baseline correction, area should be smaller
        assert areas_with_baseline[0] < areas_no_baseline[0]

    def test_labeled_with_baseline(self):
        """Test labeled compound with baseline correction applied per isotopologue."""
        time_data = np.linspace(9.5, 10.5, 50)
        num_isotopologues = 3

        # Create intensity data with different peaks on same baseline
        intensity_traces = []
        for i in range(num_isotopologues):
            baseline = 0.2 * time_data + 2
            peak = (100 - i * 20) * np.exp(-((time_data - 10) ** 2) / 0.01)
            intensity_traces.append(baseline + peak)

        intensity_data = np.array(intensity_traces).flatten()

        areas_no_baseline = calculate_peak_areas(
            time_data,
            intensity_data,
            label_atoms=2,  # 3 isotopologues
            retention_time=10.0,
            loffset=0.4,
            roffset=0.4,
            baseline_correction=False,
        )

        areas_with_baseline = calculate_peak_areas(
            time_data,
            intensity_data,
            label_atoms=2,
            retention_time=10.0,
            loffset=0.4,
            roffset=0.4,
            baseline_correction=True,
        )

        assert len(areas_no_baseline) == 3
        assert len(areas_with_baseline) == 3

        # Each isotopologue should have smaller area with baseline correction
        for i in range(3):
            assert areas_with_baseline[i] < areas_no_baseline[i]

    def test_flat_baseline_minimal_effect(self):
        """Test that a flat baseline at zero has minimal effect."""
        time_data = np.linspace(9.5, 10.5, 50)
        # Pure peak with no baseline offset
        intensity_data = 100 * np.exp(-((time_data - 10) ** 2) / 0.01)

        areas_no_baseline = calculate_peak_areas(
            time_data,
            intensity_data,
            label_atoms=0,
            retention_time=10.0,
            loffset=0.4,
            roffset=0.4,
            baseline_correction=False,
        )

        areas_with_baseline = calculate_peak_areas(
            time_data,
            intensity_data,
            label_atoms=0,
            retention_time=10.0,
            loffset=0.4,
            roffset=0.4,
            baseline_correction=True,
        )

        # With a peak that goes to near-zero at edges, baseline should be minimal
        # The corrected area should be very close to uncorrected
        assert len(areas_no_baseline) == 1
        assert len(areas_with_baseline) == 1
        # Allow small difference due to edge effects
        ratio = areas_with_baseline[0] / areas_no_baseline[0]
        assert 0.9 < ratio <= 1.0

    def test_baseline_default_is_false(self):
        """Test that baseline_correction defaults to False."""
        time_data = np.linspace(9.5, 10.5, 50)
        intensity_data = np.ones(50) * 100  # Flat signal

        # Call without baseline_correction parameter
        areas_default = calculate_peak_areas(
            time_data,
            intensity_data,
            label_atoms=0,
            retention_time=10.0,
            loffset=0.4,
            roffset=0.4,
        )

        # Call with explicit False
        areas_explicit_false = calculate_peak_areas(
            time_data,
            intensity_data,
            label_atoms=0,
            retention_time=10.0,
            loffset=0.4,
            roffset=0.4,
            baseline_correction=False,
        )

        # Should be identical
        assert areas_default == areas_explicit_false

    def test_vectorized_baseline_matches_scalar(self):
        """Vectorized path should match per-trace integration results."""
        time_data = np.linspace(0, 10, 200)
        retention_time = 5.0
        loffset = 5.0
        roffset = 5.0

        # Build three isotopologue traces on shared sloped baselines
        traces = []
        for scale in (100, 80, 60):
            baseline = 0.3 * time_data + 2
            peak = scale * np.exp(-((time_data - retention_time) ** 2) / 0.5)
            traces.append(baseline + peak)

        intensity_data = np.array(traces).flatten()

        vectorized = calculate_peak_areas(
            time_data,
            intensity_data,
            label_atoms=2,
            retention_time=retention_time,
            loffset=loffset,
            roffset=roffset,
            baseline_correction=True,
        )

        manual = []
        for trace in traces:
            total_area = integrate_peak(trace, time_data)
            baseline_area = compute_baseline_area(time_data, trace)
            manual.append(max(0.0, total_area - (baseline_area or 0.0)))

        np.testing.assert_allclose(vectorized, manual, rtol=1e-6)


class TestBaselineNumPoints:
    """Test the BASELINE_NUM_POINTS constant."""

    def test_baseline_num_points_is_three(self):
        """Verify the constant matches MATLAB implementation (3 points per edge)."""
        assert BASELINE_NUM_POINTS == 3

    def test_custom_n_points(self):
        """Test using custom number of boundary points."""
        time_data = np.linspace(0, 10, 100)
        intensity_data = time_data * 2 + 5

        # Use 5 points per edge instead of default 3
        result = compute_linear_baseline(time_data, intensity_data, n_points=5)

        assert result is not None
        td, baseline_y = result
        assert len(td) == 100
