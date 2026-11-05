from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from manic.models.analysis import AnalysisMode
from manic.ui.start_panel import StartPanel
from manic.utils.recent_files import RecentFiles

from conftest import _make_window


def _recent_names(panel: StartPanel) -> list[str]:
    return [
        button.text()
        for button in panel.findChildren(QPushButton, "recentName")
        if button.isVisibleTo(panel)
    ]


def _shown_labels(panel: StartPanel) -> list[QLabel]:
    return [label for label in panel.findChildren(QLabel) if label.isVisibleTo(panel)]


def test_clear_recent_empties_the_start_panel_at_once(qapp, monkeypatch, tmp_path):
    compounds = tmp_path / "compounds.xlsx"
    compounds.write_text("x")
    RecentFiles("compound_lists").add(str(compounds))
    window = _make_window(monkeypatch, AnalysisMode.LABELLED)
    try:
        window.show()
        QApplication.processEvents()
        assert _recent_names(window.start_panel) == ["compounds.xlsx"]
        assert "Recent" in [label.text() for label in _shown_labels(window.start_panel)]

        clear = next(a for a in window.open_recent_menu.actions() if a.text() == "Clear Recent")
        clear.trigger()
        QApplication.processEvents()
        assert _recent_names(window.start_panel) == []
        assert "Recent" not in [label.text() for label in _shown_labels(window.start_panel)]
    finally:
        window.close()


def test_long_recent_folder_elides_in_the_middle_and_explains_on_hover(qapp, tmp_path):
    deep = tmp_path.joinpath(*[f"folder_{i}" for i in range(12)])
    deep.mkdir(parents=True)
    path = deep / "compounds.xlsx"
    path.write_text("x")
    panel = StartPanel()
    try:
        panel.refresh(False, True, False, [str(path)], [])
        panel.resize(900, 600)
        panel.show()
        QApplication.processEvents()
        folder = next(
            label
            for label in panel.findChildren(QLabel)
            if label.toolTip() == str(path)
        )
        shown = folder.text()
        assert "…" in shown
        # Both ends survive: the root of the path and the folder the file is in.
        assert shown.endswith("folder_11")
        assert shown[:4] == folder.full_text()[:4]

        short = "/Volumes/list.xlsx"
        panel.refresh(False, True, False, [short], [])
        QApplication.processEvents()
        assert short not in [label.toolTip() for label in _shown_labels(panel)]
    finally:
        panel.deleteLater()
