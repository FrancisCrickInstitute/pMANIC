import numpy as np


def load_eic_data(
    filename: str,
    compound: str,
    cdf_data: dict,
    compound_data: dict,
    mass_tolerance: float = 0.25,
) -> list:
    selected_cdf_data = cdf_data[filename]
    selected_compound = compound_data[compound]
    scan_acquisition_time = selected_cdf_data["scan_acquisition_time"]
    retention_time = selected_compound["tR"]

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

    # Initializing eic_intensity to capture filtered data
    eic_intensity = np.zeros_like(eic_time[time_mask])

    return []
