"""O(1) lookup micro-benchmark for :class:`ToolRegistry` (S4).

Marked ``@pytest.mark.benchmark``. It registers a large number of tools and
asserts that a single lookup does not scale with registry size: the mean lookup
time on a large registry stays within a small multiple of the time on a tiny
one, which a linear scan could not achieve. Wall-clock is measured with
:func:`time.perf_counter`; bounds are loose to stay non-flaky. Figures are
printed for an F10-style report to harvest.
"""

from __future__ import annotations

import time

import pytest

from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tool_registry import ToolRegistry


def _mean_lookup_seconds(registry: ToolRegistry, name: str, iterations: int) -> float:
    start = time.perf_counter()
    for _ in range(iterations):
        registry.get(name, namespace="bench")
    return (time.perf_counter() - start) / iterations


@pytest.mark.benchmark
def test_lookup_is_constant_time() -> None:
    iterations = 20_000

    small = ToolRegistry(mirror_to_sweet_tea=False)
    for i in range(10):
        small.register(StubTool(name=f"t{i}"), namespace="bench", version="1.0.0")

    large = ToolRegistry(mirror_to_sweet_tea=False)
    for i in range(50_000):
        large.register(StubTool(name=f"t{i}"), namespace="bench", version="1.0.0")

    # Look up the last-registered name in each so a linear scan would be worst-case.
    small_mean = _mean_lookup_seconds(small, "t9", iterations)
    large_mean = _mean_lookup_seconds(large, "t49999", iterations)

    assert len(large) == 50_000
    # O(1): a 5000x larger registry must not make lookup meaningfully slower.
    assert large_mean < 5.0 * small_mean + 1e-6

    print(
        f"[benchmark] ToolRegistry lookup small(N=10)={small_mean * 1e9:.1f}ns "
        f"large(N=50000)={large_mean * 1e9:.1f}ns "
        f"ratio={large_mean / small_mean:.2f}x"
    )


if __name__ == "__main__":
    test_lookup_is_constant_time()
