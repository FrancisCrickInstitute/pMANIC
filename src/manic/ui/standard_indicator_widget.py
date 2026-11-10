from manic.models.analysis import AnalysisMode
from manic.models.database import get_connection
from manic.ui.sidebar_widgets import StatusRow


def lacking_amount(names: list[str], mode: AnalysisMode) -> set[str]:
    """The names export cannot calibrate with as the standard: labelled needs both amounts
    (the export prompt's check), unlabelled its int_std_amount."""
    fields = (
        ("int_std_amount", "amount_in_std_mix")
        if mode is AnalysisMode.LABELLED
        else ("int_std_amount",)
    )
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT compound_name, {', '.join(fields)} FROM compounds "
            f"WHERE deleted = 0 AND compound_name IN ({', '.join('?' * len(names))})",
            names,
        ).fetchall()
    calibrated = {
        row["compound_name"]
        for row in rows
        if all(row[f] and float(row[f]) > 0 for f in fields)
    }
    return set(names) - calibrated


class StandardIndicator(StatusRow):
    """Header row for the internal standard. Unset is neutral, not an error; a standard
    the export cannot calibrate with is marked, and its tooltip says why."""

    def __init__(self, analysis_mode: AnalysisMode = AnalysisMode.LABELLED, parent=None):
        super().__init__("Internal standard", parent)
        self._mode = analysis_mode
        self.internal_standard = None
        self.clear_internal_standard()

    def set_internal_standard(self, compound_name: str):
        self.internal_standard = compound_name
        if lacking_amount([compound_name], self._mode):
            self.set_state("warning", compound_name)
            self.setToolTip(
                "No amount: exports peak areas. The compound list gives this standard "
                "no amount, so the export cannot calibrate with it. Add its amounts and "
                "re-import the list. Click to change."
            )
        else:
            self.set_state("done", compound_name)
            self.setToolTip("Click to change")

    def clear_internal_standard(self):
        self.internal_standard = None
        self.set_state("optional", "None")
        self.setToolTip("Click to choose one")
