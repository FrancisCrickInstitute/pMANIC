from PySide6.QtWidgets import QDialog, QVBoxLayout, QProgressBar, QLabel

class ProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loading CDF Data")
        self.setModal(True)
        self.setFixedSize(300, 100)

        layout = QVBoxLayout()

        self.label = QLabel("Loading, please wait...")
        layout.addWidget(self.label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

    def set_progress(self, value):
        self.progress_bar.setValue(value)
