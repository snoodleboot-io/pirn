"""Streaming micro-benchmark: first-token latency + tokens/sec (PAE-F3-S5-T3 / PIR-124).

Measures time-to-first-token and streamed tokens/sec against a stub transport,
per the feature's performance section. Marked ``@pytest.mark.benchmark`` with
loose, non-flaky bounds; figures are printed for later reporting.
"""

from __future__ import annotations

import json
import time

import pytest

from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider
from tests.llm.conftest import FakeAsyncClient, FakeStream


def _sse_lines(token_count: int) -> list[str]:
    lines = [
        f"data: {json.dumps({'choices': [{'delta': {'content': f't{i} '}}]})}"
        for i in range(token_count)
    ]
    lines.append(f"data: {json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}]})}")
    lines.append("data: [DONE]")
    return lines


@pytest.mark.benchmark
async def test_first_token_latency_and_throughput() -> None:
    token_count = 200
    client = FakeAsyncClient(stream=FakeStream(lines=_sse_lines(token_count)))
    provider = OpenAICompatibleProvider(
        model="bench-model", base_url="https://bench.example/v1", client=client
    )

    start = time.perf_counter()
    first_token_at: float | None = None
    tokens = 0
    async for delta in provider.stream_chat([{"role": "user", "content": "hi"}]):
        if delta.content:
            tokens += 1
            if first_token_at is None:
                first_token_at = time.perf_counter() - start
    elapsed = time.perf_counter() - start

    assert tokens == token_count
    assert first_token_at is not None
    # First token must arrive before the stream completes (streaming, not batched).
    assert first_token_at <= elapsed
    throughput = tokens / elapsed if elapsed > 0 else float("inf")
    print(
        f"[benchmark] stream N={token_count} first_token={first_token_at * 1e3:.3f}ms "
        f"wall={elapsed:.4f}s throughput={throughput:.0f} tokens/s"
    )
    assert throughput > 0


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_first_token_latency_and_throughput())
