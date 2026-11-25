"""Tests for #299: deconvolution context invariance and decoupled display tR window."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest
from PySide6.QtWidgets import QLineEdit

from conftest import _gaussian, _make_window
from manic.constants import (
    DEFAULT_RT_WINDOW,
    minimum_display_rt_window,
    minimum_extract_rt_window,
)
from manic.io.eic_importer import (
    _compress,
    eic_needs_reextraction,
    regenerate_compound_eics,
    samples_needing_reextraction,
)
from manic.models import database
from manic.models.session_activity import SessionActivityService
from manic.processors.chromatographic_peak_deconvolution import (
    MIN_DECONVOLUTION_CONTEXT_MINUTES,
    _deconvolution_fit_mask,
    deconvolve_eic,
)
from manic.processors.display_deconvolution import plot_display
from manic.processors.integration import calculate_peak_areas
from manic.processors.tile_y_scale import (
    TileScaleInput,
    YScalePolicy,
    axes_for_tiles,
)
from manic.ui.graphs import GraphView
from manic.ui.integration_window_widget import IntegrationWindow


def _two_peak_trace(rt: float, extract_half_width: float, *, neighbour_offset: float):
    # Deterministic scan grid shared across extract widths; includes scans right at rt +/- 0.20.
    step = 0.005
    full_t = np.round(
        np.arange(rt - 1.0, rt + 1.0 + step / 2, step, dtype=np.float64), 6
    )
    full_y = _gaussian(full_t, rt, 0.04, 100.0) + _gaussian(
        full_t, rt + neighbour_offset, 0.045, 90.0
    )
    mask = (full_t >= rt - extract_half_width) & (full_t <= rt + extract_half_width)
    return full_t[mask], full_y[mask]


def test_deconvolved_area_is_invariant_across_extract_windows():
    """Guard against #299: a neighbour inside (0.20, 0.25) must not shift 0.20 vs 0.30/0.80."""
    assert MIN_DECONVOLUTION_CONTEXT_MINUTES == pytest.approx(DEFAULT_RT_WINDOW)
    assert minimum_extract_rt_window(0.05, 0.05) == pytest.approx(0.2)
    assert minimum_extract_rt_window(0.18, 0.12) == pytest.approx(0.28)
    assert minimum_display_rt_window(0.05, 0.05) == pytest.approx(0.07)

    # Neighbour at +0.22 min sits inside the old 0.25 context and outside 0.20, so
    # this case fails if _deconvolution_fit_mask reverts to max(0.25, lo, ro).
    areas_narrow = []
    for extract_w in (0.20, 0.30, 0.80):
        time, intensity = _two_peak_trace(5.0, extract_w, neighbour_offset=0.22)
        result = deconvolve_eic(
            time,
            intensity,
            retention_time=5.0,
            loffset=0.10,
            roffset=0.10,
            stringency="4",
        )
        assert result.model is not None
        areas_narrow.append(
            calculate_peak_areas(
                time,
                intensity,
                label_atoms=0,
                retention_time=5.0,
                loffset=0.10,
                roffset=0.10,
                baseline_correction=True,
                chromatographic_peak_deconvolution_stringency="4",
            )[0]
        )

    assert areas_narrow[0] == pytest.approx(areas_narrow[1], rel=1e-9)
    assert areas_narrow[0] == pytest.approx(areas_narrow[2], rel=1e-9)

    # Wide-offset case (0.18, 0.12): fit context is 0.28 min, neighbour at +0.30 min.
    areas_wide = []
    for extract_w in (0.28, 0.40, 0.80):
        time, intensity = _two_peak_trace(5.0, extract_w, neighbour_offset=0.30)
        result = deconvolve_eic(
            time,
            intensity,
            retention_time=5.0,
            loffset=0.18,
            roffset=0.12,
            stringency="4",
        )
        assert result.model is not None
        areas_wide.append(
            calculate_peak_areas(
                time,
                intensity,
                label_atoms=0,
                retention_time=5.0,
                loffset=0.18,
                roffset=0.12,
                baseline_correction=True,
                chromatographic_peak_deconvolution_stringency="4",
            )[0]
        )

    assert areas_wide[0] == pytest.approx(areas_wide[1], rel=1e-9)
    assert areas_wide[0] == pytest.approx(areas_wide[2], rel=1e-9)

    # Boundary-scan guard: inclusive >= / <= keeps scans sitting exactly at tR +/- 0.20.
    t_exact = np.array([4.75, 4.80, 4.90, 5.00, 5.10, 5.20, 5.25], dtype=np.float64)
    mask = _deconvolution_fit_mask(t_exact, 5.0, 0.10, 0.10)
    assert np.array_equal(t_exact[mask], np.array([4.80, 4.90, 5.00, 5.10, 5.20]))


