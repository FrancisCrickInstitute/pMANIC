import numpy as np


class CdfDirectory:
    """
    A directory containing all of the CDF objects, the directory path, and a
    list of the CDF filenames.

    cdf_directory is a dictionary where the key is the filename and the value
    is a CdfFileData object.
    """

    def __init__(
        self, directory_path: str, file_list: list, cdf_directory: dict
    ):
        self.directory = directory_path
        self.file_list = file_list
        self.cdf_directory = cdf_directory


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


class CompoundIonChromatograms:
    def __init__(self, compound_eics):
        self.compound_eics = compound_eics


class ExtractedIonChromatogramData:
    def __init__(self, eic_plot):
        self.eic_plot = eic_plot


class TotalIonChromatogramData:
    def __init__(self, tic_plot):
        self.tic_plot = tic


class MassSpectrumData:
    def __init__(self, mass_spectrum):
        self.mass_spectrum = mass_spectrum
