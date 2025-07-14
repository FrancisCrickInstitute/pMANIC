import numpy as np


class CdfFileData:
    """
    Store all of the data contained within a single CDF file.
    """

    def __init__(
        self,
        file_path: str,
        filename: str,
        scan_acquisition_time: np.ndarray,
        mass_values: np.ndarray,
        intensity_values: np.ndarray,
        scan_index: np.ndarray,
        point_count: np.ndarray,
        total_intensity: np.ndarray,
    ):
        self.file_path = file_path
        self.filename = filename
        self.scan_acquisition_time = scan_acquisition_time
        self.mass_values = mass_values
        self.intensity_values = intensity_values
        self.scan_index = scan_index
        self.point_count = point_count
        self.total_intensity = total_intensity


class CdfDirectory:
    """
    A directory containing all of the CDF objects, the directory path, and a
    list of the CDF filenames.

    cdf_directory is a dictionary where the key is the filename and the value
    is a CdfFileData object.
    """

    def __init__(
        self,
        directory_path: str,
        file_list: list[str],
        cdf_directory: dict[str, CdfFileData],
    ):
        self.directory = directory_path
        self.file_list = file_list
        self.cdf_directory = cdf_directory


class CompoundListData:
    """
    Store a list of the compound names and a list of the compound data objects.
    """

    def __init__(self, compounds: list, compound_data: list):
        self.compounds = compounds
        self.compound_data = compound_data


class CompoundData:
    """
    Store the information about a single compound.
    """

    def __init__(
        self,
        name: str,
        tR: float,
        Mass0: float,
        lOffset: float,
        rOffset: float,
    ):
        self.name = name
        self.tR = tR
        self.Mass0 = Mass0
        self.lOffset = lOffset
        self.rOffset = rOffset


class ExtractedIonChromatogramData:

    def __init__(
        self,
        sample_name: str,
        compound_name: str,
        retention_time_window: float = 0.2,
    ):
        self.sample_name = sample_name
        self.compound_name = compound_name
        self.time_x: np.ndarray | None = None
        self.intensity_y: np.ndarray | None = None
        self.retention_time_window = retention_time_window


class TotalIonChromatogramData:
    def __init__(self, tic_plot):
        self.tic_plot = tic_plot


class MassSpectrumData:
    def __init__(self, mass_spectrum):
        self.mass_spectrum = mass_spectrum
