"""
Total Ion Chromatogram (TIC) data reader.

Provides functionality to read TIC data from the database for detailed plot views.
"""

import logging
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
            cursor = conn.execute("""
                SELECT time, intensity 
                FROM tic_data 
                WHERE sample_name = ? AND deleted = 0
                ORDER BY time
            """, (sample_name,))
            
            rows = cursor.fetchall()
            
            if not rows:
                logger.warning(f"No TIC data found for sample: {sample_name}")
                return None
            
            times = np.array([row['time'] for row in rows])
            intensities = np.array([row['intensity'] for row in rows])
            
            logger.debug(f"Loaded TIC data for {sample_name}: {len(times)} points")
            
            return TICData(
                sample_name=sample_name,
                time=times,
                intensity=intensities
            )
            
    except Exception as e:
        logger.error(f"Failed to read TIC data for {sample_name}: {e}")
        return None


def tic_data_exists(sample_name: str) -> bool:
    """
    Check if TIC data exists for a sample.
    
    Args:
        sample_name: Name of the sample to check
        
    Returns:
        True if TIC data exists, False otherwise
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM tic_data 
                WHERE sample_name = ? AND deleted = 0
            """, (sample_name,))
            
            result = cursor.fetchone()
            return result['count'] > 0
            
    except Exception as e:
        logger.error(f"Failed to check TIC data existence for {sample_name}: {e}")
        return False


def _store_tic_data_with_conn(conn, sample_name: str, times: np.ndarray, intensities: np.ndarray):
    """Helper function to store TIC data with an existing connection."""
    # Clear existing data for this sample
    conn.execute("""
        UPDATE tic_data SET deleted = 1 
        WHERE sample_name = ?
    """, (sample_name,))
    
    # Insert new data
    data_to_insert = [
        (sample_name, float(time), float(intensity), 0)
        for time, intensity in zip(times, intensities)
    ]
    
    conn.executemany("""
        INSERT INTO tic_data (sample_name, time, intensity, deleted)
        VALUES (?, ?, ?, ?)
    """, data_to_insert)


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