import zlib
import numpy as np

from types import SimpleNamespace

from manic.processors.eic_correction_manager import _process_compound_batch_corrections


class FakeConn:
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

    # Fake corrector (won't be used for label_atoms=0)
    fake_corrector = SimpleNamespace(correct_time_series=lambda *args, **kwargs: None)

    res = _process_compound_batch_corrections('ISTD', compound_row, fake_corrector, conn)
    assert res['successful'] == 1
    assert conn.written is not None
    # Written payload should include the compressed arrays; check lengths
    (_, _, x_blob, y_blob, *_rest) = conn.written[0]
    assert len(zlib.decompress(x_blob)) == len(time.tobytes())
    assert len(zlib.decompress(y_blob)) == len(inten.tobytes())


def test_process_compound_batch_corrections_labeled_uses_corrector():
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