def _seed_compound_with_neighbour(
    compound: str = "Target",
    samples: tuple[tuple[str, float, float], ...] = (("S1", 0.2, 10000.0),),
    *,
    rt: float = 5.0,
    loffset: float = 0.05,
    roffset: float = 0.05,
    rt_tolerance: float | None = None,
):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO compounds "
            "(compound_name, retention_time, loffset, roffset, mass0, label_atoms, "
            "deconvolution_level, rt_tolerance) "
            "VALUES (?, ?, ?, ?, 100.0, 0, 'off', ?)",
            (compound, rt, loffset, roffset, rt_tolerance),
        )
        for sample_name, stored_window, neighbour_height in samples:
            conn.execute(
                "INSERT INTO samples (sample_name, file_name) VALUES (?, ?)",
                (sample_name, f"/fake/{sample_name}.cdf"),
            )
            t = np.linspace(rt - stored_window, rt + stored_window, 201)
            y = _gaussian(t, rt, 0.015, 100.0) + _gaussian(
                t, rt + 0.16, 0.012, neighbour_height
            )
            conn.execute(
                "INSERT INTO eic "
                "(sample_name, compound_name, x_axis, y_axis, rt_window, extraction_rt) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (sample_name, compound, _compress(t), _compress(y), stored_window, rt),
            )
        conn.commit()


def test_apply_reextracts_when_offset_exceeds_stored_fit_context(qapp):
    """S1: offset 0.18 needs 0.28 min extract, so a stored 0.20 extract must re-extract."""
    assert eic_needs_reextraction(5.0, 0.20, 5.0, 0.18, 0.05) is True
    assert eic_needs_reextraction(5.0, 0.28, 5.0, 0.18, 0.05) is False
    assert eic_needs_reextraction(5.0, 0.20, 5.0, 0.10, 0.10) is False

    _seed_compound_with_neighbour(samples=(("S1", 0.20, 100.0),))
    assert samples_needing_reextraction("Target", {"S1": (5.0, 0.18, 0.05)}) == ["S1"]

    widget = IntegrationWindow()
    widget.populate_fields_from_plots("Target", ["S1"], ["S1"])
    widget.populate_tr_window_field("Target")
    regen = []
    widget.data_regeneration_requested.connect(lambda *args: regen.append(args))

    widget.findChild(QLineEdit, "lo_input").setText("0.18")
    widget.apply_button.click()

    assert regen == [("Target", pytest.approx(0.28), ["S1"], 5.0)]
    widget.deleteLater()


def test_narrowing_tr_window_redraws_without_reextracting_and_remembers_zoom(qapp):
    _seed_compound_with_neighbour(samples=(("S1", 0.2, 10000.0),))
    widget = IntegrationWindow()
    widget.populate_fields_from_plots("Target", [], ["S1"])
    widget.populate_tr_window_field("Target")
    regen, zoomed = [], []
    widget.data_regeneration_requested.connect(lambda *args: regen.append(args))
    widget.display_window_changed.connect(lambda *args: zoomed.append(args))

    # Narrow inside stored 0.2 extract -> instant display zoom, no regeneration.
    widget.tr_window_edit.setText("0.1")
    widget.regenerate_button.click()

    assert regen == []
    assert zoomed == [("Target", pytest.approx(0.1))]
    assert widget.display_window_for("Target") == pytest.approx(0.1)
    assert not widget.has_window_draft()

    # Stored extract in DB stays untouched at 0.2.
    with database.get_connection() as conn:
        stored = conn.execute(
            "SELECT rt_window FROM eic WHERE compound_name = 'Target' AND sample_name = 'S1'"
        ).fetchone()[0]
    assert stored == pytest.approx(0.2)

    # Below display floor (max(0.05, 0.05) + 0.02 = 0.07) clamps up to 0.07.
    widget.tr_window_edit.setText("0.03")
    widget.regenerate_button.click()
    assert regen == []
    assert zoomed[-1] == ("Target", pytest.approx(0.07))
    assert widget.tr_window_edit.text() == "0.07"

    # Re-populating remembers the compound's narrowed display window.
    widget.populate_tr_window_field("Target")
    assert widget.tr_window_edit.text() == "0.07"
    widget.deleteLater()


