import os
from numpy import asarray, float64
from src.manic.models import CdfFileData, CdfDirectory
from netCDF4 import Dataset


def read_cdf_file(file_path: str) -> CdfFileData:
    """Reads a CDF file and returns a CdfFileData object."""
    with Dataset(file_path, "r") as cdf_file:
        file_name_with_extension = os.path.basename(file_path)
        file_name, file_extension = os.path.splitext(
            file_name_with_extension
        )  # Exclude extension from name

        data_object = CdfFileData(
            file_path,
            file_name,
            asarray(
                cdf_file.variables["scan_acquisition_time"][:],
                dtype=float64,
            ),
            asarray(cdf_file.variables["mass_values"][:], dtype=float64),
            asarray(cdf_file.variables["intensity_values"][:], dtype=float64),
            asarray(cdf_file.variables["scan_index"][:], dtype=float64),
            asarray(cdf_file.variables["point_count"][:], dtype=float64),
            asarray(cdf_file.variables["total_intensity"][:], dtype=float64),
        )

    return data_object


def load_cdf_files_from_directory(directory: str) -> CdfDirectory:
    """Loads all CDF files from a directory and returns a CdfDirectory object."""
    cdf_files = [
        file for file in os.listdir(directory) if file.lower().endswith(".cdf")
    ]
    if not cdf_files:
        raise FileNotFoundError(
            "No CDF files found in the selected directory."
        )

    cdf_directory_object = CdfDirectory(directory, cdf_files, {})
    for cdf_file in cdf_files:
        file_path = os.path.join(directory, cdf_file)
        file_data = read_cdf_file(file_path)
        cdf_directory_object.cdf_directory[file_data.filename] = file_data

    return cdf_directory_object
