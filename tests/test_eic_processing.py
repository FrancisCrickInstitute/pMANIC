import numpy as np

from types import SimpleNamespace

import manic.processors.eic_processing as eic_processing


def test_get_eics_for_compound_normalise(monkeypatch):
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

