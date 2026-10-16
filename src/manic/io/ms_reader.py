"""
Mass Spectrum (MS) data reader.

Provides functionality to read mass spectrum data from the database for detailed plot views.
"""

import logging
import zlib

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
                FROM ms_spectrum 
                WHERE sample_name = ? 
                AND time BETWEEN ? AND ?
                ORDER BY time
            """, (sample_name, time_min, time_max))
            
            rows = cursor.fetchall()
            
            if not rows:
                logger.warning(f"No MS data found for sample: {sample_name} at time {retention_time:.3f}")
                return None
            
            # Group by time and merge spectra whose times round together
            time_groups = {}
            for row in rows:
                time_key = round(row['time'], 3)  # Round to avoid floating point issues
                time_groups.setdefault(time_key, []).append(row)
            
            # Find the time closest to target retention time
            best_time = min(time_groups.keys(), key=lambda t: abs(t - retention_time))
            
            mz_values = np.concatenate([_unpack(row['mz']) for row in time_groups[best_time]])
            intensities = np.concatenate([_unpack(row['intensity']) for row in time_groups[best_time]])
            
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


def _pack(values) -> bytes:
    return zlib.compress(np.asarray(values, dtype=np.float64).tobytes())


def _unpack(blob: bytes) -> np.ndarray:
    return np.frombuffer(zlib.decompress(blob), dtype=np.float64)


def _spectrum_rows(sample_name: str, ms_data_points: List[tuple]) -> List[tuple]:
    """One ms_spectrum row per spectrum: its non-zero peaks, sorted by m/z."""
    rows = []
    for time, mz_values, intensities in ms_data_points:
        if len(mz_values) != len(intensities):
            logger.warning(f"Skipping MS data at time {time}: array length mismatch")
            continue

        mz = np.asarray(mz_values, dtype=np.float64)
        intensity = np.asarray(intensities, dtype=np.float64)
        # np.asarray exposes the fill value under masked (missing) CDF points; drop them.
        missing = np.ma.getmaskarray(mz_values) | np.ma.getmaskarray(intensities)
        nonzero = (intensity > 0) & ~missing
        if not np.any(nonzero):
            continue
        mz, intensity = mz[nonzero], intensity[nonzero]
        # Keep the last peak per m/z, as the old row-per-peak UNIQUE(time, mz) table did.
        _, last_reversed = np.unique(mz[::-1], return_index=True)
        keep = len(mz) - 1 - last_reversed
        rows.append((sample_name, float(time), _pack(mz[keep]), _pack(intensity[keep])))
    return rows


_INSERT_SPECTRUM = """
    INSERT OR REPLACE INTO ms_spectrum (sample_name, time, mz, intensity)
    VALUES (?, ?, ?, ?)
"""


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
            conn.execute(
                "DELETE FROM ms_spectrum WHERE sample_name = ? AND time = ?",
                (sample_name, time),
            )
            conn.executemany(
                _INSERT_SPECTRUM,
                _spectrum_rows(sample_name, [(time, mz_values, intensities)]),
            )
            
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
    
    Compounds that share a scan produce the same time twice; INSERT OR REPLACE
    keeps one spectrum per (sample_name, time).
    """
    # Clear all existing MS data for this sample to start fresh
    conn.execute("DELETE FROM ms_spectrum WHERE sample_name = ?", (sample_name,))
    conn.executemany(_INSERT_SPECTRUM, _spectrum_rows(sample_name, ms_data_points))
