"""Time-to-first-output micro-benchmark for streaming tools (S2).

Marked ``@pytest.mark.benchmark``. It proves a streaming tool surfaces its first
chunk well before a non-streaming tool that must compute every chunk before
returning. Wall-clock is measured directly with :func:`time.perf_counter`; the
bound is loose to stay non-flaky on a busy host. Figures are printed for an
F10-style report to harvest.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from pirn_agents.tool_decorator import tool


@pytest.mark.benchmark
async def test_streaming_first_output_beats_full_result() -> None:
    n = 8
    per_chunk = 0.02

    @tool
    async def streamer(count: int) -> str:
        """Yield ``count`` chunks, one every ``per_chunk`` seconds."""
        for i in range(count):
            await asyncio.sleep(per_chunk)
            yield f"chunk{i}"

    @tool
    async def batched(count: int) -> list[str]:
        """Compute every chunk before returning the whole list."""
        out: list[str] = []
        for i in range(count):
            await asyncio.sleep(per_chunk)
            out.append(f"chunk{i}")
        return out

    start = time.perf_counter()
    first_chunk = await anext(aiter(streamer.stream({"count": n})))
    time_to_first = time.perf_counter() - start

    start = time.perf_counter()
    full = await batched.invoke({"count": n})
    time_to_full = time.perf_counter() - start

    assert first_chunk == "chunk0"
    assert len(full) == n
    # First streamed chunk must arrive well before the full batched result.
    assert time_to_first < 0.5 * time_to_full

    print(
        f"[benchmark] streaming N={n} per_chunk={per_chunk}s "
        f"time_to_first={time_to_first:.4f}s time_to_full={time_to_full:.4f}s "
        f"speedup={time_to_full / time_to_first:.1f}x"
    )
