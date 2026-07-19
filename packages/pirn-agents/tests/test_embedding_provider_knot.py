"""Unit tests for :class:`EmbeddingProviderKnot`.

The vended type is :class:`pirn_agents.embedding_provider.EmbeddingProvider`
(the existing provider interface in pirn-core), mirroring how
:class:`LLMProviderKnot` vends :class:`LLMProvider`. The tests prove
one-construction-per-run: a single stub provider is built, then the knot's
``process`` is exercised many times and the same instance is vended each time
without any re-construction.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.embedding_provider_knot import EmbeddingProviderKnot


class CountingEmbeddingProvider(EmbeddingProvider):
    """Embedding provider double that records how many times it is constructed."""

    def __init__(self, counter: list[int]) -> None:
        counter[0] += 1
        self._counter = counter

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        return [[float(len(text))] for text in texts]

    async def close(self) -> None:
        return None


def _make_knot() -> EmbeddingProviderKnot:
    with Tapestry():
        knot = EmbeddingProviderKnot.__new__(EmbeddingProviderKnot)
        object.__setattr__(knot, "_config", KnotConfig(id="epk"))
    return knot


async def test_process_returns_provider_unchanged() -> None:
    counter = [0]
    provider = CountingEmbeddingProvider(counter)
    knot = _make_knot()

    result = await knot.process(provider=provider)

    assert result is provider
    assert isinstance(result, EmbeddingProvider)


async def test_single_construction_reused_across_many_process_calls() -> None:
    counter = [0]
    provider = CountingEmbeddingProvider(counter)
    knot = _make_knot()

    vended: list[Any] = []
    for _ in range(25):
        vended.append(await knot.process(provider=provider))

    assert counter[0] == 1
    assert all(item is provider for item in vended)


async def test_vends_same_instance_end_to_end_through_tapestry() -> None:
    counter = [0]
    provider = CountingEmbeddingProvider(counter)

    with Tapestry() as tapestry:
        EmbeddingProviderKnot(provider=provider, _config=KnotConfig(id="epk"))

    result = await tapestry.run(RunRequest())

    assert result.outputs["epk"] is provider
    assert counter[0] == 1
