import os
import time
from pathlib import Path

os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolButton

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


def _shown_at_centre(viewer) -> str:
    """What a user sees in the middle of the article area: the note or the page."""
    widget = viewer.content.childAt(viewer.content.rect().center())
    if widget is viewer.status_page or viewer.status_page.isAncestorOf(widget):
        return "note"
    return "page" if viewer.web_view.isAncestorOf(widget) else repr(widget)


def _has_ink(view) -> bool:
    image = view.grab().toImage()
    background = image.pixel(0, 0)
    return any(
        image.pixel(x, y) != background
        for y in range(0, image.height(), 4)
        for x in range(0, image.width(), 4)
    )


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


def test_documentation_keeps_its_loading_note_over_the_page_until_the_page_has_drawn(viewer):
    # Connected after the viewer's own handler, so it sees what that handler left on screen.
    at_load_finished = []
    viewer.web_view.loadFinished.connect(
        lambda _ok: at_load_finished.append((_shown_at_centre(viewer), viewer.status_label.text()))
    )
    viewer.open()
    assert viewer.status_label.text() == "Loading…"
    assert viewer.status_label.isVisible()
    assert not viewer.retry_button.isVisible() and not viewer.web_view.isVisible()
    assert _wait(viewer.is_rendered)
    # The load finished before the page reached the view, which was still blank then.
    assert at_load_finished == [("note", "Loading…")]
    assert _shown_at_centre(viewer) == "page" and _has_ink(viewer.web_view)
    assert _page_text(viewer) == "Quick Start\n\nLoad a compound list."


def test_a_page_that_never_draws_is_loaded_again_once_then_offers_a_retry(viewer, monkeypatch):
    monkeypatch.setattr("manic.ui.documentation_viewer._PAINT_TIMEOUT_MS", 3000)
    monkeypatch.setattr("manic.ui.documentation_viewer._PAINTED_JS", "false")
    loads = []
    viewer.web_view.loadFinished.connect(loads.append)
    viewer.open()
    assert _wait(lambda: len(loads) == 2)
    assert viewer.status_label.text() == "Loading…" and _shown_at_centre(viewer) == "note"
    assert _wait(viewer.retry_button.isVisible)
    assert viewer.status_label.text() == "This page could not be displayed."
    assert not viewer.web_view.isVisible() and loads == [True, True]
    monkeypatch.undo()
    viewer.retry_button.click()
    assert _wait(viewer.is_rendered)
    assert _page_text(viewer) == "Quick Start\n\nLoad a compound list."


def test_a_failed_render_says_so_and_offers_a_retry(viewer):
    viewer.open()
    viewer.web_view.loadFinished.emit(False)
    assert not viewer.web_view.isVisible()
    assert viewer.status_label.text() == "This page could not be displayed."
    assert viewer.retry_button.isVisible()
    viewer.retry_button.click()
    assert _wait(viewer.is_rendered)
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


def test_a_scheme_switch_while_closed_shows_the_page_on_reopen(qapp, viewer, monkeypatch):
    from manic.utils.utils import apply_color_scheme, set_appearance

    monkeypatch.setattr("manic.ui.documentation_viewer._PAINT_TIMEOUT_MS", 500)
    viewer.open()
    assert _wait(viewer.is_rendered)
    viewer.close()
    try:
        set_appearance(qapp, "dark")
        QTest.qWait(1500)
        viewer.open()
        assert _wait(viewer.is_rendered)
        assert not viewer.retry_button.isVisible() and _shown_at_centre(viewer) == "page"
        assert _page_text(viewer) == "Quick Start\n\nLoad a compound list."
    finally:
        viewer.close()
        set_appearance(qapp, "system")
        apply_color_scheme(qapp, False)
        qapp.setStyleSheet("")


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
    # The same bar opens from a visible button, and its icon buttons have names.
    QTest.mouseClick(viewer.find_button, Qt.LeftButton)
    assert viewer.find_bar.isVisible() and viewer.find_field.hasFocus()
    assert [b.accessibleName() for b in viewer.find_bar.findChildren(QToolButton, options=Qt.FindDirectChildrenOnly)] == [
        "Previous match", "Next match"
    ]
