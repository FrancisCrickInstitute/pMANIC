"""
Mass Spectrum (MS) data reader.

Provides functionality to read mass spectrum data from the database for detailed plot views.
"""

import logging
import numpy as np
from typing import Optional, List
from dataclasses import dataclass

from manic.models.database import get_connection

logger = logging.getLogger(__name__)


@dataclass
class MSData:
    """Container for Mass Spectrum data."""
    sample_name: str
    time: float
    mz: np.ndarray
    intensity: np.ndarray
    
    def __post_init__(self):
        """Ensure arrays are numpy arrays."""
        self.mz = np.asarray(self.mz)
        self.intensity = np.asarray(self.intensity)


def read_ms_at_time(sample_name: str, retention_time: float, tolerance: float = 0.1) -> Optional[MSData]:
    """
    Read mass spectrum data at a specific retention time.
    
    Args:
        sample_name: Name of the sample to read MS data for
        retention_time: Target retention time (minutes)
        tolerance: Time tolerance window (minutes)
        
    Returns:
        MSData object if data exists, None otherwise
    """
    try:
        time_min = retention_time - tolerance
        time_max = retention_time + tolerance
        
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT time, mz, intensity 
                FROM ms_data 
                WHERE sample_name = ? 
                AND time BETWEEN ? AND ?
                AND deleted = 0
                ORDER BY time, mz
            """, (sample_name, time_min, time_max))
            
            rows = cursor.fetchall()
            
            if not rows:
                logger.warning(f"No MS data found for sample: {sample_name} at time {retention_time:.3f}")
                return None
            
            # Group by time and average if multiple time points
            time_groups = {}
            for row in rows:
                time_key = round(row['time'], 3)  # Round to avoid floating point issues
                if time_key not in time_groups:
                    time_groups[time_key] = {'mz': [], 'intensity': []}
                time_groups[time_key]['mz'].append(row['mz'])
                time_groups[time_key]['intensity'].append(row['intensity'])
            
            # Find the time closest to target retention time
            best_time = min(time_groups.keys(), key=lambda t: abs(t - retention_time))
            
            mz_values = np.array(time_groups[best_time]['mz'])
            intensities = np.array(time_groups[best_time]['intensity'])
            
            # Sort by m/z
            sort_indices = np.argsort(mz_values)
            mz_values = mz_values[sort_indices]
            intensities = intensities[sort_indices]
            
            logger.debug(f"Loaded MS data for {sample_name} at time {best_time:.3f}: {len(mz_values)} peaks")
            
            return MSData(
                sample_name=sample_name,
                time=best_time,
                mz=mz_values,
                intensity=intensities
            )
            
    except Exception as e:
        logger.error(f"Failed to read MS data for {sample_name} at time {retention_time}: {e}")
        return None


def read_ms_times_for_sample(sample_name: str) -> List[float]:
    """
    Get all available MS data time points for a sample.
    
    Args:
        sample_name: Name of the sample
        
    Returns:
        List of time points where MS data is available
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT time
                FROM ms_data 
                WHERE sample_name = ? AND deleted = 0
                ORDER BY time
            """, (sample_name,))
            
            rows = cursor.fetchall()
            return [row['time'] for row in rows]
            
    except Exception as e:
        logger.error(f"Failed to get MS times for {sample_name}: {e}")
        return []


def ms_data_exists(sample_name: str, retention_time: float = None) -> bool:
    """
    Check if MS data exists for a sample, optionally at a specific time.
    
    Args:
        sample_name: Name of the sample to check
        retention_time: Optional specific time to check
        
    Returns:
        True if MS data exists, False otherwise
    """
    try:
        with get_connection() as conn:
            if retention_time is not None:
                cursor = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM ms_data 
                    WHERE sample_name = ? AND time = ? AND deleted = 0
                """, (sample_name, retention_time))
            else:
                cursor = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM ms_data 
                    WHERE sample_name = ? AND deleted = 0
                """, (sample_name,))
            
            result = cursor.fetchone()
            return result['count'] > 0
            
    except Exception as e:
        logger.error(f"Failed to check MS data existence for {sample_name}: {e}")
        return False


def store_ms_data(sample_name: str, time: float, mz_values: np.ndarray, intensities: np.ndarray) -> bool:
    """
    Store mass spectrum data in the database for a specific time point.
    
    Args:
        sample_name: Name of the sample
        time: Retention time
        mz_values: Array of m/z values
        intensities: Array of intensity values
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if len(mz_values) != len(intensities):
            raise ValueError("m/z and intensities arrays must have same length")
            
        with get_connection() as conn:
            # Clear existing data for this sample/time combination
            conn.execute("""
                UPDATE ms_data SET deleted = 1 
                WHERE sample_name = ? AND time = ?
            """, (sample_name, time))
            
            # Insert new data
            data_to_insert = [
                (sample_name, float(time), float(mz), float(intensity), 0)
                for mz, intensity in zip(mz_values, intensities)
                if intensity > 0  # Only store peaks with non-zero intensity
            ]
            
            if data_to_insert:
                # Use INSERT OR REPLACE to handle potential duplicates gracefully
                conn.executemany("""
                    INSERT OR REPLACE INTO ms_data (sample_name, time, mz, intensity, deleted)
                    VALUES (?, ?, ?, ?, ?)
                """, data_to_insert)
                
                logger.debug(f"Stored MS data for {sample_name} at time {time:.3f}: {len(data_to_insert)} peaks")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to store MS data for {sample_name} at time {time}: {e}")
        return False


def store_ms_data_batch(sample_name: str, ms_data_points: List[tuple], conn=None) -> bool:
    """
    Store multiple MS data points efficiently.
    
    Args:
        sample_name: Name of the sample
        ms_data_points: List of (time, mz_array, intensity_array) tuples
        conn: Optional database connection to use
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if conn is not None:
            # Use provided connection
            _store_ms_data_batch_with_conn(conn, sample_name, ms_data_points)
        else:
            # Create new connection
            with get_connection() as new_conn:
                _store_ms_data_batch_with_conn(new_conn, sample_name, ms_data_points)
        
        return True
            
    except Exception as e:
        logger.error(f"Failed to store MS batch data for {sample_name}: {e}")
        return False


def _store_ms_data_batch_with_conn(conn, sample_name: str, ms_data_points: List[tuple]):
    """
    Helper function to store MS batch data with an existing connection.
    
    Uses INSERT OR REPLACE to handle duplicate entries gracefully when the same
    CDF files are imported multiple times with different filenames. This allows
    the application to process identical sample data without constraint violations.
    """
    # Clear all existing MS data for this sample to start fresh
    conn.execute("""
        UPDATE ms_data SET deleted = 1 
        WHERE sample_name = ?
    """, (sample_name,))
    
    # Prepare all data for batch insert
    all_data = []
    for time, mz_values, intensities in ms_data_points:
        if len(mz_values) != len(intensities):
            logger.warning(f"Skipping MS data at time {time}: array length mismatch")
            continue
            
        for mz, intensity in zip(mz_values, intensities):
            if intensity > 0:  # Only store non-zero peaks
                all_data.append((sample_name, float(time), float(mz), float(intensity), 0))
    
    if all_data:
        # Use INSERT OR REPLACE to handle duplicate (sample_name, time, mz) entries
        # This allows importing the same CDF file multiple times without constraint violations
        conn.executemany("""
            INSERT OR REPLACE INTO ms_data (sample_name, time, mz, intensity, deleted)
            VALUES (?, ?, ?, ?, ?)
        """, all_data)
        
