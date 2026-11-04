from manic.models.analysis import IonChannel, IonRole
from manic.ui.chart_popup_dialog import ChartPopupDialog
from manic.ui.identity_chart import (
    MISSING_RATIO_STEP,
    MISSING_TOLERANCE_STEP,
    identity_unassessed_note,
)
from manic.ui.targeted_qc_widget import TargetedQcWidget
from manic.validation.unlabelled_identity import (
    IdentityAssessmentSet,
    IdentityQcResult,
    IdentitySampleAssessment,
    IdentityStatus,
    QualifierRatioResult,
    qualifier_pair,
)

Q_ION = IonChannel(174.0, IonRole.QUANTIFIER)


def _qualifier(ordinal, ratio=None, tolerance=None):
    return IonChannel(
        100.0 + ordinal, IonRole.QUALIFIER, ordinal=ordinal,
        expected_ratio=ratio, ratio_tolerance=tolerance,
    )


def _identity(*qualifiers, names=("S1",)) -> IdentityAssessmentSet:
    qc = IdentityQcResult(
        status=IdentityStatus.SUPPORTED,
        quantifier_area=100.0,
        observed_rt=7.0,
        rt_error=0.0,
        rt_passed=True,
        qualifier_ratios=tuple(
            QualifierRatioResult(q, 0.41, True if q.expected_ratio and q.ratio_tolerance else None)
            for q in qualifiers
        ),
        reasons=(),
    )
    channels = (Q_ION, *qualifiers)
    samples = tuple(
        IdentitySampleAssessment(name, qc, qualifier_pair(channels, qc), None) for name in names
    )
    return IdentityAssessmentSet("Glycine", channels, samples)


def test_missing_expected_ratio_points_to_the_compound_list_not_settings(qapp):
    note = identity_unassessed_note(_identity(_qualifier(1), _qualifier(2)))
    assert note == MISSING_RATIO_STEP
    assert "compound list" in note and "Settings" not in note


def test_missing_tolerance_alone_points_to_settings(qapp):
    note = identity_unassessed_note(_identity(_qualifier(1, 0.4), _qualifier(2, 0.2)))
    assert note == MISSING_TOLERANCE_STEP
    assert "Settings › Qualifier Ratios" in note.replace("\xa0", " ")
    assert "compound list" not in note


def test_one_missing_ratio_and_one_missing_tolerance_name_both_paths(qapp):
    note = identity_unassessed_note(_identity(_qualifier(1), _qualifier(2, 0.2)))
    assert note == f"{MISSING_RATIO_STEP} {MISSING_TOLERANCE_STEP}"


def test_a_checkable_qualifier_shows_the_grid_not_a_note(qapp):
    assert identity_unassessed_note(_identity(_qualifier(1, 0.4, 0.25), _qualifier(2))) is None


def test_the_popup_chips_name_the_missing_tolerance(qapp):
    dialog = ChartPopupDialog.for_identity(_identity(_qualifier(1, 0.4)))
    try:
        assert dialog.empty_note.text() == MISSING_TOLERANCE_STEP
        assert dialog.ion_legend.labels()[1] == "Qualifier ion 1 m/z 101   expected 0.400  no tolerance"
    finally:
        dialog.deleteLater()


def test_identity_scrolls_a_selected_row_below_the_fold_into_view(qapp):
    names = [f"Sample_{i:02d}" for i in range(30)]
    widget = TargetedQcWidget()
    try:
        widget.update_results(_identity(_qualifier(1, 0.4, 0.25), names=names))
        widget.resize(260, 400)
        widget.show()
        qapp.processEvents()
        bar = widget._scroll.verticalScrollBar()
        assert bar.value() == 0
        widget.set_highlighted(["Sample_25"])
        assert widget.highlighted_rows() == ["Sample_25"]
        mark = widget._marks[0].sceneBoundingRect()
        top = widget.chart_view.mapFromScene(mark.topLeft()).y()
        assert bar.value() <= top and top + mark.height() <= bar.value() + widget._scroll.viewport().height()
    finally:
        widget.deleteLater()