def test_narrowing_ignores_shown_sample_without_eic_row(qapp):
    """S6: a shown sample with no stored EIC row must not turn a zoom into a CDF reload."""
    _seed_compound_with_neighbour(samples=(("S1", 0.2, 100.0),))
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO samples (sample_name, file_name) VALUES ('S_missing', '/fake/missing.cdf')"
        )
        conn.commit()
    widget = IntegrationWindow()
    widget.populate_fields_from_plots("Target", [], ["S1", "S_missing"])
    widget.populate_tr_window_field("Target")
    regen, zoomed = [], []
    widget.data_regeneration_requested.connect(lambda *args: regen.append(args))
    widget.display_window_changed.connect(lambda *args: zoomed.append(args))

    widget.tr_window_edit.setText("0.1")
    widget.regenerate_button.click()

    assert regen == []
    assert zoomed == [("Target", pytest.approx(0.1))]
    widget.deleteLater()


def test_display_floor_uses_all_shown_samples_even_when_narrow_sample_selected(qapp):
    """S7: selecting a narrow-offset sample must not let Apply window clamp below another shown sample's offset."""
    _seed_compound_with_neighbour(
        samples=(("S1", 0.5, 100.0), ("S2", 0.5, 100.0)),
    )
    SessionActivityService.update_session_data("Target", ["S2"], 5.0, 0.3, 0.3)

    widget = IntegrationWindow()
    widget.populate_fields_from_plots("Target", ["S1"], ["S1", "S2"])
    widget.populate_tr_window_field("Target")
    regen, zoomed = [], []
    widget.data_regeneration_requested.connect(lambda *args: regen.append(args))
    widget.display_window_changed.connect(lambda *args: zoomed.append(args))

    widget.tr_window_edit.setText("0.07")
    widget.regenerate_button.click()

    assert regen == []
    assert zoomed == [("Target", pytest.approx(0.32))]
    assert widget.tr_window_edit.text() == "0.32"
    widget.deleteLater()


def test_widening_mixed_windows_reextracts_only_narrow_samples(qapp):
    _seed_compound_with_neighbour(
        samples=(("S1", 0.8, 100.0), ("S2", 0.3, 100.0)),
    )
    widget = IntegrationWindow()
    widget.populate_fields_from_plots("Target", [], ["S1", "S2"])
    widget.populate_tr_window_field("Target")
    regen, zoomed = [], []
    widget.data_regeneration_requested.connect(lambda *args: regen.append(args))
    widget.display_window_changed.connect(lambda *args: zoomed.append(args))

    # 0.5 is already covered by S1 (0.8), so only S2 (0.3) reloads.
    widget.tr_window_edit.setText("0.5")
    widget.regenerate_button.click()

    assert zoomed == []
    assert regen == [("Target", pytest.approx(0.5), ["S2"], 5.0)]
    assert widget.take_pending_display_window() == ("Target", pytest.approx(0.5))
    widget.deleteLater()


def test_apply_preserves_mixed_stored_extracts_when_display_window_is_set(qapp):
    """S5: with mixed stored extracts (0.8, 0.3) and display 0.1, a tR shift keeps {S1: 0.8, S2: 0.3}."""
    _seed_compound_with_neighbour(
        samples=(("S1", 0.8, 100.0), ("S2", 0.3, 100.0)),
    )
    widget = IntegrationWindow()
    widget.populate_fields_from_plots("Target", ["S1", "S2"], ["S1", "S2"])
    widget.populate_tr_window_field("Target")
    regen = []
    widget.data_regeneration_requested.connect(lambda *args: regen.append(args))

    widget.tr_window_edit.setText("0.1")
    widget.regenerate_button.click()
    assert widget.display_window_for("Target") == pytest.approx(0.1)

    widget.findChild(QLineEdit, "tr_input").setText("5.05")
    widget.apply_button.click()

    assert regen == [
        ("Target", {"S1": pytest.approx(0.8), "S2": pytest.approx(0.3)}, ["S1", "S2"], 5.05)
    ]
    widget.deleteLater()


