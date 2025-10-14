"""
Simple test data constants for MANIC tests.
Minimal, deterministic data for reproducible testing.
"""

import numpy as np


# Test compounds with known properties
TEST_COMPOUNDS = [
    {
        'compound_name': 'Pyruvate',
        'formula': 'C3H3O3',
        'label_atoms': 3,
        'label_type': 'C',
        'mass0': 87.0,
        'retention_time': 5.5,
        'loffset': 0.2,
        'roffset': 0.2,
        'amount_in_std_mix': 10.0,
        'int_std_amount': 1.0,
        'mm_files': '*MM*',
        'tbdms': 0,
        'meox': 0,
        'me': 0
    },
    {
        'compound_name': 'Lactate',
        'formula': 'C3H5O3',
        'label_atoms': 3,
        'label_type': 'C',
        'mass0': 89.0,
        'retention_time': 4.2,
        'loffset': 0.2,
        'roffset': 0.2,
        'amount_in_std_mix': 10.0,
        'int_std_amount': 1.0,
        'mm_files': '*MM*',
        'tbdms': 0,
        'meox': 0,
        'me': 0
    },
    {
        'compound_name': 'ISTD',
        'formula': 'C6H12O6',
        'label_atoms': 0,  # Unlabeled internal standard
        'label_type': None,
        'mass0': 179.0,
        'retention_time': 7.0,
        'loffset': 0.2,
        'roffset': 0.2,
        'amount_in_std_mix': 5.0,
        'int_std_amount': 5.0,
        'mm_files': '*MM*',
        'tbdms': 0,
        'meox': 0,
        'me': 0
    }
]

# Test samples
TEST_SAMPLES = [
    'Sample01',  # Experimental sample 1
    'Sample02',  # Experimental sample 2
    'MM01',      # Standard mixture 1
    'MM02'       # Standard mixture 2
]

# Test intensity patterns (M+0, M+1, M+2, M+3)
TEST_INTENSITIES = {
    'Pyruvate': {
        'Sample01': [1000.0, 500.0, 250.0, 125.0],
        'Sample02': [900.0, 450.0, 225.0, 112.5],
        'MM01': [500.0, 250.0, 125.0, 62.5],
        'MM02': [480.0, 240.0, 120.0, 60.0]
    },
    'Lactate': {
        'Sample01': [800.0, 400.0, 200.0, 100.0],
        'Sample02': [750.0, 375.0, 187.5, 93.75],
        'MM01': [400.0, 200.0, 100.0, 50.0],
        'MM02': [380.0, 190.0, 95.0, 47.5]
    },
    'ISTD': {
        'Sample01': [1000.0],  # M+0 only (unlabeled)
        'Sample02': [1000.0],
        'MM01': [1000.0],
        'MM02': [1000.0]
    }
}

# Expected corrected intensities after natural abundance correction
# These are approximations for testing
TEST_CORRECTED_INTENSITIES = {
    'Pyruvate': {
        'Sample01': [990.0, 485.0, 235.0, 115.0],  # Slightly lower after correction
        'Sample02': [891.0, 436.0, 211.0, 103.0],
        'MM01': [495.0, 242.0, 117.0, 57.0],
        'MM02': [475.0, 232.0, 113.0, 55.0]
    },
    'Lactate': {
        'Sample01': [792.0, 388.0, 188.0, 92.0],
        'Sample02': [742.0, 363.0, 176.0, 86.0],
        'MM01': [396.0, 194.0, 94.0, 46.0],
        'MM02': [376.0, 184.0, 89.0, 43.0]
    },
    'ISTD': {
        'Sample01': [1000.0],  # No correction for unlabeled
        'Sample02': [1000.0],
        'MM01': [1000.0],
        'MM02': [1000.0]
    }
}

# Test time arrays for EIC data
def generate_test_time_array(num_points=100, start=0, end=10):
    """Generate a simple time array for testing."""
    return np.linspace(start, end, num_points)

