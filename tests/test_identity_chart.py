from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
)
from shiboken6 import isValid

from manic.models.analysis import IonChannel, IonRole
from manic.ui.targeted_qc_widget import TargetedQcWidget
from manic.validation.unlabelled_identity import (
    IdentityAssessmentSet,
    IdentityQcResult,
    IdentitySampleAssessment,
    IdentityStatus,
    QualifierRatioResult,
    qualifier_pair,
)

Q_ION = IonChannel(217.0, IonRole.QUANTIFIER)
V1 = IonChannel(147.0, IonRole.QUALIFIER, ordinal=1, expected_ratio=0.4, ratio_tolerance=0.25)
V2 = IonChannel(73.0, IonRole.QUALIFIER, ordinal=2, expected_ratio=0.2, ratio_tolerance=0.25)
LONG = [f"Sample_{i:02d}" for i in range(30)]


def _qualifier(ordinal, ratio=None, tolerance=None):
    return IonChannel(
        100.0 + ordinal, IonRole.QUALIFIER, ordinal=ordinal,
        expected_ratio=ratio, ratio_tolerance=tolerance,
    )


def _identity(names, *, failed=(), qualifiers=(V1,)) -> IdentityAssessmentSet:
    """``names`` top to bottom; checkable qualifiers pass, or fail for the ``failed`` samples."""
    channels = (Q_ION, *qualifiers)

    def qc(passed: bool) -> IdentityQcResult:
        return IdentityQcResult(
            status=IdentityStatus.SUPPORTED if passed else IdentityStatus.REVIEW_REQUIRED,
            quantifier_area=100.0,
            observed_rt=7.0,
            rt_error=0.0,
            rt_passed=True,
            qualifier_ratios=tuple(
                QualifierRatioResult(
                    q,
                    0.41 if passed else 0.9,
                    passed if q.expected_ratio is not None and q.ratio_tolerance is not None else None,
                )
                for q in qualifiers
            ),
            reasons=(),
        )

    samples = []
    for name in names:
        result = qc(name not in failed)
        samples.append(IdentitySampleAssessment(name, result, qualifier_pair(channels, result), None))
    return IdentityAssessmentSet("Pyruvate", channels, tuple(samples))


LONG_A = "2026_GCMS_Experiment_17_Batch_04_Replicate_01_very_long_sample_name_Bio_017"
LONG_B = "2026_GCMS_Experiment_17_Batch_04_Replicate_01_very_long_sample_name_Bio_018"
# Top to bottom: two names too long for any chart, then one that fits.
TIP_NAMES = [LONG_A, LONG_B, "S3"]
_A_STATES = f"{LONG_A}\nQualifier 1  Validated\nQualifier 2  Validated"
_A_CELL_1 = f"{LONG_A}\nQualifier 1  Validated\nexpected 0.400  ±25%  observed 0.410"
_A_CELL_2 = f"{LONG_A}\nQualifier 2  Validated\nexpected 0.200  ±25%  observed 0.410"
# The tip each surface shows over each place; None where it shows none.
TIPS = {
    "summary identity": {
        ("name", LONG_A): _A_STATES,
        ("name", LONG_B): f"{LONG_B}\nQualifier 1  Failed\nQualifier 2  Failed",
        ("name", "S3"): "S3\nQualifier 1  Validated\nQualifier 2  Validated",
        ("cell", 1): _A_CELL_1,
        ("cell", 2): _A_CELL_2,
        ("new data",): f"{LONG_A}\nQualifier 1  Failed\nQualifier 2  Failed",
    },
    "popup identity": {
        ("name", LONG_A): LONG_A,
        ("name", LONG_B): LONG_B,
        ("name", "S3"): None,
        ("cell", 1): _A_CELL_1,
        ("cell", 2): _A_CELL_2,
    },
    "summary peak area": {
        ("name", LONG_A): f"{LONG_A}\nPeak area  3e+06",
        ("name", LONG_B): f"{LONG_B}\nPeak area  2e+06",
        ("name", "S3"): "S3\nPeak area  1e+06",
        ("cell", 1): f"{LONG_A}\nPeak area  3e+06",
        ("new data",): f"{LONG_A}\nPeak area  136",
    },
    "popup peak area": {
        ("name", LONG_A): LONG_A,
        ("name", LONG_B): LONG_B,
        ("name", "S3"): None,
        ("cell", 1): LONG_A,
    },
}
# Each case is a path; only its last step is the transition under test.
TRANSITIONS = {
    "enter name": [("name", LONG_A)],
    "enter cell": [("cell", 1)],
    "cell to same-row name": [("cell", 1), ("name", LONG_A)],
    "cell to other-row name": [("cell", 1), ("name", LONG_B)],
    "cell to neighbour cell": [("cell", 1), ("cell", 2)],
    "name to cell": [("name", LONG_A), ("cell", 1)],
    "back onto the cell before the last tip fades": [("cell", 1), ("name", "S3"), ("cell", 1)],
    "1 px along the name after a cell": [("cell", 1), ("name", LONG_A), ("nudge", LONG_A)],
    "leave the chart": [("name", LONG_A), ("leave",)],
    "close": [("cell", 1), ("close",)],
    "new data under the pointer": [("name", LONG_A), ("new data",)],
    "data cleared under the pointer": [("name", LONG_A), ("no data",)],
}


def test_identity_popup_row_selects_the_sample_through_the_qc_widget(qapp):
    widget = TargetedQcWidget()
    activated = []
    widget.sample_activated.connect(activated.append)
    seen = {}

    def drive():
        dialog = QApplication.activeModalWidget()
        if dialog is None or QApplication.focusWidget() is None:
            QTimer.singleShot(10, drive)
            return
        seen["rows"] = dialog.row_names()
        seen["dialog"] = dialog
        QTest.keyClick(QApplication.focusWidget(), Qt.Key_Up)
        QTest.keyClick(QApplication.focusWidget(), Qt.Key_Enter)

    # Closes a popup the keys never reached, so a failure cannot hang the run.
    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(lambda: QApplication.activeModalWidget().reject())
    try:
        widget.update_results(_identity(["S1", "S2"], failed=("S2",)))
        QTimer.singleShot(0, drive)
        watchdog.start(5000)
        widget.header.expand_button.click()
        assert seen["rows"] == ["S1", "S2"]
        assert activated == ["S2"]
        assert not isValid(seen["dialog"])
    finally:
        watchdog.stop()
        widget.deleteLater()


