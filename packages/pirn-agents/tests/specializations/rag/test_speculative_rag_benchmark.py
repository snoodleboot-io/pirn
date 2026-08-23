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
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.rag.speculative_rag_pipeline import SpeculativeRagPipeline
from pirn_agents.types.messaging.agent_response import AgentResponse

_STAGE_DELAY = 0.1


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

    def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[StreamDelta]:
        async def _aiter() -> AsyncIterator[StreamDelta]:
            yield StreamDelta(content="stub")

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


async def _sequential_floor() -> float:
    """Return what three serial stage delays actually cost, here and now.

    The baseline is *measured on the same runner in the same process* rather
    than computed as ``3 * _STAGE_DELAY``. A literal budget encodes "this
    machine is fast enough": it passed at 118 ms and failed at 425 ms on a
    loaded CI runner, reddening unrelated PRs (PIR-777). Scheduler delay
    inflates the baseline and the measurement together, so a ratio survives a
    slow runner while still failing if the overlap regresses.
    """
    start = time.perf_counter()
    for _ in range(3):
        await asyncio.sleep(_STAGE_DELAY)
    return time.perf_counter() - start


async def _run_pipeline() -> tuple[float, Any]:
    """Build and run one speculative pipeline, returning (elapsed, run result)."""
    with Tapestry() as tapestry:
        SpeculativeRagPipeline(
            query="q",
            memory=_SlowMemory(),
            llm=_SlowLLM(["draft", "verified"]),
            top_k=1,
            _config=KnotConfig(id="spec"),
        )
    start = time.perf_counter()
    result = await tapestry.run(RunRequest())
    return time.perf_counter() - start, result


@pytest.mark.benchmark
async def test_speculative_overlaps_draft_and_retrieval() -> None:
    # Arrange: one untimed run first. The engine's first run in a process pays
    # import and setup costs that land inside the measured window and have
    # nothing to do with overlap — that alone reddened a cold run at this
    # threshold.
    await _run_pipeline()
    sequential = await _sequential_floor()

    # Act
    elapsed, result = await _run_pipeline()

    # Assert
    assert result.succeeded
    assert isinstance(result.outputs["spec"], AgentResponse)
    # Drafting hides behind retrieval, so one whole stage disappears: the run
    # should land near max(draft, retrieve) + verify, not the sum of all three.
    # The 10% allowance is engine overhead, which the raw-sleep floor excludes.
    assert elapsed < sequential * 0.9, (
        f"no overlap: {elapsed * 1e3:.1f}ms vs sequential floor {sequential * 1e3:.1f}ms"
    )
    print(
        f"[benchmark] speculative_rag elapsed={elapsed * 1e3:.1f}ms "
        f"sequential_floor={sequential * 1e3:.1f}ms stage_delay={_STAGE_DELAY * 1e3:.1f}ms"
    )
