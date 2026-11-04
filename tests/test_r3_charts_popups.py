import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocumentFragment
from PySide6.QtWidgets import QLabel

from manic.models.analysis import IonChannel, IonRole
from manic.ui.chart_popup_dialog import ChartPopupDialog, bar_value_text
from manic.ui.targeted_qc_widget import TargetedQcWidget
from manic.validation.unlabelled_identity import (
    IdentityAssessmentSet,
    IdentityQcResult,
    IdentitySampleAssessment,
    IdentityStatus,
    QualifierRatioResult,
    qualifier_pair,
)


def test_bar_value_text_uses_one_precision():
    assert bar_value_text(0.9104) == "0.91"
    assert bar_value_text(1.0) == "1.00"
    assert bar_value_text(6.22e-05) == "<0.01"
    assert bar_value_text(0.0) == "—"
    assert bar_value_text(float("nan")) == "—"


def _abundance_popup(values, names):
    return ChartPopupDialog(
        "total_abundance", "Total Abundance", np.array(values), names, compound_name="Valine"
    )


def test_abundance_popup_puts_each_value_beside_its_own_sample(qapp):
    dialog = _abundance_popup([9100.0, 0.6, 0.0, 11300.0], ["A", "B", "C", "D"])
    try:
        y_axis = dialog.chart.axes(Qt.Vertical)[0]
        bar_set = dialog.chart.series()[0].barSets()[0]
        by_name = {
            name: bar_set.at(index) for index, name in enumerate(y_axis.categories())
        }
        assert by_name["A"] == 0.91
        assert by_name["D"] == 1.13
        assert by_name["C"] == 0.0
        # Names arrive bottom to top, as the sidebar chart draws them.
        assert dialog.row_names() == ["D", "C", "B", "A"]
        assert dialog.value_label_texts() == ["1.13", "—", "<0.01", "0.91"]
    finally:
        dialog.deleteLater()


def _hints(dialog) -> list[str]:
    return [label.text() for label in dialog.findChildren(QLabel) if "Hover" in label.text()]


def test_hover_hint_only_where_values_are_not_printed(qapp):
    abundance = _abundance_popup([1.0, 2.0], ["A", "B"])
    ratios = ChartPopupDialog(
        "isotopologue_ratios", "Label Incorporation", np.array([[0.6, 0.4], [0.5, 0.5]]), ["A", "B"]
    )
    try:
        assert _hints(abundance) == []
        assert _hints(ratios) == ["Hover a bar for its value"]
    finally:
        abundance.deleteLater()
        ratios.deleteLater()


def _identity() -> IdentityAssessmentSet:
    q_ion = IonChannel(217.0, IonRole.QUANTIFIER)
    v1 = IonChannel(147.0, IonRole.QUALIFIER, ordinal=1, expected_ratio=0.4, ratio_tolerance=0.25)
    channels = (q_ion, v1)

    def qc(passed: bool) -> IdentityQcResult:
        return IdentityQcResult(
            status=IdentityStatus.SUPPORTED if passed else IdentityStatus.REVIEW_REQUIRED,
            quantifier_area=100.0,
            observed_rt=1.2,
            rt_error=0.0,
            rt_passed=True,
            qualifier_ratios=(QualifierRatioResult(v1, 0.41 if passed else 0.9, passed),),
            reasons=(),
        )

    samples = tuple(
        IdentitySampleAssessment(name, result, qualifier_pair(channels, result, error=None), None)
        for name, result in (("S1", qc(True)), ("S2", qc(False)), ("S3", qc(False)))
    )
    return IdentityAssessmentSet("Target", channels, samples)


def test_identity_counts_name_their_units_and_grey_states(qapp):
    widget = TargetedQcWidget()
    try:
        widget.update_results(_identity())
        assert widget.header.detail.text() == "2 samples failed"
        key = widget.key.text()
        assert QTextDocumentFragment.fromHtml(key).toPlainText().startswith("Qualifier cells")
        assert "Validated&nbsp;<b>1</b>" in key
        assert "Failed&nbsp;<b>2</b>" in key
        assert "–&nbsp;Absent&nbsp;<b>3</b>" in key and "No verdict" not in key
        assert widget.key.toolTip() == (
            "Counts are qualifier cells: one per sample for each qualifier ion.\n"
            "No verdict (grey): 3 absent, 0 not assessed, 0 unavailable."
        )
    finally:
        widget.deleteLater()
