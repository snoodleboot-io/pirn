"""Unit tests for :class:`VectorStoreKnot`.

pirn-core exposes no dedicated ``VectorStore`` interface, so the knot vends the
pooled-client abstraction :class:`pirn_agents.connector_base.ConnectorBase`
(the S3 pooled-client base). The tests prove one-construction-per-run: a single
stub connector is built, then the knot's ``process`` is exercised many times and
the same instance is vended each time without any re-construction of its backend
client.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.vector_store_knot import VectorStoreKnot


class CountingVectorStore(ConnectorBase):
    """Vector-store connector double that records construction and client builds."""

    def __init__(self, counter: list[int]) -> None:
        super().__init__(credential=None)
        counter[0] += 1
        self._counter = counter
        self.client_builds = 0

    async def _create_client(self) -> Any:
        self.client_builds += 1
        return object()


def _make_knot() -> VectorStoreKnot:
    with Tapestry():
        knot = VectorStoreKnot.__new__(VectorStoreKnot)
        object.__setattr__(knot, "_config", KnotConfig(id="vsk"))
    return knot


async def test_process_returns_store_unchanged() -> None:
    counter = [0]
    store = CountingVectorStore(counter)
    knot = _make_knot()

    result = await knot.process(store=store)

    assert result is store
    assert isinstance(result, ConnectorBase)


async def test_single_construction_reused_across_many_process_calls() -> None:
    counter = [0]
    store = CountingVectorStore(counter)
    knot = _make_knot()

    vended: list[Any] = []
    for _ in range(25):
        vended.append(await knot.process(store=store))

    assert counter[0] == 1
    assert all(item is store for item in vended)


async def test_pooled_client_built_once_across_many_resolves() -> None:
    counter = [0]
    store = CountingVectorStore(counter)
    knot = _make_knot()

    for _ in range(25):
        vended = await knot.process(store=store)
        # Each resolve reuses the one connector, whose backend client is pooled.
        await vended._get_client()

    assert counter[0] == 1
    assert store.client_builds == 1


async def test_vends_same_instance_end_to_end_through_tapestry() -> None:
    counter = [0]
    store = CountingVectorStore(counter)

    with Tapestry() as tapestry:
        VectorStoreKnot(store=store, _config=KnotConfig(id="vsk"))

    result = await tapestry.run(RunRequest())

    assert result.outputs["vsk"] is store
    assert counter[0] == 1
