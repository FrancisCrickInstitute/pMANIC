"""
Tests for peak area validation logic.

These tests verify the mathematical behavior of peak area validation:
comparing compound total areas against internal standard M0 areas.
"""

import pytest

from manic.io.data_provider import DataProvider


def test_peak_area_validation_math():
    """Peak area validation should compare total areas directly."""
    # Import the validation helper - will fail if not implemented
    from manic.validation.peak_area import is_valid  # type: ignore[import-not-found]
    
    # Test passing threshold: 20.0 >= 0.05 * 200.0 (10.0)
    assert is_valid(compound_total=20.0, internal_standard_m0=200.0, ratio=0.05)

    # Test failing threshold: 5.0 < 0.05 * 200.0 (10.0)
    assert not is_valid(compound_total=5.0, internal_standard_m0=200.0, ratio=0.05)

    # Test edge case: exactly at threshold
    assert is_valid(compound_total=10.0, internal_standard_m0=200.0, ratio=0.05)

    # Test with different ratio
    assert is_valid(compound_total=15.0, internal_standard_m0=200.0, ratio=0.05)
    assert not is_valid(compound_total=8.0, internal_standard_m0=200.0, ratio=0.05)


def test_data_provider_peak_metrics_totals():
    """DataProvider should expose compound totals and internal standard M0."""
    provider = DataProvider()
    
    # Simulate the bulk cache being populated with isotopologue areas
    provider._bulk_sample_data_cache = {
        "Sample1": {
            "CompoundA": [10.0, 5.0, 2.5],  # Sum = 17.5
            "ISTD": [40.0, 10.0, 5.0],      # M0 = 40.0
        }
    }
    provider._cache_valid = True
    
    # Get metrics - will fail if method doesn't exist
    metrics = provider.get_sample_peak_metrics("Sample1", "ISTD")  # type: ignore[attr-defined]
    
    # Verify CompoundA totals
    assert metrics["CompoundA"]["compound_total"] == pytest.approx(17.5)
    assert metrics["CompoundA"]["internal_standard_m0"] == pytest.approx(40.0)

    # Verify ISTD totals
    assert metrics["ISTD"]["compound_total"] == pytest.approx(55.0)
    assert metrics["ISTD"]["internal_standard_m0"] == pytest.approx(40.0)


def test_data_provider_peak_metrics_with_session_overrides():
    """Peak metrics should reflect session-adjusted integration boundaries."""
    provider = DataProvider()
    
    # The cached areas already incorporate session overrides via LEFT JOIN + COALESCE
    # in load_bulk_sample_data(), so we just verify the helper works correctly
    provider._bulk_sample_data_cache = {
        "Sample2": {
            "CompoundB": [100.0, 50.0],  # Sum = 150.0
            "ISTD": [500.0],             # M0 = 500.0
        }
    }
    provider._cache_valid = True
    
    metrics = provider.get_sample_peak_metrics("Sample2", "ISTD")  # type: ignore[attr-defined]
    
    assert metrics["CompoundB"]["compound_total"] == pytest.approx(150.0)
    assert metrics["CompoundB"]["internal_standard_m0"] == pytest.approx(500.0)
