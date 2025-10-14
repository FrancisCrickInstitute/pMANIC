"""
Data processing tests for MANIC.
Combines tests for EIC extraction, processing, correction management,
and data flow through the application.
"""

import zlib
import numpy as np
from types import SimpleNamespace

from manic.io.cdf_reader import CdfFileData
from manic.processors.eic_calculator import extract_eic
from manic.processors.eic_correction_manager import _process_compound_batch_corrections
import manic.processors.eic_processing as eic_processing


# ============================================================================
# EIC EXTRACTION AND CALCULATION TESTS
# ============================================================================

def make_cdf(sample_name="S1"):
    """Helper function to create a mock CDF file data structure."""
    # Three scans, each with 3 masses (target, +1, +2)
    scan_time = np.array([60.0, 70.0, 80.0])  # seconds
    mass = np.array([
        100.0, 101.0, 102.0,  # scan 0
        100.0, 101.0, 102.0,  # scan 1
        100.0, 101.0, 102.0,  # scan 2
    ])
    # Intensities per mass per scan: simple increasing pattern
    intensity = np.array([
        10.0, 4.0, 2.0,   # scan 0
        20.0, 8.0, 4.0,   # scan 1
        30.0, 12.0, 6.0,  # scan 2
    ])
    scan_index = np.array([0, 3, 6])
    point_count = np.array([3, 3, 3])
    total_intensity = np.array([16.0, 32.0, 48.0])
    return CdfFileData(
        sample_name=sample_name,
        file_path=f"/fake/{sample_name}.cdf",
        scan_time=scan_time,
        mass=mass,
        intensity=intensity,
        scan_index=scan_index,
        point_count=point_count,
        total_intensity=total_intensity,
    )


def test_extract_eic_labeled_three_isotopologues():
    """Test EIC extraction for labeled compound with three isotopologues."""
    cdf = make_cdf()
    eic = extract_eic(
        compound_name="TestCmp",
        t_r=1.2,              # minutes (72 sec)
        target_mz=100.0,
        cdf=cdf,
        mass_tol=0.5,
        rt_window=0.5,        # includes all three scans
        label_atoms=2,        # M+0, M+1, M+2
    )

    # time returns minutes
    assert np.allclose(eic.time, cdf.scan_time / 60.0)
    # intensity is flattened 2D array: shape (3 isotopologues, 3 scans) raveled
    inten_2d = eic.intensity.reshape(3, -1)
    # sums per scan for each isotopologue should match our inputs at each scan
    # For our construction, summing within mass tol per scan is just the single point
    assert np.allclose(inten_2d[0], [10.0, 20.0, 30.0])  # M+0 @ 100.0
    assert np.allclose(inten_2d[1], [4.0, 8.0, 12.0])   # M+1 @ 101.0
    assert np.allclose(inten_2d[2], [2.0, 4.0, 6.0])    # M+2 @ 102.0


# ============================================================================
# EIC PROCESSING TESTS
# ============================================================================

def test_get_eics_for_compound_normalise(monkeypatch):
    """Test EIC normalization during batch processing."""
    # Stub read_compound to return an object with needed fields
    monkeypatch.setattr(
        eic_processing, 'read_compound', lambda name: SimpleNamespace(compound_name=name, label_atoms=0)
    )

    # Build two EICs with different max intensity
    def fake_read_eics_batch(samples, compound_obj, use_corrected):
        from manic.io.eic_reader import EIC
        return [
            EIC(samples[0], compound_obj.compound_name, np.array([0, 1]), np.array([1.0, 2.0])),
            EIC(samples[1], compound_obj.compound_name, np.array([0, 1]), np.array([5.0, 10.0])),
        ]

    monkeypatch.setattr(eic_processing, 'read_eics_batch', fake_read_eics_batch)

    eics = eic_processing.get_eics_for_compound('Test', ['A', 'B'], normalise=True, use_corrected=False)
    assert len(eics) == 2
    # Both should be scaled so max is 1.0
    assert eics[0].intensity.max() == 1.0
    assert eics[1].intensity.max() == 1.0