def test_apply_clamps_narrowed_display_window_and_preserves_wider_stored_extract(qapp):
    _seed_compound_with_neighbour(samples=(("S1", 0.6, 100.0),))
    widget = IntegrationWindow()
    widget.populate_fields_from_plots("Target", ["S1"], ["S1"])
    widget.populate_tr_window_field("Target")
    regen = []
    widget.data_regeneration_requested.connect(lambda *args: regen.append(args))

    # Zoom display down to 0.10 (stored extract stays 0.6).
    widget.tr_window_edit.setText("0.1")
    widget.regenerate_button.click()
    assert widget.display_window_for("Target") == pytest.approx(0.1)

    # Widen loffset to 0.12 (0.12 + 0.10 = 0.22 <= 0.6 -> no re-extraction) -> display bumps to 0.14.
    widget.findChild(QLineEdit, "lo_input").setText("0.12")
    widget.apply_button.click()
    assert regen == []
    assert widget.display_window_for("Target") == pytest.approx(0.14)
    assert widget.tr_window_edit.text() == "0.14"

    # Shift tR (requires re-extraction) -> stored extract stays 0.6, never shrinks to 0.14.
    widget.findChild(QLineEdit, "tr_input").setText("5.05")
    widget.apply_button.click()
    assert regen == [("Target", pytest.approx(0.6), ["S1"], 5.05)]
    widget.deleteLater()


def test_reset_clamps_narrowed_display_window_up_to_default_offsets(qapp):
    """S10: restoring wider default offsets must bump a narrowed display window so guides stay visible."""
    _seed_compound_with_neighbour(
        samples=(("S1", 0.5, 100.0),),
        loffset=0.2,
        roffset=0.2,
    )
    # Narrow the session override first so we can zoom display to 0.08.
    SessionActivityService.update_session_data("Target", ["S1"], 5.0, 0.05, 0.05)

    widget = IntegrationWindow()
    widget._get_main_window = lambda: SimpleNamespace(_confirm=lambda *a, **k: True)
    widget.populate_fields_from_plots("Target", ["S1"], ["S1"])
    widget.populate_tr_window_field("Target")
    widget.tr_window_edit.setText("0.08")
    widget.regenerate_button.click()
    assert widget.display_window_for("Target") == pytest.approx(0.08)

    # Reset restores default 0.2/0.2 offsets -> display window bumps to 0.22.
    widget.restore_button.click()
    assert widget.display_window_for("Target") == pytest.approx(0.22)
    assert widget.tr_window_edit.text() == "0.22"
    widget.deleteLater()


def test_regenerate_preserves_unlabelled_rt_tolerance_floor(tmp_path, monkeypatch):
    """S10: regenerate_compound_eics must not shrink stored extract below compound rt_tolerance."""
    _seed_compound_with_neighbour(
        samples=(("S1", 0.2, 100.0),),
        loffset=0.05,
        roffset=0.05,
        rt_tolerance=0.45,
    )
    cdf_file = tmp_path / "S1.cdf"
    cdf_file.write_bytes(b"")
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE samples SET file_name = ? WHERE sample_name = 'S1'",
            (str(cdf_file),),
        )
        conn.commit()
    captured = []
    monkeypatch.setattr(
        "manic.io.eic_importer.read_cdf_file",
        lambda _path, _rt_range=None: SimpleNamespace(sample_name="S1"),
    )

    def _stub_extract(_name, rt, _mz, _cdf, _mass_tol, tr_window, *_a, **_k):
        captured.append(tr_window)
        t = np.linspace(rt - tr_window, rt + tr_window, 21)
        return SimpleNamespace(time=t, intensity=np.ones_like(t))

    monkeypatch.setattr("manic.io.eic_importer.extract_eic", _stub_extract)

    regenerate_compound_eics("Target", 0.2, ["S1"], retention_time=5.0)
    assert captured == [pytest.approx(0.45)]


