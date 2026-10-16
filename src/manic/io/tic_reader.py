"""
Total Ion Chromatogram (TIC) data reader.

Provides functionality to read TIC data from the database for detailed plot views.
"""

import logging
import zlib

import numpy as np
from typing import Optional
from dataclasses import dataclass

from manic.models.database import get_connection

logger = logging.getLogger(__name__)


@dataclass
class TICData:
    """Container for Total Ion Chromatogram data."""
    sample_name: str
    time: np.ndarray
    intensity: np.ndarray
    
    def __post_init__(self):
        """Ensure arrays are numpy arrays."""
        self.time = np.asarray(self.time)
        self.intensity = np.asarray(self.intensity)


def read_tic(sample_name: str) -> Optional[TICData]:
    """
    Read TIC data for a sample from database.
    
    Args:
        sample_name: Name of the sample to read TIC data for
        
    Returns:
        TICData object if data exists, None otherwise
    """
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT time, intensity FROM tic_trace WHERE sample_name = ?",
                (sample_name,),
            ).fetchone()
            
            if row is None:
                logger.warning(f"No TIC data found for sample: {sample_name}")
                return None
            
            times = np.frombuffer(zlib.decompress(row['time']), dtype=np.float64)
            intensities = np.frombuffer(zlib.decompress(row['intensity']), dtype=np.float64)
            
            logger.debug(f"Loaded TIC data for {sample_name}: {len(times)} points")
            
            return TICData(
                sample_name=sample_name,
                time=times,
                intensity=intensities
            )
            
    except Exception as e:
        logger.error(f"Failed to read TIC data for {sample_name}: {e}")
        return None


def _store_tic_data_with_conn(conn, sample_name: str, times: np.ndarray, intensities: np.ndarray):
    """Helper function to store TIC data with an existing connection."""
    # np.asarray exposes the fill value under masked (missing) CDF scans; drop them.
    present = ~(np.ma.getmaskarray(times) | np.ma.getmaskarray(intensities))
    times = np.asarray(times, dtype=np.float64)[present]
    intensities = np.asarray(intensities, dtype=np.float64)[present]
    order = np.argsort(times, kind="stable")
    conn.execute(
        "INSERT OR REPLACE INTO tic_trace (sample_name, time, intensity) VALUES (?, ?, ?)",
        (
            sample_name,
            zlib.compress(times[order].tobytes()),
            zlib.compress(intensities[order].tobytes()),
        ),
    )


def store_tic_data(sample_name: str, times: np.ndarray, intensities: np.ndarray, conn=None) -> bool:
    """
    Store TIC data in the database.
    
    Args:
        sample_name: Name of the sample
        times: Array of time points
        intensities: Array of intensity values
        conn: Optional database connection to use
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if len(times) != len(intensities):
            raise ValueError("Times and intensities arrays must have same length")
            
        if conn is not None:
            # Use provided connection
            _store_tic_data_with_conn(conn, sample_name, times, intensities)
        else:
            # Create new connection
            with get_connection() as new_conn:
                _store_tic_data_with_conn(new_conn, sample_name, times, intensities)
            
        return True
            
    except Exception as e:
        logger.error(f"Failed to store TIC data for {sample_name}: {e}")
        return False