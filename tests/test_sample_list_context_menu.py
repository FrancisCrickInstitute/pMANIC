from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QMenu

from manic.ui.sample_list_widget import SampleListWidget


def test_context_menu_names_the_highlighted_samples(qapp, monkeypatch):
    shown: list[list[str]] = []
    monkeypatch.setattr(
        QMenu,
        "exec_",
        lambda menu, *args: shown.append([a.text() for a in menu.actions() if a.text()]),
    )
    samples = SampleListWidget()
    samples.update_samples(["S1", "S2", "S3"])
    samples.item(2).setSelected(True)
    samples.item(0).setSelected(True)

    samples._show_context_menu(QPoint(1, 1))

    assert samples._get_valid_selected_samples() == ["S1", "S3"]
    assert shown[0][:4] == [
        "Delete 2 Samples",
        "Show Only 2 Samples",
        "Hide 2 Samples",
        "Show All Samples",
    ]
