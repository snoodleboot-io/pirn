"""Replay posture: recorded outcomes are served, knots do not execute.

The distinguishing property of ``ReplaySession`` — and the thing
``pirn.replay.replay_run`` cannot do — is that a knot with a side effect is
*not run* on replay.  These tests prove that by observation (a call log, or a
knot that raises if reached) rather than by comparing outputs, which a
re-execution would satisfy just as well.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.run_history import RunHistory
from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.recording.replay_mismatch_error import ReplayMismatchError
from pirn.recording.replay_session import ReplaySession
from pirn.recording.replay_value_unavailable_error import ReplayValueUnavailableError
from pirn.tapestry import Tapestry


class Doubler(Knot):
    """Doubles its input and logs that it was actually invoked."""

    invocations: ClassVar[list[int]] = []

    def __init__(self, x: Knot, **kwargs: Any) -> None:
        super().__init__(x=x, **kwargs)

    async def process(self, x: int, **_: Any) -> int:
        Doubler.invocations.append(x)
        return x * 2


class Unreachable(Knot):
    """Stands in for a live network call: raises if it is ever executed."""

    def __init__(self, x: Knot, **kwargs: Any) -> None:
        super().__init__(x=x, **kwargs)

    async def process(self, x: int, **_: Any) -> int:
        raise AssertionError("this knot must not execute on replay")


class Scale(Knot):
    """Multiplies by a literal constructor argument, not by a parent value."""

    def __init__(self, x: Knot, factor: int, **kwargs: Any) -> None:
        super().__init__(x=x, factor=factor, **kwargs)

    async def process(self, x: int, factor: int, **_: Any) -> int:
        return x * factor


class Exploder(Knot):
    """Fails so that a failure outcome can be recorded and replayed."""

    def __init__(self, x: Knot, **kwargs: Any) -> None:
        super().__init__(x=x, **kwargs)

    async def process(self, x: int, **_: Any) -> int:
        raise ValueError(f"boom on {x}")


@pytest.fixture(autouse=True)
def _clear_invocations() -> None:
    Doubler.invocations.clear()


def _joined(source: Tapestry) -> Tapestry:
    """A second tapestry sharing *source*'s history and data store.

    Replay reads lineage from one and values from the other, so a test that
    swaps the graph has to keep both.
    """
    return Tapestry(history=source.history, data_store=source.data_store)


async def test_replay_serves_recorded_output_without_executing_the_knot() -> None:
    # Arrange — record one live run.
    with Tapestry() as tapestry:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))
    original = await tapestry.run(RunRequest(parameters={"x": 21}))
    assert Doubler.invocations == [21]

    # Act — replay it.
    session = await ReplaySession.from_history(history=tapestry.history, run_id=original.run_id)
    replayed = await tapestry.run(RunRequest(parameters={"x": 21}), replay=session)

    # Assert — same answer, and the knot was never invoked a second time.
    assert Doubler.invocations == [21]
    assert replayed.outputs["double"] == original.outputs["double"] == 42
    assert replayed.run_id != original.run_id


async def test_replay_does_not_touch_a_knot_that_would_raise_if_invoked() -> None:
    # Arrange — record with a knot that succeeds, then swap in one that
    # explodes under the same id, standing in for a live call on replay.
    with Tapestry() as recorded:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="call"))
    original = await recorded.run(RunRequest(parameters={"x": 5}))

    with _joined(recorded) as swapped:
        swapped_param = Parameter(name="x", type_=int)
        Unreachable(x=swapped_param, _config=KnotConfig(id="call"))

    # Act
    session = await ReplaySession.from_history(history=recorded.history, run_id=original.run_id)
    replayed = await swapped.run(RunRequest(parameters={"x": 5}), replay=session)

    # Assert — Unreachable.process would have raised; it never ran.
    assert replayed.succeeded
    assert replayed.outputs["call"] == 10


async def test_replayed_rows_name_the_run_they_were_served_from() -> None:
    # Arrange
    with Tapestry() as tapestry:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))
    original = await tapestry.run(RunRequest(parameters={"x": 3}))

    # Act
    session = await ReplaySession.from_history(history=tapestry.history, run_id=original.run_id)
    replayed = await tapestry.run(RunRequest(parameters={"x": 3}), replay=session)

    # Assert — the replayed knot is marked, the executed Parameter is not.
    rows = {row.knot_id: row for row in replayed.lineage}
    assert rows["double"].extra["replayed_from_run_id"] == original.run_id
    assert "replayed_from_run_id" not in rows["param:x"].extra


async def test_a_live_run_is_unchanged_when_no_session_is_passed() -> None:
    # Arrange
    with Tapestry() as tapestry:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))

    # Act — two ordinary runs, no replay anywhere.
    first = await tapestry.run(RunRequest(parameters={"x": 4}))
    second = await tapestry.run(RunRequest(parameters={"x": 4}))

    # Assert — replay is default-off, so the knot really executed twice.
    assert Doubler.invocations == [4, 4]
    assert first.outputs["double"] == second.outputs["double"] == 8
    assert all("replayed_from_run_id" not in row.extra for row in second.lineage)


async def test_a_changed_parameter_fails_loudly_instead_of_serving_stale_output() -> None:
    # Arrange — a Parameter's config hash and input hashes are identical
    # whatever the bound value is, so only an output-hash check can catch this.
    with Tapestry() as tapestry:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))
    original = await tapestry.run(RunRequest(parameters={"x": 21}))
    session = await ReplaySession.from_history(history=tapestry.history, run_id=original.run_id)

    # Act / Assert
    with pytest.raises(ReplayMismatchError) as caught:
        await tapestry.run(RunRequest(parameters={"x": 99}), replay=session)
    assert caught.value.knot_id == "param:x"


async def test_a_changed_literal_argument_fails_loudly() -> None:
    # Arrange — Scale's `factor` reaches process() as an input but is covered
    # by neither knot_config_hash nor parent_input_hashes.
    with Tapestry() as recorded:
        param = Parameter(name="x", type_=int)
        Scale(x=param, factor=2, _config=KnotConfig(id="scale"))
    original = await recorded.run(RunRequest(parameters={"x": 10}))

    with _joined(recorded) as changed:
        changed_param = Parameter(name="x", type_=int)
        Scale(x=changed_param, factor=5, _config=KnotConfig(id="scale"))

    # Act / Assert
    session = await ReplaySession.from_history(history=recorded.history, run_id=original.run_id)
    with pytest.raises(ReplayMismatchError) as caught:
        await changed.run(RunRequest(parameters={"x": 10}), replay=session)
    assert caught.value.knot_id == "scale"
    assert "literal constructor arguments" in str(caught.value)


async def test_a_knot_absent_from_the_recording_fails_loudly() -> None:
    # Arrange — record a shorter pipeline than the one being replayed.
    with Tapestry() as recorded:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))
    original = await recorded.run(RunRequest(parameters={"x": 2}))

    with _joined(recorded) as longer:
        longer_param = Parameter(name="x", type_=int)
        first = Doubler(x=longer_param, _config=KnotConfig(id="double"))
        Doubler(x=first, _config=KnotConfig(id="double-again"))

    # Act / Assert
    session = await ReplaySession.from_history(history=recorded.history, run_id=original.run_id)
    with pytest.raises(ReplayMismatchError) as caught:
        await longer.run(RunRequest(parameters={"x": 2}), replay=session)
    assert caught.value.knot_id == "double-again"


async def test_a_scrubbed_value_fails_loudly_rather_than_re_executing() -> None:
    # Arrange — lineage survives, the value does not.  This is the TTL case.
    with Tapestry() as tapestry:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))
    original = await tapestry.run(RunRequest(parameters={"x": 7}))
    recorded_row = next(row for row in original.lineage if row.knot_id == "double")
    assert recorded_row.output_hash is not None
    data_store: DataStore = tapestry.data_store
    await data_store.scrub(recorded_row.output_hash)

    # Act / Assert
    session = await ReplaySession.from_history(history=tapestry.history, run_id=original.run_id)
    with pytest.raises(ReplayValueUnavailableError) as caught:
        await tapestry.run(RunRequest(parameters={"x": 7}), replay=session)
    assert caught.value.knot_id == "double"
    assert Doubler.invocations == [7]


async def test_an_evicted_value_fails_loudly_rather_than_re_executing() -> None:
    # Arrange — the store hit its declared retention ceiling and dropped the
    # recorded output.  Lineage still names it (PIR-839).
    data_store = InMemoryDataStore(max_values=4)
    with Tapestry(data_store=data_store) as tapestry:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))
    original = await tapestry.run(RunRequest(parameters={"x": 7}))
    recorded_row = next(row for row in original.lineage if row.knot_id == "double")
    assert recorded_row.output_hash is not None
    for i in range(4):
        await data_store.put(f"sha256:filler-{i}", i)
    assert not await data_store.has(recorded_row.output_hash)
    Doubler.invocations.clear()

    # Act / Assert — replay must not quietly fall back to executing the knot.
    session = await ReplaySession.from_history(history=tapestry.history, run_id=original.run_id)
    with pytest.raises(ReplayValueUnavailableError) as caught:
        await tapestry.run(RunRequest(parameters={"x": 7}), replay=session)
    assert caught.value.knot_id == "double"
    assert "evicted" in str(caught.value)
    assert Doubler.invocations == []


async def test_a_recorded_failure_replays_as_a_failure() -> None:
    # Arrange
    with Tapestry() as tapestry:
        param = Parameter(name="x", type_=int)
        Exploder(x=param, _config=KnotConfig(id="boom"))
    original = await tapestry.run(RunRequest(parameters={"x": 1}))
    assert not original.succeeded

    # Act
    session = await ReplaySession.from_history(history=tapestry.history, run_id=original.run_id)
    replayed = await tapestry.run(RunRequest(parameters={"x": 1}), replay=session)

    # Assert — same failure, re-registered under the replayed run's id.
    assert not replayed.succeeded
    assert len(replayed.exceptions) == 1
    assert replayed.exceptions[0].exc_type == "ValueError"
    assert replayed.exceptions[0].message == "boom on 1"
    assert replayed.exceptions[0].run_id == replayed.run_id


async def test_replaying_an_unknown_run_id_raises() -> None:
    # Arrange
    with Tapestry() as tapestry:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))
    history: RunHistory = tapestry.history

    # Act / Assert
    with pytest.raises(KeyError):
        await ReplaySession.from_history(history=history, run_id="run-does-not-exist")
