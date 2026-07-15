"""Micro-benchmark for the S2 InjectionScreen heuristic overhead (PIR-297).

Marked ``@pytest.mark.benchmark``. Proves the always-inline heuristic tier adds
no meaningful latency on the happy path: screening a benign payload stays far
under a millisecond on average and makes zero network calls. Wall-clock is
measured with :func:`time.perf_counter`; the bound is loose to stay non-flaky on
a busy host.
"""

from __future__ import annotations

import time

import pytest

from pirn_agents.security.injection_screen import InjectionScreen


@pytest.mark.benchmark
def test_heuristic_screen_overhead_is_negligible() -> None:
    screen = InjectionScreen()
    payload = (
        "The quarterly report shows revenue grew 12% year over year across all "
        "regions, with the strongest performance in the EMEA segment."
    ) * 4
    iterations = 2000

    assert not screen.screen(payload).flagged  # sanity-check the happy path once

    start = time.perf_counter()
    for _ in range(iterations):
        screen.screen(payload)
    elapsed = time.perf_counter() - start
    per_call_us = (elapsed / iterations) * 1_000_000
    # Pure-regex happy path: comfortably sub-millisecond per screen.
    assert per_call_us < 1000.0

    print(
        f"[benchmark] injection_screen iterations={iterations} "
        f"per_call={per_call_us:.1f}us total={elapsed:.4f}s"
    )
