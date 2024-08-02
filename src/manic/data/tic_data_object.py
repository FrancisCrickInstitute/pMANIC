class TICData:
    def __init__(self, file_name, tic_time, tic_intensity):
        self.file_name = file_name
        self.tic_time = tic_time
        self.tic_intensity = tic_intensity

    def __repr__(self):
        return f"TIC(file_name={self.file_name})"
