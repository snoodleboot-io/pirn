"""Overhead micro-benchmark for trajectory capture (F29-S3).

Marked ``@pytest.mark.benchmark`` (registered in ``pyproject.toml``). It measures
wall-clock directly with :func:`time.perf_counter` and asserts capture overhead is
small in absolute terms, proving append-only capture is cheap. The measured figure
is printed in the ``[benchmark] <name> k=v`` format the F10 report harvester parses.
"""

from __future__ import annotations

import time

import pytest

from pirn_agents.determinism.frozen_clock import FrozenClock
from pirn_agents.determinism.trace_event_kind import TraceEventKind
from pirn_agents.determinism.trajectory_recorder import TrajectoryRecorder


@pytest.mark.benchmark
def test_capture_overhead_is_negligible() -> None:
    n = 20000
    recorder = TrajectoryRecorder(run_id="bench", clock=FrozenClock())

    start = time.perf_counter()
    for i in range(n):
        recorder.record(kind=TraceEventKind.TOOL_CALL, name="t", payload={"i": i})
    elapsed = time.perf_counter() - start

    assert recorder.event_count == n
    # 20k append-only captures must be well under a second on any CI host.
    assert elapsed < 1.0

    throughput = n / elapsed if elapsed > 0 else float("inf")
    print(
        f"[benchmark] TrajectoryCapture N={n} wall={elapsed:.4f}s throughput={throughput:.1f} ev/s"
    )


if __name__ == "__main__":
    test_capture_overhead_is_negligible()
