"""Replay refuses a knot whose connector literal was swapped (PIR-848).

Regression for a false match on ``main``: two connectors of one class hashed
equal whatever endpoint they pointed at, so a recording made against endpoint A
was served to a run configured with endpoint B.  Replay must refuse, never
substitute.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

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
