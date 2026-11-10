"""The fit workers must not outlive the app (they are separate processes)."""

import subprocess
import sys

APP = """
import os
from manic.processors import fit_prefetch

if __name__ == "__main__":
    pool = fit_prefetch.start_pool()
    list(pool.map(abs, range(64)))  # every worker is up and has served a call
    print(len(pool._processes), flush=True)
    os._exit(1)  # die as a crash or a force-quit does: no clean interpreter exit
"""


def test_fit_workers_exit_when_the_app_dies_without_a_clean_exit(tmp_path):
    script = tmp_path / "app.py"
    script.write_text(APP)
    # The workers inherit the output pipe, so this returns only once all of them have
    # exited; left running, they hold it open and the timeout fails the test.
    out = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=30
    )
    assert int(out.stdout) > 0, out.stderr
