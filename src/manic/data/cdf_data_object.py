class CDFData:
    """Class to store data from a CDF file."""
    def __init__(self, file_name, scan_acquisition_time, mass_values, intensity_values, scan_index, point_count,
                 total_intensity):
        self.file_name = file_name
        self.scan_acquisition_time = scan_acquisition_time
        self.mass_values = mass_values
        self.intensity_values = intensity_values
        self.scan_index = scan_index
        self.point_count = point_count
        self.total_intensity = total_intensity


    def __repr__(self):
        """String representation of the CDFData object."""
        return f"CDFData(file_name={self.file_name})"

