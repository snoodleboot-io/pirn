"""Provider first-token latency benchmark using a stub provider (PIR-315).

Measures the time to the first streamed chunk from a ``StubLLMProvider`` — a
deterministic, backend-free stand-in for real provider streaming.
"""

from __future__ import annotations

import time

import pytest

from tests.benchmarks.conftest import BenchmarkRecorder
from tests.conftest import StubLLMProvider


@pytest.mark.benchmark
async def test_provider_first_token_latency(benchmark_recorder: BenchmarkRecorder) -> None:
    provider = StubLLMProvider(["chunk-a", "chunk-b", "chunk-c"])

    start = time.perf_counter()
    stream = await provider.stream_chat([{"role": "user", "content": "hi"}])
    first = None
    async for chunk in stream:
        first = chunk
        break
    first_token_latency = time.perf_counter() - start

    assert first is not None
    # A pure-python stub must reach first token near-instantly.
    assert first_token_latency < 0.5

    benchmark_recorder.record("ProviderFirstTokenLatency", first_token_latency=first_token_latency)
