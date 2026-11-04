from PySide6.QtWidgets import QGridLayout, QWidget

from manic.ui.sidebar_widgets import StatusRow, shortcut_text


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


class LoadedDataWidget(QWidget):
    """Header rows saying in words what is loaded; each row is a shortcut to load it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("loadedDataWidget")
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(4)
        self._layout.setVerticalSpacing(2)
        self.compounds_row = StatusRow("Compound list")
        self.raw_data_row = StatusRow("Raw data")
        self.update_status(False, False)

    def update_status(
        self,
        raw_loaded: bool,
        compounds_loaded: bool,
        compound_count: int = 0,
        sample_count: int = 0,
    ):
        # Once both are loaded the rows only confirm it, so they share one line.
        both = raw_loaded and compounds_loaded
        self._layout.addWidget(self.compounds_row, 0, 0)
        self._layout.addWidget(self.raw_data_row, 0 if both else 1, 1 if both else 0)
        self._layout.setColumnStretch(0, 1)
        self._layout.setColumnStretch(1, 1 if both else 0)
        self.compounds_row.set_compact(both)
        self.raw_data_row.set_compact(both)

        if compounds_loaded:
            self.compounds_row.set_state("done", _plural(compound_count, "compound"))
            self.compounds_row.setToolTip(f"Find a compound ({shortcut_text('Ctrl+F')})")
        else:
            self.compounds_row.set_state("todo", "Load…")
            self.compounds_row.setToolTip(f"Load a compound list ({shortcut_text('Ctrl+O')})")

        if raw_loaded:
            self.raw_data_row.set_state("done", _plural(sample_count, "sample"))
            self.raw_data_row.setToolTip("Show the sample list")
        elif compounds_loaded:
            self.raw_data_row.set_state("todo", "Load…")
            self.raw_data_row.setToolTip(f"Load a folder of raw CDF files ({shortcut_text('Ctrl+Shift+O')})")
        else:
            self.raw_data_row.set_state("blocked", "After compounds")
            self.raw_data_row.setToolTip("Load a compound list first")
