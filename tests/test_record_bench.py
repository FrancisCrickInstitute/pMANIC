import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from record_bench import record


def _run(tmp_path, dirty=False):
    def bench(name, median, rounds):
        return {"name": name, "stats": {"median": median, "rounds": rounds}}

    path = tmp_path / "run.json"
    path.write_text(
        json.dumps(
            {
                "datetime": "2026-11-10T12:18:02.234044+00:00",
                "commit_info": {"id": "510ce490e95f7d6f", "dirty": dirty},
                "machine_info": {"node": "secret-host"},
                "benchmarks": [
                    bench("test_plot_next[labelled-nav-001]-isoleucine", 0.002, 3),
                    bench("test_export[labelled]", 21.42134, 3),
                    bench("test_plot_next[labelled-nav-002]-threonine", 0.004, 2),
                ],
            }
        )
    )
    return path


def test_records_one_row_per_action(tmp_path):
    history = tmp_path / "history.tsv"
    record(_run(tmp_path), "Apple M1 Pro, 8 cores", history)
    assert history.read_text() == (
        "date\tcommit\tmachine\taction\tmedian_ms\trounds\n"
        "2026-11-10\t510ce490\tApple M1 Pro, 8 cores\tplot_next\t3.0\t2\n"
        "2026-11-10\t510ce490\tApple M1 Pro, 8 cores\texport\t21421.3\t3\n"
    )


def test_refuses_dirty_and_repeated_runs(tmp_path):
    history = tmp_path / "history.tsv"
    with pytest.raises(ValueError, match="dirty"):
        record(_run(tmp_path, dirty=True), "m", history)
    assert not history.exists()
    record(_run(tmp_path), "m", history)
    with pytest.raises(ValueError, match="already recorded"):
        record(_run(tmp_path), "m", history)
    assert len(history.read_text().splitlines()) == 3
