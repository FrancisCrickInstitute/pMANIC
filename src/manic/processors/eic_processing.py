from typing import Iterable, List

from manic.io.eic_reader import EIC, read_eic


def get_eics_for_compound(
    compound: str,
    samples: Iterable[str],
    normalise: bool = False,
) -> List[EIC]:
    """
    Return one EIC per sample for *compound*.

    normalise=True scales every trace to its own max so shapes can
    be compared even when absolute intensity differs.
    """
    eics = []
    for sample in samples:
        eic = read_eic(sample, compound)
        if normalise:
            max_i = eic.intensity.max() or 1
            eic.intensity = eic.intensity / max_i
        eics.append(eic)
    return eics
