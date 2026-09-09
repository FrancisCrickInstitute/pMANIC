import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

import pytest
from PySide6.QtWidgets import QApplication

from manic.models import database
from manic.models.analysis import AnalysisContext, AnalysisMode
from manic.ui.documentation_viewer import documentation_index
from manic.ui.main_window import MainWindow

SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def empty_db(tmp_path, monkeypatch):
    db_path = tmp_path / "docs.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    with database.get_connection() as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return db_path


def _make_window(monkeypatch) -> MainWindow:
    monkeypatch.setattr(MainWindow, "_check_for_updates", lambda self: None)
    return MainWindow(AnalysisContext(AnalysisMode.LABELLED))


def _write_docs(docs_dir: Path) -> None:
    docs_dir.mkdir(exist_ok=True)
    (docs_dir / "Reference_Z.md").write_text("# Ref Z\n", encoding="utf-8")
    (docs_dir / "Workflow_B.md").write_text("# Flow B\n", encoding="utf-8")
    (docs_dir / "01_user_guide.md").write_text("# Guide\n", encoding="utf-8")
    (docs_dir / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
    (docs_dir / "zzz_other.md").write_text("no heading here\n", encoding="utf-8")
    (docs_dir / "Reference_A.md").write_text("# Ref A\n", encoding="utf-8")
    (docs_dir / "Workflow_A.md").write_text("# Flow A\n", encoding="utf-8")


def test_documentation_index_orders_groups_and_titles(tmp_path):
    _write_docs(tmp_path)
    index = documentation_index(tmp_path)
    assert [path.name for _, path in index] == [
        "01_user_guide.md",
        "Workflow_A.md",
        "Workflow_B.md",
        "Reference_A.md",
        "Reference_Z.md",
        "alpha.md",
        "zzz_other.md",
    ]
    assert [title for title, _ in index] == [
        "Guide",
        "Flow A",
        "Flow B",
        "Ref A",
        "Ref Z",
        "Alpha",
        "Zzz Other",
    ]


def test_documentation_window_loads_first_file(qapp, empty_db, tmp_path, monkeypatch):
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    docs_dir = tmp_path / "docs"
    _write_docs(docs_dir)

    def fake_docs_path(*parts: str) -> str:
        return str(docs_dir.joinpath(*parts)) if parts else str(docs_dir)

    monkeypatch.setattr("manic.ui.documentation_viewer.docs_path", fake_docs_path)
    window = _make_window(monkeypatch)
    try:
        window.open_documentation_window()
        viewer = window.documentation_window
        assert viewer is not None
        titles = [
            viewer.page_list.item(i).text() for i in range(viewer.page_list.count())
        ]
        assert titles == [
            "Guide",
            "Flow A",
            "Flow B",
            "Ref A",
            "Ref Z",
            "Alpha",
            "Zzz Other",
        ]
        assert viewer.current_file == docs_dir / "01_user_guide.md"
        assert viewer.windowTitle() == "MANIC Documentation"
    finally:
        if window.documentation_window is not None:
            window.documentation_window.close()
        window.close()


def test_documentation_sidebar_selection_changes_file(
    qapp, empty_db, tmp_path, monkeypatch
):
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    docs_dir = tmp_path / "docs"
    _write_docs(docs_dir)

    def fake_docs_path(*parts: str) -> str:
        return str(docs_dir.joinpath(*parts)) if parts else str(docs_dir)

    monkeypatch.setattr("manic.ui.documentation_viewer.docs_path", fake_docs_path)
    window = _make_window(monkeypatch)
    try:
        window.open_documentation_window()
        viewer = window.documentation_window
        viewer.page_list.setCurrentRow(1)
        assert viewer.current_file == docs_dir / "Workflow_A.md"
    finally:
        if window.documentation_window is not None:
            window.documentation_window.close()
        window.close()
