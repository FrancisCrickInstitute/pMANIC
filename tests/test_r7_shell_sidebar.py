from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings

from manic.models.analysis import AnalysisMode
from manic.ui.left_toolbar import Toolbar


@pytest.fixture(autouse=True)
def scratch_settings(tmp_path):
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    QSettings().clear()
    yield


@pytest.fixture
def toolbar(qapp, monkeypatch):
    monkeypatch.setattr(
        "manic.ui.left_toolbar.read_compound",
        lambda _name: SimpleNamespace(deconvolution_level="off", baseline_correction=1),
    )
    toolbar = Toolbar(AnalysisMode.LABELLED)
    toolbar.update_label_colours(True, True)
    toolbar.update_compound_list(["Alanine"], "Alanine")
    toolbar.update_sample_list(["S1", "S2"])
    toolbar.show()
    yield toolbar
    toolbar.deleteLater()


def test_section_summary_shows_only_while_the_section_is_closed(toolbar):
    for section in (toolbar.peak_section, toolbar.display_section):
        section.set_expanded(True)
        assert not section.summary.isVisible()
        section.set_expanded(False)
        assert section.summary.isVisible()
        assert section.summary.full_text()
