from manic.io.compounds_import import CompoundRow, insert_compound
from manic.models.analysis import AnalysisMode

from conftest import _make_window


def test_status_bar_names_the_deconvolution_of_the_compound_shown_after_loading(
    qapp, empty_db, monkeypatch
):
    insert_compound(
        CompoundRow(
            compound_name="Pyruvate", retention_time=6.37, mass0=174.0, loffset=0.1,
            roffset=0.15, label_atoms=3, formula="C3H4O3", label_type="C", tbdms=1,
            meox=0, me=0, amount_in_std_mix=10.0, int_std_amount=1.5, mm_files="*MM*",
        )
    )
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        # Loading selects the first compound without the user picking it.
        window.toolbar.update_compound_list(["Pyruvate"], selected_name="Pyruvate")
        window.compound_data_loaded = True
        window._refresh_shell()

        label = window.deconvolution_indicator_label
        assert not label.isHidden()
        assert label.text() == (
            "Deconvolution level 4 · automatic peak shape · balanced noise gate"
        )
    finally:
        window.close()
