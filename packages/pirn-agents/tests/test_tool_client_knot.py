"""Unit tests for :class:`ToolClientKnot`.

A tool client holds live backend state, so the knot vends the pooled-client
abstraction :class:`pirn_agents.connector_base.ConnectorBase` (the S3
pooled-client base). The tests prove one-construction-per-run: a single stub
connector is built, then the knot's ``process`` is exercised many times and the
same instance is vended each time without any re-construction of its backend
client.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.tool_client_knot import ToolClientKnot


class CountingToolClient(ConnectorBase):
    """Tool-client connector double that records construction and client builds."""

    def __init__(self, counter: list[int]) -> None:
        super().__init__(credential=None)
        counter[0] += 1
        self._counter = counter
        self.client_builds = 0

    async def _create_client(self) -> Any:
        self.client_builds += 1
        return object()


def _make_knot() -> ToolClientKnot:
    with Tapestry():
        knot = ToolClientKnot.__new__(ToolClientKnot)
        object.__setattr__(knot, "_config", KnotConfig(id="tck"))
    return knot


async def test_process_returns_client_unchanged() -> None:
    counter = [0]
    client = CountingToolClient(counter)
    knot = _make_knot()

    result = await knot.process(client=client)

    assert result is client
    assert isinstance(result, ConnectorBase)


async def test_single_construction_reused_across_many_process_calls() -> None:
    counter = [0]
    client = CountingToolClient(counter)
    knot = _make_knot()

    vended: list[Any] = []
    for _ in range(25):
        vended.append(await knot.process(client=client))

    assert counter[0] == 1
    assert all(item is client for item in vended)


async def test_pooled_client_built_once_across_many_resolves() -> None:
    counter = [0]
    client = CountingToolClient(counter)
    knot = _make_knot()

    for _ in range(25):
        vended = await knot.process(client=client)
        # Each resolve reuses the one connector, whose backend client is pooled.
        await vended._get_client()

    assert counter[0] == 1
    assert client.client_builds == 1


async def test_vends_same_instance_end_to_end_through_tapestry() -> None:
    counter = [0]
    client = CountingToolClient(counter)

    with Tapestry() as tapestry:
        ToolClientKnot(client=client, _config=KnotConfig(id="tck"))

    result = await tapestry.run(RunRequest())

    assert result.outputs["tck"] is client
    assert counter[0] == 1
