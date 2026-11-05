import os
import time
from pathlib import Path

os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from manic.ui.documentation_viewer import documentation_index

from conftest import _make_window


def _write_docs(docs_dir: Path) -> None:
    docs_dir.mkdir(exist_ok=True)
    (docs_dir / "Reference_Z.md").write_text("# Reference: Ref Z\n", encoding="utf-8")
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
    (docs_dir / "Workflow_A.md").write_text("# Workflow: Flow A\n", encoding="utf-8")


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


def _wait(predicate, timeout=20.0):
    end = time.time() + timeout
    while not predicate() and time.time() < end:
        QApplication.processEvents()
        time.sleep(0.02)
    return predicate()


def _page_text(viewer) -> str:
    result = []
    viewer.web_view.page().toPlainText(result.append)
    assert _wait(lambda: result)
    return result[0]


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
        "Workflow: Flow A",
        "Flow B",
        "Ref A",
        "Reference: Ref Z",
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


def test_documentation_shows_a_loading_note_then_the_page(viewer):
    viewer.open()
    assert viewer.status_label.text() == "Loading…"
    assert viewer.status_label.isVisible()
    assert not viewer.retry_button.isVisible() and not viewer.web_view.isVisible()
    assert _wait(viewer.web_view.isVisible)
    assert _page_text(viewer) == "Quick Start\n\nLoad a compound list."


def test_a_failed_render_says_so_and_offers_a_retry(viewer):
    viewer.open()
    viewer.web_view.loadFinished.emit(False)
    assert not viewer.web_view.isVisible()
    assert viewer.status_label.text() == "This page could not be displayed."
    assert viewer.retry_button.isVisible()
    viewer.retry_button.click()
    assert _wait(viewer.web_view.isVisible)
    assert _page_text(viewer) == "Quick Start\n\nLoad a compound list."


def test_a_new_page_shows_loading_until_that_page_renders(viewer):
    viewer.open()
    assert _wait(viewer.is_rendered)
    viewer.page_list.setCurrentRow(1)
    assert not viewer.is_rendered() and viewer.status_label.text() == "Loading…"
    # A finish while the previous page is still the one drawn is not this request's.
    viewer.web_view.loadFinished.emit(True)
    assert not viewer.is_rendered()
    assert _wait(viewer.is_rendered)
    assert _page_text(viewer) == "Guide"


def test_a_guide_link_opens_its_page_at_the_section(viewer, docs_dir):
    (docs_dir / "01_user_guide.md").write_text(
        "# Guide\n\n## Fix a missing qualifier ratio\n\nFill the column.\n", encoding="utf-8"
    )
    viewer.open_link("01_user_guide.md#fix-a-missing-qualifier-ratio")
    assert viewer.current_file == docs_dir / "01_user_guide.md"
    assert viewer.page_list.currentItem().text() == "Guide"
    assert _wait(viewer.is_rendered)
    hashes = []
    viewer.web_view.page().runJavaScript("location.hash", 0, hashes.append)
    assert _wait(lambda: hashes)
    assert hashes == ["#fix-a-missing-qualifier-ratio"]


def test_find_steps_through_matches_and_esc_closes_only_the_find_bar(viewer, docs_dir):
    (docs_dir / "00_quick_start.md").write_text(
        "# Quick Start\n\nA peak.\n\nAnother peak.\n\nThe last peak.\n", encoding="utf-8"
    )
    viewer.open()
    assert _wait(viewer.is_rendered)
    viewer.activateWindow()
    assert QTest.qWaitForWindowActive(viewer)
    QTest.keyClick(viewer.page_list, Qt.Key_F, Qt.ControlModifier)
    assert viewer.find_bar.isVisible() and viewer.find_field.hasFocus()
    QTest.keyClicks(viewer.find_field, "peak")
    assert _wait(lambda: viewer.find_count.text() == "1 of 3")
    QTest.keyClick(viewer.find_field, Qt.Key_Return)
    assert _wait(lambda: viewer.find_count.text() == "2 of 3")
    QTest.keyClick(viewer.find_field, Qt.Key_Return, Qt.ShiftModifier)
    assert _wait(lambda: viewer.find_count.text() == "1 of 3")
    QTest.keyClicks(viewer.find_field, "s")
    assert _wait(lambda: viewer.find_count.text() == "No matches")
    QTest.keyClick(viewer.find_field, Qt.Key_Escape)
    assert not viewer.find_bar.isVisible() and viewer.isVisible()
