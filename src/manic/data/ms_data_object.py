class MassSpectrumData:
    def __init__(self, file_name, retention_time, mass_values, intensity_values):
        self.file_name = file_name
        self.retention_time = retention_time
        self.mass_values = mass_values
        self.intensity_values = intensity_values

    def __repr__(self):
        return f"MassSpectrum(file_name={self.file_name}, retention_time={self.retention_time})"
