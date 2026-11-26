"""
Total Ion Chromatogram (TIC) data reader.

Stores one zlib-compressed float64 pair per sample for detailed plot views.
"""

import logging
import zlib
from dataclasses import dataclass
from typing import Optional

import numpy as np

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


def _compress_array(arr: np.ndarray) -> bytes:
    return zlib.compress(np.ascontiguousarray(arr, dtype=np.float64).tobytes())


def _decompress_array(blob: bytes) -> np.ndarray:
    return np.frombuffer(zlib.decompress(blob), dtype=np.float64).copy()


def _unmasked_pair(
    first: np.ndarray, second: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Return contiguous float64 arrays with any masked points dropped."""
    if np.ma.isMaskedArray(first) or np.ma.isMaskedArray(second):
        valid = (~np.ma.getmaskarray(first)) & (~np.ma.getmaskarray(second))
        first_arr = np.asarray(np.ma.getdata(first), dtype=np.float64)[valid]
        second_arr = np.asarray(np.ma.getdata(second), dtype=np.float64)[valid]
        return first_arr, second_arr
    return np.asarray(first, dtype=np.float64), np.asarray(second, dtype=np.float64)


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
                """
                SELECT time_blob, intensity_blob
                FROM tic_data
                WHERE sample_name = ? AND deleted = 0
                LIMIT 1
                """,
                (sample_name,),
            ).fetchone()

            if row is None:
                logger.warning(f"No TIC data found for sample: {sample_name}")
                return None

            times = _decompress_array(row["time_blob"])
            intensities = _decompress_array(row["intensity_blob"])
            if times.size == 0:
                return None

            logger.debug(f"Loaded TIC data for {sample_name}: {len(times)} points")

            return TICData(
                sample_name=sample_name,
                time=times,
                intensity=intensities,
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
            row = conn.execute(
                """
                SELECT 1
                FROM tic_data
                WHERE sample_name = ? AND deleted = 0
                LIMIT 1
                """,
                (sample_name,),
            ).fetchone()
            return row is not None

    except Exception as e:
        logger.error(f"Failed to check TIC data existence for {sample_name}: {e}")
        return False


def _store_tic_data_with_conn(conn, sample_name: str, times: np.ndarray, intensities: np.ndarray):
    """Helper function to store TIC data with an existing connection."""
    clean_times, clean_intensities = _unmasked_pair(times, intensities)
    if clean_times.size == 0:
        conn.execute("DELETE FROM tic_data WHERE sample_name = ?", (sample_name,))
        return

    if clean_times.size > 1 and np.any(clean_times[1:] < clean_times[:-1]):
        order = np.argsort(clean_times)
        clean_times = clean_times[order]
        clean_intensities = clean_intensities[order]

    conn.execute(
        """
        INSERT OR REPLACE INTO tic_data (sample_name, time_blob, intensity_blob, deleted)
        VALUES (?, ?, ?, 0)
        """,
        (sample_name, _compress_array(clean_times), _compress_array(clean_intensities)),
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
            _store_tic_data_with_conn(conn, sample_name, times, intensities)
        else:
            with get_connection() as new_conn:
                _store_tic_data_with_conn(new_conn, sample_name, times, intensities)

        return True

    except Exception as e:
        logger.error(f"Failed to store TIC data for {sample_name}: {e}")
        return False
