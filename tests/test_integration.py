import numpy as np

from manic.processors.integration import integrate_peak, calculate_peak_areas


def test_integrate_peak_time_based_vs_legacy():
    # Non-uniform time spacing to distinguish methods
    time = np.array([0.0, 0.2, 0.7, 1.5, 2.0])
    inten = np.array([1.0, 1.0, 1.0, 1.0, 1.0])

    time_based = integrate_peak(inten, time, use_legacy=False)
    legacy = integrate_peak(inten, time, use_legacy=True)

    # Time-based should equal last_time - first_time (all ones): 2.0
    assert abs(time_based - 2.0) < 1e-9
    # Legacy integrates assuming unit spacing (sum trapezoid with unit dx) ~ len-1
    assert abs(legacy - 4.0) < 1e-9


def test_calculate_peak_areas_unlabeled_with_bounds():
    time = np.linspace(0.0, 10.0, 101)  # step 0.1
    inten = np.ones_like(time)

    areas = calculate_peak_areas(
        time,
        inten,
        label_atoms=0,
        retention_time=5.0,
        loffset=1.0,
        roffset=1.0,
        use_legacy=False,
    )

    # Window size is 2.0 minutes, intensity 1.0
    assert len(areas) == 1
    assert abs(areas[0] - 2.0) < 1e-2


def test_calculate_peak_areas_labeled_three_isotopologues():
    time = np.linspace(0.0, 10.0, 11)
    n = len(time)
    # 3 isotopologues flattened: intensities 1, 2, 3
    inten = np.concatenate([
        np.ones(n),
        np.ones(n) * 2,
        np.ones(n) * 3,
    ])

    areas = calculate_peak_areas(
        time,
        inten,
        label_atoms=2,
        retention_time=5.0,
        loffset=5.0,
        roffset=5.0,
        use_legacy=False,
    )

    # Full window; trapezoid integral over 0..10 for constant intensities
    expected_width = time[-1] - time[0]
    assert len(areas) == 3
    assert abs(areas[0] - 1.0 * expected_width) < 1e-9
    assert abs(areas[1] - 2.0 * expected_width) < 1e-9
    assert abs(areas[2] - 3.0 * expected_width) < 1e-9

