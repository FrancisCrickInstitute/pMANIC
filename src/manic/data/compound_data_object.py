class Compound:
    """A class to represent a compound in the data."""
    def __init__(self, name, retention_time, mass, l_offset, r_offset):
        self.name = name
        self.retention_time = retention_time
        self.mass = mass
        self.l_offset = l_offset
        self.r_offset = r_offset

    def __repr__(self):
        """String representation of the Compound object."""
        return f"Compound(name={self.name}, retention_time={self.retention_time})"

    # Add methods for compound-specific processing if needed
