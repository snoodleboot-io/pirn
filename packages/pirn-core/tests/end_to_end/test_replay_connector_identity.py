"""Replay refuses a knot whose connector literal was swapped (PIR-848, PIR-852).

Regression for two false matches on ``main``:

* two connectors of one class hashed equal whatever endpoint they pointed at,
  so a recording made against endpoint A was served to a run configured with B;
* once hashing was keyed on ``id()``, a connector built after the recorded one
  was freed usually landed at the same address and was served A's output.

Replay must refuse, never substitute.
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
from tests.unit.core.identity_reuse_subprocess import IdentityReuseSubprocess


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


def test_replay_never_serves_a_connector_built_after_the_recorded_one_was_freed() -> None:
    # Arrange — record with connector A, drop everything but history and data
    # store, gc.collect(), build B (usually at A's address), replay. Runs in a
    # clean interpreter: a coverage-traced suite heap stops address reuse.

    # Act
    tally = IdentityReuseSubprocess.run("connector_replay", 200)

    # Assert — the loop only proves something if addresses were really reused;
    # a collision here means replay SERVED A's recording to B.
    assert tally["reuses"] > 0, f"no address was reused; the loop tested nothing: {tally}"
    assert tally["collisions"] == 0, tally
