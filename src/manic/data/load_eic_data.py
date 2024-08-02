import numpy as np


def load_eic_data(
    filename: str,
    compound: str,
    cdf_data: dict,
    compound_data: dict,
    mass_tolerance: float = 0.25,
) -> tuple[np.ndarray, np.ndarray]:
    """Load extracted ion chromatogram (EIC) data for a given compound from a CDF file."""
    selected_cdf_data = cdf_data[filename]
    selected_compound = compound_data[compound]
    scan_acquisition_time = selected_cdf_data["scan_acquisition_time"]
    retention_time = selected_compound["tR"]
    target_mass = selected_compound["mass"]
    mass_values = selected_cdf_data["mass_values"]
    intensity_values = selected_cdf_data["intensity_values"]
    scan_index = selected_cdf_data["scan_index"]

    # Convert to minutes, and filter data within retention time window
    retention_time_window = 0.2  # 0.2 minutes on each side
    eic_time = scan_acquisition_time / 60.0  # Convert to minutes
    time_mask = (eic_time >= (retention_time - retention_time_window)) & (
        eic_time <= (retention_time + retention_time_window)
    )

    # Apply time mask to filter out data outside the retention time window
    filtered_indices = np.where(time_mask)[0]
    if len(filtered_indices) == 0:
        raise ValueError("No data within the retention time window.")

    # Use vectorized operations instead of loops
    start_indices = scan_index[filtered_indices]
    end_indices = np.append(scan_index[filtered_indices[1:]], len(mass_values))

    # Create a mask for the mass range
    mass_mask = (mass_values >= target_mass - mass_tolerance) & (
        mass_values <= target_mass + mass_tolerance
    )

    # Initialize eic_intensity array
    eic_intensity = np.zeros(len(filtered_indices))

    # Use numpy's add.reduceat for efficient summation
    for i, (start, end) in enumerate(zip(start_indices, end_indices)):
        eic_intensity[i] = np.add.reduceat(
            intensity_values[start:end][mass_mask[start:end]], [0]
        )[0]

    # Final filtered results
    filtered_eic_time = eic_time[time_mask]
    filtered_eic_intensity = eic_intensity

    return filtered_eic_time, filtered_eic_intensity
