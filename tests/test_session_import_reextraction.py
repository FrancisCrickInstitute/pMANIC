"""Importing a session re-extracts the EICs not centred on its tRs (issues 195 and 264)."""

import zlib

import numpy as np

from manic.io import eic_importer
from manic.models import database


def test_import_reextracts_only_samples_whose_tr_moved(monkeypatch):
    stored = zlib.compress((np.arange(480, 521) / 100).tobytes())
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, mass0, "
            "label_atoms) VALUES ('Cmp', 5.0, 0.1, 0.1, 100.0, 0)"
        )
        # One sample moved out of its EIC, one moved inside it, one kept its tR,
        # one unedited, one deleted.
        for sample, session_rt, deleted in (
            ("Moved", 5.5, 0),
            ("Nudged", 5.05, 0),
            ("Kept", 5.0, 0),
            ("Untouched", None, 0),
            ("Deleted", 5.5, 1),
        ):
            conn.execute(
                "INSERT INTO samples (sample_name, deleted) VALUES (?, ?)", (sample, deleted)
            )
            conn.execute(
                "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, rt_window) "
                "VALUES (?, 'Cmp', ?, ?, 0.2)",
                (sample, stored, stored),
            )
            if session_rt is not None:
                conn.execute(
                    "INSERT INTO session_activity (compound_name, sample_name, "
                    "retention_time, loffset, roffset) VALUES ('Cmp', ?, ?, 0.1, 0.1)",
                    (sample, session_rt),
                )
    calls = []
    monkeypatch.setattr(
        eic_importer,
        "regenerate_compound_eics",
        lambda compound, window, samples, mass_tol, retention_time: calls.append(
            (compound, window, samples, retention_time, mass_tol)
        ),
    )

    assert eic_importer.reextract_session_eics(0.3) == []
    assert calls == [
        ("Cmp", 0.2, ["Moved", "Nudged"], {"Moved": 5.5, "Nudged": 5.05}, 0.3)
    ]

    def missing_file(*_args, **_kwargs):
        raise ValueError("CDF file not found for sample 'Moved'")

    monkeypatch.setattr(eic_importer, "regenerate_compound_eics", missing_file)
    assert eic_importer.reextract_session_eics() == [
        "Cmp: CDF file not found for sample 'Moved'"
    ]