# Test EIC patterns
def generate_test_eic(compound_name, sample_name, num_points=100):
    """
    Generate synthetic EIC data for testing.
    Returns time array and flattened intensity array.
    """
    time = generate_test_time_array(num_points)
    intensities = TEST_INTENSITIES[compound_name][sample_name]

    # Create gaussian-like peak for each isotopologue
    center_idx = num_points // 2
    width = num_points // 10

    all_intensities = []
    for iso_intensity in intensities:
        # Simple gaussian shape
        x = np.arange(num_points)
        peak = iso_intensity * np.exp(-((x - center_idx) ** 2) / (2 * width ** 2))
        all_intensities.append(peak)

    # Flatten for storage format
    intensity_flat = np.concatenate(all_intensities)

    return time, intensity_flat

# Known test values for validation
TEST_EXPECTED_VALUES = {
    'integration': {
        'trapezoid_uniform': {
            # For uniform spacing, constant intensity
            'time_based': 10.0,  # 1.0 intensity over 10 minutes
            'legacy': 99.0       # 1.0 intensity, 99 intervals (100 points)
        }
    },
    'mrrf': {
        'Pyruvate': 1.0,  # Example MRRF values
        'Lactate': 1.2,
        'ISTD': 1.0       # Always 1.0 for internal standard
    },
    'background_ratios': {
        'Pyruvate': 0.05,  # 5% background labeling
        'Lactate': 0.04   # 4% background labeling
    },
    'isotope_ratios': {
        # Expected normalized ratios for Pyruvate in Sample01
        'Pyruvate_Sample01': [0.571, 0.286, 0.095, 0.048]  # Sum to 1.0
    },
    'percent_label': {
        # Expected % label incorporation after background correction
        'Pyruvate_Sample01': 42.0,  # Example value
        'Lactate_Sample01': 45.5
    }
}

# Critical test cases for known bugs
CRITICAL_TEST_CASES = {
    'sum_vs_lastwins': {
        'masses': [204.8, 205.1],  # Both round to 205
        'intensities': [1000.0, 500.0],
        'expected_sum': 1500.0,     # Python behavior
        'expected_lastwins': 500.0  # MATLAB bug behavior
    },
    'matlab_rounding': {
        'test_values': [204.5, 205.5, 204.4, 204.6],
        'expected': [205, 206, 204, 205]  # floor(x + 0.5)
    },
    'strict_boundaries': {
        'time_points': [3.9, 4.0, 4.1, 5.9, 6.0, 6.1],
        'rt': 5.0,
        'offsets': 1.0,
        # Points at 4.0 and 6.0 exactly are excluded
        'included_indices': [2, 3]  # Only 4.1 and 5.9
    }
}

# Helper functions for test data generation
def create_test_cdf_data(sample_name, compound_name, num_scans=100):
    """
    Create synthetic CDF-like data structure for testing.
    Returns dict with scan_time, mass, intensity arrays.
    """
    scan_time = np.linspace(0, 600, num_scans)  # 10 minutes in seconds

    compound_info = next(c for c in TEST_COMPOUNDS if c['compound_name'] == compound_name)
    mass0 = compound_info['mass0']
    label_atoms = compound_info['label_atoms']

    masses = []
    intensities = []
    scan_indices = []

    for scan_idx in range(num_scans):
        for iso in range(label_atoms + 1):
            masses.append(mass0 + iso)
            # Use test intensity pattern
            base_intensity = TEST_INTENSITIES[compound_name][sample_name][iso]
            # Add gaussian shape
            center = num_scans // 2
            width = num_scans // 10
            intensity = base_intensity * np.exp(-((scan_idx - center) ** 2) / (2 * width ** 2))
            intensities.append(intensity)
            scan_indices.append(scan_idx)

    return {
        'scan_time': scan_time,
        'mass': np.array(masses),
        'intensity': np.array(intensities),
        'scan_index': np.array(scan_indices)
    }

def get_expected_mrrf(compound_name):
    """Get expected MRRF value for a compound."""
    return TEST_EXPECTED_VALUES['mrrf'].get(compound_name, 1.0)

def get_expected_background_ratio(compound_name):
    """Get expected background ratio for a compound."""
    return TEST_EXPECTED_VALUES['background_ratios'].get(compound_name, 0.0)