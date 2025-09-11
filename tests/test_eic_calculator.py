import numpy as np

from manic.io.cdf_reader import CdfFileData
from manic.processors.eic_calculator import extract_eic


def make_cdf(sample_name="S1"):
    # Three scans, each with 3 masses (target, +1, +2)
    scan_time = np.array([60.0, 70.0, 80.0])  # seconds
    mass = np.array([
        100.0, 101.0, 102.0,  # scan 0
        100.0, 101.0, 102.0,  # scan 1
        100.0, 101.0, 102.0,  # scan 2
    ])
    # Intensities per mass per scan: simple increasing pattern
    intensity = np.array([
        10.0, 4.0, 2.0,   # scan 0
        20.0, 8.0, 4.0,   # scan 1
        30.0, 12.0, 6.0,  # scan 2
    ])
    scan_index = np.array([0, 3, 6])
    point_count = np.array([3, 3, 3])
    total_intensity = np.array([16.0, 32.0, 48.0])
    return CdfFileData(
        sample_name=sample_name,
        file_path=f"/fake/{sample_name}.cdf",
        scan_time=scan_time,
        mass=mass,
        intensity=intensity,
        scan_index=scan_index,
        point_count=point_count,
        total_intensity=total_intensity,
    )


def test_extract_eic_labeled_three_isotopologues():
    cdf = make_cdf()
    eic = extract_eic(
        compound_name="TestCmp",
        t_r=1.2,              # minutes (72 sec)
        target_mz=100.0,
        cdf=cdf,
        mass_tol=0.5,
        rt_window=0.5,        # includes all three scans
        label_atoms=2,        # M+0, M+1, M+2
    )

    # time returns minutes
    assert np.allclose(eic.time, cdf.scan_time / 60.0)
    # intensity is flattened 2D array: shape (3 isotopologues, 3 scans) raveled
    inten_2d = eic.intensity.reshape(3, -1)
    # sums per scan for each isotopologue should match our inputs at each scan
    # For our construction, summing within mass tol per scan is just the single point
    assert np.allclose(inten_2d[0], [10.0, 20.0, 30.0])  # M+0 @ 100.0
    assert np.allclose(inten_2d[1], [4.0, 8.0, 12.0])   # M+1 @ 101.0
    assert np.allclose(inten_2d[2], [2.0, 4.0, 6.0])    # M+2 @ 102.0

