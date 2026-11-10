import os
from pathlib import Path

os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest

from manic.ui.documentation_viewer import documentation_index

from conftest import _make_window


def _write_docs(docs_dir: Path) -> None:
    docs_dir.mkdir(exist_ok=True)
    (docs_dir / "Reference_Z.md").write_text("# Ref Z\n", encoding="utf-8")
    (docs_dir / "Workflow_B.md").write_text("# Flow B\n", encoding="utf-8")
    (docs_dir / "00_quick_start.md").write_text(
        "# Quick Start\n\nLoad a compound list.\n", encoding="utf-8"
    )
    (docs_dir / "01_user_guide.md").write_text("# Guide\n", encoding="utf-8")
    (docs_dir / "Unlabelled_Targeted_Analysis.md").write_text(
        "# Unlabelled Targeted Analysis\n", encoding="utf-8"
    )
    (docs_dir / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
    (docs_dir / "zzz_other.md").write_text("no heading here\n", encoding="utf-8")
    (docs_dir / "Reference_A.md").write_text("# Ref A\n", encoding="utf-8")
    (docs_dir / "Workflow_A.md").write_text("# Flow A\n", encoding="utf-8")


@pytest.fixture
def docs_dir(tmp_path, monkeypatch):
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    docs = tmp_path / "docs"
    _write_docs(docs)
    monkeypatch.setattr(
        "manic.ui.documentation_viewer.docs_path",
        lambda *parts: str(docs.joinpath(*parts)) if parts else str(docs),
    )
    return docs


@pytest.fixture
def window(qapp, docs_dir, monkeypatch):
    window = _make_window(monkeypatch)
    yield window
    if window.documentation_window is not None:
        window.documentation_window.close()
    window.close()


@pytest.fixture
def viewer(qapp, docs_dir):
    from manic.ui.documentation_viewer import DocumentationViewer

    dialog = DocumentationViewer()
    yield dialog
    dialog.close()
    dialog.deleteLater()
    # Free the web page before the app exits, or WebEngine warns about its profile.
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_documentation_index_orders_groups_and_titles(tmp_path):
    _write_docs(tmp_path)
    index = documentation_index(tmp_path)
    assert [path.name for _, path in index] == [
        "00_quick_start.md",
        "01_user_guide.md",
        "Unlabelled_Targeted_Analysis.md",
        "Workflow_A.md",
        "Workflow_B.md",
        "Reference_A.md",
        "Reference_Z.md",
        "alpha.md",
        "zzz_other.md",
    ]
    assert [title for title, _ in index] == [
        "Quick Start",
        "Guide",
        "Unlabelled Targeted Analysis",
        "Flow A",
        "Flow B",
        "Ref A",
        "Ref Z",
        "Alpha",
        "Zzz Other",
    ]


def test_documentation_window_loads_first_file(window, docs_dir):
    window.documentation_action.trigger()
    viewer = window.documentation_window
    assert viewer is not None
    items = [viewer.page_list.item(i) for i in range(viewer.page_list.count())]
    assert [item.text() for item in items] == [
        "Quick Start",
        "Guide",
        "Unlabelled Targeted Analysis",
        "Workflows",
        "Flow A",
        "Flow B",
        "Reference",
        "Ref A",
        "Ref Z",
        "Alpha",
        "Zzz Other",
    ]
    # Every title fits the list, so none repeats itself in a tooltip.
    assert [item.toolTip() for item in items] == [""] * 11
    assert viewer.current_file == docs_dir / "00_quick_start.md"


def test_documentation_sidebar_selection_changes_file(window, docs_dir):
    window.documentation_action.trigger()
    viewer = window.documentation_window
    viewer.page_list.setCurrentRow(2)
    # The arrow key steps over the "Workflows" heading to its first page.
    QTest.keyClick(viewer.page_list, Qt.Key_Down)
    assert viewer.current_file == docs_dir / "Workflow_A.md"
