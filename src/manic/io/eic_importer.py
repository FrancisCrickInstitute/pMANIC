import logging
import time
import zlib
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from manic.io.cdf_reader import read_cdf_file
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

        logger.info("processed %s", cdf_path.name)

    elapsed = time.time() - start
    logger.info("imported %d EICs in %.1f s", inserted, elapsed)
    return inserted
