import logging
from typing import Iterable, List

from manic.io.compound_reader import read_compound
from manic.io.eic_reader import EIC, read_eics_batch

logger = logging.getLogger(__name__)


def get_eics_for_compound(
    compound: str,
    samples: Iterable[str],
    normalise: bool = False,
    use_corrected: bool = False,
) -> List[EIC]:
    """
    Retrieve Extracted Ion Chromatogram (EIC) data for a compound across multiple samples.
    
    This function uses batch database queries to efficiently fetch EIC data for all samples
    in a single database operation, significantly reducing query overhead compared to 
    individual sample requests.
    
    Args:
        compound: The compound name to retrieve EICs for
        samples: Collection of sample names to process
        normalise: When True, scales each trace to its maximum intensity for shape comparison
        use_corrected: When True, retrieves natural abundance corrected data; False for raw data
        
    Returns:
        List of EIC objects, one per sample, containing time and intensity arrays
    """
    samples_list = list(samples)
    if not samples_list:
        return []
    
    compound_obj = read_compound(compound)
    
    # Use batch reading for improved performance with multiple samples
    eics = read_eics_batch(samples_list, compound_obj, use_corrected=use_corrected)
    
    # Apply normalization if requested - scales each EIC to its maximum intensity
    if normalise:
        for eic in eics:
            max_i = eic.intensity.max() or 1
            eic.intensity = eic.intensity / max_i
    
    return eics
