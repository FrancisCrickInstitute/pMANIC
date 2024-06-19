import os
import netCDF4
from src.manic.data.cdf_data_object import CDFData
import pandas as pd

def read_cdf_file(file_path):
    """Reads a CDF file and returns a CDFData object."""
    cdf_file = netCDF4.Dataset(file_path, 'r')
    file_name_with_extension = os.path.basename(file_path)
    file_name, file_extension = os.path.splitext(file_name_with_extension)  # Exclude extension from name
    data = CDFData(
        file_name=file_name,
        scan_acquisition_time=cdf_file.variables['scan_acquisition_time'][:].tolist(),
        mass_values=cdf_file.variables['mass_values'][:].tolist(),
        intensity_values=cdf_file.variables['intensity_values'][:].tolist(),
        scan_index=cdf_file.variables['scan_index'][:].tolist(),
        point_count=cdf_file.variables['point_count'][:].tolist(),
        total_intensity=cdf_file.variables['total_intensity'][:].tolist()
    )
    cdf_file.close()
    return data


def load_cdf_files_from_directory(directory, progress_callback=None):
    """Loads all CDF files from a directory and returns a list of CDFData objects."""
    cdf_files = [f for f in os.listdir(directory) if f.lower().endswith('.cdf')]
    if not cdf_files:
        raise FileNotFoundError("No CDF files found in the selected directory.")

    data_list = []
    total_files = len(cdf_files)
    for index, cdf_file in enumerate(cdf_files):
        file_path = os.path.join(directory, cdf_file)
        cdf_data = read_cdf_file(file_path)
        data_list.append(cdf_data)
        # Update the progress bar using update_progress_bar function passed as an argument to this function
        if progress_callback:
            progress_callback(index + 1, total_files)

    return data_list