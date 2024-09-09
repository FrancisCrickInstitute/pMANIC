import numpy as np
from src.manic.models import (
    CdfDirectory,
    CdfFileData,
    CompoundData,
    ExtractedIonChromatogramData,
)


def load_eic_data(
    compound: CompoundData,
    cdf_data: CdfFileData,
    mass_tolerance: float = 0.25,
    retention_time_window: float = 0.2,
) -> ExtractedIonChromatogramData:
    """Load extracted ion chromatogram (EIC) data for a given compound from a CDF file."""

    scan_index = cdf_data.scan_index
    mass_values = cdf_data.mass_values
    intensity_values = cdf_data.intensity_values

    # convert time to minutes
    eic_time = cdf_data.scan_acquisition_time / 60.0

    # filter out data within the retention time retention time window
    time_mask = (eic_time >= (compound.tR - retention_time_window)) & (
        eic_time <= (compound.tR + retention_time_window)
    )
    filtered_indices = np.where(time_mask)[0]
    if len(filtered_indices) == 0:
        raise ValueError("No data within the retention time window.")

    # Get the index of the first mass value in each scan
    start_indices = scan_index[filtered_indices]
    # Get the index of the last mass value in each scan (same a first index of next scan)
    # Append the length of the mass values to the end of the array as there is no next scan
    end_indices = np.append(scan_index[filtered_indices[1:]], len(mass_values))

    # Create a mask for the mass range
    mass_mask = (mass_values >= compound.Mass0 - mass_tolerance) & (
        mass_values <= compound.Mass0 + mass_tolerance
    )

    # Initialize eic_intensity array
    eic_intensity = np.zeros(len(filtered_indices))

    # Use numpy's add.reduceat for efficient summation
    for i, (start, end) in enumerate(zip(start_indices, end_indices)):
        eic_intensity[i] = np.add.reduceat(
            intensity_values[start:end][mass_mask[start:end]], [0]
        )[0]

    # Create EIC object
    eic_data = ExtractedIonChromatogramData(
        compound.name, cdf_data.filename, eic_time[time_mask], eic_intensity
    )

    return eic_data
