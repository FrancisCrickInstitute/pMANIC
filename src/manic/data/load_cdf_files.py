import os
import numpy as np
from netCDF4 import Dataset


def read_cdf_file(file_path: str) -> dict:
    """Reads a CDF file and returns a dictionary."""
    with Dataset(file_path, "r") as cdf_file:
        file_name_with_extension = os.path.basename(file_path)
        file_name, file_extension = os.path.splitext(
            file_name_with_extension
        )  # Exclude extension from name

        cdf_file_data = {
            "file_name": file_name,
            "scan_acquisition_time": np.asarray(
                cdf_file.variables["scan_acquisition_time"][:],
                dtype=np.float64,
            ),
            "mass_values": np.asarray(
                cdf_file.variables["mass_values"][:], dtype=np.float64
            ),
            "intensity_values": np.asarray(
                cdf_file.variables["intensity_values"][:], dtype=np.float64
            ),
            "scan_index": np.asarray(
                cdf_file.variables["scan_index"][:], dtype=np.int64
            ),
            "point_count": np.asarray(
                cdf_file.variables["point_count"][:], dtype=np.int64
            ),
            "total_intensity": np.asarray(
                cdf_file.variables["total_intensity"][:], dtype=np.float64
            ),
        }
    return cdf_file_data


def load_cdf_files_from_directory(directory: str) -> dict:
    """Loads all CDF files from a directory and returns a list of CDFData objects."""
    cdf_files = [
        file for file in os.listdir(directory) if file.lower().endswith(".cdf")
    ]
    if not cdf_files:
        raise FileNotFoundError(
            "No CDF files found in the selected directory."
        )

    all_cdf_data = {}
    for cdf_file in cdf_files:
        file_path = os.path.join(directory, cdf_file)
        cdf_data = read_cdf_file(file_path)
        all_cdf_data[cdf_file] = cdf_data

    return all_cdf_data
