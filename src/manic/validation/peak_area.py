"""
Pure mathematical validation functions for peak area thresholds.

These functions perform simple arithmetic comparisons without any database
or UI dependencies, making them easy to test and reason about.
"""


def is_valid(compound_total: float, internal_standard_reference: float, ratio: float) -> bool:
    """
    Check if a compound's total area meets the minimum threshold.

    This is a pure mathematical function that compares:
        compound_total >= (internal_standard_reference × ratio)

    Args:
        compound_total: Sum of all isotopologue areas for the compound
        internal_standard_reference: reference peak area for the internal standard (M+N)
        ratio: Minimum ratio threshold (e.g., 0.05 for 5%)

    Returns:
        True if compound meets threshold, False otherwise

    Examples:
        >>> is_valid(20.0, 200.0, 0.05)
        True  # 20.0 >= (200.0 × 0.05 = 10.0)

        >>> is_valid(5.0, 200.0, 0.05)
        False  # 5.0 < (200.0 × 0.05 = 10.0)

        >>> is_valid(10.0, 200.0, 0.05)
        True  # 10.0 >= (200.0 × 0.05 = 10.0) - exactly at threshold
    """
    if internal_standard_reference <= 0:
        return True

    threshold = internal_standard_reference * ratio
    return compound_total >= threshold