# ============================================================================
# EIC CORRECTION MANAGER TESTS
# ============================================================================

class FakeConn:
    """Mock database connection for testing."""
    def __init__(self, eic_rows):
        self._eic_rows = eic_rows
        self.written = None

    def execute(self, sql, params=()):
        class Cur:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        sql_l = sql.lower().strip()
        if sql_l.startswith("select e.sample_name"):
            return Cur(self._eic_rows)
        return Cur([])

    def executemany(self, sql, batch):
        self.written = list(batch)


def test_process_compound_batch_corrections_internal_standard_copy():
    """Test processing corrections for internal standard (unlabeled compound)."""
    # Build one EIC row: internal standard (label_atoms=0), 1D intensity
    time = np.linspace(0, 1, 5)
    inten = np.array([1, 2, 3, 4, 5], dtype=np.float64)
    row = {
        'sample_name': 'S1',
        'x_axis': zlib.compress(time.tobytes()),
        'y_axis': zlib.compress(inten.tobytes()),
    }

    conn = FakeConn([row])
    compound_row = {
        'label_atoms': 0,
        'formula': 'C6H12O6',
        'label_type': 'C',
        'tbdms': 0,
        'meox': 0,
        'me': 0,
    }

    # Fake corrector that returns slightly modified data
    def fake_correct(ts, formula, label_type, label_atoms, tbdms, meox, me):
        # For unlabeled compounds, return with small modification
        return ts * 1.084  # About 8.4% increase as observed

    fake_corrector = SimpleNamespace(correct_time_series=fake_correct)

    res = _process_compound_batch_corrections('ISTD', compound_row, fake_corrector, conn)
    assert res['successful'] == 1
    assert conn.written is not None
    # Written payload should include the compressed arrays; check lengths
    (_, _, x_blob, y_blob, *_rest) = conn.written[0]
    assert len(zlib.decompress(x_blob)) == len(time.tobytes())
    # Corrected data should be slightly different
    corrected = np.frombuffer(zlib.decompress(y_blob), dtype=np.float64)
    np.testing.assert_array_almost_equal(corrected, inten * 1.084, decimal=2)


def test_process_compound_batch_corrections_labeled_uses_corrector():
    """Test processing corrections for labeled compound uses corrector."""
    # Build one labeled EIC: 2 isotopologues × 5 timepoints => flattened size 10
    time = np.linspace(0, 1, 5)
    inten2d = np.vstack([np.arange(5), np.arange(5)])
    flat = inten2d.ravel().astype(np.float64)
    row = {
        'sample_name': 'S1',
        'x_axis': zlib.compress(time.tobytes()),
        'y_axis': zlib.compress(flat.tobytes()),
    }

    conn = FakeConn([row])
    compound_row = {
        'label_atoms': 1,  # 2 isotopologues
        'formula': 'C1H4',
        'label_type': 'C',
        'tbdms': 0,
        'meox': 0,
        'me': 0,
    }

    called = {}

    def fake_correct(ts, formula, label_type, label_atoms, tbdms, meox, me):
        called['args'] = (formula, label_type, label_atoms)
        # Return same shape, scaled by 2 for easy detection
        return ts * 2.0

    fake_corrector = SimpleNamespace(correct_time_series=fake_correct)

    res = _process_compound_batch_corrections('CMP', compound_row, fake_corrector, conn)
    assert res['successful'] == 1
    assert called['args'] == ('C1H4', 'C', 1)
    # Check written intensity doubles original when decompressed
    (_, _, _xb, yb, *_rest) = conn.written[0]
    out = np.frombuffer(zlib.decompress(yb), dtype=np.float64)
    assert np.allclose(out, flat * 2.0)