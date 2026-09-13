"""Tests for :class:`CheckpointForker` (ADR "agents speaks core" WS3 part 3).

A fork is a branch of the session chain: real ``Tapestry.run()`` calls over a
shared ``InMemoryHistory``/``InMemoryDataStore``, not a ``SessionStore``
checkpoint. These exercise the whole real flow — record a source run, fork it
twice with different ``Parameter`` values, and confirm both forks share the
recorded prefix (the source knot never re-executes) while diverging after it.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.determinism.checkpoint_forker import CheckpointForker
from pirn_agents.determinism.fork_result import ForkResult
from pirn_agents.sessions.resume_token import ResumeToken


class Doubler(Knot):
    """Doubles its input and logs every actual invocation."""

    invocations: ClassVar[list[int]] = []

    def __init__(self, x: Knot, **kwargs: Any) -> None:
        super().__init__(x=x, **kwargs)

    async def process(self, x: int, **_: Any) -> int:
        Doubler.invocations.append(x)
        return x * 2


class ScaleBy(Knot):
    """Multiplies its input by a Parameter-supplied factor."""

    def __init__(self, x: Knot, factor: Knot, **kwargs: Any) -> None:
        super().__init__(x=x, factor=factor, **kwargs)

    async def process(self, x: int, factor: int, **_: Any) -> int:
        return x * factor


@pytest.fixture(autouse=True)
def _clear_invocations() -> None:
    Doubler.invocations.clear()


def _build_source_tapestry(history: InMemoryHistory, data_store: InMemoryDataStore) -> Tapestry:
    tapestry = Tapestry(history=history, data_store=data_store)
    with tapestry:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))
    return tapestry


def _build_fork_tapestry(history: InMemoryHistory, data_store: InMemoryDataStore) -> Tapestry:
    tapestry = Tapestry(history=history, data_store=data_store)
    with tapestry:
        param = Parameter(name="x", type_=int)
        doubled = Doubler(x=param, _config=KnotConfig(id="double"))
        factor = Parameter(name="factor", type_=int)
        ScaleBy(x=doubled, factor=factor, _config=KnotConfig(id="scale"))
    return tapestry


class TestCheckpointForker:
    async def test_fork_shares_the_prefix_and_diverges_after(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        source_tapestry = _build_source_tapestry(history, data_store)
        source = await source_tapestry.run(RunRequest(parameters={"x": 5}))
        assert source.outputs["double"] == 10
        assert Doubler.invocations == [5]

        fork_tapestry = _build_fork_tapestry(history, data_store)
        double_row = next(row for row in source.lineage if row.knot_id == "double")
        assert double_row.output_hash is not None
        fork_point = ResumeToken(run_id=source.run_id, output_hash=double_row.output_hash)

        result = await CheckpointForker().fork(
            tapestry=fork_tapestry,
            history=history,
            data_store=data_store,
            fork_point=fork_point,
            source_knot_id="double",
            request=RunRequest(parameters={"x": 5, "factor": 3}),
        )

        assert isinstance(result, ForkResult)
        assert result.source_run_id == source.run_id
        assert result.new_run_id != source.run_id
        assert result.result.parent_run_id == source.run_id
        assert result.result.parent_knot_id is None
        # "double" was served from the recording, not re-invoked.
        assert Doubler.invocations == [5]
        assert result.result.outputs["double"] == 10
        # "scale" is genuinely new to the recording and ran live.
        assert result.result.outputs["scale"] == 30

    async def test_two_forks_from_the_same_point_both_chain_to_it(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        source_tapestry = _build_source_tapestry(history, data_store)
        source = await source_tapestry.run(RunRequest(parameters={"x": 5}))
        double_row = next(row for row in source.lineage if row.knot_id == "double")
        assert double_row.output_hash is not None
        fork_point = ResumeToken(run_id=source.run_id, output_hash=double_row.output_hash)

        fork_a = await CheckpointForker().fork(
            tapestry=_build_fork_tapestry(history, data_store),
            history=history,
            data_store=data_store,
            fork_point=fork_point,
            source_knot_id="double",
            request=RunRequest(parameters={"x": 5, "factor": 2}),
        )
        fork_b = await CheckpointForker().fork(
            tapestry=_build_fork_tapestry(history, data_store),
            history=history,
            data_store=data_store,
            fork_point=fork_point,
            source_knot_id="double",
            request=RunRequest(parameters={"x": 5, "factor": 10}),
        )

        assert fork_a.new_run_id != fork_b.new_run_id
        assert fork_a.result.parent_run_id == source.run_id
        assert fork_b.result.parent_run_id == source.run_id
        assert fork_a.result.outputs["scale"] == 20
        assert fork_b.result.outputs["scale"] == 100

    async def test_stale_fork_point_raises(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        source_tapestry = _build_source_tapestry(history, data_store)
        source = await source_tapestry.run(RunRequest(parameters={"x": 5}))

        stale = ResumeToken(run_id=source.run_id, output_hash="sha256:not-the-real-hash")
        with pytest.raises(ValueError, match="stale fork point"):
            await CheckpointForker().fork(
                tapestry=_build_fork_tapestry(history, data_store),
                history=history,
                data_store=data_store,
                fork_point=stale,
                source_knot_id="double",
                request=RunRequest(parameters={"x": 5, "factor": 2}),
            )

    async def test_unknown_run_id_raises(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        bogus = ResumeToken(run_id="no-such-run", output_hash="sha256:whatever")
        with pytest.raises(KeyError):
            await CheckpointForker().fork(
                tapestry=_build_fork_tapestry(history, data_store),
                history=history,
                data_store=data_store,
                fork_point=bogus,
                source_knot_id="double",
            )

    async def test_rejects_non_run_history(self) -> None:
        data_store = InMemoryDataStore()
        with pytest.raises(TypeError):
            await CheckpointForker().fork(
                tapestry=_build_fork_tapestry(InMemoryHistory(), data_store),
                history="bad",  # type: ignore[arg-type]
                data_store=data_store,
                fork_point=ResumeToken(run_id="x", output_hash="sha256:y"),
                source_knot_id="double",
            )
