import logging
import time
import zlib
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from manic.io.cdf_reader import read_cdf_file
from manic.io.compound_reader import read_compound
from manic.models.database import get_connection
from manic.processors.eic_calculator import extract_eic
from manic.io.tic_reader import store_tic_data
from manic.io.ms_reader import store_ms_data_batch

logger = logging.getLogger(__name__)


# ─────────────────────────── Utility Functions ────────────────────────────
def _compress(arr: np.ndarray) -> bytes:
    """Compress numpy array to optimized byte stream for database storage.
    
    Args:
        arr: Input numpy array to compress
        
    Returns:
        Zlib-compressed bytes in float64 format
    """
    return zlib.compress(arr.astype(np.float64).tobytes())


def _iter_compounds(conn):
    """Iterate over active compounds in the database.
    
    Args:
        conn: Database connection object
        
    Yields:
        Tuple of (compound_name, retention_time, mass0, label_atoms)
    """
    for row in conn.execute(
        "SELECT compound_name, retention_time, mass0, label_atoms "
        "FROM   compounds "
        "WHERE  deleted = 0"
    ):
        yield row["compound_name"], row["retention_time"], row["mass0"], row["label_atoms"]


def _extract_tic_from_cdf(cdf):
    """
    Extract Total Ion Chromatogram from CDF data.
    
    Args:
        cdf: CdfFileData object
        
    Returns:
        tuple: (time_array, intensity_array)
    """
    try:
        # Extract time array and convert from seconds to minutes for consistency
        times = cdf.scan_time / 60.0
        intensities = cdf.total_intensity
        return times, intensities
        
    except Exception as e:
        logger.error(f"Failed to extract TIC from CDF: {e}")
        return np.array([]), np.array([])


def _extract_ms_at_retention_times(cdf, retention_times, tolerance=0.1):
    """
    Extract mass spectra at specific retention times.
    
    Args:
        cdf: CdfFileData object
        retention_times: List of retention times to extract MS at (in minutes)
        tolerance: Time tolerance window (minutes)
        
    Returns:
        List of (time, mz_array, intensity_array) tuples
    """
    try:
        ms_data_points = []
        
        # Normalize scan times to minutes for retention time matching
        scan_times_minutes = cdf.scan_time / 60.0
        
        for rt in retention_times:
            # Identify scan index nearest to target retention time
            time_diffs = np.abs(scan_times_minutes - rt)
            
            if np.min(time_diffs) > tolerance:
                # Skip if no scan falls within tolerance window
                continue
                
            # Select scan with minimum time difference
            closest_scan_idx = np.argmin(time_diffs)
            actual_time = scan_times_minutes[closest_scan_idx]
            
            # Extract mass spectrum data using scan index boundaries
            scan_start = cdf.scan_index[closest_scan_idx]
            point_count = cdf.point_count[closest_scan_idx]
            scan_end = scan_start + point_count
            
            # Retrieve m/z and intensity arrays for current scan
            mz_values = cdf.mass[scan_start:scan_end]
            intensities = cdf.intensity[scan_start:scan_end]
            
            # Remove zero-intensity peaks for storage optimization
            nonzero_mask = intensities > 0
            if np.any(nonzero_mask):
                ms_data_points.append((
                    actual_time,
                    mz_values[nonzero_mask],
                    intensities[nonzero_mask]
                ))
        
        return ms_data_points
        
    except Exception as e:
        logger.error(f"Failed to extract MS data: {e}")
        return []


