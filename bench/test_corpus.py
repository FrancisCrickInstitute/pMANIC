from __future__ import annotations

from conftest import FULL_WINDOWS, HARD_SCENARIOS


def test_corpus_covers_every_hard_scenario(case):
    keys = case.corpus_keys(FULL_WINDOWS)
    assert len(keys) == FULL_WINDOWS
    assert len(set(keys)) == FULL_WINDOWS
    scenarios = {
        (t["sample"], t["compound"]): set(t["scenarios"]) for t in case.manifest["truths"]
    }
    for scenario in HARD_SCENARIOS:
        assert any(scenario in scenarios[k] for k in keys), scenario
