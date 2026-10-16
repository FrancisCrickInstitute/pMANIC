import json

from PySide6.QtWidgets import QFileDialog, QMessageBox

from manic.models import database
from manic.models.database import soft_delete_compound

from conftest import _make_window


def _insert_compound(name: str) -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, roffset, "
            "mass0, label_atoms) VALUES (?, 1.0, 0.1, 0.1, 217.0, 2)",
            (name,),
        )


def _window_with_standard(monkeypatch):
    _insert_compound("Norvaline")
    _insert_compound("Alanine")
    window = _make_window(monkeypatch)
    window.toolbar.update_compound_list(["Norvaline", "Alanine"])
    window.toolbar.on_internal_standard_selected("Norvaline")
    window.apply_internal_standard_reference_isotope(2)
    return window


def test_deleting_internal_standard_clears_it(qapp, monkeypatch):
    window = _window_with_standard(monkeypatch)

    assert soft_delete_compound("Alanine")
    window.toolbar.compounds_deleted.emit(["Alanine"])

    assert window.toolbar.get_internal_standard() == "Norvaline"
    assert window.toolbar.standard.toolTip() == "Int Std: Norvaline"
    assert window.internal_standard_reference_isotope == 2

    assert soft_delete_compound("Norvaline")
    window.toolbar.compounds_deleted.emit(["Norvaline"])

    assert window.toolbar.get_internal_standard() is None
    assert window.toolbar.standard.toolTip() == "Int Std: none"
    assert window.internal_standard_reference_isotope == 0
    window.close()


def test_session_import_deleting_internal_standard_clears_it(
    qapp, monkeypatch, tmp_path
):
    window = _window_with_standard(monkeypatch)
    session = tmp_path / "legacy_session.json"
    session.write_text(
        json.dumps(
            {
                "compounds": [
                    {"compound_name": "Norvaline", "retention_time": 1.0,
                     "mass0": 217.0, "deleted": 1},
                    {"compound_name": "Alanine", "retention_time": 1.0,
                     "mass0": 217.0, "deleted": 0},
                ],
                "session_overrides": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(session), "")
    )
    monkeypatch.setattr(
        window, "_show_question_dialog", lambda *a, **k: QMessageBox.Yes
    )
    monkeypatch.setattr(
        window,
        "_create_message_box",
        lambda *a, **k: type("Box", (), {"exec": lambda self: None})(),
    )

    window.import_session()

    assert window.toolbar.get_internal_standard() is None
    assert window.toolbar.standard.toolTip() == "Int Std: none"
    assert window.internal_standard_reference_isotope == 0
    window.close()
