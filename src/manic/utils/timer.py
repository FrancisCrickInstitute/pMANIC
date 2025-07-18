import logging
import time
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)


@contextmanager
def measure_time(label: str) -> Generator[None, None, None]:
    """
    Context manager to measure time for a code block using time.perf_counter.

    Usage:
    with measure_time("Database fetch"):
        # Code to time
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.info(f"Time for {label}: {elapsed_time:.6f} seconds")


"""
# Exampe Usage:
with measure_time("calculation"):
    for i in range(100_000):
        _ = i * i
"""
