from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QWidget

from manic.ui.sidebar_widgets import StatusRow


class LoadedDataWidget(QWidget):
    """Header rows saying what is loaded. They only report: the start panel and File load."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("loadedDataWidget")
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(4)
        self._layout.setVerticalSpacing(2)
        self.compounds_row = StatusRow("Compound list")
        self.raw_data_row = StatusRow("Raw data")
        for row in (self.compounds_row, self.raw_data_row):
            row.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            row.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.update_status(False, False)

    def update_status(self, raw_loaded: bool, compounds_loaded: bool) -> None:
        # Once both are loaded the rows only confirm it, so they share one line.
        both = raw_loaded and compounds_loaded
        self._layout.addWidget(self.compounds_row, 0, 0)
        self._layout.addWidget(self.raw_data_row, 0 if both else 1, 1 if both else 0)
        self._layout.setColumnStretch(0, 1)
        self._layout.setColumnStretch(1, 1 if both else 0)
        for row, loaded in ((self.compounds_row, compounds_loaded), (self.raw_data_row, raw_loaded)):
            if loaded:
                row.set_state("done", "")
            else:
                row.set_state("blocked", "Not loaded")
