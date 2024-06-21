class EICData:
    def __init__(self, file_name, compound_name, eic_time, eic_intensity, retention_time, l_offset, r_offset,
                 target_mass):
        self.file_name = file_name
        self.compound_name = compound_name
        self.eic_time = eic_time
        self.eic_intensity = eic_intensity
        self.retention_time = retention_time
        self.l_offset = l_offset
        self.r_offset = r_offset
        self.target_mass = target_mass

    def __repr__(self):
        return f"EIC(file_name={self.file_name}, compound_name={self.compound_name})"

