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

logger = logging.getLogger(__name__)


# ─────────────────────────── helpers ────────────────────────────
def _compress(arr: np.ndarray) -> bytes:
    """Return a zlib-compressed `float64` byte stream."""
    return zlib.compress(arr.astype(np.float64).tobytes())


def _iter_compounds(conn):
    """Yield `(compound_name, rt, mass0)` rows that are not deleted."""
    for row in conn.execute(
        "SELECT compound_name, retention_time, mass0 "
        "FROM   compounds "
        "WHERE  deleted = 0"
    ):
        yield row["compound_name"], row["retention_time"], row["mass0"]


# ─────────────────────── public import function ─────────────────
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

    # discover CDF files (case-insensitive)
    cdf_files = [p for p in directory.iterdir() if p.suffix.lower() == ".cdf"]
    if not cdf_files:
        raise FileNotFoundError("No .CDF files found in the selected directory.")

    # fetch all active compounds once
    with get_connection() as conn:
        compounds = list(_iter_compounds(conn))
    if not compounds:
        raise RuntimeError("Compounds table is empty.")

    total_work = len(cdf_files) * len(compounds)
    done = 0
    inserted = 0

    # process each file
    for cdf_path in cdf_files:
        cdf = read_cdf_file(cdf_path)

        with get_connection() as conn:
            # ensure the sample exists (idempotent)
            conn.execute(
                "INSERT OR IGNORE INTO samples "
                "(sample_name, file_name, deleted) VALUES (?,?,0)",
                (cdf.sample_name, str(cdf_path)),
            )

            for name, rt, mz in compounds:
                try:
                    eic = extract_eic(name, rt, mz, cdf, mass_tol, rt_window)
                except ValueError:
                    # no data in the RT / m/z window
                    done += 1
                    if progress_cb:
                        progress_cb(done, total_work)
                    continue

                # store the chromatogram
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
    
    # Get compound data (retention time, mass)
    try:
        compound_data = read_compound(compound_name)
        rt = compound_data.retention_time
        mz = compound_data.mass0
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
    
    # Delete existing EIC records for this compound
    with get_connection() as conn:
        delete_result = conn.execute(
            "DELETE FROM eic WHERE compound_name = ? AND sample_name IN ({})".format(
                ','.join('?' * len(sample_names))
            ),
            [compound_name] + sample_names
        )
        deleted_count = delete_result.rowcount
        logger.info(f"Deleted {deleted_count} existing EIC records for '{compound_name}'")
    
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
            eic = extract_eic(compound_name, rt, mz, cdf, mass_tol, tr_window)
            
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
    return regenerated
