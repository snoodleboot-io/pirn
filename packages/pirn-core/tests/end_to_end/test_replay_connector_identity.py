"""Replay refuses a knot whose connector literal was swapped (PIR-848, PIR-852).

Regression for two false matches on ``main``:

* two connectors of one class hashed equal whatever endpoint they pointed at,
  so a recording made against endpoint A was served to a run configured with B;
* once hashing was keyed on ``id()``, a connector built after the recorded one
  was freed usually landed at the same address and was served A's output.

Replay must refuse, never substitute.
"""

from __future__ import annotations

import gc
from typing import Any, ClassVar

import pytest

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.connectors.connector_base import ConnectorBase
from pirn.connectors.http_connector import HttpConnector
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.recording.replay_mismatch_error import ReplayMismatchError
from pirn.recording.replay_session import ReplaySession
from pirn.tapestry import Tapestry


class FetchesFrom(Knot):
    """Holds a connector as a literal and reports the endpoint it would call."""

    invocations: ClassVar[list[str]] = []

    def __init__(self, *, connector: HttpConnector, **kwargs: Any) -> None:
        super().__init__(connector=connector, **kwargs)

    async def process(self, connector: HttpConnector, **_: Any) -> str:
        endpoint = str(connector._base_url)
        FetchesFrom.invocations.append(endpoint)
        return endpoint


class PlainEndpointConnector(ConnectorBase):
    """A connector with configuration and no self-referencing attributes."""

    def __init__(self, *, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url


class ReportsPlainEndpoint(Knot):
    """Holds a :class:`PlainEndpointConnector` literal and returns its endpoint."""

    def __init__(self, *, connector: PlainEndpointConnector, **kwargs: Any) -> None:
        super().__init__(connector=connector, **kwargs)

    async def process(self, connector: PlainEndpointConnector, **_: Any) -> str:
        return connector.base_url


@pytest.fixture(autouse=True)
def _clear_invocations() -> None:
    FetchesFrom.invocations.clear()


async def test_replay_refuses_when_the_connector_points_at_another_endpoint() -> None:
    # Arrange — record against endpoint A.
    endpoint_a = HttpConnector(base_url="https://a.example/v1")
    with Tapestry() as recorded:
        FetchesFrom(connector=endpoint_a, _config=KnotConfig(id="fetch"))
    original = await recorded.run(RunRequest())

    endpoint_b = HttpConnector(base_url="https://b.example/v1")
    with Tapestry(history=recorded.history, data_store=recorded.data_store) as swapped:
        FetchesFrom(connector=endpoint_b, _config=KnotConfig(id="fetch"))
    session = await ReplaySession.from_history(history=recorded.history, run_id=original.run_id)

    # Act / Assert
    with pytest.raises(ReplayMismatchError) as caught:
        await swapped.run(RunRequest(), replay=session)
    assert caught.value.knot_id == "fetch"
    assert FetchesFrom.invocations == ["https://a.example/v1"]


async def test_replay_refuses_an_identically_configured_separate_connector() -> None:
    # Arrange — identity semantics: equal config is still another connector.
    with Tapestry() as recorded:
        FetchesFrom(
            connector=HttpConnector(base_url="https://a.example/v1"), _config=KnotConfig(id="fetch")
        )
    original = await recorded.run(RunRequest())

    with Tapestry(history=recorded.history, data_store=recorded.data_store) as rebuilt:
        FetchesFrom(
            connector=HttpConnector(base_url="https://a.example/v1"), _config=KnotConfig(id="fetch")
        )
    session = await ReplaySession.from_history(history=recorded.history, run_id=original.run_id)

    # Act / Assert
    with pytest.raises(ReplayMismatchError):
        await rebuilt.run(RunRequest(), replay=session)


async def test_replay_still_serves_when_the_same_connector_is_reused() -> None:
    # Arrange
    endpoint_a = HttpConnector(base_url="https://a.example/v1")
    with Tapestry() as tapestry:
        FetchesFrom(connector=endpoint_a, _config=KnotConfig(id="fetch"))
    original = await tapestry.run(RunRequest())
    session = await ReplaySession.from_history(history=tapestry.history, run_id=original.run_id)

    # Act
    replayed = await tapestry.run(RunRequest(), replay=session)

    # Assert — served from the recording, the knot did not run again.
    assert replayed.outputs["fetch"] == "https://a.example/v1"
    assert FetchesFrom.invocations == ["https://a.example/v1"]


async def test_replay_never_serves_a_connector_built_after_the_recorded_one_was_freed() -> None:
    # Arrange
    iterations = 200
    outcomes: list[str] = []
    reuses = 0

    # Act — freeze the existing heap so each collection only walks new objects.
    gc.freeze()
    try:
        for _ in range(iterations):
            outcome, reused = await _record_free_and_replay()
            outcomes.append(outcome)
            reuses += reused
    finally:
        gc.unfreeze()

    # Assert — the loop only proves something if addresses were really reused.
    assert reuses > 0, "no address was reused; the regression loop tested nothing"
    assert outcomes.count("SERVED") == 0
    assert outcomes.count("REFUSED") == iterations


async def _record_free_and_replay() -> tuple[str, bool]:
    """Record with connector A, free A and its tapestry, replay with a new B.

    Only the history and data store survive, which is what a real replay keeps.
    The collection frees the recorded tapestry's reference cycles while this
    frame still holds A. A, which is in no cycle, is then released by reference
    count as the last object freed, so B lands at A's address almost every
    time: the case under test. (``HttpConnector`` stores bound methods on
    itself, so it is freed mid-collection and the allocator hands its block to
    whatever is freed after it; that is why this loop uses a plain connector.)

    Returns:
        ``("SERVED" | "REFUSED", whether B landed at A's freed address)``.
    """
    history, data_store = InMemoryHistory(), InMemoryDataStore()
    recorded_connector = PlainEndpointConnector(base_url="https://a.example/v1")
    recorded_address = id(recorded_connector)
    with Tapestry(history=history, data_store=data_store) as recorded:
        ReportsPlainEndpoint(connector=recorded_connector, _config=KnotConfig(id="fetch"))
    run = await recorded.run(RunRequest())
    del recorded
    gc.collect()
    del recorded_connector

    fresh_connector = PlainEndpointConnector(base_url="https://b.example/v1")
    reused = id(fresh_connector) == recorded_address
    with Tapestry(history=history, data_store=data_store) as replaying:
        ReportsPlainEndpoint(connector=fresh_connector, _config=KnotConfig(id="fetch"))
    session = await ReplaySession.from_history(history=history, run_id=run.run_id)
    try:
        await replaying.run(RunRequest(), replay=session)
    except ReplayMismatchError:
        return "REFUSED", reused
    return "SERVED", reused
