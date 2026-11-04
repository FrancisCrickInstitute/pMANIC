from PySide6.QtCore import QPoint

from manic.validation.peak_verdict import PeakReview

from test_r3_sidebar_review import _window_with_plots


def _context_menu(view, chart) -> dict[str, object]:
    view._show_context_menu(QPoint(0, 0), chart)
    menu = view._active_context_menu
    entries = {}
    for action in menu.actions():
        if action.menu() is not None:
            entries["fit"] = (action.menu().title(), action.isEnabled())
        elif action.text():
            entries[action.text()] = (action.isEnabled(), action.isChecked())
    menu.close()
    return entries


def _review_menu(window) -> dict[str, object]:
    window.review_menu.aboutToShow.emit()
    entries = {
        action.text(): (action.isEnabled(), action.isChecked())
        for action in (
            window.inspect_action,
            window.show_only_selected_action,
            window.accept_peak_action,
            window.reject_peak_action,
        )
    }
    entries["fit"] = (window.review_fit_menu.title(), window.review_fit_menu.isEnabled())
    return entries


def test_review_menu_and_context_menu_say_the_same_thing(qapp, monkeypatch):
    window, charts, emitted = _window_with_plots(monkeypatch)
    view = window.graph_view
    try:
        view.select_samples(["A", "B", "C"])
        view._focus_index = 0
        review = _review_menu(window)
        context = _context_menu(view, charts["A"])
        assert review == {
            "Inspect A...": (True, False),
            "Show Only 3 Selected Samples": (True, False),
            "Accept Peak (Below Threshold)": (True, False),
            "Mark 3 Peaks as Bad": (True, False),
            "fit": ("Curve Fit for 3 Samples", True),
        }
        assert {key: context[key] for key in review} == review

        window.reject_peak_action.trigger()
        assert emitted == [("Cmp", ["A", "B", "C"], PeakReview.REJECTED)]
    finally:
        window.close()