def test_busy_and_failed_regeneration_discard_pending_display_window(qapp, monkeypatch):
    """S10: a refused or failed regeneration on a real MainWindow must discard pending display zoom."""
    _seed_compound_with_neighbour(samples=(("S1", 0.2, 100.0),))
    window = _make_window(monkeypatch)
    monkeypatch.setattr(
        window,
        "_create_message_box",
        lambda *a, **k: mock.Mock(exec=lambda: None),
    )
    integration = window.toolbar.integration
    integration.populate_fields_from_plots("Target", ["S1"], ["S1"])
    integration.populate_tr_window_field("Target")

    # Busy regeneration refuses and discards the pending display window.
    monkeypatch.setattr(window, "_running_background_thread", lambda: "_regen_thread")
    window._regen_worker = SimpleNamespace(pending_regeneration=None)
    integration._pending_display_window = ("Target", 0.5)
    window.on_data_regeneration_requested("Target", 0.5, ["S1"], 5.0)
    assert integration.take_pending_display_window() is None
    assert integration.display_window_for("Target") is None

    # Failed regeneration discards both active and pending display windows.
    window._active_regen_display_window = ("Target", 0.6)
    integration._pending_display_window = ("Target", 0.6)
    window._regeneration_failed("boom")
    assert window._active_regen_display_window is None
    assert integration.take_pending_display_window() is None
    assert integration.display_window_for("Target") is None
    window.close()


def test_graph_view_zooms_x_axis_and_scales_y_axis_to_visible_range(qapp):
    _seed_compound_with_neighbour(
        samples=(("S1", 0.2, 10000.0), ("S2", 0.2, 50.0)),
    )
    gv = GraphView()
    gv.plot_compound("Target", ["S1", "S2"])
    x_full = gv._current_plots[0].chart().axes()[0]
    assert x_full.min() == pytest.approx(4.8, abs=1e-3)
    assert x_full.max() == pytest.approx(5.2, abs=1e-3)
    # Giant neighbour at 5.16 dominates full-extract scale (~1e4).
    assert gv._current_plots[0].parent().scale_label.text() == "×10⁴"

    # Narrow display to 0.1 -> excludes neighbour at 5.16; y-axis scales to target (~1e2).
    gv.set_display_tr_window("Target", 0.1)
    gv.plot_compound("Target", ["S1", "S2"])
    x_zoom = gv._current_plots[0].chart().axes()[0]
    assert x_zoom.min() == pytest.approx(4.9, abs=1e-3)
    assert x_zoom.max() == pytest.approx(5.1, abs=1e-3)
    assert gv._current_plots[0].parent().scale_label.text() == "×10²"

    # Shared Y also scales to the visible range rather than the hidden neighbour.
    gv.set_y_scale_policy(YScalePolicy.SHARED_EXTRACT)
    assert gv._current_plots[0].parent().scale_label.text() == "×10²"
    assert gv._current_plots[1].parent().scale_label.text() == "×10²"
    gv.deleteLater()


def test_tile_y_scale_slices_to_x_bounds():
    t = np.linspace(4.8, 5.2, 201)
    y = _gaussian(t, 5.0, 0.015, 100.0) + _gaussian(t, 5.16, 0.012, 10000.0)
    compound = type(
        "C",
        (),
        {
            "retention_time": 5.0,
            "loffset": 0.05,
            "roffset": 0.05,
            "deconvolution_level": "off",
            "is_unlabelled_target": False,
        },
    )()
    prepared = plot_display(t, y, compound, use_corrected=False)
    full_scale = axes_for_tiles(
        YScalePolicy.PER_TILE_EXTRACT,
        [TileScaleInput(prepared, y, False, time=t, x_bounds=None)],
    )[0]
    zoom_scale = axes_for_tiles(
        YScalePolicy.PER_TILE_EXTRACT,
        [TileScaleInput(prepared, y, False, time=t, x_bounds=(4.9, 5.1))],
    )[0]
    assert full_scale.unscaled_max > 9000.0
    assert zoom_scale.unscaled_max == pytest.approx(100.0, rel=1e-2)
