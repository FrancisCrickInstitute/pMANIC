import time

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def viewer(qapp, tmp_path, monkeypatch):
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "00_quick_start.md").write_text("# Quick Start\n\nLoad a compound list.\n")
    monkeypatch.setattr(
        "manic.ui.documentation_viewer.docs_path",
        lambda *parts: str(docs.joinpath(*parts)) if parts else str(docs),
    )
    from manic.ui.documentation_viewer import DocumentationViewer

    dialog = DocumentationViewer()
    yield dialog
    dialog.close()
    dialog.deleteLater()


def _wait(predicate, timeout=20.0):
    end = time.time() + timeout
    while not predicate() and time.time() < end:
        QApplication.processEvents()
        time.sleep(0.02)
    return predicate()


def test_documentation_shows_a_loading_note_then_the_page(viewer):
    viewer.open()
    assert not viewer.is_rendered()
    assert viewer.status_label.text() == "Loading…"
    assert viewer.status_label.isVisible() and not viewer.retry_button.isVisible()
    assert _wait(viewer.is_rendered)
    assert viewer.web_view.isVisible()


def test_a_failed_render_says_so_and_offers_a_retry(viewer):
    viewer.open()
    viewer._on_load_finished(False)
    assert not viewer.is_rendered()
    assert viewer.status_label.text() == "This page could not be displayed."
    assert viewer.retry_button.isVisible()
    viewer.retry_button.click()
    assert _wait(viewer.is_rendered)


def test_short_page_titles_carry_no_repeat_tooltip(viewer):
    assert viewer.page_list.item(0).text() == "Quick Start"
    assert viewer.page_list.item(0).toolTip() == ""
