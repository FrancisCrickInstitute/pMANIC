"""
On-demand CDF data extraction for TIC and MS data.

This module provides functions to extract TIC and MS data from CDF files
only when needed (e.g., when detailed view is opened), improving import performance.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

from manic.io.cdf_reader import read_cdf_file, CdfFileData
from manic.io.tic_reader import store_tic_data, read_tic
from manic.io.ms_reader import store_ms_data, read_ms_at_time
from manic.models.database import get_connection

logger = logging.getLogger(__name__)


def extract_tic_on_demand(sample_name: str) -> Optional['TICData']:
    """
    Extract TIC data on-demand for a sample.
    
    First checks if TIC data already exists in database. If not, loads the original
    CDF file and extracts TIC data, then stores it for future use.
    
    Args:
        sample_name: Name of the sample
        
    Returns:
        TICData object if successful, None otherwise
    """
    try:
        # First, try to load from database
        tic_data = read_tic(sample_name)
        if tic_data:
            logger.debug(f"Loaded existing TIC data for {sample_name}")
            return tic_data
        
        # If not in database, extract from original CDF file
        logger.info(f"Extracting TIC data on-demand for {sample_name}")
        
        # Get CDF file path from database
        cdf_path = _get_cdf_path_for_sample(sample_name)
        if not cdf_path:
            logger.warning(f"No CDF file path found for sample {sample_name}")
            return None
            
        # Load CDF file and extract TIC
        cdf_data = read_cdf_file(cdf_path)
        tic_times, tic_intensities = _extract_tic_from_cdf_data(cdf_data)
        
        if len(tic_times) == 0:
            logger.warning(f"No TIC data extracted for {sample_name}")
            return None
            
        # Store in database for future use
        if store_tic_data(sample_name, tic_times, tic_intensities):
            logger.info(f"Stored TIC data for {sample_name}: {len(tic_times)} points")
            # Return the newly extracted data
            return read_tic(sample_name)
        else:
            logger.error(f"Failed to store TIC data for {sample_name}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to extract TIC on-demand for {sample_name}: {e}")
        return None


def extract_ms_on_demand(sample_name: str, retention_time: float, tolerance: float = 0.1) -> Optional['MSData']:
    """
    Extract MS data on-demand for a sample at specific retention time.
    
    First checks if MS data already exists in database. If not, loads the original
    CDF file and extracts MS data at the specified retention time.
    
    Args:
        sample_name: Name of the sample
        retention_time: Target retention time (minutes)
        tolerance: Time tolerance window (minutes)
        
    Returns:
        MSData object if successful, None otherwise
    """
    try:
        # First, try to load from database
        ms_data = read_ms_at_time(sample_name, retention_time, tolerance)
        if ms_data:
            logger.debug(f"Loaded existing MS data for {sample_name} at {retention_time:.3f} min")
            return ms_data
            
        # If not in database, extract from original CDF file
        logger.info(f"Extracting MS data on-demand for {sample_name} at {retention_time:.3f} min")
        
        # Get CDF file path from database
        cdf_path = _get_cdf_path_for_sample(sample_name)
        if not cdf_path:
            logger.warning(f"No CDF file path found for sample {sample_name}")
            return None
            
        # Load CDF file and extract MS at retention time
        cdf_data = read_cdf_file(cdf_path)
        mz_values, intensities, actual_time = _extract_ms_at_time_from_cdf_data(
            cdf_data, retention_time, tolerance
        )
        
        if len(mz_values) == 0:
            logger.warning(f"No MS data extracted for {sample_name} at {retention_time:.3f} min")
            return None
            
        # Store in database for future use
        if store_ms_data(sample_name, actual_time, mz_values, intensities):
            logger.info(f"Stored MS data for {sample_name} at {actual_time:.3f} min: {len(mz_values)} peaks")
            # Return the newly extracted data
            return read_ms_at_time(sample_name, retention_time, tolerance)
        else:
            logger.error(f"Failed to store MS data for {sample_name}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to extract MS on-demand for {sample_name} at {retention_time:.3f}: {e}")
        return None


def _get_cdf_path_for_sample(sample_name: str) -> Optional[str]:
    """Get the CDF file path for a sample from the database."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT file_name 
                FROM samples 
                WHERE sample_name = ? AND deleted = 0
            """, (sample_name,))
            
            row = cursor.fetchone()
            if row:
                file_path = row['file_name']
                # Verify file still exists
                if Path(file_path).exists():
                    return file_path
                else:
                    logger.warning(f"CDF file not found at {file_path}")
                    return None
            else:
                logger.warning(f"Sample {sample_name} not found in database")
                return None
                
    except Exception as e:
        logger.error(f"Failed to get CDF path for {sample_name}: {e}")
        return None


def _extract_tic_from_cdf_data(cdf_data: CdfFileData) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract Total Ion Chromatogram from CDF data.
    
    Uses the total_intensity field which is already calculated in the CDF file.
    """
    try:
        # CDF files typically have total_intensity already calculated
        times = cdf_data.scan_time
        intensities = cdf_data.total_intensity
        
        return times, intensities
        
    except Exception as e:
        logger.error(f"Failed to extract TIC from CDF data: {e}")
        return np.array([]), np.array([])


def _extract_ms_at_time_from_cdf_data(cdf_data: CdfFileData, target_time: float, 
                                     tolerance: float = 0.1) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Extract mass spectrum at specific retention time from CDF data.
    
    Returns:
        Tuple of (mz_values, intensities, actual_time)
    """
    try:
        # Find the scan closest to target time
        time_diffs = np.abs(cdf_data.scan_time - target_time)
        
        if np.min(time_diffs) > tolerance:
            # No scan within tolerance
            return np.array([]), np.array([]), target_time
            
        # Get the closest scan
        closest_scan_idx = np.argmin(time_diffs)
        actual_time = cdf_data.scan_time[closest_scan_idx]
        
        # Extract mass spectrum for this scan
        # scan_index tells us where each scan starts in the mass/intensity arrays
        scan_start = cdf_data.scan_index[closest_scan_idx]
        point_count = cdf_data.point_count[closest_scan_idx]
        scan_end = scan_start + point_count
        
        # Extract m/z and intensity values for this scan
        mz_values = cdf_data.mass[scan_start:scan_end]
        intensities = cdf_data.intensity[scan_start:scan_end]
        
        # Filter out zero intensities to save space
        nonzero_mask = intensities > 0
        mz_values = mz_values[nonzero_mask]
        intensities = intensities[nonzero_mask]
        
        return mz_values, intensities, actual_time
        
    except Exception as e:
        logger.error(f"Failed to extract MS at time {target_time}: {e}")
        return np.array([]), np.array([]), target_time


def check_cdf_availability(sample_name: str) -> bool:
    """
    Check if the original CDF file is available for on-demand extraction.
    
    Args:
        sample_name: Name of the sample
        
    Returns:
        True if CDF file is available, False otherwise
    """
    cdf_path = _get_cdf_path_for_sample(sample_name)
    return cdf_path is not None