"""
Minimal pytest fixtures for MANIC tests.
Provides shared test infrastructure without complexity.
"""

import os
import sys
import sqlite3
from pathlib import Path

import pytest
import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from test_data import TEST_COMPOUNDS, TEST_SAMPLES


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary database path for testing."""
    return str(tmp_path / "test.db")


@pytest.fixture
def simple_arrays():
    """Provide simple numpy arrays for testing."""
    return {
        'time': np.linspace(0, 10, 100),
        'intensity': np.ones(100),
        'masses': np.array([87.0, 88.0, 89.0, 90.0]),
        'zero_array': np.zeros(100)
    }


@pytest.fixture
def mock_data_provider():
    """
    Create a mock DataProvider for testing without database.
    Only used when needed to avoid database setup overhead.
    """
    class MockDataProvider:
        def __init__(self):
            self.use_legacy_integration = False
            self._cache = {}

        def get_all_compounds(self):
            return TEST_COMPOUNDS

        def get_all_samples(self):
            return TEST_SAMPLES

        def get_sample_corrected_data(self, sample_name):
            # Return simple test data
            return {
                'Pyruvate': [900.0, 450.0, 225.0, 112.5],
                'Lactate': [800.0, 400.0, 200.0, 100.0],
                'ISTD': [1000.0]
            }

        def get_sample_raw_data(self, sample_name):
            # Return simple test data
            return {
                'Pyruvate': [1000.0, 500.0, 250.0, 125.0],
                'Lactate': [900.0, 450.0, 225.0, 112.5],
                'ISTD': [1000.0]
            }

        def resolve_mm_samples(self, pattern):
            if 'MM' in pattern or '*' in pattern:
                return ['MM01']
            return []

        def get_mrrf_values(self, compounds, internal_standard):
            return {
                'Pyruvate': 1.0,
                'Lactate': 1.2,
                'ISTD': 1.0
            }

        def get_background_ratios(self, compounds):
            return {
                'Pyruvate': 0.05,
                'Lactate': 0.04
            }

        def invalidate_cache(self):
            self._cache.clear()

    return MockDataProvider()


@pytest.fixture
def init_test_db():
    """
    Initialize a test database with schema.
    Returns a connection object.
    """
    def _init_db(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # Would need to create schema manually here
        # For now, tests that need a DB should create their own schema
        return conn
    return _init_db


@pytest.fixture(autouse=True)
def cleanup_env():
    """Clean up environment variables after each test."""
    yield
    # Remove any test database paths from environment
    if 'MANIC_DB_PATH' in os.environ:
        del os.environ['MANIC_DB_PATH']


@pytest.fixture
def sample_eic_data():
    """Provide sample EIC data for testing."""
    time = np.linspace(0, 10, 100)
    # Create multi-isotopologue data (M+0, M+1, M+2, M+3)
    intensities = np.concatenate([
        np.ones(100) * 1000,  # M+0
        np.ones(100) * 500,   # M+1
        np.ones(100) * 250,   # M+2
        np.ones(100) * 125    # M+3
    ])
    return time, intensities


@pytest.fixture
def test_formula_dict():
    """Provide test chemical formulas for correction testing."""
    return {
        'simple': {'C': 1, 'H': 4},
        'pyruvate': {'C': 3, 'H': 3, 'O': 3},
        'glucose': {'C': 6, 'H': 12, 'O': 6},
        'complex': {'C': 10, 'H': 15, 'N': 2, 'O': 5}
    }


# Performance monitoring fixture
@pytest.fixture
def performance_monitor():
    """Monitor test performance (time and memory)."""
    import time
    import tracemalloc

    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.start_snapshot = None

        def start(self):
            self.start_time = time.time()
            tracemalloc.start()
            self.start_snapshot = tracemalloc.take_snapshot()

        def stop(self):
            elapsed = time.time() - self.start_time
            current = tracemalloc.take_snapshot()
            stats = current.compare_to(self.start_snapshot, 'lineno')
            total_mb = sum(stat.size_diff for stat in stats) / 1024 / 1024
            tracemalloc.stop()
            return elapsed, total_mb

    return PerformanceMonitor()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )