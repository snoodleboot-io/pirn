"""Overhead micro-benchmark for the retry/usage wrapper (PAE-F3-S1-T3 / PIR-89).

Measures the wall-clock overhead the ``BaseLLMProvider`` request path
(retry loop + response mapping + usage/cost accounting) adds over a raw stub
call that does none of it. Marked ``@pytest.mark.benchmark``; wall-clock is
measured directly and the bound is loose to stay non-flaky on busy CI hosts.
Figures are printed so a later report can harvest them.
"""

from __future__ import annotations

import time

import pytest

from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider
from tests.llm.conftest import FakeAsyncClient, FakeResponse


def _completion() -> FakeResponse:
    return FakeResponse(
        json_body={
            "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 4},
        }
    )


@pytest.mark.benchmark
async def test_retry_wrapper_overhead_is_bounded() -> None:
    iterations = 300
    messages = [{"role": "user", "content": "hi"}]

    client = FakeAsyncClient(post_results=[_completion()], repeat_last=True)
    provider = OpenAICompatibleProvider(
        model="bench-model",
        base_url="https://bench.example/v1",
        client=client,
        pricing=ModelPricing(input_per_million=1.0, output_per_million=1.0),
    )

    # Warm the pooled client.
    await provider.chat_response(messages)

    start = time.perf_counter()
    for _ in range(iterations):
        await provider.chat_response(messages)
    wrapped = time.perf_counter() - start

    raw_client = FakeAsyncClient(post_results=[_completion()], repeat_last=True)
    start = time.perf_counter()
    for _ in range(iterations):
        response = await raw_client.post("u", json={}, headers={})
        _ = response.json()
    raw = time.perf_counter() - start

    per_call_overhead = (wrapped - raw) / iterations
    print(
        f"[benchmark] BaseLLMProvider overhead N={iterations} "
        f"wrapped={wrapped:.4f}s raw={raw:.4f}s "
        f"per_call_overhead={per_call_overhead * 1e6:.1f}us"
    )

    # Loose guard: the wrapper must not add more than 1ms/call on average.
    assert per_call_overhead < 1e-3


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_retry_wrapper_overhead_is_bounded())
