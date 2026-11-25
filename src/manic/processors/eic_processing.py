import logging
from typing import Iterable, List

from manic.io.compound_reader import read_compound
from manic.io.eic_reader import EIC, read_eics_batch

logger = logging.getLogger(__name__)


def get_eics_for_compound(
    compound: str,
    samples: Iterable[str],
    normalise: bool = False,
) -> List[EIC]:
    """Retrieve raw Extracted Ion Chromatogram (EIC) data for a compound across samples."""
    samples_list = list(samples)
    if not samples_list:
        return []

    compound_obj = read_compound(compound)
    eics = read_eics_batch(samples_list, compound_obj)

    if normalise:
        for eic in eics:
            max_i = eic.intensity.max() or 1
            eic.intensity = eic.intensity / max_i

    return eics
