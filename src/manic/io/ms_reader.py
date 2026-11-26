"""
Mass Spectrum (MS) data reader.

Stores one zlib-compressed float64 pair per (sample, scan time) for detailed plot views.
"""

import logging
import zlib
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

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


def _compress_array(arr: np.ndarray) -> bytes:
    return zlib.compress(np.ascontiguousarray(arr, dtype=np.float64).tobytes())


def _decompress_array(blob: bytes) -> np.ndarray:
    return np.frombuffer(zlib.decompress(blob), dtype=np.float64).copy()


def _prepare_spectrum(
    mz_values: np.ndarray, intensities: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Drop masked or non-positive peaks and sort by m/z ascending."""
    if np.ma.isMaskedArray(mz_values) or np.ma.isMaskedArray(intensities):
        valid = (~np.ma.getmaskarray(mz_values)) & (~np.ma.getmaskarray(intensities))
        mz_arr = np.asarray(np.ma.getdata(mz_values), dtype=np.float64)[valid]
        int_arr = np.asarray(np.ma.getdata(intensities), dtype=np.float64)[valid]
    else:
        mz_arr = np.asarray(mz_values, dtype=np.float64)
        int_arr = np.asarray(intensities, dtype=np.float64)

    positive = int_arr > 0
    if not np.all(positive):
        mz_arr = mz_arr[positive]
        int_arr = int_arr[positive]

    if mz_arr.size > 1 and np.any(mz_arr[1:] < mz_arr[:-1]):
        order = np.argsort(mz_arr)
        mz_arr = mz_arr[order]
        int_arr = int_arr[order]

    return mz_arr, int_arr


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
            row = conn.execute(
                """
                SELECT time, mz_blob, intensity_blob
                FROM ms_data
                WHERE sample_name = ?
                  AND time BETWEEN ? AND ?
                  AND deleted = 0
                ORDER BY ABS(time - ?) ASC, time ASC
                LIMIT 1
                """,
                (sample_name, time_min, time_max, retention_time),
            ).fetchone()

            if row is None:
                logger.warning(
                    f"No MS data found for sample: {sample_name} at time {retention_time:.3f}"
                )
                return None

            mz_values = _decompress_array(row["mz_blob"])
            intensities = _decompress_array(row["intensity_blob"])
            if mz_values.size == 0:
                return None

            best_time = float(row["time"])
            logger.debug(
                f"Loaded MS data for {sample_name} at time {best_time:.3f}: {len(mz_values)} peaks"
            )

            return MSData(
                sample_name=sample_name,
                time=best_time,
                mz=mz_values,
                intensity=intensities,
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
            rows = conn.execute(
                """
                SELECT time
                FROM ms_data
                WHERE sample_name = ? AND deleted = 0
                ORDER BY time
                """,
                (sample_name,),
            ).fetchall()
            return [float(row["time"]) for row in rows]

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
                row = conn.execute(
                    """
                    SELECT 1
                    FROM ms_data
                    WHERE sample_name = ? AND time = ? AND deleted = 0
                    LIMIT 1
                    """,
                    (sample_name, retention_time),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT 1
                    FROM ms_data
                    WHERE sample_name = ? AND deleted = 0
                    LIMIT 1
                    """,
                    (sample_name,),
                ).fetchone()

            return row is not None

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

        clean_mz, clean_int = _prepare_spectrum(mz_values, intensities)
        time_val = float(time)
        with get_connection() as conn:
            if clean_mz.size == 0:
                conn.execute(
                    "DELETE FROM ms_data WHERE sample_name = ? AND time = ?",
                    (sample_name, time_val),
                )
                return True

            conn.execute(
                """
                INSERT OR REPLACE INTO ms_data (sample_name, time, mz_blob, intensity_blob, deleted)
                VALUES (?, ?, ?, ?, 0)
                """,
                (sample_name, time_val, _compress_array(clean_mz), _compress_array(clean_int)),
            )
            logger.debug(
                f"Stored MS data for {sample_name} at time {time_val:.3f}: {len(clean_mz)} peaks"
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
            _store_ms_data_batch_with_conn(conn, sample_name, ms_data_points)
        else:
            with get_connection() as new_conn:
                _store_ms_data_batch_with_conn(new_conn, sample_name, ms_data_points)

        return True

    except Exception as e:
        logger.error(f"Failed to store MS batch data for {sample_name}: {e}")
        return False


def _store_ms_data_batch_with_conn(conn, sample_name: str, ms_data_points: List[tuple]):
    """Store one compressed row per distinct scan time for ``sample_name``."""
    conn.execute("DELETE FROM ms_data WHERE sample_name = ?", (sample_name,))

    rows_by_time: dict[float, tuple[str, float, bytes, bytes, int]] = {}
    for time_val, mz_values, intensities in ms_data_points:
        if len(mz_values) != len(intensities):
            logger.warning(f"Skipping MS data at time {time_val}: array length mismatch")
            continue
        t = float(time_val)
        if t in rows_by_time:
            continue
        clean_mz, clean_int = _prepare_spectrum(mz_values, intensities)
        if clean_mz.size > 0:
            rows_by_time[t] = (
                sample_name,
                t,
                _compress_array(clean_mz),
                _compress_array(clean_int),
                0,
            )

    if rows_by_time:
        conn.executemany(
            """
            INSERT OR REPLACE INTO ms_data (sample_name, time, mz_blob, intensity_blob, deleted)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows_by_time.values(),
        )
