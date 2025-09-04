import logging
from typing import Iterable, List

from manic.io.compound_reader import read_compound
from manic.io.eic_reader import EIC, read_eic

logger = logging.getLogger(__name__)


def get_eics_for_compound(
    compound: str,
    samples: Iterable[str],
    normalise: bool = False,
    use_corrected: bool = False,
) -> List[EIC]:
    """
    Return one EIC per sample for *compound*.

    normalise=True scales every trace to its own max so shapes can
    be compared even when absolute intensity differs.
    use_corrected=True reads from the natural abundance corrected data.
    """
    # EIC retrieval - logging removed to reduce noise
    eics = []
    compound_obj = read_compound(compound)
    for sample in samples:
        eic = read_eic(sample, compound_obj, use_corrected=use_corrected)
        if normalise:
            max_i = eic.intensity.max() or 1
            eic.intensity = eic.intensity / max_i
        eics.append(eic)
    return eics
