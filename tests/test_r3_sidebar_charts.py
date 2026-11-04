from types import SimpleNamespace

import numpy as np

from manic.ui.isotopologue_ratio_widget import IsotopologueRatioWidget
from manic.ui.total_abundance_widget import TotalAbundanceWidget


def _eics(names):
    return [
        SimpleNamespace(sample_name=name, intensity=np.zeros((3, 4)), time=np.zeros(4))
        for name in names
    ]


def test_mini_charts_pair_each_sample_with_its_own_values(qapp, monkeypatch):
    names = ["S1", "S2", "S3"]
    ratios = np.array([[0.9, 0.1, 0.0], [0.5, 0.3, 0.2], [0.2, 0.2, 0.6]])
    totals = np.array([100.0, 2000.0, 30000.0])
    ratio_chart = IsotopologueRatioWidget()
    abundance_chart = TotalAbundanceWidget()
    monkeypatch.setattr(
        ratio_chart, "_calculate_integrated_data", lambda eics, _name: (ratios, totals)
    )
    try:
        eics = _eics(names)
        ratio_chart.update_ratios("Cmp", eics)
        abundances, shared = ratio_chart.get_last_total_abundances()
        abundance_chart.update_abundance_from_data("Cmp", shared, abundances)

        # Top bar first in both charts, which is the first sample.
        top = len(names) - 1
        assert ratio_chart.hover_text(top) == "S1\nM+0  90.0%\nM+1  10.0%\nM+2  0.0%"
        assert abundance_chart.hover_text(top) == "S1\nTotal abundance  100"
        assert abundance_chart.hover_text(0) == "S3\nTotal abundance  3e+04"
        assert [e.sample_name for e in eics] == names

        assert ratio_chart.key.isVisibleTo(ratio_chart)
        key = ratio_chart.key.text()
        assert [label in key for label in ("M+0", "M+1", "M+2", "M+3")] == [
            True,
            True,
            True,
            False,
        ]
    finally:
        ratio_chart.deleteLater()
        abundance_chart.deleteLater()