# ─────────────────────── Public API Functions ─────────────────
def import_eics(
    directory: str | Path,
    mass_tol: float = 0.25,
    rt_window: float = 0.2,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> int:
    """
    Scan *directory* for .cdf / .CDF files, compute an extracted-ion
    chromatogram for every compound × file pair and insert the result
    into the *samples* and *eic* tables.

    Parameters
    ----------
    directory : str | Path
        Folder that contains the CDF files.
    mass_tol : float
        ± m/z tolerance used during extraction (Da).
    rt_window : float
        Half-window applied around each compound’s retention time (min).
    progress_cb : Callable[[done, total], None] | None
        Optional callback for GUI progress bars.

    Returns
    -------
    int
        Number of EIC rows inserted.
    """
    start = time.time()
    directory = Path(directory).expanduser()

    # Discover all CDF files in directory (case-insensitive matching)
    cdf_files = [p for p in directory.iterdir() if p.suffix.lower() == ".cdf"]
    if not cdf_files:
        raise FileNotFoundError("No .CDF files found in the selected directory.")

    # Retrieve all active compounds for processing
    with get_connection() as conn:
        compounds = list(_iter_compounds(conn))
    if not compounds:
        raise RuntimeError("Compounds table is empty.")

    # Count compounds that will need correction
    corrections_needed = 0
    with get_connection() as conn:
        # Get formula info for compounds that need correction
        correction_sql = """
            SELECT COUNT(DISTINCT compound_name) as count
            FROM compounds
            WHERE deleted = 0
            AND formula IS NOT NULL
            AND label_atoms > 0
        """
        result = conn.execute(correction_sql).fetchone()
        correction_compounds = result["count"] if result else 0
        corrections_needed = correction_compounds * len(cdf_files)

    total_work = len(cdf_files) * len(compounds) + corrections_needed
    done = 0
    inserted = 0
    tic_count = 0
    ms_count = 0
    total_ms_peaks = 0

    # Process each CDF file sequentially
    for cdf_path in cdf_files:
        cdf = read_cdf_file(cdf_path)

        with get_connection() as conn:
            # Create or verify sample record (idempotent operation)
            conn.execute(
                "INSERT OR IGNORE INTO samples "
                "(sample_name, file_name, deleted) VALUES (?,?,0)",
                (cdf.sample_name, str(cdf_path)),
            )

            # Process Total Ion Chromatogram data
            tic_times, tic_intensities = _extract_tic_from_cdf(cdf)
            if len(tic_times) > 0:
                if store_tic_data(cdf.sample_name, tic_times, tic_intensities, conn):
                    tic_count += 1
                else:
                    logger.warning(f"Failed to store TIC data for {cdf.sample_name}")
            
            # Process and store mass spectrum data for all retention times  
            compound_retention_times = [rt for name, rt, mz, label_atoms in compounds]
            ms_data_points = _extract_ms_at_retention_times(cdf, compound_retention_times)
            if ms_data_points:
                if store_ms_data_batch(cdf.sample_name, ms_data_points, conn):
                    ms_count += 1
                    total_ms_peaks += sum(len(mz_vals) for _, mz_vals, _ in ms_data_points)
                else:
                    logger.warning(f"Failed to store MS data for {cdf.sample_name}")

            for name, rt, mz, label_atoms in compounds:
                try:
                    eic = extract_eic(name, rt, mz, cdf, mass_tol, rt_window, label_atoms)
                except ValueError:
                    # Skip compounds with no data in specified RT/m/z window
                    done += 1
                    if progress_cb:
                        progress_cb(done, total_work)
                    continue

                # Persist extracted ion chromatogram to database
                conn.execute(
                    """
                    INSERT INTO eic (
                        sample_name, compound_name,
                        x_axis, y_axis,
                        rt_window, corrected, deleted,
                        spectrum_pos, chromat_pos
                    ) VALUES (?,?,?,?,?,0,0,NULL,NULL)
                    """,
                    (
                        eic.sample_name,
                        eic.compound_name,
                        _compress(eic.time),
                        _compress(eic.intensity),
                        rt_window,
                    ),
                )
                inserted += 1
                done += 1
                if progress_cb:
                    progress_cb(done, total_work)

        # logger.info("processed %s", cdf_path.name)

    # Report additional data storage statistics
    if tic_count > 0 or ms_count > 0:
        logger.info(f"Stored additional data: {tic_count} TIC chromatograms, {ms_count} MS spectra sets ({total_ms_peaks:,} total peaks)")
    
    # Automatically calculate natural abundance corrections
    if corrections_needed > 0:
        try:
            from manic.processors.eic_correction_manager import process_all_corrections
            
            # Create progress callback that continues from where EIC import left off
            def correction_progress(current, total):
                if progress_cb:
                    # Map correction progress to remaining work
                    correction_done = int((current / total) * corrections_needed)
                    progress_cb(done + correction_done, total_work)
            
            corrections_count = process_all_corrections(progress_cb=correction_progress)
        except Exception as e:
            logger.warning(f"Failed to calculate natural abundance corrections: {e}")
    
    elapsed = time.time() - start
    logger.info("imported %d EICs in %.1f s", inserted, elapsed)
    
    return inserted


def regenerate_compound_eics(
    compound_name: str,
    tr_window: float,
    sample_names: list,
    mass_tol: float = 0.25,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> int:
    """
    Regenerate EIC data for a specific compound across given samples with new tR window.
    
    This function deletes existing EIC records for the compound and recalculates them
    using the new tR window parameter. Session data is NOT touched.
    
    Parameters
    ----------
    compound_name : str
        Name of the compound to regenerate
    tr_window : float
        New half-window around retention time (min)
    sample_names : list
        List of sample names to regenerate
    mass_tol : float
        ± m/z tolerance used during extraction (Da)
    progress_cb : Callable[[done, total], None] | None
        Optional callback for GUI progress bars
        
    Returns
    -------
    int
        Number of EIC rows regenerated
    """
    start = time.time()
    
    logger.info(f"Starting regeneration for compound '{compound_name}' with tR window {tr_window}")
    
    # Get compound data (retention time, mass, label_atoms)
    try:
        compound_data = read_compound(compound_name)
        rt = compound_data.retention_time
        mz = compound_data.mass0
        label_atoms = compound_data.label_atoms
    except Exception as e:
        raise RuntimeError(f"Failed to read compound '{compound_name}': {e}")
    
    # Get sample file paths from database
    sample_files = {}
    with get_connection() as conn:
        for sample_name in sample_names:
            row = conn.execute(
                "SELECT file_name FROM samples WHERE sample_name = ? AND deleted = 0",
                (sample_name,)
            ).fetchone()
            if row:
                sample_files[sample_name] = Path(row["file_name"])
            else:
                logger.warning(f"Sample '{sample_name}' not found in database")
    
    if not sample_files:
        raise RuntimeError("No valid samples found for regeneration")
    
    total_work = len(sample_files)
    done = 0
    regenerated = 0
    
    # Delete existing EIC and corrected records for this compound
    with get_connection() as conn:
        # Delete raw EIC records
        delete_result = conn.execute(
            "DELETE FROM eic WHERE compound_name = ? AND sample_name IN ({})".format(
                ','.join('?' * len(sample_names))
            ),
            [compound_name] + sample_names
        )
        deleted_count = delete_result.rowcount
        logger.info(f"Deleted {deleted_count} existing EIC records for '{compound_name}'")
        
        # Also delete corrected EIC records
        delete_corrected_result = conn.execute(
            "DELETE FROM eic_corrected WHERE compound_name = ? AND sample_name IN ({})".format(
                ','.join('?' * len(sample_names))
            ),
            [compound_name] + sample_names
        )
        deleted_corrected_count = delete_corrected_result.rowcount
        if deleted_corrected_count > 0:
            logger.info(f"Deleted {deleted_corrected_count} existing corrected EIC records for '{compound_name}'")
    
    # Regenerate EICs for each sample
    for sample_name, cdf_path in sample_files.items():
        try:
            # Check if CDF file exists
            if not cdf_path.exists():
                logger.warning(f"CDF file not found: {cdf_path}")
                done += 1
                if progress_cb:
                    progress_cb(done, total_work)
                continue
            
            # Read CDF file and extract EIC
            cdf = read_cdf_file(cdf_path)
            eic = extract_eic(compound_name, rt, mz, cdf, mass_tol, tr_window, label_atoms)
            
            # Insert new EIC record
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO eic (
                        sample_name, compound_name,
                        x_axis, y_axis,
                        rt_window, corrected, deleted,
                        spectrum_pos, chromat_pos
                    ) VALUES (?,?,?,?,?,0,0,NULL,NULL)
                    """,
                    (
                        eic.sample_name,
                        eic.compound_name,
                        _compress(eic.time),
                        _compress(eic.intensity),
                        tr_window,
                    ),
                )
            
            regenerated += 1
            logger.debug(f"Regenerated EIC for '{compound_name}' in sample '{sample_name}' - time range: {eic.time.min():.3f} to {eic.time.max():.3f} min")
            
        except ValueError as e:
            logger.warning(f"No data in RT/m/z window for '{compound_name}' in '{sample_name}': {e}")
        except Exception as e:
            logger.error(f"Failed to regenerate EIC for '{compound_name}' in '{sample_name}': {e}")
            
        done += 1
        if progress_cb:
            progress_cb(done, total_work)
    
    elapsed = time.time() - start
    logger.info(f"Regenerated {regenerated} EICs for '{compound_name}' in {elapsed:.1f} s")
    
    # Recalculate natural abundance corrections for this compound
    try:
        from manic.processors.eic_correction_manager import apply_correction_to_eic
        logger.info(f"Recalculating natural abundance corrections for '{compound_name}'...")
        corrections_count = 0
        for sample_name in sample_names:
            if apply_correction_to_eic(sample_name, compound_name):
                corrections_count += 1
        if corrections_count > 0:
            logger.info(f"Successfully recalculated {corrections_count} corrections for '{compound_name}'")
    except Exception as e:
        logger.warning(f"Failed to recalculate corrections for '{compound_name}': {e}")
    
    return regenerated
