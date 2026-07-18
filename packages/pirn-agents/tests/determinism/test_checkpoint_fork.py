"""Mirrored tests for snapshot/fork from an F14 checkpoint (F29-S5)."""

from __future__ import annotations

import unittest

from pirn_agents.determinism.checkpoint_forker import CheckpointForker
from pirn_agents.determinism.fork_result import ForkResult
from pirn_agents.sessions.execution_cursor import ExecutionCursor
from pirn_agents.sessions.in_memory_session_store import InMemorySessionStore
from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_message import SessionMessage
from pirn_agents.sessions.session_store import SessionStore


def _state(session_id: str = "orig") -> RunState:
    return RunState(
        session_id=session_id,
        messages=(SessionMessage(role="user", content="hi"),),
        plan=("a", "b", "c"),
        cursor=ExecutionCursor(step_index=2, completed_steps=("a", "b")),
    )


async def _seeded_store() -> SessionStore:
    store = InMemorySessionStore()
    await store.save("orig", RunCheckpoint.create(_state()))
    return store


class CheckpointForkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_fork_creates_distinguishable_new_session(self) -> None:
        store = await _seeded_store()
        result = await CheckpointForker().fork(
            store=store, source_session_id="orig", new_session_id="fork-1"
        )
        assert isinstance(result, ForkResult)
        assert result.new_session_id == "fork-1"
        assert result.source_session_id == "orig"
        assert result.forked_from_checkpoint_id == RunCheckpoint.create(_state()).checkpoint_id
        # The forked run is persisted under its own id and keyed to it.
        stored = await store.load("fork-1")
        assert stored is not None
        assert stored.state.session_id == "fork-1"

    async def test_fork_preserves_prior_trace(self) -> None:
        store = await _seeded_store()
        result = await CheckpointForker().fork(
            store=store, source_session_id="orig", new_session_id="fork-1"
        )
        assert result.checkpoint.state.messages == _state().messages
        assert result.checkpoint.state.plan == ("a", "b", "c")

    async def test_fork_point_rewinds_cursor(self) -> None:
        store = await _seeded_store()
        result = await CheckpointForker().fork(
            store=store, source_session_id="orig", new_session_id="fork-1", fork_point=1
        )
        assert result.fork_point == 1
        assert result.checkpoint.state.cursor.step_index == 1
        assert result.checkpoint.state.cursor.completed_steps == ("a",)
        # Diverges only from the fork point onward: the tail is replayable.
        assert result.checkpoint.state.remaining_plan() == ("b", "c")

    async def test_fork_result_round_trips(self) -> None:
        store = await _seeded_store()
        result = await CheckpointForker().fork(
            store=store, source_session_id="orig", new_session_id="fork-1"
        )
        assert ForkResult.from_payload(result.to_payload()) == result

    async def test_missing_source_raises(self) -> None:
        store = InMemorySessionStore()
        with self.assertRaises(ValueError):
            await CheckpointForker().fork(
                store=store, source_session_id="ghost", new_session_id="fork-1"
            )

    async def test_out_of_range_fork_point_raises(self) -> None:
        store = await _seeded_store()
        with self.assertRaises(ValueError):
            await CheckpointForker().fork(
                store=store, source_session_id="orig", new_session_id="fork-1", fork_point=99
            )

    async def test_rejects_non_store(self) -> None:
        with self.assertRaises(TypeError):
            await CheckpointForker().fork(
                store=object(),  # type: ignore[arg-type]
                source_session_id="orig",
                new_session_id="fork-1",
            )


if __name__ == "__main__":
    unittest.main()
