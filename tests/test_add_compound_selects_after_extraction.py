from __future__ import annotations

import gc
import threading
import time
import zlib

import numpy as np
import shiboken6
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QMessageBox

from conftest import _gaussian, _make_window
from manic.models import database


def _insert_compound(name: str) -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds (compound_name, retention_time, loffset, "
            "roffset, mass0, label_atoms) VALUES (?, 5.0, 0.2, 0.2, 100.0, 0)",
            (name,),
        )


def _insert_eic(sample: str, compound: str) -> None:
    times = np.linspace(4.5, 5.5, 200)
    with database.get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO samples (sample_name, file_name) VALUES (?, ?)",
            (sample, f"/fake/{sample}.cdf"),
        )
        conn.execute(
            "INSERT INTO eic (sample_name, compound_name, x_axis, y_axis, "
            "rt_window) VALUES (?, ?, ?, ?, 0.5)",
            (
                sample,
                compound,
                zlib.compress(times.tobytes()),
                zlib.compress(_gaussian(times, 5.0, 0.03, 1e5).tobytes()),
            ),
        )


def _process_events_until(done, timeout=10.0) -> None:
    deadline = time.monotonic() + timeout
    while not done() and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)


def test_added_compound_is_plotted_once_its_eics_are_extracted(qapp, monkeypatch):
    def extract(compound_name, sample_names, **_kwargs):
        for sample in sample_names:
            _insert_eic(sample, compound_name)
        return len(sample_names)

    monkeypatch.setattr("manic.utils.workers.regenerate_compound_eics", extract)
    _insert_compound("A")
    _insert_eic("S1", "A")
    window = _make_window(monkeypatch)
    boxes = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: boxes.append(box.text()))
    window.compound_data_loaded = window.cdf_data_loaded = True
    window.toolbar.update_sample_list(["S1"])
    window.toolbar.update_compound_list(["A"], "A")

    _insert_compound("NewOne")
    window._after_compound_added("NewOne")
    thread = window._regen_thread
    _process_events_until(lambda: not shiboken6.isValid(thread) or thread.isFinished())

    assert boxes == []
    assert window.toolbar.get_selected_compound() == "NewOne"
    assert window.graph_view.get_current_compound() == "NewOne"


def test_added_first_compound_is_not_plotted_before_its_eics_exist(qapp, monkeypatch):
    def extract(compound_name, sample_names, **_kwargs):
        for sample in sample_names:
            _insert_eic(sample, compound_name)
        return len(sample_names)

    monkeypatch.setattr("manic.utils.workers.regenerate_compound_eics", extract)
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO samples (sample_name, file_name) VALUES ('S1', '/fake/S1.cdf')"
        )
    window = _make_window(monkeypatch)
    boxes = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: boxes.append(box.text()))
    window.cdf_data_loaded = True
    window.toolbar.update_sample_list(["S1"])

    _insert_compound("NewOne")
    window._after_compound_added("NewOne")
    thread = window._regen_thread
    _process_events_until(lambda: not shiboken6.isValid(thread) or thread.isFinished())

    assert boxes == []
    assert window.toolbar.get_selected_compound() == "NewOne"
    assert window.graph_view.get_current_compound() == "NewOne"


def test_added_compound_is_selected_after_its_worker_is_destroyed(qapp, monkeypatch):
    def extract(compound_name, sample_names, **_kwargs):
        for sample in sample_names:
            _insert_eic(sample, compound_name)
        return len(sample_names)

    monkeypatch.setattr("manic.utils.workers.regenerate_compound_eics", extract)
    _insert_compound("A")
    _insert_eic("S1", "A")
    window = _make_window(monkeypatch)
    monkeypatch.setattr(QMessageBox, "exec", lambda box: None)
    window.compound_data_loaded = window.cdf_data_loaded = True
    window.toolbar.update_sample_list(["S1"])
    window.toolbar.update_compound_list(["A"], "A")

    _insert_compound("NewOne")
    window._after_compound_added("NewOne")
    emitted = threading.Event()
    window._regen_worker.finished.connect(
        lambda _count: emitted.set(), Qt.ConnectionType.DirectConnection
    )
    assert emitted.wait(10)
    # A second regeneration replaces the worker before the first one's signal is delivered.
    worker = window._regen_worker
    window._regen_worker = None
    del worker
    gc.collect()
    thread = window._regen_thread
    _process_events_until(lambda: not shiboken6.isValid(thread) or thread.isFinished())

    assert window.toolbar.get_selected_compound() == "NewOne"
    assert window.graph_view.get_current_compound() == "NewOne"
