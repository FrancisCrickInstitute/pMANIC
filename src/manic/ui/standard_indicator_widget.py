from manic.ui.sidebar_widgets import StatusRow


class StandardIndicator(StatusRow):
    """Header row for the optional internal standard. Unset is neutral, not an error."""

    def __init__(self, parent=None):
        super().__init__("Internal standard", parent)
        self.internal_standard = None
        self.clear_internal_standard()

    def set_internal_standard(self, compound_name: str):
        self.internal_standard = compound_name
        self.set_state("done", compound_name)
        self.setToolTip(f"Internal standard: {compound_name}\nClick to change")

    def clear_internal_standard(self):
        self.internal_standard = None
        self.set_state("optional", "None (optional)")
        self.setToolTip(
            "No internal standard (optional)\nClick to choose one from the compounds"
        )
