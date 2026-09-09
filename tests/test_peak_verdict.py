from manic.validation.peak_verdict import PeakReview, PeakVerdict, resolve_verdict


def test_resolve_verdict_combinations():
    cases = [
        (True, None, PeakVerdict.PASS),
        (False, None, PeakVerdict.FAIL),
        (True, PeakReview.ACCEPTED, PeakVerdict.ACCEPTED),
        (False, PeakReview.ACCEPTED, PeakVerdict.ACCEPTED),
        (True, PeakReview.REJECTED, PeakVerdict.REJECTED),
        (False, PeakReview.REJECTED, PeakVerdict.REJECTED),
    ]
    assert [(t, r, resolve_verdict(t, r)) for t, r, _ in cases] == cases
