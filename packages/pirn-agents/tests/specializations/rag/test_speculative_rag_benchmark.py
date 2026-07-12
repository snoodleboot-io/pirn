"""Benchmark: Speculative RAG overlap vs sequential baseline (S6-T3).

The draft branch does not depend on retrieval, so the tapestry runs the two
concurrently: drafting is hidden behind retrieval latency. This benchmark uses
artificially slow draft and retrieval stubs and shows the speculative pipeline's
wall-clock is close to ``max(draft, retrieve) + verify`` — strictly less than the
non-speculative ``draft + retrieve + verify`` sum.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.speculative_rag_pipeline import SpeculativeRagPipeline
from pirn_agents.types.agent_response import AgentResponse

_STAGE_DELAY = 0.05


class _SlowLLM(LLMProvider):
    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        await asyncio.sleep(_STAGE_DELAY)
        text = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        return {"role": "assistant", "content": text}

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            yield {"content": "stub"}

        return _aiter()

    async def close(self) -> None:
        return None


class _SlowMemory(MemoryStore):
    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        return None

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return None

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        await asyncio.sleep(_STAGE_DELAY)

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            yield {"id": "1", "text": "evidence"}

        return _aiter()

    async def forget(self, key: str) -> None:
        return None

    async def close(self) -> None:
        return None


@pytest.mark.benchmark
async def test_speculative_overlaps_draft_and_retrieval() -> None:
    llm = _SlowLLM(["draft", "verified"])
    memory = _SlowMemory()
    with Tapestry() as t:
        SpeculativeRagPipeline(
            query="q", memory=memory, llm=llm, top_k=1, _config=KnotConfig(id="spec")
        )
    start = time.perf_counter()
    result = await t.run(RunRequest())
    elapsed = time.perf_counter() - start
    assert result.succeeded
    assert isinstance(result.outputs["spec"], AgentResponse)

    sequential = 3 * _STAGE_DELAY  # draft + retrieve + verify with no overlap
    assert elapsed < sequential
    print(
        f"[benchmark] speculative_rag elapsed={elapsed * 1e3:.1f}ms "
        f"sequential_baseline={sequential * 1e3:.1f}ms stage_delay={_STAGE_DELAY * 1e3:.1f}ms"
    )
